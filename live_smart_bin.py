import cv2
import numpy as np
import tensorflow as tf
import os
import argparse
import time

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

def connect_arduino(port=None, baud=9600):
    """
    Attempt to connect to Arduino over USB Serial.
    Auto-detects Arduino port if port is 'auto' or None.
    Returns serial.Serial object or None.
    """
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("\n[WARNING] 'pyserial' is not installed.")
        print("          Run: pip install pyserial")
        print("          Continuing in SIMULATION MODE (no hardware triggers).\n")
        return None

    if port and port.lower() != 'auto':
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2.0)  # Arduino resets when serial opens
            print(f"[HARDWARE] Connected to Arduino on {port} @ {baud} baud.")
            return ser
        except Exception as e:
            print(f"[WARNING] Could not open specified port {port}: {e}")
            print("          Falling back to SIMULATION MODE.\n")
            return None

    # Auto-detect Arduino on macOS / Linux / Windows
    ports = list(serial.tools.list_ports.comports())
    candidate_port = None
    for p in ports:
        desc = (p.description or '').lower()
        hwid = (p.hwid or '').lower()
        pname = (p.device or '').lower()
        if any(k in desc or k in hwid or k in pname for k in ['arduino', 'ch340', 'usb serial', 'usbmodem', 'usbserial']):
            candidate_port = p.device
            break

    # If no obvious name, check for any usbmodem / usbserial port on macOS
    if not candidate_port and ports:
        for p in ports:
            if 'usbmodem' in p.device.lower() or 'usbserial' in p.device.lower():
                candidate_port = p.device
                break

    if candidate_port:
        try:
            ser = serial.Serial(candidate_port, baud, timeout=1)
            time.sleep(2.0)
            print(f"[HARDWARE] Auto-detected Arduino on {candidate_port} @ {baud} baud.")
            # Clear initial boot messages
            ser.reset_input_buffer()
            return ser
        except Exception as e:
            print(f"[WARNING] Found serial device on {candidate_port}, but failed to connect: {e}")
            print("          Running in SIMULATION MODE.\n")
            return None

    print("[HARDWARE] No Arduino found on USB ports. Running in SIMULATION MODE.")
    return None

def send_servo_command(arduino, cmd_char, label):
    """Sends a single-byte command to Arduino ('G' or 'R')."""
    if arduino and arduino.is_open:
        try:
            arduino.write(cmd_char.encode('utf-8'))
            arduino.flush()
            print(f"[HARDWARE TRIGGER] Sent '{cmd_char}' to Arduino -> {label}")
        except Exception as e:
            print(f"[ERROR] Failed to send serial command: {e}")
    else:
        print(f"[SIMULATION TRIGGER] Command '{cmd_char}' -> {label} (Arduino not connected)")

