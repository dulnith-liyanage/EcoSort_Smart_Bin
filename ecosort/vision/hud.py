"""
Real-time OpenCV HUD overlays (telemetry, confidence bars, PiP thumbnail, shortcuts modal).
"""
import cv2
from ecosort.config import CATEGORY_CONFIG


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
    cv2.putText(frame, "RELATIVE MATCH SCORES", (card_x + 12, card_y + 20),
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
            ("[1] : PAPER (Blue Bin)", "Manual test: front-left"),
            ("[2] : PLASTIC (Orange Bin)", "Manual test: front-right"),
            ("[3] : METAL CANS (Green Bin)", "Manual test: rear-left"),
            ("[4] : FOOD SCRAPS (Red Bin)", "Manual test: rear-right"),
            ("[C] : Recalibrate Tray", "Resets background subtraction"),
            ("[Space] : Scan", "Keeps score/stability checks"),
            ("[H] : Close Help Menu", "Toggles this screen"),
            ("[Q] : Quit EcoSort", "Resets servos to neutral & exits")
        ]

        sy = my1 + 72
        for key_text, desc in shortcuts:
            cv2.putText(frame, key_text, (mx1 + 25, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"- {desc}", (mx1 + 220, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1, cv2.LINE_AA)
            sy += 22
