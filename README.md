# EcoSort: AI-Powered Smart Waste Bin

EcoSort is an Edge AI computer vision project designed to automate waste segregation. By simulating a smart scanning tray using a standard webcam, EcoSort categorizes discarded items into **Recycling** or **Landfill Trash** in real-time, simulating the triggering of physical servo motors to open the corresponding waste chutes.

## Hardware (Simulated)
- Any computer with a webcam (Mac, Windows, Linux)
- Alternatively, a Raspberry Pi 4 with a Pi Camera Module.

## Software Stack
- **Python 3**
- **TensorFlow / Keras** (MobileNetV2 Transfer Learning)
- **OpenCV** (Computer Vision & Live Camera feed)
- **Dataset:** Stanford's [TrashNet](https://github.com/garythung/trashnet)

---

## Setup Instructions

### 1. Create a Virtual Environment (Optional but recommended)
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Download the Dataset
The AI model needs to be trained on the TrashNet dataset. Run the following command to download and extract it into a `dataset` folder:

**Mac/Linux:**
```bash
curl -L -o trashnet.zip "https://github.com/garythung/trashnet/raw/master/data/dataset-resized.zip" && unzip -q trashnet.zip && rm -rf dataset && mv dataset-resized dataset && rm trashnet.zip
```

### 4. Train the Model
Once the dataset is downloaded, you can train the AI model. This uses a pre-trained MobileNetV2 architecture and fine-tunes it on the waste images.
```bash
python train_model.py
```
*Note: This will take a few minutes. Once complete, it will save the model as `ecosort_model.keras`.*

### 5. Run the Live Smart Bin Simulator
Start the webcam script to simulate the physical smart bin!
```bash
python live_smart_bin.py
```
* **How to use:** Hold a piece of trash, paper, plastic bottle, or cardboard inside the white "Scanning Tray" square on the screen. 
* Once the AI is >90% confident, the system will lock and display an actuation message, simulating a servo motor opening the correct chute!

*(Tip: If using an external camera or iPhone Continuity Camera on macOS, you can pass `--camera 1`)*
