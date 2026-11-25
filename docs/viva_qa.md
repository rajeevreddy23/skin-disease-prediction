# Viva Voce Examination: 30 Comprehensive Questions & Answers
## Project: Skin Disease Prediction Using Machine Learning with Live Image Capture and Web Dashboard

---

### Category 1: Problem Definition & Clinical Context

#### Q1. What is the motivation behind developing this computer-aided skin disease prediction system?
**Answer:**  
Skin cancer, particularly malignant melanoma, is one of the most fatal forms of dermatological malignancies globally. However, if diagnosed early in stage I or in situ, the five-year survival rate exceeds 99%. Unfortunately, dermatological expertise is scarce, expensive, and geographically concentrated in major urban centers, causing diagnostic delays in rural and underserved areas. This project bridges that gap by providing a software-only, deep learning-powered clinical decision support system that can ingest images via a laptop webcam or photo upload, classify them across seven diagnostic categories, provide explainable Grad-CAM heatmaps, and advise the user on seeking timely professional consultation.

#### Q2. Why did you choose the HAM10000 dataset, and what are its diagnostic categories?
**Answer:**  
The HAM10000 ("Human Against Machine with 10,000 training images") dataset released by the International Skin Imaging Collaboration (ISIC) is the global benchmark for dermatoscopic research. It contains 10,015 high-resolution dermatoscopic images curated by the Medical University of Vienna and the Cliff Rosendahl Clinic in Queensland. The dataset spans seven ground-truth histopathologically verified diagnostic categories:
1. `nv`: Melanocytic nevi (benign common moles)
2. `mel`: Melanoma (malignant skin cancer)
3. `bkl`: Benign keratosis-like lesions (seborrheic keratoses, solar lentigines)
4. `bcc`: Basal cell carcinoma (locally invasive cancer)
5. `akiec`: Actinic keratoses and intraepithelial carcinoma (pre-cancerous lesions)
6. `vasc`: Vascular lesions (angiomas, pyogenic granulomas)
7. `df`: Dermatofibroma (benign fibrous nodules)

#### Q3. What is the fundamental difference between dermatoscopic and clinical photography?
**Answer:**  
Standard clinical photography captures the surface of the skin under ambient light with surface reflections that obscure deeper epidermal and dermal architecture. Dermatoscopy (epiluminescence microscopy) uses polarized or immersion fluid optics that eliminate surface stratum corneum reflection. This exposes deep morphological structures such as the pigment network, blue-white veil, vascular arborization, and peripheral globules that are essential for accurate cancer detection.

---

### Category 2: Image Preprocessing & Feature Engineering

#### Q4. What is the DullRazor algorithm and why is it essential for dermatological images?
**Answer:**  
Dermatological photographs frequently contain hair strands that overlay the lesion. If fed raw into a deep neural network, the convolutional kernels may mistakenly associate linear dark hair artifacts with atypical network structures or spiculated lesion borders. The DullRazor algorithm eliminates hair artifacts via a 4-step morphological process:
1. Converts the RGB image to grayscale $I_{\text{gray}}$.
2. Applies a Morphological Black Hat (bottom-hat) transformation using an $n \times n$ rectangular or cross structuring element $B$:  
   $$I_{\text{blackhat}} = (I_{\text{gray}} \bullet B) - I_{\text{gray}}$$  
   where $\bullet$ represents morphological closing. This isolates narrow, dark linear structures.
3. Thresholds $I_{\text{blackhat}}$ into a binary hair mask $M_{\text{hair}}$.
4. Inpaints the lesion pixels under $M_{\text{hair}}$ using Telea's fast marching method or Navier-Stokes PDE inpainting, restoring the underlying pigmentation smoothly.

#### Q5. How does Contrast Limited Adaptive Histogram Equalization (CLAHE) assist lesion diagnosis?
**Answer:**  
Standard histogram equalization increases global contrast, which often overamplifies background noise in homogeneous skin areas. CLAHE operates on localized $8 \times 8$ contextual tiles and clips the histogram slope at a predefined contrast limit (typically 2.0). The clipped pixels are uniformly redistributed across the histogram bins before computing the Cumulative Distribution Function (CDF). We apply CLAHE exclusively to the luminance channel (L-channel) in the LAB color space, enhancing subtle vascular and pigment textures without altering clinical chromaticity (A and B channels).

