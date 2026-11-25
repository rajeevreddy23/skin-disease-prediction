"""
preprocess.py - Dermatological Image Preprocessing Pipeline.
Implements:
1. DullRazor algorithm: morphological hair artifact removal and inpainting
2. Color equalization (CLAHE) for lesion contrast enhancement
3. Tensor transforms with data augmentation for training, validation, and inference
"""

import os
import cv2
import numpy as np
from PIL import Image
import torch
from torchvision import transforms

# Standard normalization constants (ImageNet statistics)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
DEFAULT_IMAGE_SIZE = (128, 128)


def dull_razor_hair_removal(image_rgb: np.ndarray, kernel_size: int = 9) -> np.ndarray:
    """
    Applies the classic DullRazor morphological algorithm to remove hair and dark line artifacts.
    1. Converts image to grayscale.
    2. Applies morphological Black Hat filtering to detect dark linear features (hairs).
    3. Thresholds the result to create a binary hair mask.
    4. Inpaints the hair pixels using cv2.inpaint.
    
    Args:
        image_rgb: RGB image as a numpy array uint8 (H, W, 3).
        kernel_size: Size of the morphological structuring element.
        
    Returns:
        Cleaned RGB image without hair artifacts.
    """
    if image_rgb is None or image_rgb.size == 0:
        raise ValueError("Invalid image provided to DullRazor.")
    
    # Convert RGB to Grayscale
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    
    # Morphological Black Hat filter (Highlights dark features on bright background)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    
    # Threshold the black hat to segment hairs
    _, hair_mask = cv2.threshold(blackhat, 10, 255, cv2.THRESH_BINARY)
    
    # Slight dilation to ensure full hair strand coverage
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    hair_mask = cv2.dilate(hair_mask, dilate_kernel, iterations=1)
    
    # Inpaint the original RGB image using Telea algorithm
    clean_rgb = cv2.inpaint(image_rgb, hair_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    return clean_rgb


def apply_clahe(image_rgb: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)) -> np.ndarray:
    """
    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) on the L-channel of LAB color space.
    Enhances diagnostic texture and border visibility without distorting lesion hue.
    """
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_equalized = clahe.apply(l_channel)
    
    lab_equalized = cv2.merge((l_equalized, a_channel, b_channel))
    enhanced_rgb = cv2.cvtColor(lab_equalized, cv2.COLOR_LAB2RGB)
    return enhanced_rgb


def get_train_transforms(image_size: tuple = DEFAULT_IMAGE_SIZE) -> transforms.Compose:
    """Returns PyTorch transform pipeline for training with data augmentation."""
    return transforms.Compose([
        transforms.Resize(image_size),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomRotation(degrees=25),
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_val_test_transforms(image_size: tuple = DEFAULT_IMAGE_SIZE) -> transforms.Compose:
    """Returns deterministic PyTorch transform pipeline for validation and testing."""
    return transforms.Compose([
        transforms.Resize(image_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def preprocess_for_inference(
    image_input,
    apply_dull_razor: bool = False,
    apply_contrast_enhancement: bool = False,
    image_size: tuple = DEFAULT_IMAGE_SIZE,
):
    """
    Preprocesses a single image for model inference.
    
    Args:
        image_input: Can be a file path (str), PIL.Image.Image, or numpy.ndarray (RGB).
        apply_dull_razor: Whether to remove hair using DullRazor.
        apply_contrast_enhancement: Whether to apply CLAHE contrast enhancement.
        image_size: Target dimensions (width, height).
        
    Returns:
        tuple: (tensor of shape [1, 3, H, W], processed_pil_image, original_pil_image)
    """
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"Image not found at path: {image_input}")
        pil_image = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        pil_image = image_input.convert("RGB")
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim == 2:
            image_input = cv2.cvtColor(image_input, cv2.COLOR_GRAY2RGB)
        elif image_input.shape[2] == 4:
            image_input = cv2.cvtColor(image_input, cv2.COLOR_RGBA2RGB)
        pil_image = Image.fromarray(image_input)
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    orig_pil = pil_image.copy()
    np_img = np.array(pil_image)

    if apply_dull_razor:
        np_img = dull_razor_hair_removal(np_img)

    if apply_contrast_enhancement:
        np_img = apply_clahe(np_img)

    processed_pil = Image.fromarray(np_img)
    transform = get_val_test_transforms(image_size=image_size)
    tensor = transform(processed_pil).unsqueeze(0)  # Shape [1, 3, H, W]

    return tensor, processed_pil, orig_pil


def denormalize_tensor(tensor: torch.Tensor) -> np.ndarray:
    """
    Converts a normalized PyTorch tensor [3, H, W] back to a displayable uint8 numpy image [H, W, 3].
    """
    t = tensor.detach().cpu().clone()
    if t.ndim == 4:
        t = t.squeeze(0)
    for c, m, s in zip(t, IMAGENET_MEAN, IMAGENET_STD):
        c.mul_(s).add_(m)
    t = torch.clamp(t, 0.0, 1.0)
    np_arr = (t.permute(1, 2, 0).numpy() * 255.0).astype(np.uint8)
    return np_arr
