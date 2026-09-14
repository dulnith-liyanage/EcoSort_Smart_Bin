import cv2
import numpy as np
import os
import sys
import json
import argparse
import time
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel

# =====================================================================
#  EcoSort Smart Bin - Zero-Shot CLIP 4-Way Waste Sorting System
# =====================================================================

# ANSI Colors for Terminal Output
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_BLUE   = "\033[94m"
C_YELLOW = "\033[93m"
C_RED    = "\033[91m"
C_CYAN   = "\033[96m"
C_MAG    = "\033[95m"

def log_info(msg):
    print(f"{C_CYAN}[INFO]{C_RESET} {msg}")

def log_success(msg):
    print(f"{C_GREEN}[SUCCESS]{C_RESET} {msg}")

def log_warning(msg):
    print(f"{C_YELLOW}[WARNING]{C_RESET} {msg}")

def log_error(msg):
    print(f"{C_RED}[ERROR]{C_RESET} {msg}")

def log_sort_event(category, confidence, cmd, desc):
    print(f"\n{C_BOLD}{C_GREEN}>>> [SORT EVENT] {category.upper()} ({confidence*100:.1f}% confidence) -> Triggering '{cmd}' ({desc}){C_RESET}\n")

# Category Definitions, Hardware Commands, and UI Colors (BGR)
CATEGORY_CONFIG = {
    'paper': {
        'label': 'Paper',
        'cmd': 'P',
        'servo_desc': 'Servo 1 Left (45 deg)',
        'color': (80, 220, 80),      # Soft Green
        'default_prompt': "a piece of paper, cardboard box, brown corrugated cardboard, notebook, or paper packaging"
    },
    'plastic_metal': {
        'label': 'Plastic/Metal',
        'cmd': 'M',
        'servo_desc': 'Servo 1 Right (135 deg)',
        'color': (255, 170, 50),     # Azure / Blue
        'default_prompt': "a plastic bottle, plastic container, aluminum soda can, or metal can"
    },
    'organic': {
        'label': 'Organic',
        'cmd': 'O',
        'servo_desc': 'Servo 2 Forward (45 deg)',
        'color': (0, 215, 255),      # Gold / Amber
        'default_prompt': "organic food waste, fruit, vegetable, food scraps, or banana peel"
    },
    'general': {
        'label': 'General Trash',
        'cmd': 'G',
        'servo_desc': 'Servo 2 Backward (135 deg)',
        'color': (80, 80, 235),      # Crimson / Red
        'default_prompt': "dirty non-recyclable garbage, greasy snack wrapper, or general landfill trash"
    }
}

def connect_arduino(port=None, baud=9600):
    """Auto-detect or connect to Arduino over USB Serial."""
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        log_warning("'pyserial' not installed. Running in SIMULATION MODE.")
        return None

    if port and port.lower() != 'auto':
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2.0)
            log_success(f"Connected to Arduino on {port} @ {baud} baud.")
            return ser
        except Exception as e:
            log_warning(f"Could not open {port}: {e}. Running in SIMULATION MODE.")
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
            log_success(f"Auto-detected Arduino on {candidate_port} @ {baud} baud.")
            ser.reset_input_buffer()
            return ser
        except Exception as e:
            log_warning(f"Found {candidate_port} but failed to open: {e}. Running in SIMULATION MODE.")
            return None

    log_warning("No Arduino detected. Running in SIMULATION MODE.")
    return None

def send_servo_command(arduino, cmd_char, label):
    """Sends a single-byte command to Arduino over Serial."""
    if arduino and arduino.is_open:
        try:
            arduino.write(cmd_char.encode('utf-8'))
            arduino.flush()
            log_info(f"Hardware Trigger: Sent '{cmd_char}' to Arduino -> {label}")
        except Exception as e:
            log_error(f"Failed to send serial command: {e}")
    else:
        log_info(f"Simulation Trigger: Command '{cmd_char}' -> {label} (Arduino simulated)")

