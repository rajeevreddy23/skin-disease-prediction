"""
app.py - DermaScan AI: Skin Disease Prediction & Diagnostic Web Dashboard.
Features:
- Live laptop webcam capture, file upload, and preloaded sample lesion gallery
- DullRazor hair removal and CLAHE contrast enhancement
- Multi-model selection (MobileNetV2, EfficientNetB0, Custom CNN)
- Explainable AI with Grad-CAM heatmap overlays
- Top-3 diagnostic probability bar chart & clinical information card
- SQLite prediction history table with CSV export
- Simulated Edge IoT hardware architecture mode (ESP32-CAM -> Raspberry Pi -> Laptop)
- Prominent educational medical disclaimer
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np
from PIL import Image
import streamlit as st
import matplotlib.pyplot as plt

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.predict import SkinDiseasePredictor
from src.preprocess import dull_razor_hair_removal, apply_clahe
from src.database import (
    get_all_predictions,
    get_history_count,
    clear_history,
    export_history_to_csv,
    DEFAULT_DB_PATH,
)
from src.device_simulator import EdgeDeviceSimulator

# Configure Streamlit page
st.set_page_config(
    page_title="DermaScan AI - Skin Lesion Diagnostic System",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
CSS_PATH = os.path.join(BASE_DIR, "app", "assets", "styles.css")
if os.path.exists(CSS_PATH):
    with open(CSS_PATH, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

SAMPLE_ASSETS_DIR = os.path.join(BASE_DIR, "app", "assets", "sample_images")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MODELS_DIR = os.path.join(BASE_DIR, "models")


@st.cache_resource
def load_predictor(model_choice: str):
    """Cached loader for the neural network predictor."""
    weights_filename = "best_model.pth"
    model_arch = None

    if "Custom" in model_choice:
        weights_filename = "custom_cnn.pth"
        model_arch = "custom_cnn"
    elif "MobileNet" in model_choice:
        weights_filename = "mobilenet_v2.pth"
        model_arch = "mobilenet_v2"
    elif "EfficientNet" in model_choice:
        weights_filename = "efficientnet_b0.pth"
        model_arch = "efficientnet_b0"

    weights_path = os.path.join(MODELS_DIR, weights_filename)
    if not os.path.exists(weights_path):
        # Fallback to any existing .pth in models/
        available_pths = [f for f in os.listdir(MODELS_DIR) if f.endswith(".pth")]
        if available_pths:
            weights_path = os.path.join(MODELS_DIR, available_pths[0])

    return SkinDiseasePredictor(weights_path=weights_path, model_name=model_arch)


# Initialize device simulator in session state
if "device_simulator" not in st.session_state:
    st.session_state.device_simulator = None


# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("## 🔬 DermaScan AI")
    st.markdown("**Computer-Aided Skin Lesion Diagnostic System**")
    st.caption("Final-Year Engineering Project • Software-Only Architecture")
    st.markdown("---")

    st.markdown("### ⚙️ Inference Settings")
    model_options = [
        "Best Model (Auto-selected)",
        "MobileNetV2 (Fine-Tuned)",
        "EfficientNetB0 (Fine-Tuned)",
        "Custom CNN (Baseline)",
    ]
    selected_model = st.selectbox("Select Model Architecture", model_options, index=0)
    
    st.markdown("### 🧹 Preprocessing Filters")
    enable_dull_razor = st.checkbox("DullRazor Hair Removal", value=True, help="Removes hair artifacts and dark streaks using morphological inpainting.")
    enable_clahe = st.checkbox("CLAHE Contrast Enhancement", value=False, help="Enhances lesion border visibility via adaptive histogram equalization.")

    st.markdown("### 🎨 Explainable AI (Grad-CAM)")
    gradcam_alpha = st.slider("Heatmap Opacity (α)", min_value=0.1, max_value=0.9, value=0.45, step=0.05)

    st.markdown("---")
    st.markdown("### 📡 Simulated IoT Edge Mode")
    st.caption("Emulates ESP32-CAM → Raspberry Pi → Laptop pipeline in software.")

    sim_active = st.session_state.device_simulator is not None and st.session_state.device_simulator.is_running
    if not sim_active:
        if st.button("▶ Start Edge Stream Simulator", use_container_width=True):
            predictor = load_predictor(selected_model)
            simulator = EdgeDeviceSimulator(predictor=predictor, capture_interval_sec=3.5)
            simulator.start()
            st.session_state.device_simulator = simulator
            st.success("Edge IoT stream simulation active!")
            st.rerun()
    else:
        if st.button("⏹ Stop Edge Stream Simulator", use_container_width=True):
            st.session_state.device_simulator.stop()
            st.session_state.device_simulator = None
            st.info("Edge IoT stream stopped.")
            st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div class="disclaimer-banner">
            ⚠️ <b>EDUCATIONAL DISCLAIMER</b><br>
            This system is strictly for academic research and educational evaluation. It is <b>NOT</b> a certified medical diagnostic device. Always seek direct consultation with a qualified dermatologist.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# MAIN TABS
# ==============================================================================
tab_diag, tab_hist, tab_eval, tab_device, tab_about = st.tabs([
    "🩺 Live Diagnosis & Grad-CAM",
    "📋 Prediction History",
    "📊 Model Analytics & Comparison",
    "📡 Edge Device Architecture (Simulated)",
    "ℹ️ Project Documentation",
])

# Load Predictor
predictor = load_predictor(selected_model)


# ------------------------------------------------------------------------------
# TAB 1: LIVE DIAGNOSIS
# ------------------------------------------------------------------------------
with tab_diag:
    st.markdown("### 🎯 Patient Skin Lesion Diagnostic Workspace")
    st.markdown("Capture a live lesion image using your laptop webcam, upload a clinical photograph, or choose from standard pre-screened samples.")

    source_col, preview_col = st.columns([1, 1])

    input_image = None
    input_source = "upload"
    image_label = "uploaded_lesion"

    with source_col:
        st.markdown("#### 1. Select Input Modality")
        input_choice = st.radio(
            "Image Input Source",
            ["📷 Laptop Webcam Live Capture", "📁 Upload Image File", "🖼️ Curated Sample Gallery"],
            index=2,
            horizontal=True,
        )

        if "Webcam" in input_choice:
            input_source = "webcam"
            camera_file = st.camera_input("Capture Lesion from Laptop Webcam")
            if camera_file is not None:
                input_image = Image.open(camera_file).convert("RGB")
                image_label = f"Webcam_Capture_{int(time.time())}"

        elif "Upload" in input_choice:
            input_source = "upload"
            uploaded_file = st.file_uploader(
                "Choose a dermatoscopic or clinical image",
                type=["jpg", "jpeg", "png"],
                help="Supports JPEG, JPG, and PNG formats.",
            )
            if uploaded_file is not None:
                input_image = Image.open(uploaded_file).convert("RGB")
                image_label = uploaded_file.name

        elif "Gallery" in input_choice:
            input_source = "sample"
            st.markdown("Select a lesion from the HAM10000 benchmark categories:")
            sample_options = {
                "Melanoma (mel) - High Malignancy": "sample_mel_1.jpg",
                "Basal Cell Carcinoma (bcc) - Common Skin Cancer": "sample_bcc_1.jpg",
                "Melanocytic Nevus (nv) - Benign Mole": "sample_nv_1.jpg",
                "Benign Keratosis (bkl) - Non-cancerous Growth": "sample_bkl_1.jpg",
                "Actinic Keratosis (akiec) - Pre-cancerous Lesion": "sample_akiec_1.jpg",
                "Vascular Lesion (vasc) - Hemangioma/Angioma": "sample_vasc_1.jpg",
                "Dermatofibroma (df) - Benign Cutaneous Nodule": "sample_df_1.jpg",
            }
            chosen_sample_name = st.selectbox("Benchmark Diagnostic Sample", list(sample_options.keys()))
            chosen_filename = sample_options[chosen_sample_name]
            sample_path = os.path.join(SAMPLE_ASSETS_DIR, chosen_filename)

            if os.path.exists(sample_path):
                input_image = Image.open(sample_path).convert("RGB")
                image_label = chosen_filename
            else:
                st.warning("Sample assets directory being initialized...")

    with preview_col:
        st.markdown("#### 2. Input Image & Preprocessing Preview")
        if input_image is not None:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.image(input_image, caption="Original Input Image", use_container_width=True)
            with p_col2:
                # Show effect of preprocessing
                np_preview = np.array(input_image)
                if enable_dull_razor:
                    np_preview = dull_razor_hair_removal(np_preview)
                if enable_clahe:
                    np_preview = apply_clahe(np_preview)
                st.image(np_preview, caption="Preprocessed Image (DullRazor/CLAHE)", use_container_width=True)
        else:
            st.info("👆 Please select or capture an image on the left to begin diagnosis.")

    st.markdown("---")

    # Run Prediction if image is present
    if input_image is not None:
        if st.button("🚀 Run Deep Learning Diagnostic & Explainability Analysis", type="primary", use_container_width=True):
            with st.spinner("Executing neural inference and computing Grad-CAM activation maps..."):
                results = predictor.predict(
                    image_input=input_image,
                    apply_dull_razor=enable_dull_razor,
                    apply_contrast_enhancement=enable_clahe,
                    generate_gradcam=True,
                    gradcam_alpha=gradcam_alpha,
                    save_to_db=True,
                    source=input_source,
                    image_path_label=image_label,
                )

            st.success("Diagnostic Analysis Complete!")

            # ------------------------------------------------------------------
            # Results Presentation
            # ------------------------------------------------------------------
            res_left, res_right = st.columns([1.1, 0.9])

            with res_left:
                st.markdown("### 🏆 Diagnostic Finding")
                risk_badge_class = "risk-low"
                if "Moderate" in results["risk_level"]:
                    risk_badge_class = "risk-moderate"
                elif "High" in results["risk_level"]:
                    risk_badge_class = "risk-high"
                elif "Critical" in results["risk_level"]:
                    risk_badge_class = "risk-critical"

                st.markdown(
                    f"""
                    <div class="diagnostic-card">
                        <div class="metric-label">Predicted Diagnostic Classification</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #0f172a; margin: 0.3rem 0;">
                            {results['prediction_name']} ({results['prediction_class'].upper()})
                        </div>
                        <div style="margin: 0.5rem 0;">
                            <span class="risk-badge {risk_badge_class}">{results['risk_level']}</span>
                        </div>
                        <div style="display: flex; gap: 2rem; margin-top: 1rem;">
                            <div>
                                <span class="metric-label">Model Confidence</span><br>
                                <span class="metric-highlight">{results['confidence']:.1f}%</span>
                            </div>
                            <div>
                                <span class="metric-label">Inference Latency</span><br>
                                <span class="metric-highlight" style="color: #64748b;">{results['latency_ms']:.1f} ms</span>
                            </div>
                            <div>
                                <span class="metric-label">Record ID</span><br>
                                <span class="metric-highlight" style="color: #64748b;">#{results['record_id']}</span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("#### 📊 Top-3 Ranked Probabilities")
                top3_df = pd.DataFrame([
                    {"Disease / Condition": item["name"], "Probability (%)": item["probability"]}
                    for item in results["top3"]
                ])
                st.bar_chart(top3_df.set_index("Disease / Condition"), color="#0284c7")

                # Full distribution table
                with st.expander("🔍 View All 7 Diagnostic Class Probabilities"):
                    all_df = pd.DataFrame([
                        {"Class Code": k.upper(), "Probability (%)": round(v, 2)}
                        for k, v in results["all_probabilities"].items()
                    ]).sort_values("Probability (%)", ascending=False)
                    st.dataframe(all_df, use_container_width=True, hide_index=True)

            with res_right:
                st.markdown("### 🧠 Grad-CAM Explainable AI Visualizer")
                st.caption("Visualizes the specific spatial receptive fields that drove the convolutional network's decision.")

                cam_col1, cam_col2 = st.columns(2)
                with cam_col1:
                    st.image(results["gradcam_heatmap"], caption="Grad-CAM Raw Heatmap (JET Colormap)", use_container_width=True)
                with cam_col2:
                    st.image(results["gradcam_overlay"], caption=f"Heatmap Overlay on Lesion (α={gradcam_alpha})", use_container_width=True)

                st.markdown(
                    """
                    > **Clinical Receptive Field Interpretation**:  
                    > • **Red / Yellow Zones**: High diagnostic saliency. The neural network's convolutional filters focused heavily on irregular pigment networks, atypical borders, or vascular telangiectatic structures in these regions.  
                    > • **Blue Zones**: Low diagnostic relevance (healthy background epidermis / perilesional tissue).
                    """
                )

            # Disease Information Card
            st.markdown("---")
            st.markdown("### 📖 Clinical Condition Overview & Recommendations")
            info = results["disease_info"]
            
            c_card1, c_card2 = st.columns([1, 1])
            with c_card1:
                st.markdown(f"**Classification Type**: `{info.get('type', 'N/A')}`")
                st.write(info.get("description", "No description available."))
                st.markdown("**Common Clinical Symptoms / Signs:**")
                for s in info.get("symptoms", []):
                    st.markdown(f"- {s}")
            with c_card2:
                st.markdown("#### 👨‍⚕️ Dermatological Consultation Advice")
                st.info(info.get("consultation_advice", "Please consult a healthcare professional for clinical confirmation."))
                st.warning("⚠️ **Reminder**: Biopsy and histopathological examination remain the definitive gold standard for skin lesion diagnosis.")


