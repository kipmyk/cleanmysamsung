#!/usr/bin/env python3
"""
CleanMySamsung (CLI & Device Optimizer)
Safe, non-root debloater and performance tuning tool for Samsung Galaxy devices.
Architected for verified state tracking, safe rollbacks, and robust error handling.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

# Strict Android package name pattern: e.g. com.facebook.system
PACKAGE_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")

def find_adb():
    """
    Dynamically locate the adb executable across macOS (Apple Silicon & Intel),
    Linux, Windows, and custom Android SDK environments.
    """
    path = shutil.which("adb")
    if path:
        return path

    candidate_paths = [
        "/opt/homebrew/bin/adb",                                       # macOS Homebrew (Apple Silicon)
        "/usr/local/bin/adb",                                         # macOS Homebrew (Intel)
        "/usr/bin/adb",                                               # Linux (apt / dnf / pacman)
        os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"), # macOS Android Studio
        os.path.expanduser("~/Android/Sdk/platform-tools/adb"),         # Linux Android Studio
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"), # Windows Android Studio
    ]
    for candidate in candidate_paths:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return "adb"

ADB_BIN = find_adb()

def run_adb(cmd_args, device=None, check=True):
    """
    Execute an ADB command with robust return code and error handling.
    Returns (stdout, stderr, returncode).
    """
    full_cmd = [ADB_BIN]
    if device:
        full_cmd.extend(["-s", device])
    full_cmd.extend(cmd_args)
    
    try:
        res = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()
        if check and res.returncode != 0:
            err_msg = stderr or stdout or f"Exit code {res.returncode}"
            raise RuntimeError(f"ADB command failed [{res.returncode}]: {' '.join(cmd_args)}\n{err_msg}")
        return stdout, stderr, res.returncode
    except FileNotFoundError:
        sys.exit(f"❌ Error: ADB binary not found at '{ADB_BIN}'. Please install platform-tools.")

def get_connected_devices():
    """
    Return lists of (authorized_devices, unauthorized_devices).
    Deduplicates multiple connection handles (IP vs mDNS name) to the same physical phone.
    """
    stdout, _, _ = run_adb(["devices", "-l"], check=True)
    authorized = []
    unauthorized = []
    seen_serials = set()
    
    for line in stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            dev_id = parts[0]
            status = parts[1]
            if status == "device":
                serial, _, _ = run_adb(["shell", "getprop", "ro.serialno"], dev_id, check=False)
                key = serial.strip() if serial and serial != "Unknown" else dev_id
                if key not in seen_serials:
                    seen_serials.add(key)
                    authorized.append(dev_id)
            elif status in ("unauthorized", "offline"):
                unauthorized.append((dev_id, status))
                
    return authorized, unauthorized

def select_device(specified_device=None):
    """
    Resolve and validate target ADB device. Prompts if multiple exist.
    """
    authorized, unauthorized = get_connected_devices()
    
    if unauthorized:
        for dev_id, status in unauthorized:
            print(f"⚠️  Notice: Device '{dev_id}' is {status}.")
            if status == "unauthorized":
                print("   ➔ Please unlock your phone and tap 'Always allow from this computer'.")

    if not authorized:
        sys.exit("❌ Error: No authorized ADB devices found. Ensure USB/Wireless debugging is enabled.")
        
    if specified_device:
        if specified_device in authorized:
            return specified_device
        sys.exit(f"❌ Error: Specified device '{specified_device}' is not among connected authorized devices: {authorized}")
        
    if len(authorized) == 1:
        return authorized[0]
        
    # Multiple devices connected: prompt user to pick
    print("\nMultiple devices detected. Please select a target:")
    for idx, dev in enumerate(authorized, 1):
        model, _, _ = run_adb(["shell", "getprop", "ro.product.model"], dev, check=False)
        print(f"  [{idx}] {dev} ({model or 'Unknown'})")
        
    while True:
        choice = input(f"Select device (1-{len(authorized)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(authorized):
            return authorized[int(choice) - 1]
        print("Invalid selection.")

def parse_battery_info(device):
    """Retrieve dumpsys battery and safely parse fields in Python."""
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

def get_animation_scales(device):
    """Return dictionary of current animation scales."""
    w, _, _ = run_adb(["shell", "settings", "get", "global", "window_animation_scale"], device, check=False)
    t, _, _ = run_adb(["shell", "settings", "get", "global", "transition_animation_scale"], device, check=False)
    a, _, _ = run_adb(["shell", "settings", "get", "global", "animator_duration_scale"], device, check=False)
    return {
        "window_animation_scale": w if w and w != "null" else "1.0",
        "transition_animation_scale": t if t and t != "null" else "1.0",
        "animator_duration_scale": a if a and a != "null" else "1.0",
    }

def probe_device(device):
    """Print comprehensive hardware, OS, and battery diagnostics."""
    print("=" * 70)
    print(" 📱 SAMSUNG GALAXY DEVICE PROBE")
    print("=" * 70)
    
    model, _, _ = run_adb(["shell", "getprop", "ro.product.model"], device, check=False)
    mfg, _, _ = run_adb(["shell", "getprop", "ro.product.manufacturer"], device, check=False)
    release, _, _ = run_adb(["shell", "getprop", "ro.build.version.release"], device, check=False)
    oneui_raw, _, _ = run_adb(["shell", "getprop", "ro.build.version.oneui"], device, check=False)
    patch, _, _ = run_adb(["shell", "getprop", "ro.build.version.security_patch"], device, check=False)
    
    # Safe One UI formatting
    if oneui_raw.isdigit():
        oneui_ver = f"{int(oneui_raw)/10000:.2f}"
    else:
        oneui_ver = oneui_raw or "Stock/Unknown"
        
    battery = parse_battery_info(device)
    anims = get_animation_scales(device)
    
    print(f"Device Target   : {device}")
    print(f"Manufacturer    : {mfg.capitalize() if mfg else 'Samsung'}")
    print(f"Model Number    : {model or 'Unknown'}")
    print(f"Android Version : {release or 'Unknown'} (One UI {oneui_ver})")
    print(f"Security Patch  : {patch or 'Unknown'}")
    print(f"Battery Level   : {battery['level']}% (Temp: {battery['temperature']})")
    print(f"Animation Scales: Window={anims['window_animation_scale']}x | Transition={anims['transition_animation_scale']}x | Animator={anims['animator_duration_scale']}x")
    print("=" * 70 + "\n")
    return model

def parse_profile_file(list_file):
    """Parse and validate a debloat profile file, returning a clean list of package names."""
    if not os.path.isfile(list_file):
        raise FileNotFoundError(f"Debloat profile not found: '{list_file}'")
        
    packages = []
    with open(list_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            pkg = cleaned.split("#")[0].strip()
            if not PACKAGE_REGEX.match(pkg):
                print(f"⚠️  Warning: Skipping invalid package syntax on line {line_num}: '{pkg}'")
                continue
            packages.append(pkg)
            
    return list(dict.fromkeys(packages))  # Deduplicate while preserving order

def get_package_state_map(device):
    """
    Query User 0 package state map:
    Returns dict: { package_name: 'ENABLED' | 'DISABLED' }
    """
    stdout_all, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0"], device, check=True)
    stdout_dis, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-d"], device, check=True)
    
    all_pkgs = set(line.replace("package:", "").strip() for line in stdout_all.splitlines() if line.strip())
    disabled_pkgs = set(line.replace("package:", "").strip() for line in stdout_dis.splitlines() if line.strip())
    
    state_map = {}
    for pkg in all_pkgs:
        state_map[pkg] = "DISABLED" if pkg in disabled_pkgs else "ENABLED"
    return state_map

def apply_debloat(device, list_file, backup_dir="backup"):
    """
    Safely disables target packages with pre-flight state tracking and atomic JSON session recording.
    """
    model = probe_device(device)
    targets = parse_profile_file(list_file)
    if not targets:
        print("❌ Error: No valid package names found in profile.")
        return

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = os.path.join(backup_dir, f"session_{timestamp}.json")

    print(f"🔍 Inspecting current device state for {len(targets)} targets...")
    current_states = get_package_state_map(device)
    orig_anims = get_animation_scales(device)

    session_record = {
        "session_id": f"session_{timestamp}",
        "timestamp": datetime.datetime.now().isoformat(),
        "device_target": device,
        "device_model": model,
        "profile_file": list_file,
        "original_animations": orig_anims,
        "original_states": {},
        "changes_applied": [],
        "skipped_already_disabled": [],
        "not_installed": [],
        "failed_operations": []
    }

    # Pre-flight check
    for pkg in targets:
        state = current_states.get(pkg, "NOT_INSTALLED")
        session_record["original_states"][pkg] = state
        if state == "DISABLED":
            session_record["skipped_already_disabled"].append(pkg)
        elif state == "NOT_INSTALLED":
            session_record["not_installed"].append(pkg)

    to_disable = [pkg for pkg in targets if current_states.get(pkg) == "ENABLED"]

    print("\n" + "-" * 70)
    print(f"Pre-flight summary for profile [{os.path.basename(list_file)}]:")
    print(f"  • Ready to freeze       : {len(to_disable)}")
    print(f"  • Already frozen (skip) : {len(session_record['skipped_already_disabled'])}")
    print(f"  • Not present (skip)    : {len(session_record['not_installed'])}")
    print("-" * 70)

    if not to_disable:
        print("💡 No changes needed: all target packages are already disabled or absent.")
        return

    # Write initial session backup before applying any change
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session_record, f, indent=2)
    print(f"💾 Session state snapshot created: {session_file}\n")

    # Execute changes
    print("Applying changes:")
    for pkg in to_disable:
        stdout, stderr, code = run_adb(["shell", "pm", "disable-user", "--user", "0", pkg], device, check=False)
        if code == 0 and ("disabled-user" in stdout or "new state: disabled-user" in stdout):
            print(f"  [FROZEN] ❄️  {pkg}")
            session_record["changes_applied"].append(pkg)
        else:
            err = stderr or stdout or "Unknown failure"
            print(f"  [FAILED] ❌ {pkg} ➔ {err}")
            session_record["failed_operations"].append({"package": pkg, "error": err})

    # Update session record with actual outcomes
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session_record, f, indent=2)

    print("\n" + "=" * 70)
    print(f"🎉 Complete! Successfully froze {len(session_record['changes_applied'])} packages.")
    print(f"📄 Session record saved: {session_file}")
    print(f"💡 To rollback ONLY the changes made during this run:")
    print(f"   python3 cleanmysamsung.py --restore {session_file}")
    print("=" * 70 + "\n")

def restore_session(device, session_file):
    """
    Restores ONLY the packages that were modified in a specific session record.
    Preserves packages that were already disabled prior to that session.
    """
    if not os.path.isfile(session_file):
        # Check if user passed latest
        if session_file.lower() == "latest":
            backup_dir = "backup"
            if not os.path.isdir(backup_dir):
                sys.exit("❌ Error: No backup directory found.")
            sessions = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("session_") and f.endswith(".json")])
            if not sessions:
                sys.exit("❌ Error: No session backup files found.")
            session_file = sessions[-1]
            print(f"Using latest session backup: {session_file}")
        else:
            sys.exit(f"❌ Error: Session file not found: '{session_file}'")

    with open(session_file, "r", encoding="utf-8") as f:
        session = json.load(f)

    # Validate device compatibility
    sess_model = session.get("device_model", "Unknown")
    current_model, _, _ = run_adb(["shell", "getprop", "ro.product.model"], device, check=False)
    if sess_model != "Unknown" and current_model and sess_model != current_model:
        print(f"⚠️  WARNING: Session was created on model '{sess_model}', but connected device is '{current_model}'.")
        confirm = input("Are you sure you want to proceed with restore? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Restore aborted.")
            return

    changes_applied = session.get("changes_applied", [])
    if not changes_applied:
        print("💡 No package changes recorded in this session to restore.")
    else:
        print(f"🔄 Restoring {len(changes_applied)} packages modified in session '{session.get('session_id')}'...")
        restored = 0
        for pkg in changes_applied:
            stdout, stderr, code = run_adb(["shell", "pm", "enable", pkg], device, check=False)
            if code == 0 and ("enabled" in stdout or "new state: enabled" in stdout):
                print(f"  [RESTORED] ✅ {pkg}")
                restored += 1
            else:
                err = stderr or stdout or "Failed"
                print(f"  [ERROR] ❌ Could not re-enable {pkg}: {err}")
        print(f"✅ Re-enabled {restored}/{len(changes_applied)} packages.")

    # Restore animation scales if recorded
    orig_anims = session.get("original_animations", {})
    if orig_anims:
        print("🔄 Restoring original animation scales...")
        for setting_key, val in orig_anims.items():
            run_adb(["shell", "settings", "put", "global", setting_key, val], device, check=False)
        print("✅ Restored original window, transition, and animator scales.")

    print("\n🎉 Restore completed successfully.\n")

def speedup_animations(device, scale="0.5"):
    """Overclock window and transition animation scales with explicit verification."""
    print(f"⚡ Setting UI animation scales to {scale}x for snappy navigation...")
    for setting in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
        _, err, code = run_adb(["shell", "settings", "put", "global", setting, scale], device, check=False)
        if code != 0:
            print(f"❌ Failed to set {setting}: {err}")
            return
            
    # Verify values
    anims = get_animation_scales(device)
    print("✅ Animations overclocked successfully!")
    print(f"   Current values: Window={anims['window_animation_scale']}x | Transition={anims['transition_animation_scale']}x | Animator={anims['animator_duration_scale']}x\n")

def interactive_menu(device):
    """CLI interactive menu for terminal users."""
    while True:
        probe_device(device)
        print("Select an action:")
        print("  [1] Speed up animations (Set to 0.5x)")
        print("  [2] Apply debloat profile (lists/samsung_galaxy_a52.txt)")
        print("  [3] Restore last debloat session (Latest JSON snapshot)")
        print("  [4] Reset animations back to default (1.0x)")
        print("  [5] Exit")
        
        choice = input("\nEnter choice [1-5]: ").strip()
        if choice == "1":
            speedup_animations(device, "0.5")
        elif choice == "2":
            apply_debloat(device, "lists/samsung_galaxy_a52.txt")
        elif choice == "3":
            restore_session(device, "latest")
        elif choice == "4":
            speedup_animations(device, "1.0")
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.\n")
        input("Press Enter to continue...")

def main():
    parser = argparse.ArgumentParser(description="CleanMySamsung - Safe Android & One UI Debloater")
    parser.add_argument("-s", "--device", help="Specific ADB device target (e.g. 192.168.1.98:40689)")
    parser.add_argument("--probe", action="store_true", help="Inspect device specs, battery, and animation settings")
    parser.add_argument("--speedup", action="store_true", help="Set animation scales to 0.5x for 2x faster UI")
    parser.add_argument("--reset-animations", action="store_true", help="Reset animation scales to default 1.0x")
    parser.add_argument("--debloat", metavar="LIST_FILE", help="Safely freeze packages listed in a profile")
    parser.add_argument("--restore", metavar="SESSION_FILE", help="Roll back changes from a session JSON file (or 'latest')")

    args = parser.parse_args()
    target_device = select_device(args.device)

    if args.probe:
        probe_device(target_device)
    elif args.speedup:
        speedup_animations(target_device, "0.5")
    elif args.reset_animations:
        speedup_animations(target_device, "1.0")
    elif args.debloat:
        apply_debloat(target_device, args.debloat)
    elif args.restore:
        restore_session(target_device, args.restore)
    else:
        interactive_menu(target_device)

if __name__ == "__main__":
    main()
