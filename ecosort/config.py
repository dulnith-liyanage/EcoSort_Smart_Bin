"""
Configuration settings, category metadata, and hardware mapping for EcoSort.
"""
from pathlib import Path

# Project root directory and default calibration file
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_CALIBRATION_FILE = PROJECT_ROOT / 'servo_calibration.json'

# ANSI Terminal Formatting
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_BLUE   = "\033[94m"
C_YELLOW = "\033[93m"
C_RED    = "\033[91m"
C_CYAN   = "\033[96m"
C_MAG    = "\033[95m"

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
        'color': (235, 135, 40),      # Blue (BGR: B=235, G=135, R=40)
        'prompts': [
            "a photo of a piece of paper",
            "a photo of newspaper",
            "a photo of cardboard packaging"
        ]
    },
    'plastic': {
        'label': 'Rigid Plastic (Orange Bin)',
        'bin_pos': 'Front-Right',
        'cmd': 'M',
        'pan': 45,
        'tilt': 35,
        'servo_desc': 'Front-Right bin',
        'color': (30, 140, 255),     # Orange (BGR: B=30, G=140, R=255)
        'prompts': [
            "a photo of a plastic bottle",
            "a photo of a rigid plastic food container",
            "a photo of a plastic cup"
        ]
    },
    'metal': {
        'label': 'Metal Cans (Green Bin)',
        'bin_pos': 'Rear-Left',
        'cmd': 'O',
        'pan': 45,
        'tilt': 145,
        'servo_desc': 'Rear-Left bin',
        'color': (60, 210, 60),      # Green (BGR: B=60, G=210, R=60)
        'prompts': [
            "a photo of an aluminium drink can",
            "a photo of a metal food tin",
            "a photo of a crushed metal can"
        ]
    },
    'food': {
        'label': 'Fruit & Vegetable Scraps (Red Bin)',
        'bin_pos': 'Rear-Right',
        'cmd': 'G',
        'pan': 135,
        'tilt': 145,
        'servo_desc': 'Rear-Right bin',
        'color': (60, 60, 230),      # Red (BGR: B=60, G=60, R=230)
        'prompts': [
            "a photo of a banana peel",
            "a photo of orange peels",
            "a photo of vegetable scraps"
        ]
    }
}

# Derived bin mapping for manual testing CLI (keeps single source of truth)
BINS = {
    '1': {
        'name': 'Paper & Cardboard',
        'color': 'Blue',
        'pos': CATEGORY_CONFIG['paper']['bin_pos'],
        'pan': CATEGORY_CONFIG['paper']['pan'],
        'tilt': CATEGORY_CONFIG['paper']['tilt'],
        'mode': 'Forward Dump'
    },
    '2': {
        'name': 'Rigid Plastic',
        'color': 'Orange',
        'pos': CATEGORY_CONFIG['plastic']['bin_pos'],
        'pan': CATEGORY_CONFIG['plastic']['pan'],
        'tilt': CATEGORY_CONFIG['plastic']['tilt'],
        'mode': 'Forward Dump'
    },
    '3': {
        'name': 'Metal Cans',
        'color': 'Green',
        'pos': CATEGORY_CONFIG['metal']['bin_pos'],
        'pan': CATEGORY_CONFIG['metal']['pan'],
        'tilt': CATEGORY_CONFIG['metal']['tilt'],
        'mode': 'Backward Dump'
    },
    '4': {
        'name': 'Fruit & Vegetable Scraps',
        'color': 'Red/Black',
        'pos': CATEGORY_CONFIG['food']['bin_pos'],
        'pan': CATEGORY_CONFIG['food']['pan'],
        'tilt': CATEGORY_CONFIG['food']['tilt'],
        'mode': 'Backward Dump'
    }
}

UNKNOWN_PROMPTS = [
    'a photo of a glass bottle',
    'a photo of a plastic bag',
    'a photo of a foil snack wrapper',
    'a photo of an empty tray',
    'a photo of a human hand',
]

MODEL_NAMES = {
    'clip': 'openai/clip-vit-base-patch32',
    'siglip2': 'google/siglip2-base-patch16-224'
}