# ------------------------------------------------------------------------------
# TAB 2: PREDICTION HISTORY & DATABASE
# ------------------------------------------------------------------------------
with tab_hist:
    st.markdown("### 📋 SQLite Diagnostic History & Audit Log")
    st.markdown("All inferences across webcam captures, uploads, and simulated streams are securely logged in the local SQLite database.")

    h_count = get_history_count()
    h_df = get_all_predictions(limit=100)

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Scans Logged", h_count)
    with m2:
        if not h_df.empty:
            avg_conf = h_df["confidence_pct"].mean()
            st.metric("Mean Diagnostic Confidence", f"{avg_conf:.1f}%")
        else:
            st.metric("Mean Diagnostic Confidence", "N/A")
    with m3:
        if not h_df.empty:
            high_risk_count = len(h_df[h_df["risk_level"].str.contains("High|Critical", na=False)])
            st.metric("High / Critical Risk Lesions", high_risk_count)
        else:
            st.metric("High / Critical Risk Lesions", 0)
    with m4:
        if not h_df.empty:
            avg_lat = h_df["latency_ms"].mean()
            st.metric("Average Inference Latency", f"{avg_lat:.1f} ms")
        else:
            st.metric("Average Inference Latency", "N/A")

    st.markdown("---")

    if not h_df.empty:
        # Filter controls
        f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
        with f_col1:
            risk_filter = st.multiselect(
                "Filter by Risk Level",
                options=h_df["risk_level"].unique().tolist(),
                default=h_df["risk_level"].unique().tolist(),
            )
        with f_col2:
            source_filter = st.multiselect(
                "Filter by Source",
                options=h_df["source"].unique().tolist(),
                default=h_df["source"].unique().tolist(),
            )
        with f_col3:
            search_query = st.text_input("Search Condition / Image Name", "")

        filtered_df = h_df[
            (h_df["risk_level"].isin(risk_filter)) &
            (h_df["source"].isin(source_filter))
        ]
        if search_query:
            filtered_df = filtered_df[
                filtered_df["prediction_name"].str.contains(search_query, case=False, na=False) |
                filtered_df["image_path"].str.contains(search_query, case=False, na=False)
            ]

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        # Actions
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            csv_data = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download History as CSV",
                data=csv_data,
                file_name=f"dermascan_history_{int(time.time())}.csv",
                mime="text/csv",
                type="primary",
            )
        with btn_c2:
            if st.button("🗑️ Clear Prediction History Database"):
                clear_history()
                st.success("Database records cleared.")
                st.rerun()
    else:
        st.info("No prediction records logged yet. Run a diagnosis in Tab 1 to create your first record!")


