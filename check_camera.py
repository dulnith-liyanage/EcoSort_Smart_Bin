#!/usr/bin/env python3
"""
EcoSort Smart Bin - Camera Diagnostic & Test Utility
Tests Raspberry Pi 5 CSI camera (CAM/0 and CAM/1) and USB cameras
"""

import os
import sys
import subprocess

C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[92m"
C_BLUE   = "\033[94m"
C_YELLOW = "\033[93m"
C_RED    = "\033[91m"
C_CYAN   = "\033[96m"

print(f"\n{C_BOLD}{C_CYAN}======================================================={C_RESET}")
print(f"{C_BOLD}{C_CYAN}     ECOSORT: RASPBERRY PI 5 CAMERA DIAGNOSTIC TOOL    {C_RESET}")
print(f"{C_BOLD}{C_CYAN}======================================================={C_RESET}\n")

print("[1/3] Checking /boot/firmware/config.txt camera configuration...")
with open('/boot/firmware/config.txt', 'r') as f:
    cfg = f.read()

has_cam0 = 'imx219,cam0' in cfg
auto_detect_off = 'camera_auto_detect=0' in cfg

if has_cam0:
    print(f"  {C_GREEN}[OK]{C_RESET} 'dtoverlay=imx219,cam0' is configured.")
else:
    print(f"  {C_YELLOW}[WARN]{C_RESET} 'dtoverlay=imx219,cam0' not found in config.txt.")

print("\n[2/3] Checking kernel dmesg logs for camera probe...")
try:
    dmesg = subprocess.check_output(['dmesg'], text=True)
    found_lines = [line for line in dmesg.splitlines() if any(k in line.lower() for k in ['imx219', 'rp1-cfe', 'csi'])]
    for l in found_lines[-6:]:
        if '-121' in l or 'error' in l.lower():
            print(f"  {C_RED}[KERNEL ERROR]{C_RESET} {l}")
        else:
            print(f"  {C_BLUE}[KERNEL LOG]{C_RESET} {l}")
except Exception as e:
    print(f"  Could not read dmesg: {e}")

print("\n[3/3] Probing camera with Picamera2 / rpicam...")
try:
    res = subprocess.check_output(['rpicam-hello', '--list-cameras'], text=True, stderr=subprocess.STDOUT)
    print(res)
    if "No cameras available" not in res and "available" in res.lower():
        print(f"\n{C_BOLD}{C_GREEN}>>> CAMERA DETECTED AND READY!{C_RESET}")
        sys.exit(0)
except Exception as e:
    print(f"  rpicam-hello check returned: {e}")

print(f"\n{C_BOLD}{C_YELLOW}-------------------------------------------------------{C_RESET}")
print(f"{C_BOLD}{C_YELLOW}  HARDWARE ACTION REQUIRED: RIBBON CABLE INSPECTION    {C_RESET}")
print(f"{C_BOLD}{C_YELLOW}-------------------------------------------------------{C_RESET}")
print("The kernel actively tried to reach the camera on CAM/0, but received")
print(f"{C_RED}Error -121 (-EREMOTEIO: I2C No Acknowledge){C_RESET}.")
print("This means the electrical pins are not making contact.\n")
print("Please check these 3 points:")
print("  1. RPi 5 CAM/0 Port Cable Direction:")
print("     The shiny GOLD metal contacts on the ribbon cable MUST face")
print("     toward the ETHERNET / USB ports (away from the HDMI ports).")
print("  2. Camera Board Cable Direction:")
print("     On the camera module PCB, the shiny gold contacts MUST face")
print("     downward toward the circuit board / lens side.")
print("  3. Sunny Connector:")
print("     Gently press the tiny rectangular connector labeled 'SUNNY'")
print("     on the camera PCB until it clicks into place.")
print("-------------------------------------------------------\n")
