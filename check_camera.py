#!/usr/bin/env python3
"""Read-only camera diagnostics; reports observations without guessing faults."""
from ecosort.hardware.camera import probe_camera


def main():
    return probe_camera()


if __name__ == '__main__':
    raise SystemExit(main())
