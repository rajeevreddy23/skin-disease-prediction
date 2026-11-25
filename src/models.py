"""
models.py - Neural Network Architectures for Skin Lesion Classification.
Includes:
1. Custom CNN: A clean modular baseline convolutional network
2. MobileNetV2: Lightweight inverted residual bottleneck network with transfer learning
3. EfficientNetB0: Compound-scaled deep feature extractor with transfer learning
"""

import torch
import torch.nn as nn
from torchvision.models import (
    mobilenet_v2,
    MobileNet_V2_Weights,
    efficientnet_b0,
    EfficientNet_B0_Weights,
)


class CustomCNN(nn.Module):
    """
    Baseline 4-stage Convolutional Neural Network for dermatological lesion classification.
    Features batch normalization, max pooling, adaptive global average pooling, and dropout.
    """
    def __init__(self, num_classes: int = 7, in_channels: int = 3):
        super(CustomCNN, self).__init__()
        
        # Stage 1
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),  # 128 -> 64
        )
        # Stage 2
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),  # 64 -> 32
        )
        # Stage 3
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),  # 32 -> 16
        )
        # Stage 4 (Target layer for Grad-CAM)
        self.conv4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),           # -> [B, 256, 1, 1]
        )
        
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(p=0.4),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        out = self.classifier(x)
        return out


def build_mobilenet_v2(num_classes: int = 7, pretrained: bool = True) -> nn.Module:
    """
    Constructs MobileNetV2 architecture with pre-trained ImageNet weights and customized head.
    """
    weights = MobileNet_V2_Weights.DEFAULT if pretrained else None
    model = mobilenet_v2(weights=weights)
    
    # Target layer for Grad-CAM: model.features[-1] (Conv2dNormActivation 1280)
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.2),
        nn.Linear(256, num_classes),
    )
    return model


def build_efficientnet_b0(num_classes: int = 7, pretrained: bool = True) -> nn.Module:
    """
    Constructs EfficientNetB0 architecture with pre-trained ImageNet weights and customized head.
    """
    weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
    model = efficientnet_b0(weights=weights)
    
    # Target layer for Grad-CAM: model.features[-1]
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.2),
        nn.Linear(256, num_classes),
    )
    return model


def build_model(model_name: str, num_classes: int = 7, pretrained: bool = True) -> nn.Module:
    """Factory function to build requested model by name."""
    name = model_name.lower().replace("-", "").replace("_", "")
    if "custom" in name:
        return CustomCNN(num_classes=num_classes)
    elif "mobilenet" in name:
        return build_mobilenet_v2(num_classes=num_classes, pretrained=pretrained)
    elif "efficientnet" in name:
        return build_efficientnet_b0(num_classes=num_classes, pretrained=pretrained)
    else:
        raise ValueError(f"Unknown model name: {model_name}. Choose from 'custom_cnn', 'mobilenet_v2', 'efficientnet_b0'.")


def count_parameters(model: nn.Module) -> dict:
    """Returns total and trainable parameter counts for a model."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {"total": total, "trainable": trainable}
