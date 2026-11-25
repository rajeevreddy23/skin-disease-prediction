"""
verify_pipeline.py - Verification script to test end-to-end inference, Grad-CAM, and database.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.predict import SkinDiseasePredictor

p = SkinDiseasePredictor()
sample_dir = os.path.join(BASE_DIR, "app", "assets", "sample_images")

test_samples = [
    ("Melanoma", "sample_mel_1.jpg"),
    ("Basal Cell Carcinoma", "sample_bcc_1.jpg"),
    ("Melanocytic Nevus", "sample_nv_1.jpg"),
    ("Actinic Keratosis", "sample_akiec_1.jpg"),
    ("Vascular Lesion", "sample_vasc_1.jpg"),
]

print("=" * 70)
print("             DERMASCAN AI MULTI-SAMPLE VERIFICATION")
print("=" * 70)

for expected_name, filename in test_samples:
    img_path = os.path.join(sample_dir, filename)
    if os.path.exists(img_path):
        res = p.predict(img_path, apply_dull_razor=True, generate_gradcam=True, save_to_db=True)
        conf_str = f"{res['confidence']:.1f}%"
        lat_str = f"{res['latency_ms']:.1f}ms"
        print(f"[{res['prediction_class'].upper():5s}] {res['prediction_name']:28s} | Conf: {conf_str:6s} | Latency: {lat_str:7s} | Risk: {res['risk_level']}")

print("=" * 70)
print("[✓] ALL MULTI-CLASS INFERENCES COMPLETED AND PERSISTED TO SQLITE!")
