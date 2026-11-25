"""
test_predict.py - Unit tests for model architectures, dimensions, and Grad-CAM integration.
"""

import os
import sys
import pytest
import torch
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.models import build_model, CustomCNN, count_parameters
from src.gradcam import GradCAM


def test_custom_cnn_forward_dimensions():
    """Verifies CustomCNN forward pass produces [B, 7] logits."""
    model = CustomCNN(num_classes=7)
    dummy_input = torch.randn(2, 3, 128, 128)
    output = model(dummy_input)
    assert output.shape == (2, 7)


def test_mobilenet_v2_forward_dimensions():
    """Verifies MobileNetV2 forward pass produces [B, 7] logits."""
    model = build_model("mobilenet_v2", num_classes=7, pretrained=False)
    dummy_input = torch.randn(2, 3, 128, 128)
    output = model(dummy_input)
    assert output.shape == (2, 7)


def test_efficientnet_b0_forward_dimensions():
    """Verifies EfficientNetB0 forward pass produces [B, 7] logits."""
    model = build_model("efficientnet_b0", num_classes=7, pretrained=False)
    dummy_input = torch.randn(2, 3, 128, 128)
    output = model(dummy_input)
    assert output.shape == (2, 7)


def test_gradcam_heatmap_generation():
    """Verifies Grad-CAM generates valid normalized 2D heatmap and blended overlay."""
    model = CustomCNN(num_classes=7)
    cam = GradCAM(model, target_layer=model.conv4[0])
    
    dummy_input = torch.randn(1, 3, 128, 128)
    heatmap = cam.generate_heatmap(dummy_input, class_idx=0)
    
    assert heatmap.ndim == 2
    assert heatmap.shape[0] > 0 and heatmap.shape[1] > 0
    assert heatmap.min() >= 0.0
    assert heatmap.max() <= 1.0
    
    # Test overlay creation (resizes feature heatmap to target image resolution)
    test_img = np.full((128, 128, 3), 200, dtype=np.uint8)
    overlay, colored = cam.create_overlay(test_img, heatmap, alpha=0.5)
    assert overlay.shape == (128, 128, 3)
    assert colored.shape == (128, 128, 3)
