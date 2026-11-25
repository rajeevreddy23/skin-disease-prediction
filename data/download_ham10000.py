"""
download_ham10000.py - Script to download and prepare the HAM10000 dataset.
Supports automated download via Kaggle API if credentials exist,
or provides step-by-step instructions with automatic directory setup.
"""

import os
import sys
import argparse

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")


def setup_directories():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    print(f"[+] Verified directories:\n    Raw: {RAW_DIR}\n    Processed: {PROCESSED_DIR}")


def check_dataset_exists():
    meta_path = os.path.join(RAW_DIR, "HAM10000_metadata.csv")
    images_dir = os.path.join(RAW_DIR, "images")
    if os.path.exists(meta_path) and os.path.isdir(images_dir):
        image_count = len([f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        print(f"[✓] Found existing HAM10000 dataset: {image_count} images.")
        return True
    return False


def print_manual_instructions():
    print("""
================================================================================
                      HAM10000 DATASET DOWNLOAD GUIDE
================================================================================
The HAM10000 ("Human Against Machine with 10000 training images") dataset contains
10,015 dermatoscopic images of pigmented skin lesions across 7 diagnostic categories:
  1. nv    - Melanocytic nevi (6,705 images)
  2. mel   - Melanoma (1,113 images)
  3. bkl   - Benign keratosis-like lesions (1,099 images)
  4. bcc   - Basal cell carcinoma (514 images)
  5. akiec - Actinic keratoses / intraepithelial carcinoma (327 images)
  6. vasc  - Vascular lesions (142 images)
  7. df    - Dermatofibroma (115 images)

OPTION A: Automatic download with Kaggle API (Recommended if Kaggle is installed)
  1. Install kaggle CLI: pip install kaggle
  2. Place your 'kaggle.json' API token in ~/.kaggle/
  3. Run: python data/download_ham10000.py --kaggle

OPTION B: Manual Web Download
  1. Visit: https://www.kaggle.com/datasets/kmader/skin-cancer-mnist-ham10000
     (Or Harvard Dataverse: https://doi.org/10.7910/DVN/DBW86T)
  2. Download 'skin-cancer-mnist-ham10000.zip'
  3. Extract all images into:
     d:\\SkinD\\data\\raw\\images\\
  4. Place 'HAM10000_metadata.csv' into:
     d:\\SkinD\\data\\raw\\HAM10000_metadata.csv

OPTION C: Quick Demo Dataset (Instant local execution without downloading 3GB)
  Run: python data/prepare_demo_dataset.py
  This creates realistic synthetic dermoscopic samples for all 7 classes,
  allowing immediate local training and full pipeline execution within minutes!
================================================================================
""")


def try_kaggle_download():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        print("[+] Kaggle authentication successful! Downloading dataset...")
        api.dataset_download_files("kmader/skin-cancer-mnist-ham10000", path=RAW_DIR, unzip=True)
        print("[✓] Download and extraction complete!")
        return True
    except Exception as e:
        print(f"[-] Kaggle download not possible: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download HAM10000 dataset")
    parser.add_argument("--kaggle", action="store_true", help="Attempt download using Kaggle API")
    args = parser.parse_args()

    setup_directories()
    if check_dataset_exists():
        print("[✓] Dataset is ready for preprocessing.")
        sys.exit(0)

    if args.kaggle:
        success = try_kaggle_download()
        if not success:
            print_manual_instructions()
    else:
        print_manual_instructions()