# ------------------------------------------------------------------------------
# TAB 3: MODEL ANALYTICS & COMPARISON
# ------------------------------------------------------------------------------
with tab_eval:
    st.markdown("### 📊 Model Architecture Comparison & Benchmark Metrics")
    st.markdown("Empirical evaluation comparing **Custom CNN**, **MobileNetV2**, and **EfficientNetB0** on the hold-out test set.")

    # Model comparison table
    comp_csv_path = os.path.join(RESULTS_DIR, "model_comparison.csv")
    if os.path.exists(comp_csv_path):
        comp_df = pd.read_csv(comp_csv_path)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Training pipeline is running or finalizing model comparison records.")

    # Visual Analytics Grid
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("#### 1. Training & Validation Curves")
        train_curves_path = os.path.join(RESULTS_DIR, "training_curves.png")
        if os.path.exists(train_curves_path):
            st.image(train_curves_path, use_container_width=True)
        else:
            st.caption("Training curves generating...")

    with col_g2:
        st.markdown("#### 2. Model Performance Bar Chart")
        comp_plot_path = os.path.join(RESULTS_DIR, "model_comparison.png")
        if os.path.exists(comp_plot_path):
            st.image(comp_plot_path, use_container_width=True)
        else:
            st.caption("Comparison chart generating...")

    col_g3, col_g4 = st.columns(2)
    with col_g3:
        st.markdown("#### 3. Hold-Out Confusion Matrix")
        cm_path = os.path.join(RESULTS_DIR, "confusion_matrix.png")
        if os.path.exists(cm_path):
            st.image(cm_path, use_container_width=True)
        else:
            st.caption("Confusion matrix generating...")

    with col_g4:
        st.markdown("#### 4. Multi-Class ROC Curves")
        roc_path = os.path.join(RESULTS_DIR, "roc_curves.png")
        if os.path.exists(roc_path):
            st.image(roc_path, use_container_width=True)
        else:
            st.caption("ROC curves generating...")

    # Classification Report
    rep_txt_path = os.path.join(RESULTS_DIR, "classification_report.txt")
    if os.path.exists(rep_txt_path):
        with st.expander("📄 View Detailed Classification Report (Precision, Recall, F1 per Class)"):
            with open(rep_txt_path, "r") as f:
                st.code(f.read(), language="text")


