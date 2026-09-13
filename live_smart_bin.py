import cv2
import numpy as np
import os
import argparse
import time
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel

# =====================================================================
#  EcoSort Smart Bin - Pure OpenAI Zero-Shot CLIP Vision Controller
# =====================================================================

def connect_arduino(port=None, baud=9600):
    """Auto-detect or connect to Arduino over USB Serial."""
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("\n[WARNING] 'pyserial' not installed. Running in SIMULATION MODE.\n")
        return None

    if port and port.lower() != 'auto':
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2.0)
            print(f"[HARDWARE] Connected to Arduino on {port} @ {baud} baud.")
            return ser
        except Exception as e:
            print(f"[WARNING] Could not open {port}: {e}. Running in SIMULATION MODE.\n")
            return None

    ports = list(serial.tools.list_ports.comports())
    candidate_port = None
    for p in ports:
        desc = (p.description or '').lower()
        hwid = (p.hwid or '').lower()
        pname = (p.device or '').lower()
        if any(k in desc or k in hwid or k in pname for k in ['arduino', 'ch340', 'usb serial', 'usbmodem', 'usbserial', 'ttyacm', 'ttyusb']):
            candidate_port = p.device
            break

    if candidate_port:
        try:
            ser = serial.Serial(candidate_port, baud, timeout=1)
            time.sleep(2.0)
            print(f"[HARDWARE] Auto-detected Arduino on {candidate_port} @ {baud} baud.")
            ser.reset_input_buffer()
            return ser
        except Exception as e:
            print(f"[WARNING] Found {candidate_port} but failed to open: {e}. Running in SIMULATION MODE.\n")
            return None

    print("[HARDWARE] No Arduino detected. Running in SIMULATION MODE.")
    return None

def send_servo_command(arduino, cmd_char, label):
    """Sends a single-byte command to Arduino over Serial."""
    if arduino and arduino.is_open:
        try:
            arduino.write(cmd_char.encode('utf-8'))
            arduino.flush()
            print(f"[HARDWARE TRIGGER] Sent '{cmd_char}' to Arduino -> {label}")
        except Exception as e:
            print(f"[ERROR] Failed to send serial command: {e}")
    else:
        print(f"[SIMULATION TRIGGER] Command '{cmd_char}' -> {label} (Arduino simulated)")

