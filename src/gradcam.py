"""
gradcam.py - Gradient-Weighted Class Activation Mapping (Grad-CAM).
Provides explainable AI visual explanations highlighting regions that influenced the model prediction.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image


class GradCAM:
    """
    Grad-CAM class for generating explainability heatmaps from PyTorch CNN models.
    """
    def __init__(self, model: nn.Module, target_layer: nn.Module = None):
        self.model = model
        self.model.eval()
        self.target_layer = target_layer or self._find_default_target_layer()
        
        self.gradients = None
        self.activations = None
        self.hook_handles = []
        self._register_hooks()

    def _find_default_target_layer(self) -> nn.Module:
        """Automatically locates the last convolutional layer in common architectures."""
        if hasattr(self.model, "conv4"):
            # CustomCNN
            return self.model.conv4[0]
        elif hasattr(self.model, "features"):
            # MobileNetV2 / EfficientNet
            for module in reversed(list(self.model.features.modules())):
                if isinstance(module, nn.Conv2d):
                    return module
            return self.model.features[-1]
        else:
            # Fallback search for any Conv2d in reverse order
            for module in reversed(list(self.model.modules())):
                if isinstance(module, nn.Conv2d):
                    return module
            raise ValueError("Could not find a convolutional layer for Grad-CAM.")

    def _register_hooks(self):
        """Attaches forward and backward hooks to capture activations and gradients."""
        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_in, grad_out):
            self.gradients = grad_out[0].detach()

        self.hook_handles.append(self.target_layer.register_forward_hook(forward_hook))
        self.hook_handles.append(self.target_layer.register_full_backward_hook(backward_hook))

    def generate_heatmap(self, input_tensor: torch.Tensor, class_idx: int = None) -> np.ndarray:
        """
        Computes the normalized Grad-CAM heatmap for a given input tensor and class index.
        
        Args:
            input_tensor: Tensor of shape [1, 3, H, W]
            class_idx: Target class index. If None, uses model's predicted class.
            
        Returns:
            Normalized 2D heatmap numpy array (H, W) with values in [0, 1].
        """
        self.model.zero_grad()
        output = self.model(input_tensor)
        
        if class_idx is None:
            class_idx = torch.argmax(output, dim=1).item()
            
        target_score = output[0, class_idx]
        target_score.backward(retain_graph=True)
        
        # Global average pooling of gradients: alpha_k = (1/Z) * sum(grad)
        weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)  # [1, C, 1, 1]
        
        # Weighted linear combination: sum(alpha_k * A_k)
        cam = torch.sum(weights * self.activations, dim=1, keepdim=True)  # [1, 1, H, W]
        
        # Apply ReLU to retain only positive contributions
        cam = torch.relu(cam)
        cam = cam.squeeze().cpu().numpy()
        
        # Normalize between 0 and 1
        cam_min, cam_max = np.min(cam), np.max(cam)
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)
            
        return cam

    def create_overlay(
        self,
        original_pil_or_np,
        heatmap_2d: np.ndarray,
        alpha: float = 0.45,
        colormap: int = cv2.COLORMAP_JET,
    ) -> tuple:
        """
        Overlays the Grad-CAM heatmap onto the original RGB image.
        
        Args:
            original_pil_or_np: Original image as PIL Image or RGB numpy array.
            heatmap_2d: 2D numpy array [H, W] from generate_heatmap.
            alpha: Opacity weight of the heatmap overlay (0.0 = original, 1.0 = heatmap).
            colormap: OpenCV colormap (default cv2.COLORMAP_JET).
            
        Returns:
            tuple: (overlay_rgb_image, colored_heatmap_rgb)
        """
        if isinstance(original_pil_or_np, Image.Image):
            orig_rgb = np.array(original_pil_or_np.convert("RGB"))
        else:
            orig_rgb = original_pil_or_np.copy()
            
        h, w, _ = orig_rgb.shape
        
        # Resize heatmap to match image dimensions
        resized_cam = cv2.resize(heatmap_2d, (w, h), interpolation=cv2.INTER_CUBIC)
        resized_cam = np.clip(resized_cam, 0.0, 1.0)
        
        # Convert to 8-bit uint8 and apply colormap
        heatmap_uint8 = np.uint8(255 * resized_cam)
        colored_bgr = cv2.applyColorMap(heatmap_uint8, colormap)
        colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)
        
        # Blend overlay: Overlay = alpha * Heatmap + (1 - alpha) * Original
        overlay_rgb = cv2.addWeighted(colored_rgb, alpha, orig_rgb, 1.0 - alpha, 0)
        
        return overlay_rgb, colored_rgb

    def remove_hooks(self):
        """Removes registered PyTorch hooks."""
        for handle in self.hook_handles:
            handle.remove()
        self.hook_handles.clear()

    def __del__(self):
        self.remove_hooks()
