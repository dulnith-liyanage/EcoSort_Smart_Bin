import cv2
import numpy as np
import os
import sys
import ctypes
import json
import argparse
import time
import gc
from PIL import Image
import servo_settings

# On Linux ARM64 (Raspberry Pi), pre-load OpenBLAS globally to resolve BLAS symbols (sbgemm_)
if sys.platform.startswith('linux'):
    import glob
    _candidate_paths = [
        '/usr/lib/aarch64-linux-gnu/openblas-pthread/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/openblas-openmp/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/openblas-serial/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/libopenblas.so',
        '/usr/lib/arm-linux-gnueabihf/openblas-pthread/libopenblas.so.0',
        '/usr/lib/arm-linux-gnueabihf/libopenblas.so.0',
    ]
    _loaded = False
    for _lib_path in _candidate_paths:
        if os.path.exists(_lib_path):
            try:
                ctypes.CDLL(_lib_path, mode=ctypes.RTLD_GLOBAL)
                _loaded = True
                break
            except Exception:
                pass
    if not _loaded:
        for _glob_path in glob.glob('/usr/lib/**/*openblas*.so*', recursive=True):
            try:
                ctypes.CDLL(_glob_path, mode=ctypes.RTLD_GLOBAL)
                break
            except Exception:
                pass

import torch
from transformers import CLIPProcessor, CLIPModel, AutoModel, AutoProcessor

# =====================================================================
#  EcoSort Smart Bin - Waste Classifier 4-Way Waste Sorting System
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
# Project routing labels; local collection acceptance must be checked separately.
# 2x2 Grid Layout (Center-Mounted Pan-Tilt System)
# Quadrant 2: Front-Left  -> Pan: 135°, Tilt: 35° (Forward dump)
# Quadrant 1: Front-Right -> Pan: 45°,  Tilt: 35° (Forward dump)
# Quadrant 3: Rear-Left   -> Pan: 45°,  Tilt: 145° (Backward dump along 45° axis)
# Quadrant 4: Rear-Right  -> Pan: 135°, Tilt: 145° (Backward dump along 135° axis)
CATEGORY_CONFIG = {
    'paper': {
        'label': 'Paper & Cardboard (Blue Bin)',
        'bin_pos': 'Front-Left',
        'cmd': 'P',
        'pan': 135,
        'tilt': 35,
        'servo_desc': 'Front-Left bin',
        'color': (235, 135, 40),      # Project bin Blue (BGR: B=235, G=135, R=40)
        'prompts': ["a photo of a piece of paper", "a photo of newspaper", "a photo of cardboard packaging"]
    },
    'plastic': {
        'label': 'Rigid Plastic (Orange Bin)',
        'bin_pos': 'Front-Right',
        'cmd': 'M',
        'pan': 45,
        'tilt': 35,
        'servo_desc': 'Front-Right bin',
        'color': (30, 140, 255),     # Project bin Orange (BGR: B=30, G=140, R=255)
        'prompts': ["a photo of a plastic bottle", "a photo of a rigid plastic food container", "a photo of a plastic cup"]
    },
    'metal': {
        'label': 'Metal Cans (Green Bin)',
        'bin_pos': 'Rear-Left',
        'cmd': 'O',
        'pan': 45,
        'tilt': 145,
        'servo_desc': 'Rear-Left bin',
        'color': (60, 210, 60),      # Project bin Green (BGR: B=60, G=210, R=60)
        'prompts': ["a photo of an aluminium drink can", "a photo of a metal food tin", "a photo of a crushed metal can"]
    },
    'food': {
        'label': 'Fruit & Vegetable Scraps (Red Bin)',
        'bin_pos': 'Rear-Right',
        'cmd': 'G',
        'pan': 135,
        'tilt': 145,
        'servo_desc': 'Rear-Right bin',
        'color': (60, 60, 230),      # Project bin Red (BGR: B=60, G=60, R=230)
        'prompts': ["a photo of a banana peel", "a photo of orange peels", "a photo of vegetable scraps"]
    }
}

UNKNOWN_PROMPTS = [
    'a photo of a glass bottle', 'a photo of a plastic bag',
    'a photo of a foil snack wrapper', 'a photo of an empty tray',
    'a photo of a human hand',
]


MODEL_NAMES = {'clip': 'openai/clip-vit-base-patch32',
               'siglip2': 'google/siglip2-base-patch16-224'}