class ClipClassifier:
    """High-performance Zero-Shot CLIP classifier with pre-computed text embeddings."""
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        # Select best available device (Apple Silicon MPS -> CUDA -> CPU)
        if torch.backends.mps.is_available():
            self.device = "mps"
            dev_desc = "Apple Silicon GPU (Metal MPS)"
        elif torch.cuda.is_available():
            self.device = "cuda"
            dev_desc = "NVIDIA CUDA GPU"
        else:
            self.device = "cpu"
            dev_desc = "CPU (Raspberry Pi / Desktop)"

        print(f"[CLIP] Loading model '{model_name}' on {dev_desc}...")
        try:
            self.model = CLIPModel.from_pretrained(model_name, local_files_only=True).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name, local_files_only=True)
        except Exception:
            print(f"[CLIP] Cache miss or update needed. Downloading '{model_name}' from Hugging Face Hub...")
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model.eval()

        # The 4 Waste Categories and their detailed prompt descriptions
        self.categories = ['paper', 'plastic_metal', 'organic', 'general']
        self.prompts = [
            "a piece of paper, cardboard box, brown corrugated cardboard, notebook, or paper packaging",
            "a plastic bottle, plastic container, aluminum soda can, or metal can",
            "organic food waste, fruit, vegetable, food scraps, or banana peel",
            "dirty non-recyclable garbage, greasy snack wrapper, or general landfill trash"
        ]

        # PRE-COMPUTE Text Embeddings (avoids re-encoding text on every frame!)
        print("[CLIP] Pre-computing category text embeddings for real-time inference...")
        text_inputs = self.processor(text=self.prompts, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            text_outputs = self.model.get_text_features(**text_inputs)
            text_features = self._extract_tensor(text_outputs)
            self.text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        print("[CLIP] Model ready!")

    @staticmethod
    def _extract_tensor(output):
        """Extracts the raw PyTorch Tensor from transformers model output."""
        if hasattr(output, "pooler_output") and output.pooler_output is not None:
            return output.pooler_output
        if hasattr(output, "text_embeds") and output.text_embeds is not None:
            return output.text_embeds
        if hasattr(output, "image_embeds") and output.image_embeds is not None:
            return output.image_embeds
        if isinstance(output, torch.Tensor):
            return output
        return output[0]

    def predict(self, bgr_crop):
        """Classifies a cropped BGR image into one of the 4 waste categories."""
        rgb_img = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        image_inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_outputs = self.model.get_image_features(**image_inputs)
            image_features = self._extract_tensor(image_outputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Cosine similarity between image and pre-computed text vectors
            similarity = (image_features @ self.text_features.T).squeeze(0)
            probs = (similarity * 100.0).softmax(dim=-1).cpu().numpy()

        top_idx = int(np.argmax(probs))
        confidence = float(probs[top_idx])
        category = self.categories[top_idx]
        return category, confidence

def main():
    parser = argparse.ArgumentParser(description='EcoSort Smart Bin - Zero-Shot CLIP 4-Way Waste Segregator')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0 for built-in, 1 for external/USB)')
    parser.add_argument('--port', type=str, default='auto', help="Arduino Serial Port (e.g. 'auto', '/dev/cu.usbmodem...', 'COM3')")
    parser.add_argument('--baud', type=int, default=9600, help='Arduino Serial Baud Rate (default: 9600)')
    parser.add_argument('--no-arduino', action='store_true', help='Run simulation mode without connecting Arduino')
    args = parser.parse_args()

    # Initialize CLIP
    classifier = ClipClassifier()

    # Connect Arduino
    arduino = None
    if not args.no_arduino:
        arduino = connect_arduino(args.port, args.baud)
    else:
        print("[HARDWARE] --no-arduino set. Running in SIMULATION MODE.")

    # Initialize Camera with Auto-Fallback
    print(f"Opening Camera (Index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened() and args.camera != 0:
        print(f"[INFO] Camera at index {args.camera} not found. Falling back to built-in camera (Index 0)...")
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[ERROR] Could not open camera. Check permissions or connection.")
        if arduino: arduino.close()
        return

    print("\n" + "="*58)
    print(" ECOSORT SMART BIN: ZERO-SHOT CLIP 4-WAY SORTING ONLINE")
    print("   [1] PAPER            -> Command 'P' (Servo 1 Left)")
    print("   [2] PLASTIC / METAL  -> Command 'M' (Servo 1 Right)")
    print("   [3] ORGANIC          -> Command 'O' (Servo 2 Forward)")
    print("   [4] GENERAL TRASH    -> Command 'G' (Servo 2 Backward)")
    print("   Press 'q' to quit.")
    print("="*58 + "\n")

    locked_text = None
    locked_color = (0, 0, 0)
    empty_frames = 0
    cooldown_until = 0.0
    prediction_history = []
    REQUIRED_STABLE_FRAMES = 4

    # Background Subtraction Variables
    background_frame = None
    calibration_frames = 30
    frames_read = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h_f, w_f, _ = frame.shape
        now = time.time()
        in_cooldown = (now < cooldown_until)

        # Scanning Box in center
        box_size = min(400, min(h_f, w_f) - 40)
        x1 = int(w_f/2 - box_size/2)
        y1 = int(h_f/2 - box_size/2)
        x2 = x1 + box_size
        y2 = y1 + box_size

        tray_color = (160, 160, 160) if in_cooldown else (255, 255, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), tray_color, 2)
        cv2.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tray_color, 2)

        roi = frame[y1:y2, x1:x2]
        if roi.shape[0] > 0 and roi.shape[1] > 0:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)

            # Phase 1: Calibrate Empty Tray
            if frames_read < calibration_frames:
                if background_frame is None:
                    background_frame = gray_roi.astype("float")
                else:
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.1)

                frames_read += 1
                cv2.rectangle(frame, (0, h_f - 60), (w_f, h_f), (255, 255, 255), -1)
                cv2.putText(frame, f"Calibrating Empty Tray... {frames_read}/{calibration_frames}", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("EcoSort Smart Bin - Zero-Shot CLIP", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # Phase 2: Detect Object Placement
            object_detected = False
            if not in_cooldown:
                frame_delta = cv2.absdiff(background_frame.astype("uint8"), gray_roi)
                thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for c in contours:
                    if cv2.contourArea(c) > 5000:
                        object_detected = True
                        x, y, w, h = cv2.boundingRect(c)
                        cv2.rectangle(frame, (x1+x, y1+y), (x1+x+w, y1+y+h), (0, 255, 0), 2)
                        break

            if object_detected and not in_cooldown:
                empty_frames = 0

                # Crop tightly to object
                pad = 20
                crop_y1 = max(0, y - pad)
                crop_y2 = min(roi.shape[0], y + h + pad)
                crop_x1 = max(0, x - pad)
                crop_x2 = min(roi.shape[1], x + w + pad)
                obj_crop = roi[crop_y1:crop_y2, crop_x1:crop_x2]

                eval_img = obj_crop if (obj_crop.shape[0] > 15 and obj_crop.shape[1] > 15) else roi

                # PiP Thumbnail
                try:
                    pip_preview = cv2.resize(eval_img, (90, 90))
                    cv2.rectangle(frame, (w_f - 105, 50), (w_f - 11, 144), (0, 255, 0), 2)
                    frame[52:142, w_f - 103:w_f - 13] = pip_preview
                    cv2.putText(frame, "AI CROP", (w_f - 95, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                except Exception:
                    pass

                # Run CLIP Zero-Shot Inference
                predicted_class, conf = classifier.predict(eval_img)

                if conf > 0.65 and locked_text is None:
                    prediction_history.append((predicted_class, conf))
                    if len(prediction_history) > REQUIRED_STABLE_FRAMES:
                        prediction_history.pop(0)

                    recent = [p[0] for p in prediction_history]
                    if len(recent) == REQUIRED_STABLE_FRAMES and len(set(recent)) == 1:
                        final_cat = recent[0]
                        avg_conf = np.mean([p[1] for p in prediction_history])

                        if final_cat == 'paper':
                            action = "PAPER -> [1/4] PAPER (Servo 1 Left)"
                            locked_color = (0, 180, 0)
                            send_servo_command(arduino, 'P', 'PAPER')
                        elif final_cat == 'plastic_metal':
                            action = "PLASTIC / METAL -> [2/4] PLASTIC/METAL (Servo 1 Right)"
                            locked_color = (230, 140, 0)
                            send_servo_command(arduino, 'M', 'PLASTIC/METAL')
                        elif final_cat == 'organic':
                            action = "ORGANIC -> [3/4] ORGANIC (Servo 2 Forward)"
                            locked_color = (0, 215, 255)
                            send_servo_command(arduino, 'O', 'ORGANIC')
                        else:
                            action = "GENERAL TRASH -> [4/4] GENERAL (Servo 2 Backward)"
                            locked_color = (0, 0, 200)
                            send_servo_command(arduino, 'G', 'GENERAL TRASH')

                        locked_text = f"[{avg_conf*100:.0f}%] {action}"
                        prediction_history = []
                        cooldown_until = now + 2.5
                else:
                    if conf <= 0.65:
                        prediction_history = []
            else:
                if not in_cooldown:
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.05)
                    empty_frames += 1
                    if empty_frames > 10:
                        locked_text = None
                        prediction_history = []

            # --- Top Status Bar ---
            cv2.rectangle(frame, (0, 0), (w_f, 40), (40, 40, 40), -1)
            if arduino and arduino.is_open:
                hw_status = f"Arduino: CONNECTED ({arduino.port}) | OpenAI Zero-Shot CLIP"
                hw_color = (0, 255, 120)
            else:
                hw_status = "Arduino: SIMULATION | OpenAI Zero-Shot CLIP"
                hw_color = (0, 180, 255)
            cv2.putText(frame, hw_status, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.52, hw_color, 2)

            # --- Bottom Result Banner ---
            cv2.rectangle(frame, (0, h_f - 60), (w_f, h_f), (255, 255, 255), -1)
            if in_cooldown:
                cv2.putText(frame, "Sorting in progress (Servos Active)...", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (180, 80, 0), 2)
            elif locked_text:
                cv2.putText(frame, locked_text, (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.75, locked_color, 2)
            else:
                cv2.putText(frame, "Tray is empty. Place waste on tray...", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 80, 80), 2)

        cv2.imshow("EcoSort Smart Bin - Zero-Shot CLIP", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if arduino and arduino.is_open:
        try:
            arduino.write(b'0')
            time.sleep(0.2)
            arduino.close()
            print("[HARDWARE] Servos reset to Neutral. Serial closed.")
        except Exception:
            pass

if __name__ == '__main__':
    main()
