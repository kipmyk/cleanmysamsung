"""
Device Profile & Compatibility Detection Module
Gathers hardware specifications, Android release, One UI version,
and performs strict compatibility checks against debloat profiles.
"""

from .adb import run_adb

def parse_battery_info(device):
    """Retrieve dumpsys battery and safely parse fields in Python without shell pipes."""
    stdout, _, _ = run_adb(["shell", "dumpsys", "battery"], device, check=False)
    info = {"level": "Unknown", "voltage": "Unknown", "temperature": "Unknown"}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("level:"):
            info["level"] = line.split(":", 1)[1].strip()
        elif line.startswith("voltage:"):
            info["voltage"] = line.split(":", 1)[1].strip()
        elif line.startswith("temperature:"):
            temp_raw = line.split(":", 1)[1].strip()
            if temp_raw.isdigit():
                info["temperature"] = f"{int(temp_raw)/10:.1f}°C"
    return info

def get_device_info(device):
    """
    Return comprehensive dictionary of device properties.
    """
    model, _, _ = run_adb(["shell", "getprop", "ro.product.model"], device, check=False)
    mfg, _, _ = run_adb(["shell", "getprop", "ro.product.manufacturer"], device, check=False)
    release, _, _ = run_adb(["shell", "getprop", "ro.build.version.release"], device, check=False)
    oneui_raw, _, _ = run_adb(["shell", "getprop", "ro.build.version.oneui"], device, check=False)
    patch, _, _ = run_adb(["shell", "getprop", "ro.build.version.security_patch"], device, check=False)
    fingerprint, _, _ = run_adb(["shell", "getprop", "ro.build.fingerprint"], device, check=False)
    serial, _, _ = run_adb(["shell", "getprop", "ro.serialno"], device, check=False)

    # Safe One UI version calculation
    if oneui_raw.isdigit():
        oneui_ver = f"{int(oneui_raw)/10000:.2f}"
    else:
        oneui_ver = oneui_raw or "Stock/Unknown"

    battery = parse_battery_info(device)

    return {
        "target": device,
        "serial": serial or device,
        "manufacturer": mfg.capitalize() if mfg else "Samsung",
        "model": model or "Unknown",
        "android_version": release or "Unknown",
        "oneui_version": oneui_ver,
        "security_patch": patch or "Unknown",
        "fingerprint": fingerprint or "Unknown",
        "battery": battery
    }

def probe_device(device):
    """
    Pretty-print device hardware, OS, and battery diagnostics.
    """
    info = get_device_info(device)
    print("=" * 70)
    print(" 📱 SAMSUNG GALAXY DEVICE PROBE")
    print("=" * 70)
    print(f"Device Target   : {info['target']}")
    print(f"Manufacturer    : {info['manufacturer']}")
    print(f"Model Number    : {info['model']}")
    print(f"Android Version : {info['android_version']} (One UI {info['oneui_version']})")
    print(f"Security Patch  : {info['security_patch']}")
    print(f"Battery Level   : {info['battery']['level']}% (Temp: {info['battery']['temperature']})")
    print("=" * 70 + "\n")
    return info

def check_profile_compatibility(device_info, profile_data):
    """
    Validate device model and Android version against profile constraints.
    Returns (is_compatible: bool, warning_msg: str)
    """
    target_models = profile_data.get("target_models", [])
    if target_models and device_info["model"] not in target_models:
        return False, f"Device model '{device_info['model']}' is not in profile target models: {target_models}"

    android_ver = device_info.get("android_version")
    if android_ver and android_ver.isdigit():
        ver_int = int(android_ver)
        min_ver = profile_data.get("min_android_version")
        max_ver = profile_data.get("max_android_version")
        if min_ver and ver_int < min_ver:
            return False, f"Device Android version ({ver_int}) is below profile minimum ({min_ver})"
        if max_ver and ver_int > max_ver:
            return False, f"Device Android version ({ver_int}) is above profile maximum ({max_ver})"

    return True, ""
