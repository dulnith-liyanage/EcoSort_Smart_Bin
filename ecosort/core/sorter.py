"""
Core sorting runtime loop coordinating camera acquisition, presence detection,
zero-shot CLIP classification, quintic motion trajectories, and telemetry bridge.
"""
import argparse
import json
import os
import sys
import time
import cv2
import numpy as np

from ecosort.config import CATEGORY_CONFIG, MODEL_NAMES, C_BOLD, C_GREEN, C_YELLOW, C_RESET
from ecosort.logging import log_info, log_success, log_warning, log_error, log_sort_event
from ecosort.hardware.servo import init_hardware_controller
from ecosort.hardware.camera import CameraCapture
from ecosort.vision.classifier import (
    ClipClassifier,
    build_prompt_groups,
    prediction_is_eligible,
    best_window_prediction,
)
from ecosort.vision.hud import draw_hud
import servo_settings


def main(bridge=None, classifier_cls=None, camera_cls=None, controller_fn=None, cv2_mod=None):
    live = sys.modules.get('live_smart_bin')
    if classifier_cls is None:
        classifier_cls = getattr(live, 'ClipClassifier', ClipClassifier) if live else ClipClassifier
    if camera_cls is None:
        camera_cls = getattr(live, 'CameraCapture', CameraCapture) if live else CameraCapture
    if controller_fn is None:
        controller_fn = getattr(live, 'init_hardware_controller', init_hardware_controller) if live else init_hardware_controller
    if cv2_mod is None:
        cv2_mod = getattr(live, 'cv2', cv2) if live else cv2

    parser = argparse.ArgumentParser(description='EcoSort Smart Bin - 2-Axis Pan-Tilt Waste Segregator (2x2 Grid)')
    parser.add_argument('--driver', type=str, default='auto', choices=['auto', 'rpi-i2c', 'pca9685', 'sim'],
                        help="Hardware servo controller: 'auto' (Raspberry Pi PCA9685 I2C), 'rpi-i2c' (direct Raspberry Pi PCA9685), or 'sim' (simulation)")
    parser.add_argument('--pan-ch', type=int, default=0, help="PCA9685 channel for Pan servo (default: 0)")
    parser.add_argument('--tilt-ch', type=int, default=1, help="PCA9685 channel for Tilt servo (default: 1)")
    parser.add_argument('--camera', type=int, default=0, help='Camera index (0 for CSI/built-in, 1 for external USB)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode without GUI window (ideal for Raspberry Pi SSH)')
    parser.add_argument('--cpu-threads', type=int, choices=range(1, 5), default=2,
                        help='CPU inference threads (default: 2, leaving capacity for VNC)')
    parser.add_argument('--model', choices=MODEL_NAMES, default='clip',
                        help='Pretrained backend: clip (cached baseline) or siglip2 (comparison candidate)')
    parser.add_argument('--routing-policy', choices=['best-match', 'confident'], default='best-match',
                        help='best-match sorts every detected item; confident requires score/margin gates')
    parser.add_argument('--threshold', type=float, default=0.60, help='Relative score threshold to trigger physical sort (default: 0.60)')
    parser.add_argument('--margin', type=float, default=0.15, help='Minimum top-two score gap (default: 0.15; tune on validation images)')
    parser.add_argument('--stable-frames', type=int, default=3, help='Consecutive identical predictions required (default: 3)')
    parser.add_argument('--cooldown', type=float, default=3.8, help='Cooldown seconds after physical sorting action (default: 3.8)')
    parser.add_argument('--prompts-file', type=str, default=None, help='Path to JSON file with custom category prompts')
    args = parser.parse_args()

    if args.stable_frames < 1 or not 0 < args.threshold <= 1 or args.cooldown < 0 or not 0 <= args.margin <= 1:
        parser.error('stable-frames must be positive, threshold in (0,1], margin in [0,1], cooldown nonnegative')
    if args.driver != 'sim':
        try:
            servo_settings.load_calibration().validate_routes(CATEGORY_CONFIG.values())
        except (OSError, ValueError, KeyError) as error:
            parser.error(f'Sorting calibration is not usable: {error}')

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
            build_prompt_groups(custom_prompts)
            log_success(f"Loaded custom prompts from '{args.prompts_file}'")
        except Exception as e:
            parser.error(f"Invalid prompts file: {e}")

    if bridge:
        bridge.emit('state', phase='loading', paused=True, model=args.model,
                    message='Loading model. Keep the tray empty for background calibration.')

    # Initialize vision-language classifier using resolved class
    classifier = classifier_cls(
        model_name=MODEL_NAMES[args.model],
        custom_prompts=custom_prompts,
        cpu_threads=args.cpu_threads
    )

    if bridge and bridge.stopping:
        return

    # Initialize Hardware Controller
    controller = controller_fn(
        driver_mode=args.driver,
        pan_ch=args.pan_ch,
        tilt_ch=args.tilt_ch
    )

    # Initialize Camera
    try:
        cam = camera_cls(args.camera)
    except Exception:
        controller.close()
        raise
    if not cam.is_opened():
        log_error("Could not open camera. Please check camera connection or permissions.")
        cam.release()
        controller.close()
        if bridge:
            bridge.emit('error', message='Camera unavailable. Close other camera applications and check the CSI connection.')
        return

    print("\n" + "=" * 72)
    print(f" {C_BOLD}{C_GREEN}ECOSORT SMART BIN: 2-AXIS PAN-TILT 2x2 GRID WASTE SEGREGATION{C_RESET}")
    print("   Four project waste routes; verify local collection requirements separately")
    print(f"   Device Acceleration : {classifier.dev_desc}")
    print(f"   Routing policy: {args.routing_policy} (match scores are not accuracy measurements)")
    print(f"   Relative Score Cutoff: {args.threshold * 100:.0f}% | Cooldown: {args.cooldown}s")
    print(f"   Minimum top-two gap : {args.margin * 100:.0f}% | Stable predictions: {args.stable_frames}")
    print(f"   Pretrained model: {MODEL_NAMES[args.model]}")
    print("   Always displays a best-match bin. Low-quality guesses do not trigger motors.")
    print("   --- 4 Target Bins in 2x2 Grid (Center-Mounted Pan-Tilt) ---")
    saved = servo_settings.load_calibration()
    print(f"   Calibrated HOME: Pan {saved.pan_home}°, Tilt {saved.tilt_home}°")
    for index, cfg in enumerate(CATEGORY_CONFIG.values(), 1):
        pan, tilt, _ = saved.route(cfg)
        print(f"   [{index}] {cfg['label']} -> {cfg['bin_pos']} (Pan {pan}°, Tilt {tilt}°)")
    if saved.forward_tilt is not None:
        print("   Explicit tilt endpoints: verify clearance and waste delivery physically.")
    if not is_headless:
        print("   Interactive Hotkeys : [1-4] Test Bins | [C] Recalibrate | [Space] Scan | [H] Help | [Q] Quit")
    else:
        print("   Headless Mode Active: Press Ctrl+C to terminate.")
    print("=" * 72 + "\n")

    # State Variables
    locked_text = None
    decision_text = None
    locked_color = (0, 0, 0)
    empty_frames = 0
    cooldown_until = 0.0
    prediction_history = []
    last_probs = {c: 0.0 for c in classifier.categories}
    show_help = False
    pip_preview = None

    # FPS Calculation
    prev_time = time.monotonic()
    fps = 0.0

    # Background Subtraction Variables
    background_frame = None
    calibration_frames = 30
    frames_read = 0
    warmup_remaining = getattr(bridge, 'warmup_frames', 0) if bridge else 0

    try:
        while True:
            dashboard_actions = bridge.poll() if bridge else []
            if bridge and bridge.stopping:
                break
            if 'recalibrate' in dashboard_actions:
                background_frame = None
                frames_read = 0
                prediction_history = []
                locked_text = decision_text = None
                last_probs = {c: 0.0 for c in classifier.categories}
            ret, frame = cam.read()
            if not ret:
                log_error("Camera frame read failed. Exiting loop.")
                if bridge:
                    bridge.emit('error', message='Camera frame read failed. Session stopped.')
                break

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 * (1.0 / max(0.001, now - prev_time))
            prev_time = now
            in_cooldown = (now < cooldown_until)

            if bridge:
                bridge.frame(frame)
                phase = ('calibrating' if frames_read < calibration_frames else
                         'cooldown' if in_cooldown else 'observing' if bridge.paused else
                         'waiting_clear' if locked_text is not None else 'ready')
                bridge.emit('state', phase=phase, paused=bridge.paused, fps=round(fps, 1),
                            scores=last_probs, stable=len(prediction_history),
                            calibration_progress=min(1.0, frames_read / calibration_frames),
                            routing_policy=args.routing_policy,
                            message=('Previous route completed. Clear the tray before adding another item.'
                                     if phase == 'waiting_clear' else locked_text or decision_text) or (
                                         'Keep the tray empty while calibrating.' if phase == 'calibrating' else 'Place one item in the scanning area.'))

            if warmup_remaining > 0:
                warmup_remaining -= 1
                continue

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

            gray_roi = cv2_mod.cvtColor(roi, cv2_mod.COLOR_BGR2GRAY)
            gray_roi = cv2_mod.GaussianBlur(gray_roi, (21, 21), 0)

            # Phase 1: Background Tray Calibration
            if frames_read < calibration_frames:
                if background_frame is None:
                    background_frame = gray_roi.astype("float")
                else:
                    cv2_mod.accumulateWeighted(gray_roi, background_frame, 0.1)

                frames_read += 1
                if bridge and frames_read == calibration_frames:
                    bridge.calibrated()
                calib_msg = f"Calibrating Empty Tray... {frames_read}/{calibration_frames}"

                if not is_headless:
                    cv2_mod.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                    cv2_mod.rectangle(frame, (0, h_f - 55), (w_f, h_f), (245, 245, 245), -1)
                    cv2_mod.putText(frame, calib_msg, (20, h_f - 20), cv2_mod.FONT_HERSHEY_SIMPLEX, 0.80, (0, 120, 255), 2)
                    cv2_mod.imshow("EcoSort Smart Bin - Waste Classifier", frame)
                    key = cv2_mod.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                else:
                    print(f"\r[CALIBRATING] {calib_msg}", end='', flush=True)
                continue

            # Phase 2: Object Motion / Presence Detection
            object_detected = False
            obj_crop = roi
            force_scan = 'scan' in dashboard_actions

            # Check key presses in GUI mode
            if not is_headless:
                key = cv2_mod.waitKey(1) & 0xFF
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
                    decision_text = None
                    continue
                elif key == ord(' '):
                    # Force scan current frame
                    log_info("Scan requested via Spacebar; score and stability checks remain active.")
                    force_scan = True
                elif key in [ord('1'), ord('2'), ord('3'), ord('4')]:
                    # Manual servo triggers for testing
                    cat_map = {
                        ord('1'): 'paper',
                        ord('2'): 'plastic',
                        ord('3'): 'metal',
                        ord('4'): 'food'
                    }
                    sel_cat = cat_map[key]
                    cfg = CATEGORY_CONFIG[sel_cat]
                    controller.trigger_sort(sel_cat, cfg)
                    log_sort_event(cfg['label'], 1.0, cfg['cmd'], f"MANUAL HOTKEY: {cfg['servo_desc']}")
                    locked_text = f"[MANUAL TRIGGER] {cfg['label'].upper()} ({cfg['servo_desc']})"
                    locked_color = cfg['color']
                    cooldown_until = time.monotonic() + args.cooldown
                    prediction_history = []
                    continue

            if not in_cooldown:
                frame_delta = cv2_mod.absdiff(background_frame.astype("uint8"), gray_roi)
                thresh = cv2_mod.threshold(frame_delta, 30, 255, cv2_mod.THRESH_BINARY)[1]
                thresh = cv2_mod.dilate(thresh, None, iterations=2)
                contours, _ = cv2_mod.findContours(thresh.copy(), cv2_mod.RETR_EXTERNAL, cv2_mod.CHAIN_APPROX_SIMPLE)

                for c in contours:
                    if cv2_mod.contourArea(c) > 5000:
                        object_detected = True
                        x, y, w, h = cv2_mod.boundingRect(c)
                        if not is_headless:
                            cv2_mod.rectangle(frame, (x1 + x, y1 + y), (x1 + x + w, y1 + y + h), (0, 255, 0), 2)

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
                inference_started = time.monotonic()
                pred_cat, conf, probs = classifier.predict(eval_img)
                last_probs = probs
                if bridge:
                    bridge.emit('state', category=pred_cat, score=float(conf), scores=probs,
                                inference_ms=round((time.monotonic() - inference_started) * 1000))

                if is_headless:
                    print(f"\r[EVAL] Paper: {probs['paper']*100:2.0f}% | Plastic: {probs['plastic']*100:2.0f}% | Metal: {probs['metal']*100:2.0f}% | Food scraps: {probs['food']*100:2.0f}% | Top: {pred_cat} ({conf*100:.0f}%)", end='', flush=True)

                if ((args.routing_policy == 'best-match' or
                     prediction_is_eligible(pred_cat, probs, args.threshold, args.margin))
                        and locked_text is None and (bridge is None or not (bridge.paused or bridge.stopping))):
                    decision_text = f"Best match: {CATEGORY_CONFIG[pred_cat]['label']}; checking stability..."
                    prediction_history.append((pred_cat, conf, probs))
                    if len(prediction_history) > args.stable_frames:
                        prediction_history.pop(0)

                    recent_classes = [p[0] for p in prediction_history]
                    # Trigger physical action once category is stable across required frames
                    if len(recent_classes) == args.stable_frames and (
                            args.routing_policy == 'best-match' or len(set(recent_classes)) == 1):
                        if args.routing_policy == 'best-match':
                            final_cat, avg_conf = best_window_prediction(prediction_history)
                        else:
                            final_cat = recent_classes[0]
                            avg_conf = np.mean([p[1] for p in prediction_history])
                        cfg = CATEGORY_CONFIG[final_cat]

                        # The dashboard pause/stop flag may change during inference.
                        if bridge and (bridge.paused or bridge.stopping):
                            prediction_history = []
                            continue
                        if bridge:
                            bridge.emit('state', phase='sorting', message='Executing route; commanded angles are not sensor measurements.')
                        capture = bridge.capture(eval_img) if bridge and hasattr(bridge, 'capture') else None
                        # Trigger Hardware Pan-Tilt Dump
                        controller.trigger_sort(final_cat, cfg)
                        if bridge:
                            bridge.emit('sort', category=final_cat, score=float(avg_conf),
                                        capture=capture, model=args.model)
                        pan, tilt, _ = saved.route(cfg)
                        route_desc = f"Pan {pan} -> Tilt {tilt} ({cfg['bin_pos']})"
                        log_sort_event(cfg['label'], avg_conf, cfg['cmd'], route_desc)

                        locked_text = f"[{avg_conf*100:.0f}%] {cfg['label'].upper()} -> {cfg['bin_pos']}"
                        locked_color = cfg['color']
                        prediction_history = []
                        cooldown_until = time.monotonic() + args.cooldown
                else:
                    prediction_history = []
                    if locked_text is None:
                        label = CATEGORY_CONFIG.get(pred_cat, {}).get('label', 'Unsupported item')
                        message = (f'Best guess: {label}; observation only, routing paused.'
                                   if bridge and bridge.paused else
                                   f'Best guess: {label}; low confidence, no sort.')
                        if decision_text != message:
                            log_info(message)
                        decision_text = message
            else:
                pip_preview = None
                if not in_cooldown:
                    prediction_history = []
                    # Dynamically adapt background slowly
                    cv2_mod.accumulateWeighted(gray_roi, background_frame, 0.05)
                    empty_frames += 1
                    if empty_frames > 12:
                        if bridge and empty_frames == 13:
                            bridge.emit('state', category=None, score=None, inference_ms=None, stable=0)
                        locked_text = None
                        decision_text = None
                        prediction_history = []
                        # Fade out probability display when tray is empty
                        last_probs = {c: max(0.0, last_probs[c] * 0.85) for c in classifier.categories}

            # Phase 4: Display Output
            if not is_headless:
                tray_color = (140, 140, 140) if in_cooldown else (255, 255, 255)
                cv2_mod.rectangle(frame, (x1, y1), (x2, y2), tray_color, 2)
                cv2_mod.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10),
                            cv2_mod.FONT_HERSHEY_SIMPLEX, 0.65, tray_color, 2, cv2_mod.LINE_AA)

                # Hardware status text
                hw_status = f"{controller.status_str} | {classifier.dev_desc}"
                hw_color = (0, 255, 120) if "SIMULATION" not in controller.status_str else (0, 190, 255)

                draw_hud(frame, last_probs, fps, hw_status, hw_color, in_cooldown,
                         locked_text or decision_text, locked_color if locked_text else (0, 100, 180),
                         show_help, pip_preview)
                cv2_mod.imshow("EcoSort Smart Bin - Waste Classifier", frame)
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}[EXIT] Stopped by user (Ctrl+C).{C_RESET}")

    finally:
        cam.release()
        if not is_headless:
            cv2_mod.destroyAllWindows()

        controller.close()
        if bridge:
            bridge.emit('state', phase='idle', paused=True, message='Session stopped. Camera released.')
        log_info("EcoSort shutdown complete.")


if __name__ == '__main__':
    main()