class ClipClassifier:
    """Zero-Shot CLIP Classifier with pre-computed text embeddings and custom prompt support."""
    def __init__(self, model_name="openai/clip-vit-base-patch32", custom_prompts=None):
        # Select best available hardware acceleration
        if torch.backends.mps.is_available():
            self.device = "mps"
            self.dev_desc = "Apple Silicon GPU (Metal MPS)"
        elif torch.cuda.is_available():
            self.device = "cuda"
            self.dev_desc = "NVIDIA CUDA GPU"
        else:
            self.device = "cpu"
            self.dev_desc = "CPU (Raspberry Pi / Desktop)"

        log_info(f"Loading CLIP model '{model_name}' on {self.dev_desc}...")
        try:
            # Cache-first: loads instantly if already downloaded locally
            self.model = CLIPModel.from_pretrained(model_name, local_files_only=True).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name, local_files_only=True)
        except Exception:
            log_info(f"Cache miss or update needed. Downloading '{model_name}' from Hugging Face Hub...")
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model.eval()

        self.categories = list(CATEGORY_CONFIG.keys())
        
        # Build prompt list with optional user customizations
        prompts_dict = {cat: CATEGORY_CONFIG[cat]['default_prompt'] for cat in self.categories}
        if custom_prompts:
            for cat, prompt in custom_prompts.items():
                if cat in prompts_dict and prompt:
                    prompts_dict[cat] = prompt
                    log_info(f"Custom prompt loaded for '{cat}': \"{prompt[:60]}...\"")

        self.prompts = [prompts_dict[cat] for cat in self.categories]

        # Pre-compute text embeddings once at startup
        log_info("Pre-computing category text embeddings for instant zero-shot inference...")
        text_inputs = self.processor(text=self.prompts, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            text_outputs = self.model.get_text_features(**text_inputs)
            text_features = self._extract_tensor(text_outputs)
            self.text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        log_success("CLIP Classifier initialized and ready!")

    @staticmethod
    def _extract_tensor(output):
        """Extracts the raw PyTorch Tensor from transformers model output (handles BaseModelOutputWithPooling)."""
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
        """Classifies a cropped BGR image and returns top category, confidence, and full probability map."""
        rgb_img = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        image_inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_outputs = self.model.get_image_features(**image_inputs)
            image_features = self._extract_tensor(image_outputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Cosine similarity between visual embedding and category text embeddings
            similarity = (image_features @ self.text_features.T).squeeze(0)
            probs = (similarity * 100.0).softmax(dim=-1).cpu().numpy()

        top_idx = int(np.argmax(probs))
        confidence = float(probs[top_idx])
        category = self.categories[top_idx]
        probs_dict = {cat: float(p) for cat, p in zip(self.categories, probs)}
        return category, confidence, probs_dict

def draw_hud(frame, last_probs, fps, hw_status, hw_color, in_cooldown, locked_text, locked_color, show_help, pip_preview=None):
    """Renders real-time HUD overlays: Header, Confidence Card, PiP Thumbnail, and Help Menu."""
    h_f, w_f, _ = frame.shape

    # 1. Top Navigation Bar
    cv2.rectangle(frame, (0, 0), (w_f, 38), (28, 28, 28), -1)
    cv2.line(frame, (0, 38), (w_f, 38), (55, 55, 55), 1)
    cv2.putText(frame, hw_status, (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.50, hw_color, 1, cv2.LINE_AA)
    right_status = f"FPS: {fps:4.1f} | [H] Help"
    cv2.putText(frame, right_status, (w_f - 170, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)

    # 2. Probability Breakdown Glassmorphism Card (Top-Right)
    card_w, card_h = 245, 155
    card_x = w_f - card_w - 14
    card_y = 48

    # Translucent background overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (70, 70, 70), 1)

    # Card Title
    cv2.putText(frame, "CLIP ZERO-SHOT PROBS", (card_x + 12, card_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1, cv2.LINE_AA)

    # Render category progress bars
    highest_cat = max(last_probs, key=last_probs.get) if last_probs else None
    y_offset = card_y + 45
    bar_x = card_x + 95
    bar_w = 85
    bar_h = 9

    for cat_key, cfg in CATEGORY_CONFIG.items():
        p = last_probs.get(cat_key, 0.0) if last_probs else 0.0
        is_leader = (cat_key == highest_cat and p > 0.25)
        text_col = (255, 255, 255) if is_leader else (175, 175, 175)

        # Category name
        cv2.putText(frame, cfg['label'], (card_x + 12, y_offset + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_col, 1, cv2.LINE_AA)

        # Progress bar background
        cv2.rectangle(frame, (bar_x, y_offset - 8), (bar_x + bar_w, y_offset - 8 + bar_h), (45, 45, 45), -1)

        # Progress bar fill
        fill_w = int(bar_w * p)
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x, y_offset - 8), (bar_x + fill_w, y_offset - 8 + bar_h), cfg['color'], -1)

        # Percentage Text
        pct_text = f"{p*100:3.0f}%"
        cv2.putText(frame, pct_text, (bar_x + bar_w + 8, y_offset + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, cfg['color'] if is_leader else (160, 160, 160), 1, cv2.LINE_AA)

        y_offset += 26

    # 3. Picture-in-Picture (PiP) AI Crop Thumbnail
    if pip_preview is not None:
        try:
            thumb_size = 90
            thumb_x1 = card_x - thumb_size - 12
            thumb_y1 = 48
            resized_pip = cv2.resize(pip_preview, (thumb_size, thumb_size))
            cv2.rectangle(frame, (thumb_x1 - 2, thumb_y1 - 2), (thumb_x1 + thumb_size + 2, thumb_y1 + thumb_size + 2), (0, 255, 120), 2)
            frame[thumb_y1:thumb_y1 + thumb_size, thumb_x1:thumb_x1 + thumb_size] = resized_pip
            cv2.putText(frame, "AI CROP", (thumb_x1 + 4, thumb_y1 + thumb_size - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 120), 1, cv2.LINE_AA)
        except Exception:
            pass

    # 4. Bottom Result / Action Banner
    cv2.rectangle(frame, (0, h_f - 55), (w_f, h_f), (245, 245, 245), -1)
    cv2.line(frame, (0, h_f - 55), (w_f, h_f - 55), (210, 210, 210), 1)

    if in_cooldown:
        cv2.putText(frame, "Sorting in progress (Servos Active)...", (20, h_f - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.80, (180, 80, 0), 2, cv2.LINE_AA)
    elif locked_text:
        cv2.putText(frame, locked_text, (20, h_f - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, locked_color, 2, cv2.LINE_AA)
    else:
        cv2.putText(frame, "Tray is empty. Place waste on tray (or press [Space] to scan)...", (20, h_f - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.72, (90, 90, 90), 2, cv2.LINE_AA)

    # 5. Interactive Help Overlay Modal (Toggled with 'H')
    if show_help:
        modal_w, modal_h = 480, 270
        mx1 = int(w_f / 2 - modal_w / 2)
        my1 = int(h_f / 2 - modal_h / 2)
        mx2 = mx1 + modal_w
        my2 = my1 + modal_h

        modal_overlay = frame.copy()
        cv2.rectangle(modal_overlay, (mx1, my1), (mx2, my2), (18, 18, 18), -1)
        cv2.addWeighted(modal_overlay, 0.90, frame, 0.10, 0, frame)
        cv2.rectangle(frame, (mx1, my1), (mx2, my2), (0, 255, 200), 2)

        cv2.putText(frame, "ECOSORT KEYBOARD SHORTCUTS", (mx1 + 25, my1 + 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 200), 2, cv2.LINE_AA)
        cv2.line(frame, (mx1 + 25, my1 + 45), (mx2 - 25, my1 + 45), (60, 60, 60), 1)

        shortcuts = [
            ("[1] : Trigger PAPER", "Servo 1 Left ('P')"),
            ("[2] : Trigger PLASTIC / METAL", "Servo 1 Right ('M')"),
            ("[3] : Trigger ORGANIC", "Servo 2 Forward ('O')"),
            ("[4] : Trigger GENERAL TRASH", "Servo 2 Backward ('G')"),
            ("[C] : Recalibrate Tray", "Resets background subtraction"),
            ("[Space] : Force Instant Scan", "Evaluates current tray frame"),
            ("[H] : Close Help Menu", "Toggles this screen"),
            ("[Q] : Quit EcoSort", "Resets servos to neutral & exits")
        ]

        sy = my1 + 72
        for key_text, desc in shortcuts:
            cv2.putText(frame, key_text, (mx1 + 25, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"- {desc}", (mx1 + 220, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1, cv2.LINE_AA)
            sy += 22

def main():
    parser = argparse.ArgumentParser(description='EcoSort Smart Bin - Zero-Shot CLIP 4-Way Waste Segregator')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0 for built-in, 1 for external/USB)')
    parser.add_argument('--port', type=str, default='auto', help="Arduino Serial Port (e.g. 'auto', '/dev/ttyACM0', 'COM3')")
    parser.add_argument('--baud', type=int, default=9600, help='Arduino Serial Baud Rate (default: 9600)')
    parser.add_argument('--no-arduino', action='store_true', help='Run in simulation mode without physical Arduino')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode without GUI window (ideal for Raspberry Pi SSH)')
    parser.add_argument('--threshold', type=float, default=0.60, help='Confidence threshold to trigger physical sort (default: 0.60)')
    parser.add_argument('--stable-frames', type=int, default=3, help='Consecutive identical predictions required (default: 3)')
    parser.add_argument('--cooldown', type=float, default=2.5, help='Cooldown seconds after physical sorting action (default: 2.5)')
    parser.add_argument('--prompts-file', type=str, default=None, help='Path to JSON file with custom category prompts')
    args = parser.parse_args()

    # Auto-detect headless mode if running on Linux without an active display
    is_headless = args.headless
    if not is_headless and sys.platform.startswith('linux'):
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
            log_info("No graphical display detected (SSH session). Auto-enabling --headless mode.")
            is_headless = True

    # Load custom prompts if provided
    custom_prompts = None
    if args.prompts_file:
        try:
            with open(args.prompts_file, 'r') as f:
                custom_prompts = json.load(f)
            log_success(f"Loaded custom prompts from '{args.prompts_file}'")
        except Exception as e:
            log_warning(f"Could not load prompts file '{args.prompts_file}': {e}. Using defaults.")

    # Initialize CLIP
    classifier = ClipClassifier(custom_prompts=custom_prompts)

    # Connect Arduino
    arduino = None
    if not args.no_arduino:
        arduino = connect_arduino(args.port, args.baud)
    else:
        log_info("--no-arduino set. Running in SIMULATION MODE.")

    # Initialize Camera with Auto-Fallback
    log_info(f"Opening Camera (Index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened() and args.camera != 0:
        log_warning(f"Camera index {args.camera} not found. Falling back to built-in camera (Index 0)...")
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        log_error("Could not open camera. Please check USB connection or camera permissions.")
        if arduino: arduino.close()
        return

    print("\n" + "="*65)
    print(f" {C_BOLD}{C_GREEN}ECOSORT SMART BIN: ZERO-SHOT CLIP 4-WAY SORTING READY{C_RESET}")
    print(f"   Device Acceleration : {classifier.dev_desc}")
    print(f"   Confidence Cutoff   : {args.threshold * 100:.0f}%")
    print(f"   Stability Requirement: {args.stable_frames} frames")
    print("   [1] PAPER            -> Command 'P' (Servo 1 Left)")
    print("   [2] PLASTIC / METAL  -> Command 'M' (Servo 1 Right)")
    print("   [3] ORGANIC          -> Command 'O' (Servo 2 Forward)")
    print("   [4] GENERAL TRASH    -> Command 'G' (Servo 2 Backward)")
    if not is_headless:
        print("   Interactive Hotkeys : [1-4] Test Servos | [C] Recalibrate | [Space] Scan | [H] Help | [Q] Quit")
    else:
        print("   Headless Mode Active: Press Ctrl+C to terminate.")
    print("="*65 + "\n")

    # State Variables
    locked_text = None
    locked_color = (0, 0, 0)
    empty_frames = 0
    cooldown_until = 0.0
    prediction_history = []
    last_probs = {c: 0.0 for c in classifier.categories}
    show_help = False
    pip_preview = None

    # FPS Calculation
    prev_time = time.time()
    fps = 0.0

    # Background Subtraction Variables
    background_frame = None
    calibration_frames = 30
    frames_read = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                log_error("Camera frame read failed. Exiting loop.")
                break

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(0.001, now - prev_time))
            prev_time = now
            in_cooldown = (now < cooldown_until)

            h_f, w_f, _ = frame.shape

            # Scanning Box in center
            box_size = min(400, min(h_f, w_f) - 40)
            x1 = int(w_f / 2 - box_size / 2)
            y1 = int(h_f / 2 - box_size / 2)
            x2 = x1 + box_size
            y2 = y1 + box_size

            roi = frame[y1:y2, x1:x2]
            if roi.shape[0] == 0 or roi.shape[1] == 0:
                continue

            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)

            # Phase 1: Background Tray Calibration
            if frames_read < calibration_frames:
                if background_frame is None:
                    background_frame = gray_roi.astype("float")
                else:
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.1)

                frames_read += 1
                calib_msg = f"Calibrating Empty Tray... {frames_read}/{calibration_frames}"

                if not is_headless:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                    cv2.rectangle(frame, (0, h_f - 55), (w_f, h_f), (245, 245, 245), -1)
                    cv2.putText(frame, calib_msg, (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (0, 120, 255), 2)
                    cv2.imshow("EcoSort Smart Bin - Zero-Shot CLIP", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                else:
                    print(f"\r[CALIBRATING] {calib_msg}", end='', flush=True)
                continue

            # Phase 2: Object Motion / Presence Detection
            object_detected = False
            obj_crop = roi
            force_scan = False

            # Check key presses in GUI mode
            if not is_headless:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('h'):
                    show_help = not show_help
                elif key in [ord('c'), ord('r')]:
                    # Manual Recalibrate
                    log_info("Manual tray recalibration triggered.")
                    background_frame = None
                    frames_read = 0
                    locked_text = "[RECALIBRATING] Empty tray recalibrated..."
                    locked_color = (0, 165, 255)
                    prediction_history = []
                    continue
                elif key == ord(' '):
                    # Force scan current frame
                    log_info("Force scan triggered via Spacebar.")
                    force_scan = True
                elif key in [ord('1'), ord('2'), ord('3'), ord('4')]:
                    # Manual servo triggers for testing
                    cat_map = {
                        ord('1'): 'paper',
                        ord('2'): 'plastic_metal',
                        ord('3'): 'organic',
                        ord('4'): 'general'
                    }
                    sel_cat = cat_map[key]
                    cfg = CATEGORY_CONFIG[sel_cat]
                    send_servo_command(arduino, cfg['cmd'], cfg['label'])
                    log_sort_event(cfg['label'], 1.0, cfg['cmd'], f"MANUAL HOTKEY: {cfg['servo_desc']}")
                    locked_text = f"[MANUAL TRIGGER] {cfg['label'].upper()} ({cfg['servo_desc']})"
                    locked_color = cfg['color']
                    cooldown_until = now + args.cooldown

            if not in_cooldown:
                frame_delta = cv2.absdiff(background_frame.astype("uint8"), gray_roi)
                thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for c in contours:
                    if cv2.contourArea(c) > 5000:
                        object_detected = True
                        x, y, w, h = cv2.boundingRect(c)
                        if not is_headless:
                            cv2.rectangle(frame, (x1 + x, y1 + y), (x1 + x + w, y1 + y + h), (0, 255, 0), 2)
                        
                        # Crop tightly around item
                        pad = 20
                        crop_y1 = max(0, y - pad)
                        crop_y2 = min(roi.shape[0], y + h + pad)
                        crop_x1 = max(0, x - pad)
                        crop_x2 = min(roi.shape[1], x + w + pad)
                        obj_crop = roi[crop_y1:crop_y2, crop_x1:crop_x2]
                        break

            # Phase 3: CLIP Zero-Shot Classification
            if (object_detected or force_scan) and not in_cooldown:
                empty_frames = 0
                eval_img = obj_crop if (obj_crop.shape[0] > 20 and obj_crop.shape[1] > 20) else roi
                pip_preview = eval_img

                # Perform classification
                pred_cat, conf, probs = classifier.predict(eval_img)
                last_probs = probs

                if is_headless:
                    print(f"\r[EVAL] Paper: {probs['paper']*100:2.0f}% | Plastic/Metal: {probs['plastic_metal']*100:2.0f}% | Organic: {probs['organic']*100:2.0f}% | General: {probs['general']*100:2.0f}% | Top: {pred_cat} ({conf*100:.0f}%)", end='', flush=True)

                if (conf >= args.threshold or force_scan) and locked_text is None:
                    prediction_history.append((pred_cat, conf))
                    if len(prediction_history) > args.stable_frames:
                        prediction_history.pop(0)

                    recent_classes = [p[0] for p in prediction_history]
                    # Trigger physical action once category is stable across required frames
                    if (len(recent_classes) == args.stable_frames and len(set(recent_classes)) == 1) or force_scan:
                        final_cat = recent_classes[0] if not force_scan else pred_cat
                        avg_conf = np.mean([p[1] for p in prediction_history]) if not force_scan else conf
                        cfg = CATEGORY_CONFIG[final_cat]

                        # Send Serial Hardware Trigger
                        send_servo_command(arduino, cfg['cmd'], cfg['label'])
                        log_sort_event(cfg['label'], avg_conf, cfg['cmd'], cfg['servo_desc'])

                        locked_text = f"[{avg_conf*100:.0f}%] {cfg['label'].upper()} -> {cfg['servo_desc']}"
                        locked_color = cfg['color']
                        prediction_history = []
                        cooldown_until = now + args.cooldown
                else:
                    if conf < args.threshold:
                        prediction_history = []
            else:
                pip_preview = None
                if not in_cooldown:
                    # Dynamically adapt background slowly
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.05)
                    empty_frames += 1
                    if empty_frames > 12:
                        locked_text = None
                        prediction_history = []
                        # Fade out probability display when tray is empty
                        last_probs = {c: max(0.0, last_probs[c] * 0.85) for c in classifier.categories}

            # Phase 4: Display Output
            if not is_headless:
                tray_color = (140, 140, 140) if in_cooldown else (255, 255, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), tray_color, 2)
                cv2.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, tray_color, 2, cv2.LINE_AA)

                # Hardware status text
                if arduino and arduino.is_open:
                    hw_status = f"Arduino: CONNECTED ({arduino.port}) | {classifier.dev_desc}"
                    hw_color = (0, 255, 120)
                else:
                    hw_status = f"Arduino: SIMULATION | {classifier.dev_desc}"
                    hw_color = (0, 190, 255)

                draw_hud(frame, last_probs, fps, hw_status, hw_color, in_cooldown, locked_text, locked_color, show_help, pip_preview)
                cv2.imshow("EcoSort Smart Bin - Zero-Shot CLIP", frame)
            else:
                # Modest sleep in headless mode to prevent high CPU utilization
                time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}[EXIT] Stopped by user (Ctrl+C).{C_RESET}")

    finally:
        cap.release()
        if not is_headless:
            cv2.destroyAllWindows()

        # Reset servos to neutral before closing
        if arduino and arduino.is_open:
            try:
                arduino.write(b'0')
                time.sleep(0.2)
                arduino.close()
                log_success("Servos returned to Neutral position. Serial connection closed.")
            except Exception:
                pass
        log_info("EcoSort shutdown complete.")

if __name__ == '__main__':
    main()