def main():
    parser = argparse.ArgumentParser(description='EcoSort Smart Bin Live Camera with Dual Servo Hardware Control')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0 for built-in, 1 for external/iPhone)')
    parser.add_argument('--port', type=str, default='auto', help="Arduino Serial Port (e.g., 'auto', '/dev/cu.usbmodem1101', 'COM3')")
    parser.add_argument('--baud', type=int, default=9600, help='Arduino Serial Baud Rate (default: 9600)')
    parser.add_argument('--no-arduino', action='store_true', help='Force simulation mode without connecting to Arduino')
    args = parser.parse_args()

    model_path = 'ecosort_model.keras'
    labels_path = 'labels.txt'

    if not os.path.exists(model_path) or not os.path.exists(labels_path):
        print("Error: Model or labels not found. Please train model or verify files in current directory!")
        return

    print(f"Loading EcoSort AI Model ({model_path})...")
    model = tf.keras.models.load_model(model_path)
    with open(labels_path, 'r') as f:
        class_names = [line.strip().lower() for line in f.readlines()]

    print(f"Model classes: {class_names}")

    # Establish Arduino Serial connection
    arduino = None
    if not args.no_arduino:
        arduino = connect_arduino(args.port, args.baud)
    else:
        print("[HARDWARE] --no-arduino specified. Running in pure SIMULATION MODE.")

    print(f"Opening Webcam (Index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        if arduino and arduino.is_open:
            arduino.close()
        return

    print("\n" + "="*58)
    print(" ECOSORT SMART BIN: 4-WAY WASTE SEGREGATION ONLINE")
    print("   [1] PAPER            -> Command 'P' (Servo 1 Left)")
    print("   [2] PLASTIC / METAL  -> Command 'M' (Servo 1 Right)")
    print("   [3] ORGANIC          -> Command 'O' (Servo 2 Forward)")
    print("   [4] GENERAL TRASH    -> Command 'G' (Servo 2 Backward)")
    print("   Press 'q' to quit.")
    print("="*58 + "\n")

    locked_text = None
    locked_color = (0, 0, 0)
    empty_frames = 0
    cooldown_until = 0.0  # Timestamp to prevent re-triggering while servo is moving
    prediction_history = []  # Rolling votes to prevent single-frame false positives
    REQUIRED_STABLE_FRAMES = 4  # Must be consistently classified for 4 frames
    
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
        
        # Define the scanning tray (center box)
        box_size = 400
        x1 = int(w_f/2 - box_size/2)
        y1 = int(h_f/2 - box_size/2)
        x2 = x1 + box_size
        y2 = y1 + box_size
        
        # Draw Tray bounding box
        tray_color = (180, 180, 180) if in_cooldown else (255, 255, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), tray_color, 2)
        cv2.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tray_color, 2)
        
        roi = frame[y1:y2, x1:x2]
        if roi.shape[0] > 0 and roi.shape[1] > 0:
            
            # Convert ROI to grayscale and blur it for motion detection
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)
            
            # Phase 1: Calibrate the empty tray
            if frames_read < calibration_frames:
                if background_frame is None:
                    background_frame = gray_roi.astype("float")
                else:
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.1)
                
                frames_read += 1
                cv2.rectangle(frame, (0, h_f - 60), (w_f, h_f), (255, 255, 255), -1)
                cv2.putText(frame, f"Calibrating Empty Tray... {frames_read}/{calibration_frames}", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("EcoSort Smart Bin Simulator", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # Phase 2: Detect Objects (skip detection if currently in servo movement cooldown)
            object_detected = False
            if not in_cooldown:
                frame_delta = cv2.absdiff(background_frame.astype("uint8"), gray_roi)
                thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for c in contours:
                    if cv2.contourArea(c) > 5000:  # Ignore tiny shadows / noise
                        object_detected = True
                        x, y, w, h = cv2.boundingRect(c)
                        cv2.rectangle(frame, (x1+x, y1+y), (x1+x+w, y1+y+h), (0, 255, 0), 2)
                        break
            
            if object_detected and not in_cooldown:
                empty_frames = 0
                
                # --- Object-Centric Crop (Exclude surrounding tray background) ---
                pad = 20
                crop_y1 = max(0, y - pad)
                crop_y2 = min(roi.shape[0], y + h + pad)
                crop_x1 = max(0, x - pad)
                crop_x2 = min(roi.shape[1], x + w + pad)
                obj_crop = roi[crop_y1:crop_y2, crop_x1:crop_x2]
                
                if obj_crop.shape[0] > 15 and obj_crop.shape[1] > 15:
                    eval_img = obj_crop
                else:
                    eval_img = roi

                # Picture-in-Picture (PiP) inset preview showing what the AI is analyzing
                try:
                    pip_preview = cv2.resize(eval_img, (90, 90))
                    cv2.rectangle(frame, (w_f - 105, 50), (w_f - 11, 144), (0, 255, 0), 2)
                    frame[52:142, w_f - 103:w_f - 13] = pip_preview
                    cv2.putText(frame, "AI CROP", (w_f - 95, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                except Exception:
                    pass

                # Run Keras Model
                roi_rgb = cv2.cvtColor(eval_img, cv2.COLOR_BGR2RGB)
                roi_resized = cv2.resize(roi_rgb, (224, 224))
                img_array = tf.keras.utils.img_to_array(roi_resized)
                img_array = tf.expand_dims(img_array, 0)
                
                predictions = model.predict(img_array, verbose=0)
                score = predictions[0]
                max_score = np.max(score)
                predicted_class = class_names[np.argmax(score)]
                
                if max_score > 0.82 and locked_text is None:
                    # Accumulate predictions across consecutive frames to verify stability
                    prediction_history.append((predicted_class, max_score))
                    if len(prediction_history) > REQUIRED_STABLE_FRAMES:
                        prediction_history.pop(0)

                    # Check if all recent frames agree
                    recent_classes = [p[0] for p in prediction_history]
                    if len(recent_classes) == REQUIRED_STABLE_FRAMES and len(set(recent_classes)) == 1:
                        final_class = recent_classes[0]
                        avg_conf = np.mean([p[1] for p in prediction_history])
                        
                        # Route into 4 distinct categories
                        if final_class == 'paper':
                            action = "PAPER -> [1/4] PAPER (Servo 1 Left)"
                            locked_color = (0, 180, 0)  # Green
                            send_servo_command(arduino, 'P', 'PAPER')
                        elif final_class == 'plastic_metal':
                            action = "PLASTIC / METAL -> [2/4] PLASTIC/METAL (Servo 1 Right)"
                            locked_color = (230, 140, 0)  # Cyan/Blue
                            send_servo_command(arduino, 'M', 'PLASTIC/METAL')
                        elif final_class == 'organic':
                            action = "ORGANIC -> [3/4] ORGANIC (Servo 2 Forward)"
                            locked_color = (0, 215, 255)  # Yellow / Gold
                            send_servo_command(arduino, 'O', 'ORGANIC')
                        else:
                            action = "GENERAL TRASH -> [4/4] GENERAL (Servo 2 Backward)"
                            locked_color = (0, 0, 200)  # Red
                            send_servo_command(arduino, 'G', 'GENERAL TRASH')
                            
                        locked_text = f"[{avg_conf*100:.0f}%] {action}"
                        prediction_history = []
                        cooldown_until = now + 2.5
                else:
                    if max_score <= 0.82:
                        prediction_history = []
            else:
                if not in_cooldown:
                    # Adaptively update background to handle slow ambient lighting changes
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.05)
                    empty_frames += 1
                    if empty_frames > 10:
                        locked_text = None
                        prediction_history = []

            # --- Top Hardware Status Bar ---
            cv2.rectangle(frame, (0, 0), (w_f, 40), (40, 40, 40), -1)
            if arduino and arduino.is_open:
                hw_status = f"Arduino: CONNECTED ({arduino.port}) | 4-WAY SEGREGATION ACTIVE"
                hw_color = (0, 255, 120)
            else:
                hw_status = "Arduino: SIMULATION MODE (Connect USB or pass --port)"
                hw_color = (0, 180, 255)
            cv2.putText(frame, hw_status, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, hw_color, 2)

            # --- Bottom Result Banner ---
            cv2.rectangle(frame, (0, h_f - 60), (w_f, h_f), (255, 255, 255), -1)
            if in_cooldown:
                cv2.putText(frame, "Sorting in progress (Servos Active)...", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (180, 80, 0), 2)
            elif locked_text:
                cv2.putText(frame, locked_text, (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.75, locked_color, 2)
            else:
                cv2.putText(frame, "Tray is empty. Place waste on tray...", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 80, 80), 2)

        cv2.imshow("EcoSort Smart Bin - Vision & Servo Controller", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
    if arduino and arduino.is_open:
        # Reset servos to neutral before exiting
        try:
            arduino.write(b'N')
            time.sleep(0.2)
            arduino.close()
            print("[HARDWARE] Servos reset to Neutral. Serial connection closed.")
        except Exception:
            pass

if __name__ == '__main__':
    main()