#### Q6. What image normalization technique did you apply before feeding tensors to the model?
**Answer:**  
Images are resized to $128 \times 128$ pixels and converted to 32-bit floating-point tensors with pixel values scaled to $[0, 1]$. We then apply channel-wise standardization using ImageNet population statistics:
- Mean $\mu = [0.485, 0.456, 0.406]$ for RGB channels
- Standard Deviation $\sigma = [0.229, 0.224, 0.225]$  
$$X_{\text{norm}}^{(c)} = \frac{X^{(c)} - \mu_c}{\sigma_c}$$  
This aligns the input distribution with the manifold on which the pre-trained transfer learning weights were originally optimized.

---

### Category 3: Machine Learning & Deep Learning Architectures

#### Q7. Which three model architectures did you implement and compare?
**Answer:**  
1. **Custom CNN (Baseline)**: A 4-stage convolutional neural network with batch normalization, ReLU non-linearities, max pooling, adaptive global average pooling, and dropout ($p=0.4$). It establishes the baseline achievable purely on the domain dataset without pre-training.
2. **MobileNetV2 (Transfer Learning)**: A lightweight inverted residual bottleneck architecture optimized for edge devices and laptops, leveraging depthwise separable convolutions and linear bottlenecks.
3. **EfficientNetB0 (Transfer Learning)**: A state-of-the-art architecture designed through compound scaling, balancing network depth, width, and input resolution using a compound coefficient $\phi$.

#### Q8. Explain Depthwise Separable Convolutions as used in MobileNetV2.
**Answer:**  
Standard convolution applies a 3D kernel $K \times K \times C_{\text{in}}$ across all channels simultaneously, requiring computational cost:
$$\text{Cost}_{\text{standard}} = H \times W \times C_{\text{in}} \times C_{\text{out}} \times K^2$$  
Depthwise Separable Convolution factors this into two independent steps:
1. **Depthwise Convolution**: Applies a single 2D spatial filter $K \times K$ per input channel independently (cost: $H \times W \times C_{\text{in}} \times K^2$).
2. **Pointwise Convolution**: Applies $1 \times 1 \times C_{\text{in}}$ convolutions across all channels to compute linear combinations (cost: $H \times W \times C_{\text{in}} \times C_{\text{out}}$).  
The total computation is reduced by approximately:
$$\frac{\text{Cost}_{\text{depthwise-separable}}}{\text{Cost}_{\text{standard}}} \approx \frac{1}{C_{\text{out}}} + \frac{1}{K^2}$$  
For a $3 \times 3$ kernel, this delivers an **8 to 9-fold reduction** in floating-point operations (FLOPs) with minimal accuracy degradation.

#### Q9. What are Inverted Residuals and Linear Bottlenecks in MobileNetV2?
**Answer:**  
Traditional residual networks (like ResNet) compress features through a bottleneck and expand them back. In contrast, **MobileNetV2** uses:
1. **Inverted Residuals**: The input channel dimension (low dimension) is first expanded (typically $6\times$) to a high-dimensional feature space using $1 \times 1$ conv, then filtered with a $3 \times 3$ depthwise conv, and then projected back to a low-dimensional manifold. Skip connections connect the low-dimensional bottlenecks directly.
2. **Linear Bottlenecks**: Non-linear activation functions (like ReLU) in low-dimensional spaces inadvertently destroy manifold information by zeroing out negative values. Removing non-linearities from the final projection layer preserves subtle diagnostic feature representations.

#### Q10. What is Compound Scaling in EfficientNetB0?
**Answer:**  
Previous CNNs scaled only one dimension: depth (e.g., ResNet-50 to ResNet-152), width (e.g., WideResNet), or image resolution. EfficientNet demonstrated that these dimensions are interdependent. Compound scaling uses a compound coefficient $\phi$ to uniformly scale:
- Depth: $d = \alpha^\phi$
- Width: $w = \beta^\phi$
- Resolution: $r = \gamma^\phi$  
subject to $\alpha \cdot \beta^2 \cdot \gamma^2 \approx 2$ (so total FLOPs scale as $2^\phi$). EfficientNetB0 serves as the foundational baseline discovered through neural architecture search (NAS).

---

### Category 4: Training Methodology & Imbalance Mitigation

