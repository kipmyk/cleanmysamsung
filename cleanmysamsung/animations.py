"""
Animation Settings Management Module
Provides independent settings tracking, verification, and non-destructive rollbacks.
"""

from .adb import run_adb

def get_animation_scales(device):
    """
    Return dictionary of current animation scales.
    Preserves raw values without assuming defaults.
    """
    w, _, _ = run_adb(["shell", "settings", "get", "global", "window_animation_scale"], device, check=False)
    t, _, _ = run_adb(["shell", "settings", "get", "global", "transition_animation_scale"], device, check=False)
    a, _, _ = run_adb(["shell", "settings", "get", "global", "animator_duration_scale"], device, check=False)
    return {
        "window_animation_scale": w if w and w != "null" else "1.0",
        "transition_animation_scale": t if t and t != "null" else "1.0",
        "animator_duration_scale": a if a and a != "null" else "1.0",
    }

def set_animation_scales(device, scales_dict):
    """
    Set animation scales and verify that the system persisted the changes.
    Returns (success: bool, applied: dict, error: str)
    """
    for key, val in scales_dict.items():
        _, err, code = run_adb(["shell", "settings", "put", "global", key, str(val)], device, check=False)
        if code != 0:
            return False, {}, f"Failed to set {key}: {err}"

    # Post-verification
    current = get_animation_scales(device)
    for key, val in scales_dict.items():
        if current.get(key) != str(val):
            return False, current, f"Verification failed for {key}: expected {val}, got {current.get(key)}"

    return True, current, ""

def speedup_animations(device, scale="0.5"):
    """
    Overclock window and transition animation scales with explicit verification.
    Returns (success: bool, original_scales: dict, error: str)
    """
    orig = get_animation_scales(device)
    target = {
        "window_animation_scale": scale,
        "transition_animation_scale": scale,
        "animator_duration_scale": scale
    }
    success, applied, err = set_animation_scales(device, target)
    if success:
        print(f"⚡ Animations set to {scale}x (Overclocked from {orig['window_animation_scale']}x)")
    return success, orig, err

def restore_animations(device, original_scales):
    """
    Restore previously recorded animation scales.
    """
    if not original_scales:
        return False, "No original scales provided"
    success, applied, err = set_animation_scales(device, original_scales)
    return success, err
