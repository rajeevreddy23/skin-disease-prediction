"""
train.py - End-to-End Training & Model Comparison Pipeline.
Trains and compares:
1. Custom CNN (Baseline)
2. MobileNetV2 (Transfer Learning)
3. EfficientNetB0 (Transfer Learning)

Applies:
- Stratified class weighting to handle class imbalance
- Comprehensive data augmentation (flips, rotations, color jitter)
- ReduceLROnPlateau learning rate scheduling & Model Checkpointing
- Full test evaluation, metrics generation, and saving the best model to models/best_model.pth
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.utils.class_weight import compute_class_weight

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau

# Import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.models import build_model, count_parameters
from src.preprocess import get_train_transforms, get_val_test_transforms
from src.evaluate import (
    evaluate_model_on_dataloader,
    plot_and_save_confusion_matrix,
    plot_and_save_roc_curves,
    plot_and_save_training_curves,
    plot_and_save_model_comparison,
)

DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MODELS_DIR = os.path.join(BASE_DIR, "models")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

CLASS_NAMES = ["akiec", "bcc", "bkl", "df", "mel", "nv", "vasc"]
CLASS_TO_IDX = {cls_name: i for i, cls_name in enumerate(CLASS_NAMES)}
IDX_TO_CLASS = {i: cls_name for i, cls_name in enumerate(CLASS_NAMES)}


class SkinLesionDataset(Dataset):
    """PyTorch Dataset for skin lesion images loaded from metadata DataFrame."""
    def __init__(self, df: pd.DataFrame, base_dir: str, transform=None):
        self.df = df.reset_index(drop=True)
        self.base_dir = base_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        file_path = row["file_path"]
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.base_dir, file_path)

        image = Image.open(file_path).convert("RGB")
        label = CLASS_TO_IDX[row["dx"]]

        if self.transform:
            image = self.transform(image)

        return image, label


def train_single_epoch(model, loader, criterion, optimizer, device):
    """Trains a model for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