#### Q11. How did you handle the severe class imbalance inherent in skin lesion datasets?
**Answer:**  
In natural clinical practice, common benign nevi (`nv`) constitute over 67% of presented lesions, while rare malignancies like dermatofibroma (`df`) and vascular lesions (`vasc`) account for less than 1.5% each. If unaddressed, the network suffers from majority-class bias. We tackled this through:
1. **Cost-Sensitive Learning (Inverse Frequency Class Weights)**: We weighted the categorical Cross-Entropy loss by the inverse class frequencies:
   $$w_c = \frac{N_{\text{total}}}{C \times N_c}$$  
   where $N_{\text{total}}$ is the total number of training samples, $C=7$ classes, and $N_c$ is the sample count for class $c$. This penalizes misclassifications on rare malignancies much more severely.
2. **Data Augmentation**: Extensive stochastic affine rotations ($\pm 25^\circ$), horizontal/vertical flips, and HSV color jittering effectively synthesized underrepresented feature orientations.

#### Q12. Why did you use Stratified Partitioning for the dataset split?
**Answer:**  
A naive random train/test split could accidentally place almost all rare cases (such as vascular lesions or dermatofibroma) entirely into the training set, leaving the test set with zero representation, or vice versa. **Stratified 70/15/15 partitioning** guarantees that every split maintains the exact identical class ratio across all seven classes, preventing distribution drift and ensuring statistically robust validation.

#### Q13. Explain the learning rate scheduling and early stopping mechanisms applied.
**Answer:**  
- **ReduceLROnPlateau**: We monitored the validation loss. If the validation loss stagnates for 2 consecutive epochs (`patience=2`), the learning rate is halved (`factor=0.5`). This allows coarse optimization during initial epochs followed by fine convergence into sharp loss minima.
- **ModelCheckpoint**: The system serializes the model weights only when validation loss achieves a new minimum, preventing the saving of overfitted weights.
- **AdamW Optimizer**: Incorporates decoupled weight decay ($1 \times 10^{-4}$), providing superior regularization over classical L2-regularized SGD.

---

### Category 5: Explainable AI (Grad-CAM)

#### Q14. What is Grad-CAM and why is Explainable AI (XAI) legally and clinically critical in healthcare?
**Answer:**  
Grad-CAM (Gradient-weighted Class Activation Mapping) is an explainability technique that produces visual explanations for decisions made by convolutional neural networks. In healthcare, deep learning models cannot be deployed as opaque "black boxes." Under regulatory frameworks (such as the EU AI Act and FDA SaMD guidelines), clinicians must understand *why* a model flagged a lesion as malignant. If the model focuses on background hair, surgical marker ink, or vignetting rather than the lesion's asymmetric borders, the clinician can immediately detect the spurious correlation and disregard the recommendation.

#### Q15. Walk through the mathematical derivation of Grad-CAM.
**Answer:**  
1. Let $Y^c$ be the raw unnormalized class logit for diagnosis $c$ prior to the softmax layer.
2. Let $A^k$ represent the $k$-th feature activation map of the final convolutional layer, having dimensions $H \times W$.
3. We compute the partial derivative of $Y^c$ with respect to each spatial location $(i, j)$ in $A^k$: $\frac{\partial Y^c}{\partial A_{i,j}^k}$.
4. We apply Global Average Pooling (GAP) across spatial coordinates to obtain the neuron importance weight $\alpha_k^c$:
   $$\alpha_k^c = \frac{1}{Z} \sum_{i=1}^H \sum_{j=1}^W \frac{\partial Y^c}{\partial A_{i,j}^k}$$  
   where $Z = H \times W$.
5. We calculate the weighted linear combination of forward activation maps and apply the Rectified Linear Unit (ReLU) to filter out features that decrease the target class score:
   $$L_{\text{Grad-CAM}}^c = \text{ReLU}\left( \sum_k \alpha_k^c A^k \right)$$
6. The resulting 2D matrix is normalized to $[0, 1]$, interpolated to the input image size, and overlaid using a JET colormap.

#### Q16. Why do we target the final convolutional layer for Grad-CAM rather than early layers or dense layers?
**Answer:**  
Early convolutional layers capture low-level primitive features (edges, corners, simple color contrasts) that lack high-level class semantics. Dense (fully connected) layers discard spatial dimensions entirely through flattening. The **final convolutional layer** provides the optimal balance: it possesses high-level semantic class-discriminative information while still preserving coarse spatial coordinates ($H \times W$).

---

### Category 6: Performance Metrics & Evaluation

