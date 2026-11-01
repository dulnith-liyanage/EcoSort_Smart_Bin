"""
Zero-Shot Multi-Modal Classifier using OpenAI CLIP and Google SigLIP 2.
"""
import gc
import os
import sys
import cv2
import numpy as np
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel, AutoModel, AutoProcessor

from ecosort.config import CATEGORY_CONFIG, UNKNOWN_PROMPTS, MODEL_NAMES
from ecosort.logging import log_info, log_success


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
    square.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
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


def best_window_prediction(history):
    """Choose one bin from several frames without renormalising the match score."""
    if not history:
        raise ValueError('At least one prediction is required.')
    for _, _, scores in history:
        values = np.asarray([scores[key] for key in CATEGORY_CONFIG], dtype=float)
        if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
            raise ValueError('Invalid supported-class scores.')
    means = {key: float(np.mean([scores[key] for _, _, scores in history]))
             for key in CATEGORY_CONFIG}
    return best_supported_prediction(means)


def configure_cpu_threads(requested=2):
    """Leave CPU capacity for the desktop/VNC; this cannot repair undervoltage."""
    if type(requested) is not int or not 1 <= requested <= 4:
        raise ValueError('CPU threads must be an integer from 1 to 4.')
    live = sys.modules.get('live_smart_bin')
    os_mod = getattr(live, 'os', os) if live else os
    torch_mod = getattr(live, 'torch', torch) if live else torch
    cv2_mod = getattr(live, 'cv2', cv2) if live else cv2

    threads = min(requested, os_mod.cpu_count() or 1)
    torch_mod.set_num_threads(threads)
    cv2_mod.setNumThreads(1)
    return threads


class ClipClassifier:
    """Zero-Shot CLIP Classifier with pre-computed text embeddings and custom prompt support."""
    def __init__(self, model_name="openai/clip-vit-base-patch32", custom_prompts=None, cpu_threads=2):
        if model_name not in MODEL_NAMES.values():
            raise ValueError('Use one of the supported CLIP or SigLIP 2 checkpoints.')
        self.model_name = model_name
        self.is_siglip = model_name == MODEL_NAMES['siglip2']

        live = sys.modules.get('live_smart_bin')
        torch_mod = getattr(live, 'torch', torch) if live else torch
        os_mod = getattr(live, 'os', os) if live else os
        configure_fn = getattr(live, 'configure_cpu_threads', configure_cpu_threads) if live else configure_cpu_threads

        # Select best available hardware acceleration
        if torch_mod.backends.mps.is_available():
            self.device = "mps"
            self.dev_desc = "Apple Silicon GPU (Metal MPS)"
        elif torch_mod.cuda.is_available():
            self.device = "cuda"
            self.dev_desc = "NVIDIA CUDA GPU"
        else:
            self.device = "cpu"
            # Reduce CPU contention and peak load alongside the VNC desktop.
            num_cores = os_mod.cpu_count() or 1
            num_threads = configure_fn(cpu_threads)
            self.dev_desc = f"CPU (Raspberry Pi / {num_cores} cores, {num_threads} threads)"

        log_info(f"Loading vision-language model '{model_name}' on {self.dev_desc}...")
        
        if self.is_siglip:
            model_class = getattr(live, 'AutoModel', AutoModel) if live else AutoModel
            processor_class = getattr(live, 'AutoProcessor', AutoProcessor) if live else AutoProcessor
        else:
            model_class = getattr(live, 'CLIPModel', CLIPModel) if live else CLIPModel
            processor_class = getattr(live, 'CLIPProcessor', CLIPProcessor) if live else CLIPProcessor

        try:
            # Cache-first: loads instantly if already downloaded locally
            self.model = model_class.from_pretrained(
                model_name, local_files_only=True, use_safetensors=self.is_siglip, weights_only=True
            ).to(self.device)
            self.processor = processor_class.from_pretrained(model_name, local_files_only=True)
        except OSError:
            log_info(f"Cache miss or update needed. Downloading '{model_name}' from Hugging Face Hub...")
            self.model = model_class.from_pretrained(
                model_name, use_safetensors=self.is_siglip, weights_only=True
            ).to(self.device)
            self.processor = processor_class.from_pretrained(model_name)
        self.model.eval()

        groups = build_prompt_groups(custom_prompts)
        self.categories = list(groups)
        self.prompts = [prompt for group in groups.values() for prompt in group]
        if self.is_siglip:
            self.prompts = [p.replace('a photo of ', 'This is a photo of ', 1) + '.' for p in self.prompts]

        # Encode short descriptions separately, then average normalised features
        # within each class. Different prompt counts do not weight the bins.
        text_inputs = self.processor(
            text=self.prompts,
            return_tensors="pt",
            truncation=True,
            padding='max_length' if self.is_siglip else True,
            max_length=64 if self.is_siglip else 77
        ).to(self.device)

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
            scale = self.model.logit_scale.exp().clamp(max=100)
            probs = (similarity * scale).softmax(dim=-1).cpu().numpy()

        probs_dict = {cat: float(p) for cat, p in zip(self.categories, probs)}
        category, confidence = best_supported_prediction(probs_dict)
        return category, confidence, probs_dict
