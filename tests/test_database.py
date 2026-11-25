"""
test_database.py - Unit tests for SQLite prediction history database.
"""

import os
import sys
import tempfile
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.database import (
    init_db,
    insert_prediction,
    get_all_predictions,
    get_history_count,
    clear_history,
    export_history_to_csv,
)


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_history.db")
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_insert_and_get_predictions(temp_db):
    """Verifies inserting a prediction and reading it back."""
    top3_sample = [
        {"class_code": "mel", "name": "Melanoma", "probability": 88.5},
        {"class_code": "nv", "name": "Melanocytic Nevus", "probability": 8.2},
        {"class_code": "bkl", "name": "Benign Keratosis", "probability": 3.3},
    ]
    
    rec_id = insert_prediction(
        prediction_class="mel",
        prediction_name="Melanoma",
        confidence=88.5,
        risk_level="Critical Risk (Malignant)",
        top3=top3_sample,
        image_path="test_image.jpg",
        source="upload",
        latency_ms=45.2,
        db_path=temp_db,
    )
    
    assert rec_id == 1
    assert get_history_count(temp_db) == 1
    
    df = get_all_predictions(limit=10, db_path=temp_db)
    assert len(df) == 1
    assert df.iloc[0]["prediction_class"] == "mel"
    assert df.iloc[0]["confidence_pct"] == 88.5


def test_clear_and_export_csv(temp_db):
    """Verifies CSV export and history clearing."""
    top3_sample = [{"class_code": "nv", "name": "Mole", "probability": 95.0}]
    insert_prediction("nv", "Nevus", 95.0, "Low", top3_sample, db_path=temp_db)
    
    csv_path = temp_db.replace(".db", ".csv")
    exported = export_history_to_csv(csv_path, db_path=temp_db)
    assert os.path.exists(exported)
    
    clear_history(temp_db)
    assert get_history_count(temp_db) == 0
    if os.path.exists(csv_path):
        os.remove(csv_path)
