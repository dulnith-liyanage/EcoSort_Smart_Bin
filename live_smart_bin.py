import cv2
import numpy as np
import tensorflow as tf
import os
import argparse

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

def main():
    parser = argparse.ArgumentParser(description='EcoSort Smart Bin Live Camera')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0 for built-in, 1 for external/iPhone)')
    args = parser.parse_args()

    if not os.path.exists('ecosort_model.keras') or not os.path.exists('labels.txt'):
        print("Error: Model or labels not found. Please add images to dataset/ and run train_model.py first!")
        return

    print("Loading EcoSort AI Model...")
    model = tf.keras.models.load_model('ecosort_model.keras')
    with open('labels.txt', 'r') as f:
        class_names = [line.strip().lower() for line in f.readlines()]
        
    print(f"Opening Webcam (Index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("\n" + "="*40)
    print("ECOSORT SMART BIN ONLINE! Press 'q' to quit.")
    print("="*40 + "\n")

    locked_text = None
    empty_frames = 0
    
    # Background Subtraction Variables
    background_frame = None
    calibration_frames = 30
    frames_read = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h_f, w_f, _ = frame.shape
        
        # Define the scanning tray (center box)
        box_size = 400
        x1 = int(w_f/2 - box_size/2)
        y1 = int(h_f/2 - box_size/2)
        x2 = x1 + box_size
        y2 = y1 + box_size
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
        cv2.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
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
                cv2.putText(frame, f"Calibrating Empty Tray... {frames_read}/{calibration_frames}", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                cv2.imshow("EcoSort Smart Bin Simulator", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
                continue

            # Phase 2: Detect Objects
            frame_delta = cv2.absdiff(background_frame.astype("uint8"), gray_roi)
            thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            object_detected = False
            for c in contours:
                if cv2.contourArea(c) > 5000: # Threshold for a valid object size (e.g. ignore tiny shadows)
                    object_detected = True
                    # Draw a green box around the detected object
                    x, y, w, h = cv2.boundingRect(c)
                    cv2.rectangle(frame, (x1+x, y1+y), (x1+x+w, y1+y+h), (0, 255, 0), 2)
                    break
            
            if object_detected:
                empty_frames = 0
                
                # Only run the heavy AI model if an object is actually present!
                roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                roi_resized = cv2.resize(roi_rgb, (224, 224))
                img_array = tf.keras.utils.img_to_array(roi_resized)
                img_array = tf.expand_dims(img_array, 0)
                
                predictions = model.predict(img_array, verbose=0)
                score = predictions[0]
                max_score = np.max(score)
                
                if max_score > 0.85:
                    if locked_text is None:
                        # New object placed! Lock in the prediction
                        predicted_class = class_names[np.argmax(score)]
                        
                        if predicted_class == 'paper':
                            action = "Paper (Recyclable)"
                        elif predicted_class == 'plastic_metal':
                            action = "Plastic/Metal (Recyclable)"
                        elif predicted_class == 'organic':
                            action = "Organic (General Trash)"
                        else:
                            action = "Trash (General Trash)"
                            
                        locked_text = f"[{max_score*100:.0f}%] {action}"
            else:
                # No object detected. Slowly update the background to adapt to lighting changes
                cv2.accumulateWeighted(gray_roi, background_frame, 0.05)
                empty_frames += 1
                if empty_frames > 10:
                    locked_text = None

            # Draw UI
            cv2.rectangle(frame, (0, h_f - 60), (w_f, h_f), (255, 255, 255), -1)
            if locked_text:
                cv2.putText(frame, locked_text, (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 3)
            else:
                cv2.putText(frame, "Tray is empty. Waiting for item...", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 3)

        cv2.imshow("EcoSort Smart Bin Simulator", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
