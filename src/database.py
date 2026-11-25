"""
database.py - SQLite Database Management for Skin Disease Prediction History.
Provides persistent storage, retrieval, analytics, and CSV export for predictions.
"""

import os
import sqlite3
import json
from datetime import datetime
import pandas as pd

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "history.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates parent directory if needed and returns a SQLite connection."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the prediction history database schema."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            image_path TEXT,
            prediction_class TEXT NOT NULL,
            prediction_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            risk_level TEXT NOT NULL,
            top3_json TEXT NOT NULL,
            source TEXT DEFAULT 'upload',
            latency_ms REAL DEFAULT 0.0
        )
        """
    )
    conn.commit()
    conn.close()


def insert_prediction(
    prediction_class: str,
    prediction_name: str,
    confidence: float,
    risk_level: str,
    top3: list,
    image_path: str = "",
    source: str = "upload",
    latency_ms: float = 0.0,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Inserts a new prediction record into SQLite and returns the generated row ID."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top3_json = json.dumps(top3)

    cursor.execute(
        """
        INSERT INTO prediction_history (
            timestamp, image_path, prediction_class, prediction_name,
            confidence, risk_level, top3_json, source, latency_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_str,
            image_path,
            prediction_class,
            prediction_name,
            float(confidence),
            risk_level,
            top3_json,
            source,
            float(latency_ms),
        ),
    )
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_predictions(limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Fetches the latest prediction records as a pandas DataFrame."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    query = """
        SELECT id, timestamp, prediction_class, prediction_name,
               ROUND(confidence, 2) AS confidence_pct, risk_level,
               source, ROUND(latency_ms, 1) AS latency_ms, image_path
        FROM prediction_history
        ORDER BY id DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df


def get_history_count(db_path: str = DEFAULT_DB_PATH) -> int:
    """Returns the total number of logged predictions."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM prediction_history")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def clear_history(db_path: str = DEFAULT_DB_PATH) -> None:
    """Clears all records from the prediction history table."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prediction_history")
    conn.commit()
    conn.close()


def export_history_to_csv(csv_path: str, db_path: str = DEFAULT_DB_PATH) -> str:
    """Exports all prediction history records to a CSV file."""
    df = get_all_predictions(limit=100000, db_path=db_path)
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    df.to_csv(csv_path, index=False)
    return csv_path
