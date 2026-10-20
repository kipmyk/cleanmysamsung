#!/usr/bin/env python3
"""
CleanMySamsung (CLI & Device Optimizer)
Safe, non-root debloater and performance tuning tool for Samsung Galaxy devices.
Inspired by cleanyourtv and modern Android optimization practices.
"""

import argparse
import os
import subprocess
import shutil

def find_adb():
    """
    Dynamically locate the adb executable across macOS (Apple Silicon & Intel),
    Linux, Windows, and custom Android SDK environments.
    """
    # 1. Check system PATH first (standard cross-platform lookup)
    path = shutil.which("adb")
    if path:
        return path

    # 2. Check platform-specific standard installation directories
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

    return "adb"  # Default fallback to PATH invocation

ADB_BIN = find_adb()

def run_adb(cmd_args, device=None, capture=True):
    """Run an ADB command and return stdout/stderr."""
    full_cmd = [ADB_BIN]
    if device:
        full_cmd.extend(["-s", device])
    full_cmd.extend(cmd_args)
    try:
        if capture:
            res = subprocess.run(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return res.stdout.strip()
        else:
            subprocess.run(full_cmd, check=True)
            return ""
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"

def get_connected_devices():
    """List all ADB devices currently connected."""
    out = run_adb(["devices"])
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices

def probe_device(device):
    """Print comprehensive hardware and software profile of the Samsung device."""
    print("=" * 68)
    print(" 📱 SAMSUNG GALAXY DEVICE PROBE")
    print("=" * 68)
    
    model = run_adb(["shell", "getprop", "ro.product.model"], device)
    mfg = run_adb(["shell", "getprop", "ro.product.manufacturer"], device)
    release = run_adb(["shell", "getprop", "ro.build.version.release"], device)
    oneui = run_adb(["shell", "getprop", "ro.build.version.oneui"], device)
    patch = run_adb(["shell", "getprop", "ro.build.version.security_patch"], device)
    battery = run_adb(["shell", "dumpsys battery | grep level | awk '{print $2}'"], device)
    
    # Animations
    anim_w = run_adb(["shell", "settings get global window_animation_scale"], device)
    anim_t = run_adb(["shell", "settings get global transition_animation_scale"], device)
    anim_d = run_adb(["shell", "settings get global animator_duration_scale"], device)
    
    print(f"Device Target   : {device}")
    print(f"Manufacturer    : {mfg.capitalize()}")
    print(f"Model Number    : {model}")
    print(f"Android Version : {release} (One UI {int(oneui)/10000 if oneui.isdigit() else oneui})")
    print(f"Security Patch  : {patch}")
    print(f"Battery Level   : {battery}%")
    print(f"Animation Scales: Window={anim_w}x | Transition={anim_t}x | Animator={anim_d}x")
    print("=" * 68 + "\n")

def backup_packages(device, backup_path):
    """Save full list of enabled packages for User 0."""
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    print(f"📸 Backing up enabled packages to: {backup_path}...")
    out = run_adb(["shell", "pm list packages --user 0 -e"], device)
    with open(backup_path, "w") as f:
        f.write(out + "\n")
    pkg_count = len([l for l in out.splitlines() if l.strip()])
    print(f"✅ Successfully backed up {pkg_count} packages.\n")

def speedup_animations(device, scale="0.5"):
    """Overclock window and transition animation scales."""
    print(f"⚡ Setting UI animation scales to {scale}x for snappy navigation...")
    run_adb(["shell", f"settings put global window_animation_scale {scale}"], device)
    run_adb(["shell", f"settings put global transition_animation_scale {scale}"], device)
    run_adb(["shell", f"settings put global animator_duration_scale {scale}"], device)
    print("✅ Animations overclocked! Noticeably snappier touch and app launch response.\n")

def apply_debloat(device, list_file):
    """Disable packages safely for User 0."""
    if not os.path.exists(list_file):
        sys.exit(f"❌ Debloat list file not found: {list_file}")
        
    print(f"🧹 Reading debloat profile: {list_file}")
    with open(list_file) as f:
        lines = f.readlines()
        
    targets = []
    for line in lines:
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            pkg = cleaned.split("#")[0].strip()
            targets.append(pkg)
            
    print(f"Found {len(targets)} packages targeted for freezing.\n")
    disabled_count = 0
    for pkg in targets:
        res = run_adb(["shell", f"pm disable-user --user 0 {pkg}"], device)
        if "disabled-user" in res or "new state: disabled-user" in res:
            print(f"  [DISABLED] ❄️  {pkg}")
            disabled_count += 1
        elif "already" in res:
            print(f"  [ALREADY FROZEN] {pkg}")
        else:
            print(f"  [SKIPPED/NOT PRESENT] {pkg} ({res})")
            
    print(f"\n🎉 Done! {disabled_count} bloatware packages safely frozen.")
    print("💡 Zero data was uninstalled. You can revert anytime using --restore.\n")

def restore_packages(device, list_file):
    """Re-enable all frozen packages."""
    if not os.path.exists(list_file):
        sys.exit(f"❌ List file not found: {list_file}")
        
    print(f"🔄 Re-enabling packages from: {list_file}...")
    with open(list_file) as f:
        lines = f.readlines()
        
    restored = 0
    for line in lines:
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            pkg = cleaned.split("#")[0].strip().replace("package:", "")
            res = run_adb(["shell", f"pm enable {pkg}"], device)
            if "enabled" in res or "new state: enabled" in res:
                print(f"  [RESTORED] ✅ {pkg}")
                restored += 1
    print(f"\n✅ Restored {restored} packages back to factory state.\n")

def main():
    parser = argparse.ArgumentParser(description="CleanMySamsung - Safe Android & One UI Debloater")
    parser.add_argument("-s", "--device", help="Specific ADB device target (e.g. 192.168.1.98:40689)")
    parser.add_argument("--probe", action="store_true", help="Inspect device specs and animation settings")
    parser.add_argument("--backup", action="store_true", help="Create a snapshot backup of enabled packages")
    parser.add_argument("--speedup", action="store_true", help="Set animation scales to 0.5x for 2x faster UI")
    parser.add_argument("--debloat", metavar="LIST_FILE", help="Safely freeze packages listed in a file")
    parser.add_argument("--restore", metavar="LIST_FILE", help="Re-enable packages from a file or backup")
    
    args = parser.parse_args()
    
    devices = get_connected_devices()
    if not devices:
        sys.exit("❌ No ADB devices connected. Connect over Wi-Fi or USB first.")
        
    target_device = args.device or devices[0]
    
    if args.probe:
        probe_device(target_device)
    elif args.backup:
        backup_path = "backup/samsung_packages_backup.txt"
        backup_packages(target_device, backup_path)
    elif args.speedup:
        speedup_animations(target_device)
    elif args.debloat:
        backup_packages(target_device, "backup/pre_debloat_backup.txt")
        apply_debloat(target_device, args.debloat)
    elif args.restore:
        restore_packages(target_device, args.restore)
    else:
        # Interactive default
        probe_device(target_device)
        print("Available actions:")
        print("  1. Speed up animations (0.5x)")
        print("  2. Apply safe debloat profile (lists/samsung_galaxy_a52.txt)")
        print("  3. Restore all frozen packages")
        print("  4. Full Backup\n")

if __name__ == "__main__":
    main()
