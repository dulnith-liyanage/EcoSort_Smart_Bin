"""
Standardized ANSI logging utilities for EcoSort.
"""
from ecosort.config import C_RESET, C_BOLD, C_GREEN, C_CYAN, C_YELLOW, C_RED

def log_info(msg: str) -> None:
    print(f"{C_CYAN}[INFO]{C_RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{C_GREEN}[SUCCESS]{C_RESET} {msg}")

def log_warning(msg: str) -> None:
    print(f"{C_YELLOW}[WARNING]{C_RESET} {msg}")

# Compatibility alias for servo_control
log_warn = log_warning

def log_error(msg: str) -> None:
    print(f"{C_RED}[ERROR]{C_RESET} {msg}")

def log_sort_event(category: str, confidence: float, cmd: str, desc: str) -> None:
    print(f"\n{C_BOLD}{C_GREEN}>>> [SORT EVENT] {category.upper()} ({confidence*100:.1f}% confidence) -> Triggering '{cmd}' ({desc}){C_RESET}\n")