#### Q17. Why is raw Accuracy an inadequate metric for evaluating dermatological models?
**Answer:**  
Due to class imbalance, if a model predicts Melanocytic Nevus (`nv`) for 100% of all test cases, it could achieve a seemingly high accuracy of 67% while completely failing to detect every single fatal Melanoma (`mel`) and Basal Cell Carcinoma (`bcc`). Therefore, **Sensitivity (Recall)**, **Precision**, **Macro-F1 score**, and **Area Under the ROC Curve (AUC)** are the clinically sound metrics.

#### Q18. Distinguish between Sensitivity (Recall) and Specificity in cancer screening.
**Answer:**  
- **Sensitivity (Recall)**:  
  $$\text{Sensitivity} = \frac{\text{True Positives}}{\text{True Positives} + \text{False Negatives}}$$  
  Measures the ability to correctly identify patients who genuinely have skin cancer. High sensitivity minimizes **False Negatives** (missing a life-threatening melanoma).
- **Specificity**:  
  $$\text{Specificity} = \frac{\text{True Negatives}}{\text{True Negatives} + \text{False Positives}}$$  
  Measures the ability to correctly identify patients with benign lesions. High specificity minimizes **False Positives** (unnecessary surgical biopsies and patient anxiety).

#### Q19. What is an ROC curve, and how do you calculate multi-class AUC?
**Answer:**  
A Receiver Operating Characteristic (ROC) curve plots the True Positive Rate (Sensitivity) on the y-axis against the False Positive Rate ($1 - \text{Specificity}$) on the x-axis across all diagnostic classification thresholds from $0.0$ to $1.0$. In our 7-class multi-class setup, we use the **One-vs-Rest (OvR)** formulation: we binarize the ground truth and compute 7 independent ROC curves, calculating the Area Under the Curve ($\text{AUC}_c$) for each class. An AUC of $1.0$ represents a flawless classifier, while $0.5$ denotes random chance.

#### Q20. What is a Confusion Matrix, and what do off-diagonal elements signify?
**Answer:**  
A confusion matrix is an $N \times N$ grid (where $N=7$) where row $i$ represents the actual ground-truth medical diagnosis and column $j$ represents the model's predicted classification.  
- Diagonal elements ($i = j$) represent correctly classified cases (True Positives).  
- Off-diagonal elements ($i \neq j$) represent diagnostic errors: elements above the diagonal represent false predictions into later categories, while elements below represent false predictions into earlier categories. For example, a non-zero count at `(row: mel, col: nv)` indicates a dangerous false negative where a malignant melanoma was misclassified as a benign mole.

---

### Category 7: Software Architecture & Simulated Edge Mode

#### Q21. Explain the multi-tier software architecture of this project.
**Answer:**  
The software architecture runs entirely on a single laptop and comprises four decoupled layers:
1. **Input Acquisition Layer**: Employs Streamlit camera input / OpenCV for live webcam frames, high-resolution upload, and a sample gallery.
2. **Preprocessing Layer**: Implements morphological DullRazor hair removal, CLAHE contrast enhancement, tensor resizing, and ImageNet standardization.
3. **Inference & Explainability Engine**: Evaluates PyTorch CNN architectures, computes Top-3 softmax probability distributions, and executes Grad-CAM backpropagation.
4. **Presentation & Persistence Layer**: Renders an interactive Streamlit dashboard, persists audit logs into an ACID-compliant SQLite database, and supports instant CSV exports.

#### Q22. How does the simulated "Device Mode" mimic the ESP32-CAM and Raspberry Pi hardware without physical devices?
**Answer:**  
The simulated device mode (`src/device_simulator.py`) encapsulates the entire IoT edge pipeline within an asynchronous background Python daemon thread:
1. **ESP32-CAM Layer (Sensor)**: Simulates camera capture at periodic intervals (3.5s), JPEG compression, and telemetry packet serialization.
2. **Raspberry Pi Gateway (Broker)**: Receives the packet over a thread-safe `queue.Queue`, performs edge validation, and monitors throughput.
3. **Laptop Deep Learning Core**: Consumes frames from the queue, performs inference, logs results to SQLite, and updates the real-time telemetry dashboard (baud rate, Wi-Fi RSSI, transmitted bytes, and queue depth).

#### Q23. Why was a software-only approach chosen over microcontrollers for this capstone?
**Answer:**  
1. **Elimination of Hardware Bottlenecks**: Microcontrollers like ESP32-CAM have severe hardware constraints (OV2640 lens distortion, noisy sensors, 520 KB SRAM), which degrade dermatological image quality.
2. **Standardization & Portability**: Evaluators, examiners, and remote users can clone the repository, install requirements, and execute the entire pipeline on any laptop without purchasing external electronics or wiring breadboards.
3. **Academic Focus**: Enables rigorous focus on state-of-the-art computer vision, deep transfer learning, and clinical explainability rather than low-level embedded serial firmware.

