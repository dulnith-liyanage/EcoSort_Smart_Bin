import cv2
import numpy as np
import tensorflow as tf
import os
import argparse
import time

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

    # Hardware simulation state
    sorting_state = "IDLE"
    sort_timer = 0

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
        
        if time.time() > sort_timer:
            sorting_state = "IDLE"

        if sorting_state == "IDLE":
            roi = frame[y1:y2, x1:x2]
            if roi.shape[0] > 0 and roi.shape[1] > 0:
                roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                roi_resized = cv2.resize(roi_rgb, (224, 224))
                img_array = tf.keras.utils.img_to_array(roi_resized)
                img_array = tf.expand_dims(img_array, 0)
                
                predictions = model.predict(img_array, verbose=0)
                score = predictions[0]
                max_score = np.max(score)
                
                # Require high confidence to trigger the physical motors (90%)
                if max_score > 0.90:
                    predicted_class = class_names[np.argmax(score)]
                    
                    recycling_items = ['cardboard', 'glass', 'metal', 'paper', 'plastic']
                    if any(item in predicted_class for item in recycling_items):
                        action = f"ACTUATING SERVO: RECYCLING CHUTE ♻️ ({predicted_class})"
                        color = (255, 200, 0) # Blue/Cyan in BGR
                    elif 'compost' in predicted_class or 'organic' in predicted_class:
                        action = f"ACTUATING SERVO: COMPOST CHUTE 🍏 ({predicted_class})"
                        color = (0, 200, 0) # Green
                    else:
                        action = f"ACTUATING SERVO: LANDFILL TRASH 🗑️ ({predicted_class})"
                        color = (0, 0, 255) # Red
                        
                    sorting_state = action
                    sort_timer = time.time() + 3.0 # Hold the state for 3 seconds to let the item drop
                    print(f"[{max_score*100:.0f}% Confidence] {action}")
                else:
                    status_text = "Place item on tray..."
                    cv2.putText(frame, status_text, (10, h_f - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)

        else:
            # Display the sorting action prominently
            cv2.putText(frame, sorting_state, (10, h_f - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
            cv2.putText(frame, "(Item dropped)", (10, h_f - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow("EcoSort Smart Bin Simulator", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
