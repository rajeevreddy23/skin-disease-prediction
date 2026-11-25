"""
predict.py - Inference Engine for Skin Disease Classification.
Handles single-image preprocessing, model execution, Top-K ranking, Grad-CAM visualization,
and logging to the SQLite database.
"""

import os
import sys
import time
import json
import torch
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.models import build_model
from src.preprocess import preprocess_for_inference
from src.gradcam import GradCAM
from src.database import insert_prediction

MODELS_DIR = os.path.join(BASE_DIR, "models")
CLASS_LABELS_PATH = os.path.join(MODELS_DIR, "class_labels.json")
DISEASE_INFO_PATH = os.path.join(MODELS_DIR, "disease_info.json")
MODEL_META_PATH = os.path.join(MODELS_DIR, "model_meta.json")
DEFAULT_WEIGHTS_PATH = os.path.join(MODELS_DIR, "best_model.pth")


class SkinDiseasePredictor:
    """
    Production-grade predictor for skin lesion diagnosis with integrated Grad-CAM explainability.
    """
    def __init__(self, weights_path: str = DEFAULT_WEIGHTS_PATH, model_name: str = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = weights_path
        
        # Load class labels
        with open(CLASS_LABELS_PATH, "r") as f:
            raw_labels = json.load(f)
            self.idx_to_class = {int(k): v for k, v in raw_labels.items()}
            self.class_to_idx = {v: int(k) for k, v in raw_labels.items()}
            
        # Load disease information
        with open(DISEASE_INFO_PATH, "r") as f:
            self.disease_info = json.load(f)

        # Detect model architecture
        if model_name is None:
            if os.path.exists(MODEL_META_PATH):
                with open(MODEL_META_PATH, "r") as f:
                    meta = json.load(f)
                    model_name = meta.get("best_model_name", "mobilenet_v2")
            else:
                model_name = "mobilenet_v2"

        self.model_name = model_name
        self.model = build_model(model_name, num_classes=len(self.idx_to_class), pretrained=False)
        
        if os.path.exists(weights_path):
            state_dict = torch.load(weights_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            print(f"[✓] Loaded {model_name} weights from: {weights_path}")
        else:
            print(f"[!] Warning: Weights file not found at {weights_path}. Model initialized with random weights.")
            
        self.model.to(self.device)
        self.model.eval()

        # Initialize Grad-CAM helper
        self.grad_cam = GradCAM(self.model)

    def predict(
        self,
        image_input,
        apply_dull_razor: bool = False,
        apply_contrast_enhancement: bool = False,
        generate_gradcam: bool = True,
        gradcam_alpha: float = 0.45,
        save_to_db: bool = True,
        source: str = "upload",
        image_path_label: str = "",
    ) -> dict:
        """
        Executes end-to-end diagnosis on an input image.
        
        Args:
            image_input: File path, PIL Image, or numpy array.
            apply_dull_razor: Whether to execute morphological hair removal.
            apply_contrast_enhancement: Whether to run CLAHE.
            generate_gradcam: Whether to compute Grad-CAM visual explanation.
            gradcam_alpha: Transparency weight for Grad-CAM overlay.
            save_to_db: Whether to record result in SQLite history.
            source: 'webcam', 'upload', 'sample', or 'device_simulator'.
            image_path_label: Descriptive image path/name for database history.
            
        Returns:
            Dictionary with comprehensive diagnostic and explainability results.
        """
        t0 = time.time()
        
        # Preprocessing
        tensor, processed_pil, orig_pil = preprocess_for_inference(
            image_input=image_input,
            apply_dull_razor=apply_dull_razor,
            apply_contrast_enhancement=apply_contrast_enhancement,
            image_size=(128, 128),
        )
        tensor = tensor.to(self.device)

        # Inference
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze().cpu().numpy()

        latency_ms = (time.time() - t0) * 1000.0

        # Predicted class & confidence
        pred_idx = int(np.argmax(probs))
        pred_class = self.idx_to_class[pred_idx]
        confidence = float(probs[pred_idx]) * 100.0

        info = self.disease_info.get(pred_class, {})
        pred_name = info.get("name", pred_class)
        risk_level = info.get("risk_level", "Unknown")
        risk_color = info.get("risk_color", "#3b82f6")

        # Top-3 Probabilities
        top3_indices = np.argsort(probs)[::-1][:3]
        top3 = []
        for idx in top3_indices:
            cls_code = self.idx_to_class[idx]
            cls_info = self.disease_info.get(cls_code, {})
            top3.append({
                "class_code": cls_code,
                "name": cls_info.get("short_name", cls_code),
                "probability": float(probs[idx]) * 100.0,
                "risk_level": cls_info.get("risk_level", "Unknown"),
            })

        # All Probabilities map
        all_probs = {self.idx_to_class[i]: float(probs[i]) * 100.0 for i in range(len(probs))}

        # Grad-CAM Visual Explanation
        gradcam_overlay = None
        gradcam_heatmap = None
        if generate_gradcam:
            tensor_for_gradcam = tensor.clone().requires_grad_(True)
            heatmap = self.grad_cam.generate_heatmap(tensor_for_gradcam, class_idx=pred_idx)
            gradcam_overlay, gradcam_heatmap = self.grad_cam.create_overlay(
                orig_pil, heatmap, alpha=gradcam_alpha
            )

        # Record to SQLite database
        record_id = None
        if save_to_db:
            try:
                record_id = insert_prediction(
                    prediction_class=pred_class,
                    prediction_name=pred_name,
                    confidence=confidence,
                    risk_level=risk_level,
                    top3=top3,
                    image_path=image_path_label or "in_memory_image",
                    source=source,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                print(f"[!] Warning: Failed to log prediction to database: {e}")

        return {
            "record_id": record_id,
            "prediction_class": pred_class,
            "prediction_name": pred_name,
            "confidence": confidence,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "top3": top3,
            "all_probabilities": all_probs,
            "disease_info": info,
            "latency_ms": latency_ms,
            "original_image": orig_pil,
            "preprocessed_image": processed_pil,
            "gradcam_overlay": gradcam_overlay,
            "gradcam_heatmap": gradcam_heatmap,
        }
