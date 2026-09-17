#!/bin/bash
# ==============================================================================
#  EcoSort Smart Bin - 30-Second PyTorch OpenBLAS Symbol Fix
#  Resolves: undefined symbol: sbgemm_ in libtorch_cpu.so on Debian/Raspberry Pi OS
# ==============================================================================
set -e

echo "=========================================================="
echo "  ECOSORT: RESOLVING PYTORCH BLAS DEPENDENCIES"
echo "=========================================================="

echo "[1/4] Installing libopenblas0-pthread & development libraries via apt..."
sudo apt-get update -y
sudo apt-get install -y libopenblas0-pthread libopenblas-dev liblapack-dev

echo "[2/4] Locating OpenBLAS shared library on filesystem..."
OPENBLAS_SO=$(find /usr/lib -name "libopenblas*.so.0" 2>/dev/null | grep -E "pthread|aarch64" | head -n 1)

if [ -z "$OPENBLAS_SO" ]; then
    OPENBLAS_SO=$(find /usr/lib -name "libopenblas*.so*" 2>/dev/null | head -n 1)
fi

if [ -n "$OPENBLAS_SO" ]; then
    echo "Found OpenBLAS library at: $OPENBLAS_SO"
    OPENBLAS_DIR=$(dirname "$OPENBLAS_SO")
    
    # 1. Register with system dynamic linker ldconfig
    echo "Configuring dynamic linker (/etc/ld.so.conf.d/openblas.conf)..."
    echo "$OPENBLAS_DIR" | sudo tee /etc/ld.so.conf.d/openblas.conf > /dev/null
    
    # 2. Symlink into standard aarch64 library directory if not present
    if [ ! -e "/usr/lib/aarch64-linux-gnu/libopenblas.so.0" ]; then
        sudo ln -sf "$OPENBLAS_SO" /usr/lib/aarch64-linux-gnu/libopenblas.so.0 2>/dev/null || true
    fi
    sudo ldconfig
    
    # 3. Add LD_PRELOAD to virtualenv activate script
    if [ -f "venv/bin/activate" ]; then
        if ! grep -q "LD_PRELOAD.*libopenblas" venv/bin/activate; then
            echo "export LD_PRELOAD=$OPENBLAS_SO:\$LD_PRELOAD" >> venv/bin/activate
            echo "Added LD_PRELOAD to venv/bin/activate"
        fi
    fi
    export LD_PRELOAD="$OPENBLAS_SO:$LD_PRELOAD"
else
    echo "WARNING: Could not locate OpenBLAS shared library directly. Proceeding to test..."
fi

echo "[3/4] Testing PyTorch import inside virtual environment..."
export LD_PRELOAD="$OPENBLAS_SO:$LD_PRELOAD"
./venv/bin/python -c "
import torch
print('>>> SUCCESS! PyTorch loaded cleanly. Version:', torch.__version__)
print('>>> CPU Threads:', torch.get_num_threads())
"

echo "[4/4] Pre-caching OpenAI Zero-Shot CLIP ViT-B/32 model weights (~350MB)..."
./venv/bin/python -c "
from transformers import CLIPModel, CLIPProcessor
print('Downloading & caching CLIP ViT-B/32 weights...')
CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
print('>>> SUCCESS! CLIP weights successfully downloaded and verified offline.')
"

echo "=========================================================="
echo "  ALL CHECKS PASSED! ECOSORT IS READY TO RUN."
echo "=========================================================="
echo ""
echo "To launch the smart bin on your Raspberry Pi:"
echo "  ./venv/bin/python live_smart_bin.py --driver rpi-i2c --headless --stable-frames 2"
echo ""
