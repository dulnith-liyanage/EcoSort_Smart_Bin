"""
Hardware device locking via POSIX advisory locks to prevent concurrent controller access.
"""
import os
from pathlib import Path


class HardwareInUseError(RuntimeError):
    """Another process owns the motor driver."""


def acquire_device_lock(address, directory='/tmp'):
    """Hold this file handle for the controller lifetime. No motor I/O here."""
    import fcntl
    if type(address) is not int or not 0x08 <= address <= 0x77:
        raise ValueError('Expected a non-reserved seven-bit I2C address.')
    path = Path(directory) / f'ecosort-pca9685-{address:02x}.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    lock = os.fdopen(fd, 'r+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        lock.close()
        raise HardwareInUseError(
            'Another EcoSort process controls this PCA9685. Close the other '
            'sorter/calibrator before starting; no servo commands were sent.'
        ) from error
    return lock
