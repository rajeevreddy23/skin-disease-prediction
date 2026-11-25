"""
prepare_demo_dataset.py - Generates realistic synthetic dermatoscopic images for all 7 HAM10000 classes.
Ensures the software project runs out-of-the-box on any laptop without requiring 3GB downloads.
Includes hair artifacts for DullRazor testing, dermatoscope lens vignetting, and stratified splits.
"""

import os
import random
import math
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

CLASSES = ["akiec", "bcc", "bkl", "df", "mel", "nv", "vasc"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
IMAGES_DIR = os.path.join(PROCESSED_DIR, "images")
ASSETS_SAMPLE_DIR = os.path.join(BASE_DIR, "app", "assets", "sample_images")


def create_skin_background(width=128, height=128):
    """Generates synthetic skin tone background with natural melanin variation."""
    # Skin tone palette (Fitzpatrick types I-IV)
    base_tones = [
        (238, 206, 179),  # Fair / Peach
        (225, 190, 160),  # Light Tan
        (242, 218, 195),  # Ivory
        (210, 175, 140),  # Medium Beige
        (245, 210, 190),  # Warm Cream
    ]
    r, g, b = random.choice(base_tones)
    # Add subtle spatial gradient
    arr = np.zeros((height, width, 3), dtype=np.float32)
    for c, val in enumerate([r, g, b]):
        noise = np.random.normal(val, 4.0, (height, width))
        arr[:, :, c] = noise
    
    # Smooth skin texture
    arr = cv2.GaussianBlur(arr, (5, 5), 1.5)
    return np.clip(arr, 0, 255).astype(np.uint8)


def add_hair_artifacts(img_rgb, num_hairs=3):
    """Draws realistic dark hair strands for DullRazor testing."""
    h, w, _ = img_rgb.shape
    for _ in range(num_hairs):
        # Generate a spline or curved line
        x0, y0 = random.randint(0, w), random.randint(0, h)
        x1, y1 = random.randint(0, w), random.randint(0, h)
        ctrl_x = (x0 + x1) // 2 + random.randint(-20, 20)
        ctrl_y = (y0 + y1) // 2 + random.randint(-20, 20)
        
        # Approximate curve with points
        points = []
        for t in np.linspace(0, 1, 30):
            px = int((1 - t)**2 * x0 + 2 * (1 - t) * t * ctrl_x + t**2 * x1)
            py = int((1 - t)**2 * y0 + 2 * (1 - t) * t * ctrl_y + t**2 * y1)
            points.append((px, py))
            
        hair_color = (random.randint(20, 45), random.randint(15, 35), random.randint(10, 25))
        thickness = random.choice([1, 2])
        for i in range(len(points) - 1):
            cv2.line(img_rgb, points[i], points[i+1], hair_color, thickness, cv2.LINE_AA)
    return img_rgb


def add_dermatoscope_vignette(img_rgb):
    """Applies subtle circular vignetting characteristic of dermatoscope optics."""
    h, w, _ = img_rgb.shape
    mask = np.zeros((h, w), dtype=np.float32)
    center = (w // 2, h // 2)
    radius = int(min(w, h) * 0.65)
    cv2.circle(mask, center, radius, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (31, 31), 10)
    # Blend vignette
    vignette = (img_rgb.astype(np.float32) * mask[:, :, np.newaxis] * 0.9 + 
                img_rgb.astype(np.float32) * 0.1)
    return np.clip(vignette, 0, 255).astype(np.uint8)


def draw_lesion_nv(img_rgb):
    """Melanocytic nevi: regular, symmetrical, uniform brown pigment network."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-4, 4), h // 2 + random.randint(-4, 4))
    axes = (random.randint(22, 38), random.randint(20, 34))
    angle = random.randint(0, 180)
    
    # Outer light brown ring
    outer_color = (random.randint(140, 165), random.randint(95, 120), random.randint(65, 85))
    cv2.ellipse(img_rgb, center, axes, angle, 0, 360, outer_color, -1, cv2.LINE_AA)
    
    # Inner darker regular pigment core
    inner_axes = (int(axes[0] * 0.7), int(axes[1] * 0.7))
    inner_color = (random.randint(90, 120), random.randint(55, 80), random.randint(35, 55))
    cv2.ellipse(img_rgb, center, inner_axes, angle, 0, 360, inner_color, -1, cv2.LINE_AA)
    
    # Regular pigment network globules
    for _ in range(12):
        ox = center[0] + int(inner_axes[0] * random.uniform(-0.6, 0.6))
        oy = center[1] + int(inner_axes[1] * random.uniform(-0.6, 0.6))
        cv2.circle(img_rgb, (ox, oy), random.randint(1, 3), (70, 40, 25), -1)
        
    return cv2.GaussianBlur(img_rgb, (5, 5), 1.2)


def draw_lesion_mel(img_rgb):
    """Melanoma: asymmetrical, notched border, multi-color (black, dark brown, red, blue-white veil)."""
    h, w, _ = img_rgb.shape
    cx = w // 2 + random.randint(-12, 12)
    cy = h // 2 + random.randint(-12, 12)
    
    # Irregular jagged polygon border
    num_pts = random.randint(10, 16)
    pts = []
    base_radius = random.randint(28, 44)
    for i in range(num_pts):
        th = 2 * math.pi * i / num_pts
        r = base_radius + random.randint(-12, 14)
        px = int(cx + r * math.cos(th))
        py = int(cy + r * math.sin(th))
        pts.append([px, py])
    pts = np.array([pts], dtype=np.int32)
    
    # Atypical dark brown/black base
    cv2.fillPoly(img_rgb, pts, (random.randint(45, 75), random.randint(25, 45), random.randint(15, 35)))
    
    # Asymmetric deep black blotch
    bx = cx + random.randint(-10, 10)
    by = cy + random.randint(-10, 10)
    cv2.circle(img_rgb, (bx, by), random.randint(12, 20), (20, 10, 10), -1)
    
    # Blue-white veil patch (hallmark of invasive melanoma)
    vx = cx + random.randint(-14, 14)
    vy = cy + random.randint(-14, 14)
    veil_overlay = img_rgb.copy()
    cv2.ellipse(veil_overlay, (vx, vy), (14, 9), random.randint(0, 180), 0, 360, (180, 195, 215), -1)
    cv2.addWeighted(veil_overlay, 0.45, img_rgb, 0.55, 0, img_rgb)
    
    # Atypical dots and peripheral globules
    for _ in range(15):
        gx = cx + random.randint(-28, 28)
        gy = cy + random.randint(-28, 28)
        if cv2.pointPolygonTest(pts[0], (gx, gy), False) >= 0:
            cv2.circle(img_rgb, (gx, gy), random.randint(1, 3), (15, 5, 5), -1)
            
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.8)


def draw_lesion_bcc(img_rgb):
    """Basal cell carcinoma: translucent pink-white papule, arborizing telangiectatic vessels."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-6, 6), h // 2 + random.randint(-6, 6))
    axes = (random.randint(24, 38), random.randint(22, 34))
    angle = random.randint(0, 180)
    
    # Pearly pinkish-red background
    pearly_color = (random.randint(225, 245), random.randint(170, 195), random.randint(170, 195))
    cv2.ellipse(img_rgb, center, axes, angle, 0, 360, pearly_color, -1, cv2.LINE_AA)
    
    # Central shallow ulceration / crust
    if random.random() > 0.3:
        cv2.circle(img_rgb, center, random.randint(6, 12), (160, 90, 85), -1)
    
    # Arborizing (branching tree-like) blood vessels (telangiectasia)
    for _ in range(random.randint(3, 5)):
        vx, vy = center[0] + random.randint(-12, 12), center[1] + random.randint(-12, 12)
        vessel_pts = [(vx, vy)]
        for _ in range(random.randint(3, 5)):
            vx += random.randint(-6, 6)
            vy += random.randint(-6, 6)
            vessel_pts.append((vx, vy))
        for i in range(len(vessel_pts) - 1):
            cv2.line(img_rgb, vessel_pts[i], vessel_pts[i+1], (180, 20, 30), 1, cv2.LINE_AA)
            
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.7)


def draw_lesion_bkl(img_rgb):
    """Benign keratosis: stuck-on waxy appearance, brownish-yellow, pseudofollicular openings."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-6, 6), h // 2 + random.randint(-6, 6))
    axes = (random.randint(26, 42), random.randint(24, 38))
    angle = random.randint(0, 180)
    
    # Waxy yellowish-brown base
    waxy_color = (random.randint(160, 185), random.randint(120, 145), random.randint(80, 105))
    cv2.ellipse(img_rgb, center, axes, angle, 0, 360, waxy_color, -1, cv2.LINE_AA)
    
    # Cerebriform / keratin fissures
    fissure_color = (random.randint(110, 135), random.randint(80, 105), random.randint(50, 75))
    for _ in range(8):
        fx = center[0] + random.randint(-axes[0]//2, axes[0]//2)
        fy = center[1] + random.randint(-axes[1]//2, axes[1]//2)
        cv2.ellipse(img_rgb, (fx, fy), (random.randint(4, 9), 2), random.randint(0, 180), 0, 360, fissure_color, -1)
        
    # Comedo-like openings (tiny dark pits)
    for _ in range(10):
        px = center[0] + random.randint(-int(axes[0]*0.7), int(axes[0]*0.7))
        py = center[1] + random.randint(-int(axes[1]*0.7), int(axes[1]*0.7))
        cv2.circle(img_rgb, (px, py), random.randint(1, 2), (60, 40, 25), -1)
        
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.8)


def draw_lesion_akiec(img_rgb):
    """Actinic keratosis: erythematous red/pink scaly patch, yellow-white hyperkeratotic crust."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-8, 8), h // 2 + random.randint(-8, 8))
    axes = (random.randint(24, 38), random.randint(20, 32))
    angle = random.randint(0, 180)
    
    # Erythematous red halo
    red_color = (random.randint(220, 245), random.randint(120, 150), random.randint(120, 150))
    cv2.ellipse(img_rgb, center, axes, angle, 0, 360, red_color, -1, cv2.LINE_AA)
    
    # Rough scaly yellow-white crust
    for _ in range(12):
        cx = center[0] + random.randint(-axes[0]//2, axes[0]//2)
        cy = center[1] + random.randint(-axes[1]//2, axes[1]//2)
        scale_color = (random.randint(235, 255), random.randint(225, 245), random.randint(180, 205))
        cv2.circle(img_rgb, (cx, cy), random.randint(2, 5), scale_color, -1)
        
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.9)


def draw_lesion_vasc(img_rgb):
    """Vascular lesions: characteristic cherry red to purple-red vascular lagoons / lacunae."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-6, 6), h // 2 + random.randint(-6, 6))
    
    # Cluster of distinct red-purple lacunae
    lacuna_colors = [
        (180, 25, 45),   # Crimson
        (150, 20, 60),   # Deep wine
        (210, 40, 65),   # Cherry red
        (130, 25, 75),   # Purple violaceous
    ]
    for _ in range(random.randint(8, 14)):
        ox = center[0] + random.randint(-18, 18)
        oy = center[1] + random.randint(-18, 18)
        rad = random.randint(4, 9)
        col = random.choice(lacuna_colors)
        cv2.circle(img_rgb, (ox, oy), rad, col, -1, cv2.LINE_AA)
        
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.7)


def draw_lesion_df(img_rgb):
    """Dermatofibroma: central white scar-like patch, peripheral delicate pigment network."""
    h, w, _ = img_rgb.shape
    center = (w // 2 + random.randint(-5, 5), h // 2 + random.randint(-5, 5))
    axes = (random.randint(24, 36), random.randint(22, 32))
    
    # Outer light brownish halo
    halo_color = (random.randint(165, 190), random.randint(130, 150), random.randint(100, 120))
    cv2.ellipse(img_rgb, center, axes, 0, 0, 360, halo_color, -1, cv2.LINE_AA)
    
    # Distinct central white scar-like patch
    scar_color = (random.randint(240, 255), random.randint(235, 250), random.randint(230, 245))
    inner_axes = (int(axes[0] * 0.45), int(axes[1] * 0.45))
    cv2.ellipse(img_rgb, center, inner_axes, 0, 0, 360, scar_color, -1, cv2.LINE_AA)
    
    return cv2.GaussianBlur(img_rgb, (3, 3), 0.8)


GENERATOR_MAP = {
    "nv": draw_lesion_nv,
    "mel": draw_lesion_mel,
    "bcc": draw_lesion_bcc,
    "bkl": draw_lesion_bkl,
    "akiec": draw_lesion_akiec,
    "vasc": draw_lesion_vasc,
    "df": draw_lesion_df,
}


def generate_single_sample(dx_class, image_id, img_size=128):
    """Generates a complete dermatoscopic image for the specified disease class."""
    img = create_skin_background(img_size, img_size)
    generator_fn = GENERATOR_MAP[dx_class]
    img = generator_fn(img)
    
    # 35% chance to have hair artifacts (for DullRazor verification)
    if random.random() < 0.35:
        img = add_hair_artifacts(img, num_hairs=random.randint(2, 4))
        
    # Apply lens optics vignette
    img = add_dermatoscope_vignette(img)
    return img


def generate_dataset(samples_per_class=70, img_size=128):
    """Generates demo dataset and creates stratified train/val/test splits."""
    random.seed(42)
    np.random.seed(42)
    
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(ASSETS_SAMPLE_DIR, exist_ok=True)
    
    metadata_rows = []
    localizations = ["back", "lower extremity", "trunk", "upper extremity", "abdomen", "face", "chest", "neck"]
    dx_types = ["histo", "follow_up", "consensus", "confocal"]
    
    print(f"[+] Generating demo dataset ({samples_per_class} samples/class across 7 classes = {samples_per_class * 7} images)...")
    
    for cls in CLASSES:
        for idx in range(samples_per_class):
            img_id = f"ISIC_{cls}_{idx:04d}"
            filename = f"{img_id}.jpg"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            img_arr = generate_single_sample(cls, img_id, img_size=img_size)
            pil_img = Image.fromarray(img_arr)
            pil_img.save(filepath, quality=92)
            
            # Save first 2 of each class directly into sample assets for the dashboard
            if idx < 2:
                sample_path = os.path.join(ASSETS_SAMPLE_DIR, f"sample_{cls}_{idx+1}.jpg")
                pil_img.save(sample_path, quality=95)
            
            age = random.choice([25, 35, 45, 55, 65, 75])
            sex = random.choice(["male", "female"])
            localization = random.choice(localizations)
            dx_type = random.choice(dx_types)
            
            metadata_rows.append({
                "image_id": img_id,
                "dx": cls,
                "dx_type": dx_type,
                "age": age,
                "sex": sex,
                "localization": localization,
                "file_path": os.path.relpath(filepath, BASE_DIR),
            })
            
    df = pd.DataFrame(metadata_rows)
    
    # Stratified 70% Train, 15% Val, 15% Test split
    from sklearn.model_selection import train_test_split
    train_df, temp_df = train_test_split(df, test_size=0.30, stratify=df["dx"], random_state=42)
    val_df, test_df = train_test_split(temp_df, test_size=0.50, stratify=temp_df["dx"], random_state=42)
    
    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()
    
    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"
    
    final_df = pd.concat([train_df, val_df, test_df]).sort_values("image_id").reset_index(drop=True)
    meta_csv_path = os.path.join(PROCESSED_DIR, "metadata.csv")
    final_df.to_csv(meta_csv_path, index=False)
    
    print(f"[✓] Dataset generated successfully!")
    print(f"    Total images: {len(final_df)}")
    print(f"    Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")
    print(f"    Metadata saved to: {meta_csv_path}")
    print(f"    Assets saved to: {ASSETS_SAMPLE_DIR}")
    return final_df


if __name__ == "__main__":
    generate_dataset(samples_per_class=70, img_size=128)
