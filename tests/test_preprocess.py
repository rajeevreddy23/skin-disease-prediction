"""
test_preprocess.py - Unit tests for dermatological image preprocessing.
"""

import os
import sys
import numpy as np
import pytest
from PIL import Image
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.preprocess import (
    dull_razor_hair_removal,
    apply_clahe,
    get_train_transforms,
    get_val_test_transforms,
    preprocess_for_inference,
    denormalize_tensor,
)


def test_dull_razor_hair_removal():
    """Verifies DullRazor removes dark hair lines without altering image dimensions."""
    # Create synthetic skin patch with dark line simulating hair
    img = np.full((128, 128, 3), 200, dtype=np.uint8)
    img[60:68, :, :] = 20  # Horizontal dark hair line
    
    cleaned = dull_razor_hair_removal(img, kernel_size=9)
    
    assert cleaned.shape == img.shape
    assert cleaned.dtype == np.uint8
    # Center pixel should now be much lighter than the original hair pixel (20)
    assert cleaned[64, 64, 0] > 100


def test_apply_clahe():
    """Verifies CLAHE contrast enhancement works on RGB images."""
    img = np.full((128, 128, 3), 150, dtype=np.uint8)
    enhanced = apply_clahe(img)
    
    assert enhanced.shape == (128, 128, 3)
    assert enhanced.dtype == np.uint8


def test_transforms_output_shapes():
    """Verifies that transforms produce expected tensor dimensions and value ranges."""
    pil_img = Image.new("RGB", (128, 128), color=(220, 180, 150))
    
    train_tf = get_train_transforms((128, 128))
    val_tf = get_val_test_transforms((128, 128))
    
    t_train = train_tf(pil_img)
    t_val = val_tf(pil_img)
    
    assert t_train.shape == (3, 128, 128)
    assert t_val.shape == (3, 128, 128)
    assert isinstance(t_train, torch.Tensor)
    assert isinstance(t_val, torch.Tensor)


def test_preprocess_for_inference():
    """Verifies single-image inference preprocessing pipeline."""
    pil_img = Image.new("RGB", (160, 160), color=(210, 170, 140))
    tensor, proc_pil, orig_pil = preprocess_for_inference(
        pil_img,
        apply_dull_razor=True,
        apply_contrast_enhancement=True,
        image_size=(128, 128),
    )
    
    assert tensor.shape == (1, 3, 128, 128)
    assert proc_pil.size == (160, 160)
    assert orig_pil.size == (160, 160)


def test_denormalize_tensor():
    """Verifies tensor denormalization outputs valid displayable RGB numpy array."""
    t = torch.zeros(3, 128, 128)
    denorm = denormalize_tensor(t)
    
    assert denorm.shape == (128, 128, 3)
    assert denorm.dtype == np.uint8
    assert denorm.min() >= 0
    assert denorm.max() <= 255
