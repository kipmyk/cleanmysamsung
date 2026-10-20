"""
Animation Settings Management Module
Author: Mike Kipruto (https://mike.co.ke/contact)

Provides independent animation settings tracking, verification, and non-destructive rollbacks.
"""

from typing import Any, Dict, Optional, Tuple
from .adb import run_adb

ANIMATION_KEYS = (
    "window_animation_scale",
    "transition_animation_scale",
    "animator_duration_scale",
)

def is_valid_scale(val: Any) -> bool:
    """Validate that animation scale is a non-negative float."""
    try:
        f = float(val)
        return f >= 0.0
    except (ValueError, TypeError):
        return False

def get_animation_scales(device: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Return dictionary of current animation scales.
    Preserves raw captured values and records None for missing or null values,
    avoiding assumed default values.
    """
    scales: Dict[str, Optional[str]] = {}
    for key in ANIMATION_KEYS:
        val, _, code = run_adb(["shell", "settings", "get", "global", key], device, check=False)
        val = val.strip()
        if code == 0 and val and val != "null" and is_valid_scale(val):
            scales[key] = val
        else:
            scales[key] = None
    return scales

def set_animation_scales(
    device: Optional[str],
    scales_dict: Dict[str, str]
) -> Tuple[bool, Dict[str, Optional[str]], str]:
    """
    Set animation scales and verify that the system persisted the changes.
    Returns (success: bool, applied: dict, error: str)
    """
    for key, val in scales_dict.items():
        if key not in ANIMATION_KEYS:
            continue
        if not is_valid_scale(str(val)):
            return False, {}, f"Invalid scale value for {key}: '{val}'"
        _, err, code = run_adb(["shell", "settings", "put", "global", key, str(val)], device, check=False)
        if code != 0:
            return False, {}, f"Failed to set {key}: {err}"

    current = get_animation_scales(device)
    for key, val in scales_dict.items():
        if key not in ANIMATION_KEYS:
            continue
        if current.get(key) != str(val):
            return False, current, f"Verification failed for {key}: expected {val}, got {current.get(key)}"

    return True, current, ""

def speedup_animations(
    device: Optional[str],
    scale: str = "0.5"
) -> Tuple[bool, Dict[str, Optional[str]], str]:
    """
    Set window and transition animation scales with explicit verification.
    Returns (success: bool, original_scales: dict, error: str)
    """
    if not is_valid_scale(scale):
        return False, {}, f"Invalid target scale: '{scale}'"

    orig = get_animation_scales(device)
    target = {
        "window_animation_scale": scale,
        "transition_animation_scale": scale,
        "animator_duration_scale": scale
    }
    success, applied, err = set_animation_scales(device, target)
    if success:
        orig_win = orig.get("window_animation_scale") or "standard"
        print(f"Animations set to {scale}x (previously {orig_win}x)")
    return success, orig, err

def restore_animations(
    device: Optional[str],
    original_scales: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Restore previously recorded animation scales.
    Restores only keys that contain valid non-None original values.
    """
    if not original_scales or not isinstance(original_scales, dict):
        return False, "No valid original scales provided"

    to_restore: Dict[str, str] = {}
    for key in ANIMATION_KEYS:
        val = original_scales.get(key)
        if val is not None and is_valid_scale(str(val)):
            to_restore[key] = str(val)

    if not to_restore:
        return False, "No valid captured animation values to restore"

    success, _, err = set_animation_scales(device, to_restore)
    return success, err
