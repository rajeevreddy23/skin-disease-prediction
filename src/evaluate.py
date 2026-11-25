"""
evaluate.py - Evaluation Suite for Skin Disease Classification Models.
Computes and saves:
1. Classification report (Precision, Recall, F1-score per class)
2. Confusion Matrix heatmap plot
3. Multi-class ROC curves and AUC scores
4. Training and validation loss/accuracy curves
5. Multi-model comparative analysis summary table and chart
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_curve,
    auc,
    accuracy_score,
    precision_recall_fscore_support,
)
from sklearn.preprocessing import label_binarize
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def evaluate_model_on_dataloader(
    model: nn.Module,
    data_loader: DataLoader,
    device: torch.device,
    class_names: list,
) -> dict:
    """
    Evaluates a PyTorch model on a data loader and returns predictions, probabilities, and ground truth.
    """
    model.eval()
    all_preds = []
    all_probs = []
    all_targets = []

    with torch.no_grad():
        for images, targets in data_loader:
            images = images.to(device)
            outputs = model(images)
            probs = torch.softmax(outputs, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)

            all_probs.extend(probs)
            all_preds.extend(preds)
            all_targets.extend(targets.numpy())

    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)
    all_targets = np.array(all_targets)

    acc = accuracy_score(all_targets, all_preds)
    precision, recall, f1, _ = precision_recall_fscore_support(all_targets, all_preds, average="weighted", zero_division=0)
    
    report_dict = classification_report(
        all_targets,
        all_preds,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    report_text = classification_report(
        all_targets,
        all_preds,
        target_names=class_names,
        zero_division=0,
    )

    cm = confusion_matrix(all_targets, all_preds)

    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "predictions": all_preds,
        "probabilities": all_probs,
        "targets": all_targets,
        "report_dict": report_dict,
        "report_text": report_text,
        "confusion_matrix": cm,
    }


def plot_and_save_confusion_matrix(cm: np.ndarray, class_names: list, save_path: str = None) -> str:
    """Plots and saves a professional confusion matrix heatmap."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    save_path = save_path or os.path.join(RESULTS_DIR, "confusion_matrix.png")
    
    plt.figure(figsize=(8, 6.5), dpi=300)
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        cbar=True,
        annot_kws={"size": 11, "weight": "bold"},
    )
    plt.title("Confusion Matrix - Best Model (Test Set)", fontsize=14, fontweight="bold", pad=12)
    plt.xlabel("Predicted Diagnostic Class", fontsize=11, labelpad=8)
    plt.ylabel("True Diagnostic Class", fontsize=11, labelpad=8)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    return save_path


def plot_and_save_roc_curves(y_true: np.ndarray, y_probs: np.ndarray, class_names: list, save_path: str = None) -> str:
    """Plots and saves multi-class One-vs-Rest ROC curves with AUC values."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    save_path = save_path or os.path.join(RESULTS_DIR, "roc_curves.png")
    
    n_classes = len(class_names)
    y_true_bin = label_binarize(y_true, classes=list(range(n_classes)))
    
    fpr = dict()
    tpr = dict()
    roc_auc = dict()
    
    plt.figure(figsize=(8.5, 6.5), dpi=300)
    colors = sns.color_palette("tab10", n_classes)
    
    for i in range(n_classes):
        fpr[i], tpr[i], _ = roc_curve(y_true_bin[:, i], y_probs[:, i])
        roc_auc[i] = auc(fpr[i], tpr[i])
        plt.plot(
            fpr[i], tpr[i],
            color=colors[i],
            lw=2,
            label=f"{class_names[i]} (AUC = {roc_auc[i]:.2f})",
        )
        
    plt.plot([0, 1], [0, 1], "k--", lw=1.5, label="Random Guess (AUC = 0.50)")
    plt.xlim([-0.02, 1.02])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate (1 - Specificity)", fontsize=11, labelpad=8)
    plt.ylabel("True Positive Rate (Sensitivity)", fontsize=11, labelpad=8)
    plt.title("Multi-Class Receiver Operating Characteristic (ROC) Curves", fontsize=14, fontweight="bold", pad=12)
    plt.legend(loc="lower right", fontsize=10, frameon=True)
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    return save_path


def plot_and_save_training_curves(training_histories: dict, save_path: str = None) -> str:
    """
    Plots and saves comparative training & validation loss and accuracy curves for all models.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    save_path = save_path or os.path.join(RESULTS_DIR, "training_curves.png")
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    
    palette = sns.color_palette("bright", len(training_histories))
    
    for idx, (model_name, hist) in enumerate(training_histories.items()):
        color = palette[idx]
        epochs = range(1, len(hist["train_loss"]) + 1)
        # Loss Curves
        ax1.plot(epochs, hist["train_loss"], color=color, linestyle="--", alpha=0.7, label=f"{model_name} (Train)")
        ax1.plot(epochs, hist["val_loss"], color=color, linestyle="-", lw=2, label=f"{model_name} (Val)")
        # Accuracy Curves
        ax2.plot(epochs, [a * 100 for a in hist["train_acc"]], color=color, linestyle="--", alpha=0.7, label=f"{model_name} (Train)")
        ax2.plot(epochs, [a * 100 for a in hist["val_acc"]], color=color, linestyle="-", lw=2, label=f"{model_name} (Val)")
        
    ax1.set_title("Training and Validation Cross-Entropy Loss", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Epoch", fontsize=10)
    ax1.set_ylabel("Loss", fontsize=10)
    ax1.legend(loc="upper right", fontsize=8.5)
    
    ax2.set_title("Training and Validation Accuracy (%)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Epoch", fontsize=10)
    ax2.set_ylabel("Accuracy (%)", fontsize=10)
    ax2.legend(loc="lower right", fontsize=8.5)
    
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    return save_path


def plot_and_save_model_comparison(comparison_df: pd.DataFrame, save_path: str = None) -> str:
    """
    Plots a bar chart comparing Accuracy, Precision, Recall, and F1 across models and saves summary table.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    save_path = save_path or os.path.join(RESULTS_DIR, "model_comparison.png")
    
    # Save CSV and JSON
    csv_path = os.path.join(RESULTS_DIR, "model_comparison.csv")
    json_path = os.path.join(RESULTS_DIR, "model_comparison.json")
    comparison_df.to_csv(csv_path, index=False)
    comparison_df.to_json(json_path, orient="records", indent=2)
    
    # Bar plot
    metrics = ["Accuracy (%)", "Precision (%)", "Recall (%)", "F1-Score (%)"]
    plot_df = comparison_df.melt(id_vars=["Model"], value_vars=metrics, var_name="Metric", value_name="Score")
    
    plt.figure(figsize=(10, 5.5), dpi=300)
    ax = sns.barplot(data=plot_df, x="Metric", y="Score", hue="Model", palette="Set2")
    plt.title("Comparative Performance Analysis: Custom CNN vs MobileNetV2 vs EfficientNetB0", fontsize=13, fontweight="bold", pad=12)
    plt.ylabel("Performance Score (%)", fontsize=11)
    plt.xlabel("")
    plt.ylim([0, 105])
    plt.legend(title="Model Architecture", frameon=True)
    
    # Add values on top of bars
    for p in ax.patches:
        h = p.get_height()
        if h > 0:
            ax.annotate(f"{h:.1f}%", (p.get_x() + p.get_width() / 2., h + 1.2),
                        ha="center", va="bottom", fontsize=8.5, rotation=0)
            
    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    return save_path
