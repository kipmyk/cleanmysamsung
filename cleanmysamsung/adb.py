"""
ADB Execution & Device Resolution Module
Handles binary resolution, command execution with strict error checking,
and device selection with serial deduplication.
"""

import os
import shutil
import subprocess
import sys

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
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"), # Windows
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

    print("\nMultiple devices detected. Please select a target:")
    for idx, dev in enumerate(authorized, 1):
        model, _, _ = run_adb(["shell", "getprop", "ro.product.model"], dev, check=False)
        print(f"  [{idx}] {dev} ({model or 'Unknown'})")

    while True:
        choice = input(f"Select device (1-{len(authorized)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(authorized):
            return authorized[int(choice) - 1]
        print("Invalid selection.")