# ------------------------------------------------------------------------------
# TAB 4: SIMULATED EDGE DEVICE ARCHITECTURE
# ------------------------------------------------------------------------------
with tab_device:
    st.markdown("### 📡 Simulated IoT Edge Pipeline: ESP32-CAM → Raspberry Pi → Laptop")
    st.markdown("Demonstrates the full distributed hardware architecture completely within software using background threading and asynchronous queuing.")

    st.markdown(
        """
        ```mermaid
        flowchart LR
            ESP["📷 Layer 1: ESP32-CAM Sensor<br/>(Frame Capture, JPEG Encapsulation)"]
            RPi["🧠 Layer 2: Raspberry Pi Gateway<br/>(Packet Verification, Edge Queue)"]
            Laptop["💻 Layer 3: Laptop AI Engine<br/>(CNN Inference, Grad-CAM, SQLite DB)"]
            
            ESP -->|"Simulated Wi-Fi / Serial (115200 bps)"| RPi
            RPi -->|"Thread-Safe Queue Buffer"| Laptop
        ```
        """
    )

    dev_c1, dev_c2 = st.columns([1, 1])

    with dev_c1:
        st.markdown("#### 🛰️ Hardware Telemetry Console")
        if st.session_state.device_simulator is not None and st.session_state.device_simulator.is_running:
            stats = st.session_state.device_simulator.get_telemetry()
            st.markdown(
                f"""
                <div class="telemetry-card">
                    <b>[EDGE_STATUS]</b>: {stats['status']}<br>
                    <b>[NETWORK_ROUTE]</b>: {stats['simulated_edge_ip']}<br>
                    <b>[BAUD_RATE]</b>: {stats['simulated_baud_rate']}<br>
                    <b>[WIFI_RSSI]</b>: {stats['simulated_wifi_rssi']}<br>
                    <b>[FRAMES_CAPTURED]</b>: {stats['frames_captured']}<br>
                    <b>[PACKETS_TRANSMITTED]</b>: {stats['packets_transmitted']}<br>
                    <b>[BYTES_TRANSFERRED]</b>: {stats['bytes_transferred']:,} bytes<br>
                    <b>[QUEUE_DEPTH]</b>: {stats['queue_depth']} frames<br>
                    <b>[LAST_TICK]</b>: {stats['last_capture_time']}
                </div>
                """,
                unsafe_allow_html=True,
            )
            time.sleep(1.0)
            st.button("🔄 Refresh Telemetry Feed")
        else:
            st.info("Simulated edge mode is currently OFFLINE. Toggle it on in the sidebar to stream simulated frames!")

    with dev_c2:
        st.markdown("#### ⚡ Latest Edge Stream Prediction")
        if st.session_state.device_simulator is not None and st.session_state.device_simulator.is_running:
            stats = st.session_state.device_simulator.get_telemetry()
            lp = stats.get("last_prediction")
            if lp:
                st.success(f"Latest Stream Frame Processed ({lp['timestamp']})")
                st.markdown(f"**Predicted Disease**: {lp['name']} (`{lp['class']}`)")
                st.markdown(f"**Confidence**: `{lp['confidence']:.1f}%` | **Risk**: `{lp['risk_level']}`")
                st.markdown(f"**Inference Latency**: `{lp['latency_ms']:.1f} ms`")
                st.caption(f"Source: {lp['source']}")
            else:
                st.caption("Waiting for first streamed frame from edge queue...")
        else:
            st.caption("No active telemetry stream.")