def validate_single_epoch(model, loader, criterion, device):
    """Evaluates a model for one epoch."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


def train_and_evaluate_model(
    model_name: str,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    epochs: int = 7,
    lr: float = 3e-4,
) -> tuple:
    """
    Trains a model with ReduceLROnPlateau, saves its checkpoint, and evaluates on test set.
    """
    print(f"\n{'='*70}\n[>] Training Model: {model_name.upper()} (Epochs: {epochs}, Initial LR: {lr})\n{'='*70}")
    model = build_model(model_name, num_classes=len(CLASS_NAMES), pretrained=True)
    model.to(device)
    
    params_info = count_parameters(model)
    print(f"    Total parameters: {params_info['total']:,} | Trainable: {params_info['trainable']:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=2)

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_val_loss = float("inf")
    best_weights_path = os.path.join(MODELS_DIR, f"{model_name}.pth")

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_single_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate_single_epoch(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        epoch_time = time.time() - t0
        curr_lr = optimizer.param_groups[0]["lr"]
        print(f"    Epoch {epoch:02d}/{epochs:02d} [{epoch_time:.1f}s] - "
              f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc*100:.2f}% | "
              f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc*100:.2f}% | LR: {curr_lr:.2e}")

        # Model Checkpoint: Save best weights based on validation loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), best_weights_path)
            print(f"      [✓] Checkpoint saved: {best_weights_path}")

    total_time = time.time() - start_time
    print(f"[✓] Training complete for {model_name} in {total_time/60:.2f} minutes.")

    # Load best weights for final test evaluation
    model.load_state_dict(torch.load(best_weights_path))
    test_results = evaluate_model_on_dataloader(model, test_loader, device, CLASS_NAMES)
    print(f"    Hold-Out Test Accuracy: {test_results['accuracy']*100:.2f}% | F1: {test_results['f1_score']*100:.2f}%")

    return model, history, test_results, total_time


def run_training_pipeline(epochs: int = 7, batch_size: int = 32):
    """Executes the full multi-model training, evaluation, and comparison pipeline."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    metadata_path = os.path.join(PROCESSED_DIR, "metadata.csv")
    if not os.path.exists(metadata_path):
        print("[-] metadata.csv not found! Running prepare_demo_dataset.py first...")
        from data.prepare_demo_dataset import generate_dataset
        generate_dataset()

    df = pd.read_csv(metadata_path)
    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "val"].copy()
    test_df = df[df["split"] == "test"].copy()

    print(f"\n[+] Dataset Partition Summary:")
    print(f"    Training samples   : {len(train_df)}")
    print(f"    Validation samples : {len(val_df)}")
    print(f"    Testing samples    : {len(test_df)}")

    # Compute Class Weights to tackle class imbalance
    train_classes = [CLASS_TO_IDX[dx] for dx in train_df["dx"]]
    raw_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.arange(len(CLASS_NAMES)),
        y=np.array(train_classes),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    class_weights_tensor = torch.tensor(raw_weights, dtype=torch.float32).to(device)
    print(f"    Class Weights: {np.round(raw_weights, 3)}")

    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor)

    # Prepare PyTorch DataLoaders
    train_dataset = SkinLesionDataset(train_df, BASE_DIR, transform=get_train_transforms())
    val_dataset = SkinLesionDataset(val_df, BASE_DIR, transform=get_val_test_transforms())
    test_dataset = SkinLesionDataset(test_df, BASE_DIR, transform=get_val_test_transforms())

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # Models to train and compare
    models_to_train = [
        ("custom_cnn", 5e-4),
        ("mobilenet_v2", 2e-4),
        ("efficientnet_b0", 2e-4),
    ]

    all_histories = {}
    comparison_records = []
    best_overall_score = -1.0
    best_overall_model_name = None
    best_eval_results = None

    for model_name, lr in models_to_train:
        _, hist, test_res, train_duration = train_and_evaluate_model(
            model_name=model_name,
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            criterion=criterion,
            device=device,
            epochs=epochs,
            lr=lr,
        )
        all_histories[model_name] = hist

        comparison_records.append({
            "Model": model_name.replace("_", " ").title(),
            "Accuracy (%)": round(test_res["accuracy"] * 100, 2),
            "Precision (%)": round(test_res["precision"] * 100, 2),
            "Recall (%)": round(test_res["recall"] * 100, 2),
            "F1-Score (%)": round(test_res["f1_score"] * 100, 2),
            "Training Time (s)": round(train_duration, 1),
        })

        if test_res["f1_score"] > best_overall_score:
            best_overall_score = test_res["f1_score"]
            best_overall_model_name = model_name
            best_eval_results = test_res

    # Save best model to models/best_model.pth
    best_source_weights = os.path.join(MODELS_DIR, f"{best_overall_model_name}.pth")
    best_target_weights = os.path.join(MODELS_DIR, "best_model.pth")
    import shutil
    shutil.copyfile(best_source_weights, best_target_weights)
    print(f"\n[★] Best Model Selected: {best_overall_model_name.upper()} (F1: {best_overall_score*100:.2f}%)")
    print(f"    Saved as: {best_target_weights}")

    # Save Best Model Metadata
    model_metadata = {
        "best_model_name": best_overall_model_name,
        "classes": CLASS_NAMES,
        "input_size": [128, 128],
        "test_accuracy": best_eval_results["accuracy"],
        "test_f1": best_eval_results["f1_score"],
    }
    with open(os.path.join(MODELS_DIR, "model_meta.json"), "w") as f:
        json.dump(model_metadata, f, indent=2)

    # Generate and save all analytical plots & reports
    print("\n[+] Generating evaluation plots and comparison reports...")
    plot_and_save_training_curves(all_histories)
    plot_and_save_confusion_matrix(best_eval_results["confusion_matrix"], CLASS_NAMES)
    plot_and_save_roc_curves(best_eval_results["targets"], best_eval_results["probabilities"], CLASS_NAMES)

    comp_df = pd.DataFrame(comparison_records)
    plot_and_save_model_comparison(comp_df)

    # Save classification report
    with open(os.path.join(RESULTS_DIR, "classification_report.json"), "w") as f:
        json.dump(best_eval_results["report_dict"], f, indent=2)
    with open(os.path.join(RESULTS_DIR, "classification_report.txt"), "w") as f:
        f.write(best_eval_results["report_text"])

    print(f"\n{'='*70}\n[✓] ALL TRAINING AND EVALUATION DELIVERABLES GENERATED SUCCESSFULLY!\n{'='*70}")
    print(comp_df.to_string(index=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train Skin Disease Classification Models")
    parser.add_argument("--epochs", type=int, default=7, help="Number of epochs per model (default: 7)")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size (default: 32)")
    args = parser.parse_args()

    run_training_pipeline(epochs=args.epochs, batch_size=args.batch_size)
