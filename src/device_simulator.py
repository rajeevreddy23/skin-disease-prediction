"""
device_simulator.py - Software-Only IoT Edge Architecture Simulator.
Mimics the full pipeline:
[ESP32-CAM Camera Sensor] ---> [Raspberry Pi Edge Gateway / Broker] ---> [Laptop Deep Learning Inference Engine]
Runs as an asynchronous background thread with a thread-safe frame queue and telemetry reporting.
"""

import os
import time
import queue
import random
import threading
from datetime import datetime
from PIL import Image
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_ASSETS_DIR = os.path.join(BASE_DIR, "app", "assets", "sample_images")


class EdgeDeviceSimulator:
    """
    Simulates the multi-tier hardware architecture (ESP32-CAM -> Raspberry Pi -> Laptop)
    in software without requiring any physical microcontrollers.
    """
    def __init__(self, predictor=None, capture_interval_sec: float = 3.5):
        self.predictor = predictor
        self.capture_interval_sec = capture_interval_sec
        self.frame_queue = queue.Queue(maxsize=10)
        
        self.is_running = False
        self.worker_thread = None
        self.lock = threading.Lock()
        
        # Telemetry metrics
        self.stats = {
            "status": "IDLE",
            "frames_captured": 0,
            "packets_transmitted": 0,
            "bytes_transferred": 0,
            "simulated_baud_rate": "115200 bps",
            "simulated_wifi_rssi": "-58 dBm",
            "simulated_edge_ip": "192.168.4.1 (ESP32) -> 192.168.4.2 (RPi)",
            "last_capture_time": None,
            "last_prediction": None,
            "queue_depth": 0,
        }

    def _get_candidate_frames(self) -> list:
        """Finds sample image paths to simulate camera frame captures."""
        if os.path.exists(SAMPLE_ASSETS_DIR):
            files = [
                os.path.join(SAMPLE_ASSETS_DIR, f)
                for f in os.listdir(SAMPLE_ASSETS_DIR)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if files:
                return files
        return []

    def _simulate_esp32_capture(self) -> tuple:
        """
        Stage 1: Simulates ESP32-CAM frame capture, JPEG compression, and packetization.
        """
        candidate_paths = self._get_candidate_frames()
        if candidate_paths:
            chosen_path = random.choice(candidate_paths)
            img = Image.open(chosen_path).convert("RGB")
            frame_source = os.path.basename(chosen_path)
        else:
            # Fallback synthetic frame
            arr = np.random.randint(180, 240, (128, 128, 3), dtype=np.uint8)
            img = Image.fromarray(arr)
            frame_source = "synthetic_esp32_sensor_frame"

        # Simulate JPEG payload size (approx 12-25 KB for 128x128)
        simulated_bytes = random.randint(14200, 26800)
        return img, frame_source, simulated_bytes

    def _worker_loop(self):
        """Continuous background execution mimicking the IoT streaming pipeline."""
        while self.is_running:
            try:
                # 1. ESP32-CAM Sensor Capture
                frame_img, frame_source, payload_bytes = self._simulate_esp32_capture()
                
                # 2. Raspberry Pi Gateway Ingestion & Queueing
                with self.lock:
                    self.stats["status"] = "STREAMING (ESP32-CAM -> RPi Gateway)"
                    self.stats["frames_captured"] += 1
                    self.stats["packets_transmitted"] += 1
                    self.stats["bytes_transferred"] += payload_bytes
                    self.stats["last_capture_time"] = datetime.now().strftime("%H:%M:%S")

                # Put frame on edge buffer queue
                if not self.frame_queue.full():
                    self.frame_queue.put((frame_img, frame_source, payload_bytes))
                self.stats["queue_depth"] = self.frame_queue.qsize()

                # 3. Laptop Deep Learning Ingestion & Inference
                if not self.frame_queue.empty() and self.predictor is not None:
                    img_to_process, src_label, p_bytes = self.frame_queue.get()
                    
                    with self.lock:
                        self.stats["status"] = "INFERENCE (Laptop Deep Learning Engine)"
                        
                    pred_result = self.predictor.predict(
                        image_input=img_to_process,
                        apply_dull_razor=True,
                        generate_gradcam=True,
                        save_to_db=True,
                        source="device_simulator",
                        image_path_label=f"ESP32_RPi_Stream_{src_label}",
                    )
                    
                    with self.lock:
                        self.stats["last_prediction"] = {
                            "class": pred_result["prediction_class"],
                            "name": pred_result["prediction_name"],
                            "confidence": pred_result["confidence"],
                            "risk_level": pred_result["risk_level"],
                            "latency_ms": pred_result["latency_ms"],
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "source": src_label,
                        }
                        self.stats["status"] = "IDLE (Waiting for next telemetry tick)"
                        self.stats["queue_depth"] = self.frame_queue.qsize()

            except Exception as e:
                with self.lock:
                    self.stats["status"] = f"ERROR: {str(e)}"

            # Wait for next telemetry tick
            time.sleep(self.capture_interval_sec)

    def start(self):
        """Starts the simulated device telemetry pipeline in a background thread."""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            self.stats["status"] = "ONLINE (ESP32-CAM & RPi Gateway Active)"
            print("[+] Device Simulator started successfully.")

    def stop(self):
        """Stops the simulated background thread."""
        if self.is_running:
            self.is_running = False
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2.0)
            self.stats["status"] = "OFFLINE"
            print("[✓] Device Simulator stopped.")

    def get_telemetry(self) -> dict:
        """Returns current simulated hardware telemetry data."""
        with self.lock:
            return dict(self.stats)