#### Q24. How is persistent storage managed in the project?
**Answer:**  
We utilize an embedded **SQLite3** relational database (`data/history.db`). Each diagnosis records the timestamp, source modality, prediction class, disease name, confidence score, risk classification level, full Top-3 JSON string, image identifier, and inference latency. The database supports atomic transactions, schema initialization, real-time querying for Streamlit dashboards, and on-demand CSV serialization.

---

### Category 8: Clinical Ethics, Safety & Future Scope

#### Q25. Why is the educational medical disclaimer mandatory in this application?
**Answer:**  
Software medical applications are strictly regulated under international standards (such as IEC 62304 and HIPAA). While deep learning algorithms can achieve high academic test accuracy, they are vulnerable to distribution shifts, atypical lesion presentations, rare skin tones, and lens artifacts. Misdiagnosis of an early melanoma as benign could cause a patient to forgo life-saving biopsy. The disclaimer prominently warns users that the tool is strictly for educational research and does not constitute a certified medical diagnosis.

#### Q26. What are the ABCDE clinical criteria used by dermatologists to identify melanoma?
**Answer:**  
The ABCDE criteria are the foundational dermatological rules for melanoma screening:
- **A - Asymmetry**: One half of the spot does not match the other.
- **B - Border**: The edges are irregular, ragged, notched, or blurred.
- **C - Color**: The color is not uniform; exhibits shades of tan, brown, black, with patches of pink, red, white, or blue.
- **D - Diameter**: Greater than 6 millimeters (approx. pencil eraser size), though early melanomas can be smaller.
- **E - Evolving**: Any changing shape, size, elevation, or new symptom like bleeding, itching, or crusting.

#### Q27. How does skin tone (Fitzpatrick skin types I–VI) impact model bias?
**Answer:**  
The HAM10000 dataset predominantly consists of dermatoscopic images from Caucasian populations in Austria and Australia (Fitzpatrick skin types I to III). Darker skin phototypes (Fitzpatrick IV to VI) have higher baseline epidermal melanin, which can reduce contrast between the lesion and surrounding skin. Training models solely on light skin tones can lead to biased diagnostic performance. An essential future direction is incorporating balanced datasets like the ISIC diversity cohorts and African dermatology registries.

#### Q28. What are the main limitations of the current implementation?
**Answer:**  
1. **2D Surface Imagery**: Cannot assess the physical 3D elevation, induration, or tactile firmness of the lesion.
2. **Lack of Patient Metadata Fusion**: Clinical dermatologists integrate patient age, personal/family history of skin cancer, and lesion evolution over time; our model evaluates isolated static images.
3. **Synthetic / Downscaled Input**: For rapid laptop execution, inputs are processed at $128 \times 128$ resolution; clinical production systems benefit from $224 \times 224$ or $512 \times 512$ native resolutions.

#### Q29. How would you transition this software architecture to real physical hardware in the future?
**Answer:**  
1. **Edge Node**: Mount an ESP32-CAM with an optical dermatoscope polarized lens attachment onto a 3D-printed handheld dermatoscope casing.
2. **Communication**: Transmit compressed frames via HTTP POST or MQTT over local Wi-Fi to a Raspberry Pi 4/5.
3. **Edge Optimization**: Convert the trained PyTorch MobileNetV2 model into **TensorFlow Lite (TFLite)** or **ONNX Runtime** format with 8-bit post-training quantization (`INT8`), allowing full inference to execute directly on the Raspberry Pi edge device in under 150ms without laptop dependency.

#### Q30. Summarize your major contributions and findings in this project.
**Answer:**  
1. Successfully designed and built an end-to-end, software-only skin lesion diagnostic system running on a standard laptop.
2. Implemented clinical DullRazor hair removal and CLAHE contrast enhancement pipelines.
3. Implemented and benchmarked three distinct CNN architectures (Custom CNN, MobileNetV2, EfficientNetB0), demonstrating that transfer learning substantially improves diagnostic sensitivity on rare and critical lesions.
4. Integrated explainable AI through Grad-CAM, enabling clinicians to visually verify neural receptive fields.
5. Implemented a fully functional Streamlit dashboard with webcam capture, SQLite prediction history, and an IoT edge device simulator.
