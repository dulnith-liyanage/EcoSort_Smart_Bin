"""
Platform compatibility helpers (OpenBLAS runtime symbol resolution).
"""
import ctypes
import glob
import os
import sys

_OPENBLAS_LOADED = False

def preload_openblas():
    """
    On Linux ARM64 (e.g. Raspberry Pi 5), preload OpenBLAS globally.
    Resolves undefined BLAS symbols (like sbgemm_) in PyTorch/libtorch_cpu.so.
    """
    global _OPENBLAS_LOADED
    if _OPENBLAS_LOADED or not sys.platform.startswith('linux'):
        return

    candidate_paths = [
        '/usr/lib/aarch64-linux-gnu/openblas-pthread/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/openblas-openmp/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/openblas-serial/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/libopenblas.so.0',
        '/usr/lib/aarch64-linux-gnu/libopenblas.so',
        '/usr/lib/arm-linux-gnueabihf/openblas-pthread/libopenblas.so.0',
        '/usr/lib/arm-linux-gnueabihf/libopenblas.so.0',
    ]
    for lib_path in candidate_paths:
        if os.path.exists(lib_path):
            try:
                ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                _OPENBLAS_LOADED = True
                return
            except Exception:
                pass

    for glob_path in glob.glob('/usr/lib/**/*openblas*.so*', recursive=True):
        try:
            ctypes.CDLL(glob_path, mode=ctypes.RTLD_GLOBAL)
            _OPENBLAS_LOADED = True
            return
        except Exception:
            pass