# ------------------------------------------------------------------------------
# TAB 5: PROJECT DOCUMENTATION & ARCHITECTURE
# ------------------------------------------------------------------------------
with tab_about:
    st.markdown("### 📖 Final-Year Project Overview")
    st.markdown(
        """
        **Project Title**: *Skin Disease Prediction Using Machine Learning with Live Image Capture and Web Dashboard*  
        **Author**: Senior Full-Stack ML Engineer  
        **Dataset**: HAM10000 (Human Against Machine with 10,000 training images)  
        **Target Classes**:
        1. `nv`: Melanocytic nevi (Common moles)
        2. `mel`: Melanoma (Malignant melanoma)
        3. `bkl`: Benign keratosis-like lesions
        4. `bcc`: Basal cell carcinoma
        5. `akiec`: Actinic keratoses & intraepithelial carcinoma
        6. `vasc`: Vascular lesions
        7. `df`: Dermatofibroma

        ---
        #### 🏗️ System Architecture
        1. **Image Ingestion**: Laptop Webcam (Live capture via OpenCV / browser) or High-resolution file upload.
        2. **Preprocessing**: DullRazor morphological filtering (black hat + inpainting) to eliminate hair artifacts, CLAHE contrast equalization, resizing to 128x128, and ImageNet standardization.
        3. **Deep Learning Core**: Transfer-learning with fine-tuned MobileNetV2 and EfficientNetB0, benchmarked against a 4-stage Custom CNN baseline.
        4. **Explainability**: Gradient-weighted Class Activation Mapping (Grad-CAM) targeting the final convolutional layer.
        5. **Persistence**: SQLite database tracking all historical scans with CSV export.
        6. **Simulated Hardware Gateway**: Software thread mimicking ESP32-CAM and Raspberry Pi edge routing without requiring physical hardware.
        """
    )