def best_supported_prediction(probabilities):
    """Always name one of four bins, without disguising unsupported evidence."""
    if any(key not in probabilities or not np.isfinite(probabilities[key])
           for key in CATEGORY_CONFIG):
        raise ValueError('Missing or invalid supported-class scores.')
    category = max(CATEGORY_CONFIG, key=lambda key: probabilities[key])
    return category, float(probabilities[category])


def prepare_classifier_image(bgr):
    """Pad to square so the model's centre crop does not cut off item edges."""
    if bgr.ndim != 3 or bgr.shape[2] != 3 or not bgr.size:
        raise ValueError('Expected a non-empty three-channel BGR image.')
    image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    side = max(image.size)
    square = Image.new('RGB', (side, side), color=(128, 128, 128))
    square.paste(image, ((side-image.width)//2, (side-image.height)//2))
    return square


def build_prompt_groups(custom=None):
    groups = {key: list(cfg['prompts']) for key, cfg in CATEGORY_CONFIG.items()}
    groups['unknown'] = list(UNKNOWN_PROMPTS)
    if custom is not None:
        if not isinstance(custom, dict) or set(custom) - set(groups):
            raise ValueError('Prompt keys must be paper, plastic, metal, food or unknown. Old category files must be migrated.')
        for key, value in custom.items():
            prompts = [value] if isinstance(value, str) else value
            if not isinstance(prompts, list) or not prompts or any(
                    not isinstance(p, str) or not p.strip() for p in prompts):
                raise ValueError(f'{key}: supply a non-empty string or list of short descriptions.')
            groups[key] = [p.strip() for p in prompts]
    return groups


def ensemble_text_features(features, group_sizes):
    features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    groups = torch.split(features, group_sizes)
    means = torch.stack([group.mean(dim=0) for group in groups])
    return means / means.norm(dim=-1, keepdim=True).clamp_min(1e-12)


def prediction_is_eligible(category, probabilities, threshold=0.60, margin=0.15):
    """Reject unknown, invalid scores, ties and ambiguous supported classes."""
    if category not in CATEGORY_CONFIG or category not in probabilities:
        return False
    values = np.asarray(list(probabilities.values()), dtype=float)
    if len(values) < 2 or not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        return False
    score = probabilities[category]
    runner_up = max(p for key, p in probabilities.items() if key != category)
    return bool(score >= threshold and score > runner_up and score - runner_up >= margin)


class BaseServoController:
    """Base interface for Servo Actuation."""
    def trigger_sort(self, cat_key, cfg):
        raise NotImplementedError

    def reset_home(self):
        pass

    def close(self):
        pass

    @property
    def status_str(self):
        return "SIMULATION"

class DirectPca9685Controller(BaseServoController):
    """Direct Raspberry Pi I2C control of PCA9685 (2x MG996R Servos in 2x2 Grid)."""
    def __init__(self, pan_channel=0, tilt_channel=1, address=0x40):
        if not (0 <= pan_channel < 16 and 0 <= tilt_channel < 16) or pan_channel == tilt_channel:
            raise ValueError('Pan and tilt must use distinct PCA9685 channels from 0 to 15.')
        self.calibration = servo_settings.load_calibration()
        # Reject unreachable routes BEFORE initialising hardware or emitting HOME.
        self.calibration.validate_routes(CATEGORY_CONFIG.values())
        try:
            from adafruit_servokit import ServoKit
        except ImportError:
            raise RuntimeError("Missing 'adafruit-circuitpython-servokit'. Install it via: pip install adafruit-circuitpython-servokit")

        self._hardware_lock = servo_settings.acquire_device_lock(address)
        self.kit = servo_settings.prepare_servo_kit(ServoKit(channels=16, address=address))
        self.pan_ch = pan_channel
        self.tilt_ch = tilt_channel

        # Standard MG996R servo pulse width range (600us to 2400us)
        self.kit.servo[self.pan_ch].set_pulse_width_range(600, 2400)
        self.kit.servo[self.tilt_ch].set_pulse_width_range(600, 2400)

        self.current_pan = self.calibration.pan_home
        self.current_tilt = self.calibration.tilt_home
        self._pan_released = False
        self.reset_home()
        log_success(f"Direct Raspberry Pi I2C PCA9685 Connected (Pan: Ch{pan_channel}, Tilt: Ch{tilt_channel})")

    def release_idle_pan(self):
        """Quiet the verified unloaded vertical pan axis; always retain tilt torque."""
        if (self.calibration.release_pan_at_home
                and self.current_pan == self.calibration.pan_home
                and self.current_tilt == self.calibration.tilt_home):
            time.sleep(0.25)
            self.kit.servo[self.pan_ch].angle = None
            self._pan_released = True

    def _smooth_move(self, channel, from_ang, to_ang, step_delay=None):
        if channel == self.pan_ch and self._pan_released:
            self.kit.servo[self.pan_ch].angle = self.current_pan
            self._pan_released = False
            time.sleep(0.15)
        from_ang = int(from_ang)
        to_ang = int(to_ang)
        if from_ang == to_ang:
            return
        step = 1 if to_ang > from_ang else -1
        step_delay = max(step_delay or self.calibration.step_delay, self.calibration.step_delay)
        for a in range(from_ang, to_ang + step, step):
            self.kit.servo[channel].angle = a
            time.sleep(step_delay)

    def trigger_sort(self, cat_key, cfg):
        target_pan, target_tilt, shake_tilt = self.calibration.route(cfg)
        bin_pos = cfg.get('bin_pos', 'Unknown')
        log_info(f"[RPi I2C PCA9685] Sorting into {cfg['label']} ({bin_pos}) | Pan: {target_pan}°, Tilt: {target_tilt}°...")

        # A previous interrupted/manual cycle may have left the tray tilted.
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        # Step 1: Pan with tilt at the calibrated level position.
        self._smooth_move(self.pan_ch, self.current_pan, target_pan)
        self.current_pan = target_pan
        time.sleep(0.20)

        # Step 2: Tilt downward along pan (forward 35° or backward 145°)
        log_info(f"[RPi I2C PCA9685] Tilting tray to {target_tilt}° to drop waste into {bin_pos}...")
        self._smooth_move(self.tilt_ch, self.current_tilt, target_tilt)
        self.current_tilt = target_tilt
        time.sleep(1.0)

        if shake_tilt != target_tilt:
            self._smooth_move(self.tilt_ch, target_tilt, shake_tilt)
            self.current_tilt = shake_tilt
            time.sleep(0.12)
            self._smooth_move(self.tilt_ch, shake_tilt, target_tilt)
            self.current_tilt = target_tilt
            time.sleep(0.20)

        # Step 4: Return tilt to the calibrated HOME.
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        time.sleep(0.20)

        # Step 5: Return pan to the calibrated HOME.
        self._smooth_move(self.pan_ch, self.current_pan, self.calibration.pan_home)
        self.current_pan = self.calibration.pan_home
        self.release_idle_pan()
        log_success(f"2x2 Sort cycle for {cfg['label']} ({bin_pos}) complete. Returned to HOME.")

    def reset_home(self):
        self._smooth_move(self.tilt_ch, self.current_tilt, self.calibration.tilt_home)
        self.current_tilt = self.calibration.tilt_home
        self._smooth_move(self.pan_ch, self.current_pan, self.calibration.pan_home)
        self.current_pan = self.calibration.pan_home
        # The initial cached angles are not measurements. Always send HOME.
        self.kit.servo[self.tilt_ch].angle = self.calibration.tilt_home
        self.kit.servo[self.pan_ch].angle = self.calibration.pan_home
        self._pan_released = False
        self.release_idle_pan()

    def close(self):
        self.reset_home()

    @property
    def status_str(self):
        return "Hardware: RASPBERRY PI I2C (PCA9685 - 2x2 Grid)"

class SimulatedServoController(BaseServoController):
    """Simulation fallback."""
    def trigger_sort(self, cat_key, cfg):
        target_pan, target_tilt, _ = servo_settings.load_calibration().route(cfg)
        bin_pos = cfg.get('bin_pos', 'Unknown')
        log_info(f"[SIMULATION TRIGGER] Pan {target_pan}° -> Tilt {target_tilt}° ({bin_pos}) -> {cfg['label']}")

    @property
    def status_str(self):
        return "Hardware: SIMULATION (2x2 Grid)"

def init_hardware_controller(driver_mode='auto', pan_ch=0, tilt_ch=1):
    """Initializes the Raspberry Pi I2C PCA9685 servo controller or simulation."""
    if driver_mode == 'sim':
        log_info("Running in SIMULATION MODE as requested.")
        return SimulatedServoController()

    # Configuration failures (including missing files/keys) are not missing
    # hardware and must not silently fall back to simulation.
    saved = servo_settings.load_calibration()
    saved.validate_routes(CATEGORY_CONFIG.values())

    try:
        if os.path.exists('/dev/i2c-1') or driver_mode in ['auto', 'rpi-i2c', 'pca9685']:
            return DirectPca9685Controller(pan_channel=pan_ch, tilt_channel=tilt_ch)
    except (ValueError, servo_settings.HardwareInUseError):
        # A mechanically unreachable calibration must never masquerade as a
        # successful simulation fallback in automatic mode.
        raise
    except Exception as e:
        if driver_mode != 'auto':
            raise RuntimeError(f'Requested hardware driver failed: {e}') from e
        log_warning(f"Direct Raspberry Pi I2C PCA9685 unavailable ({e}). Falling back to simulation.")

    return SimulatedServoController()

def configure_cpu_threads(requested=2):
    """Leave CPU capacity for the desktop/VNC; this cannot repair undervoltage."""
    if type(requested) is not int or not 1 <= requested <= 4:
        raise ValueError('CPU threads must be an integer from 1 to 4.')
    threads = min(requested, os.cpu_count() or 1)
    torch.set_num_threads(threads)
    cv2.setNumThreads(1)
    return threads


class ClipClassifier:
    """Zero-Shot CLIP Classifier with pre-computed text embeddings and custom prompt support."""
    def __init__(self, model_name="openai/clip-vit-base-patch32", custom_prompts=None, cpu_threads=2):
        if model_name not in MODEL_NAMES.values():
            raise ValueError('Use one of the supported CLIP or SigLIP 2 checkpoints.')
        self.model_name = model_name
        self.is_siglip = model_name == MODEL_NAMES['siglip2']
        # Select best available hardware acceleration
        if torch.backends.mps.is_available():
            self.device = "mps"
            self.dev_desc = "Apple Silicon GPU (Metal MPS)"
        elif torch.cuda.is_available():
            self.device = "cuda"
            self.dev_desc = "NVIDIA CUDA GPU"
        else:
            self.device = "cpu"
            # Reduce CPU contention and peak load alongside the VNC desktop.
            num_cores = os.cpu_count() or 1
            num_threads = configure_cpu_threads(cpu_threads)
            self.dev_desc = f"CPU (Raspberry Pi / {num_cores} cores, {num_threads} threads)"

        log_info(f"Loading vision-language model '{model_name}' on {self.dev_desc}...")
        model_class = AutoModel if self.is_siglip else CLIPModel
        processor_class = AutoProcessor if self.is_siglip else CLIPProcessor
        # The official CLIP checkpoint/cache uses a PyTorch state dictionary;
        # SigLIP 2 supplies safetensors. Never request remote Python model code.
        # weights_only keeps legacy CLIP loading restricted to weight tensors.
        try:
            # Cache-first: loads instantly if already downloaded locally
            self.model = model_class.from_pretrained(model_name, local_files_only=True, use_safetensors=self.is_siglip, weights_only=True).to(self.device)
            self.processor = processor_class.from_pretrained(model_name, local_files_only=True)
        except OSError:
            log_info(f"Cache miss or update needed. Downloading '{model_name}' from Hugging Face Hub...")
            self.model = model_class.from_pretrained(model_name, use_safetensors=self.is_siglip, weights_only=True).to(self.device)
            self.processor = processor_class.from_pretrained(model_name)
        self.model.eval()

        self.categories = list(CATEGORY_CONFIG.keys())
        
        groups = build_prompt_groups(custom_prompts)
        self.categories = list(groups)
        self.prompts = [prompt for group in groups.values() for prompt in group]
        if self.is_siglip:
            self.prompts = [p.replace('a photo of ', 'This is a photo of ', 1) + '.' for p in self.prompts]

        # Encode short descriptions separately, then average normalised features
        # within each class. Different prompt counts do not weight the bins.
        text_inputs = self.processor(text=self.prompts, return_tensors="pt", truncation=True,
                                     padding='max_length' if self.is_siglip else True,
                                     max_length=64 if self.is_siglip else 77).to(self.device)
        with torch.no_grad():
            text_outputs = self.model.get_text_features(**text_inputs)
            text_features = self._extract_tensor(text_outputs)
            self.text_features = ensemble_text_features(text_features, [len(g) for g in groups.values()])

        # Labels are fixed for this run. Keep their embeddings, then free the
        # unused text encoder (especially large in SigLIP 2) for the 4 GB Pi.
        self.model.text_model = None
        if hasattr(self.model, 'text_projection'):
            self.model.text_projection = None
        gc.collect()

        log_success("Classifier ready: every detected item gets a best-match bin; motor checks remain separate.")

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
        """Return the best supported bin, its relative score and all scores, including unknown."""
        pil_img = prepare_classifier_image(bgr_crop)

        image_inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_outputs = self.model.get_image_features(**image_inputs)
            image_features = self._extract_tensor(image_outputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Cosine similarity between visual embedding and category text embeddings
            similarity = (image_features @ self.text_features.T).squeeze(0)
            # Relative choice scores, not calibrated correctness probabilities
            # or SigLIP's independent image/text sigmoid probabilities.
            scale = self.model.logit_scale.exp().clamp(max=100)
            probs = (similarity * scale).softmax(dim=-1).cpu().numpy()

        probs_dict = {cat: float(p) for cat, p in zip(self.categories, probs)}
        category, confidence = best_supported_prediction(probs_dict)
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

class CameraCapture:
    """Unified camera capture supporting Raspberry Pi CSI cameras (Picamera2) and USB/standard cameras (OpenCV)."""
    def __init__(self, camera_idx=0):
        self.use_picam2 = False
        self.picam2 = None
        self.cap = None

        # 1. On Raspberry Pi / Linux, prioritize native Picamera2 for CSI camera (CAM 0 / CAM 1)
        if sys.platform.startswith('linux'):
            try:
                from picamera2 import Picamera2
                log_info("[CAMERA] Probing Raspberry Pi CSI Camera via Picamera2...")
                self.picam2 = Picamera2(camera_idx)
                config = self.picam2.create_preview_configuration(
                    main={"size": (640, 480), "format": "RGB888"},
                    controls={"FrameRate": 15}
                )
                self.picam2.configure(config)
                self.picam2.start()
                self.use_picam2 = True
                log_success("[CAMERA] Raspberry Pi CSI Camera online via Picamera2 (640x480)!")
                return
            except Exception as e:
                if self.picam2 is not None:
                    self.picam2.close()
                    self.picam2 = None
                log_info(f"[CAMERA] Picamera2 not active ({e}). Falling back to OpenCV VideoCapture...")

        # 2. Fallback to OpenCV (USB cameras, libcamerify wrapper, or desktop)
        log_info(f"[CAMERA] Opening OpenCV VideoCapture (Index {camera_idx})...")
        if sys.platform.startswith('linux'):
            self.cap = cv2.VideoCapture(camera_idx, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(camera_idx)
        else:
            self.cap = cv2.VideoCapture(camera_idx)

        if not self.cap.isOpened() and camera_idx != 0:
            log_warning(f"[CAMERA] Index {camera_idx} failed. Falling back to Index 0...")
            self.cap = cv2.VideoCapture(0)

        if self.cap is not None and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            log_success(f"[CAMERA] OpenCV VideoCapture ready on index {camera_idx}.")

    def is_opened(self):
        if self.use_picam2:
            return True
        return self.cap is not None and self.cap.isOpened()

    def read(self):
        if self.use_picam2 and self.picam2 is not None:
            try:
                # libcamera RGB888 is B,G,R byte order, as OpenCV expects.
                return True, self.picam2.capture_array()
            except Exception:
                return False, None
        elif self.cap is not None:
            return self.cap.read()
        return False, None

    def release(self):
        if self.use_picam2 and self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
        if self.cap is not None:
            self.cap.release()

def main(bridge=None):
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

    # Initialize CLIP
    classifier = ClipClassifier(model_name=MODEL_NAMES[args.model], custom_prompts=custom_prompts,
                                cpu_threads=args.cpu_threads)

    if bridge and bridge.stopping:
        return

    # Initialize Hardware Controller (Direct Raspberry Pi I2C PCA9685 or Simulation)
    controller = init_hardware_controller(
        driver_mode=args.driver,
        pan_ch=args.pan_ch,
        tilt_ch=args.tilt_ch
    )

    # Initialize Camera (Picamera2 CSI or OpenCV USB)
    try:
        cam = CameraCapture(args.camera)
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

    print("\n" + "="*72)
    print(f" {C_BOLD}{C_GREEN}ECOSORT SMART BIN: 2-AXIS PAN-TILT 2x2 GRID WASTE SEGREGATION{C_RESET}")
    print("   Four project waste routes; verify local collection requirements separately")
    print(f"   Device Acceleration : {classifier.dev_desc}")
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
    print("="*72 + "\n")

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
                         'cooldown' if in_cooldown else 'observing' if bridge.paused else 'ready')
                bridge.emit('state', phase=phase, paused=bridge.paused, fps=round(fps, 1),
                            scores=last_probs, stable=len(prediction_history),
                            calibration_progress=min(1.0, frames_read / calibration_frames),
                            message=locked_text or decision_text or ('Keep the tray empty while calibrating.' if phase == 'calibrating' else 'Place one item in the scanning area.'))

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

            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)

            # Phase 1: Background Tray Calibration
            if frames_read < calibration_frames:
                if background_frame is None:
                    background_frame = gray_roi.astype("float")
                else:
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.1)

                frames_read += 1
                if bridge and frames_read == calibration_frames:
                    bridge.calibrated()
                calib_msg = f"Calibrating Empty Tray... {frames_read}/{calibration_frames}"

                if not is_headless:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                    cv2.rectangle(frame, (0, h_f - 55), (w_f, h_f), (245, 245, 245), -1)
                    cv2.putText(frame, calib_msg, (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (0, 120, 255), 2)
                    cv2.imshow("EcoSort Smart Bin - Waste Classifier", frame)
                    key = cv2.waitKey(1) & 0xFF
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
                    # Discard this pre-movement frame; do not auto-sort it again.
                    continue

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
                inference_started = time.monotonic()
                pred_cat, conf, probs = classifier.predict(eval_img)
                last_probs = probs
                if bridge:
                    bridge.emit('state', category=pred_cat, score=float(conf), scores=probs,
                                inference_ms=round((time.monotonic() - inference_started) * 1000))

                if is_headless:
                    print(f"\r[EVAL] Paper: {probs['paper']*100:2.0f}% | Plastic: {probs['plastic']*100:2.0f}% | Metal: {probs['metal']*100:2.0f}% | Food scraps: {probs['food']*100:2.0f}% | Top: {pred_cat} ({conf*100:.0f}%)", end='', flush=True)

                if (prediction_is_eligible(pred_cat, probs, args.threshold, args.margin)
                        and locked_text is None and (bridge is None or not (bridge.paused or bridge.stopping))):
                    decision_text = f"Best match: {CATEGORY_CONFIG[pred_cat]['label']}; checking stability..."
                    prediction_history.append((pred_cat, conf))
                    if len(prediction_history) > args.stable_frames:
                        prediction_history.pop(0)

                    recent_classes = [p[0] for p in prediction_history]
                    # Trigger physical action once category is stable across required frames
                    if len(recent_classes) == args.stable_frames and len(set(recent_classes)) == 1:
                        final_cat = recent_classes[0]
                        avg_conf = np.mean([p[1] for p in prediction_history])
                        cfg = CATEGORY_CONFIG[final_cat]

                        # The dashboard pause/stop flag may change during inference.
                        if bridge and (bridge.paused or bridge.stopping):
                            prediction_history = []
                            continue
                        if bridge:
                            bridge.emit('state', phase='sorting', message='Executing route; commanded angles are not sensor measurements.')
                        # Trigger Hardware Pan-Tilt Dump
                        controller.trigger_sort(final_cat, cfg)
                        if bridge:
                            bridge.emit('sort', category=final_cat, score=float(avg_conf))
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
                    cv2.accumulateWeighted(gray_roi, background_frame, 0.05)
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
                cv2.rectangle(frame, (x1, y1), (x2, y2), tray_color, 2)
                cv2.putText(frame, "EcoSort Scanning Tray", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, tray_color, 2, cv2.LINE_AA)

                # Hardware status text
                hw_status = f"{controller.status_str} | {classifier.dev_desc}"
                hw_color = (0, 255, 120) if "SIMULATION" not in controller.status_str else (0, 190, 255)

                draw_hud(frame, last_probs, fps, hw_status, hw_color, in_cooldown,
                         locked_text or decision_text, locked_color if locked_text else (0, 100, 180),
                         show_help, pip_preview)
                cv2.imshow("EcoSort Smart Bin - Waste Classifier", frame)
            else:
                # Modest sleep in headless mode to prevent high CPU utilization
                time.sleep(0.01)

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}[EXIT] Stopped by user (Ctrl+C).{C_RESET}")

    finally:
        cam.release()
        if not is_headless:
            cv2.destroyAllWindows()

        controller.close()
        if bridge:
            bridge.emit('state', phase='idle', paused=True, message='Session stopped. Camera released.')
        log_info("EcoSort shutdown complete.")

if __name__ == '__main__':
    main()
