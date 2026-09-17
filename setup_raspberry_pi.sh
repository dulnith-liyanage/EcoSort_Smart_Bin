#!/bin/bash
# ==============================================================================
#  EcoSort Smart Bin - Raspberry Pi Automated Environment Setup Script
#  Supports: Direct Raspberry Pi I2C (PCA9685) and USB Arduino Modes
# ==============================================================================
set -e

echo "=========================================================="
echo "  ECOSORT SMART BIN: RASPBERRY PI ENVIRONMENT SETUP"
echo "=========================================================="

echo "[1/6] Updating system packages & installing required system libraries..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libgl1 \
    libopenblas-dev \
    v4l-utils \
    i2c-tools \
    python3-smbus

echo "[2/6] Enabling Raspberry Pi I2C interface for PCA9685..."
# Automatically enable hardware I2C interface (GPIO 2 & 3)
sudo raspi-config nonint do_i2c 0 || echo "I2C interface enabled."

echo "[3/6] Configuring user permissions (I2C & Serial)..."
# Adding user to i2c and dialout groups avoids needing sudo
sudo usermod -a -G dialout,i2c $USER

echo "[4/6] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
    echo "Virtual environment created at ./venv"
else
    echo "Virtual environment already exists."
fi

echo "[5/6] Installing Python packages (PyTorch, Transformers, OpenCV, Adafruit-ServoKit)..."
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt

echo "[6/6] Pre-caching OpenAI Zero-Shot CLIP ViT-B/32 model weights..."
./venv/bin/python -c "
from transformers import CLIPModel, CLIPProcessor
print('Downloading and caching OpenAI CLIP weights (~350MB)...')
CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
print('Pre-caching complete! CLIP is ready for offline real-time inference.')
"

echo "=========================================================="
echo "  SETUP COMPLETE!"
echo "=========================================================="
echo ""
echo "Verify your I2C PCA9685 connection (Should show '40' on bus 1):"
echo "  i2cdetect -y 1"
echo ""
echo "To run the smart bin on your Raspberry Pi:"
echo "  1. Headless mode (SSH without monitor):"
echo "     ./venv/bin/python live_smart_bin.py --headless --stable-frames 2"
echo ""
echo "  2. Desktop mode (with HDMI monitor attached):"
echo "     ./venv/bin/python live_smart_bin.py --stable-frames 2"
echo ""
echo "NOTE: If this is your first time setting up I2C, run:"
echo "      newgrp i2c"
echo "      or reboot your Pi ('sudo reboot') so I2C permissions take effect."
echo "=========================================================="
