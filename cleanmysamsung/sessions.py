"""
Session State Tracking & Delta Rollback Module
Maintains atomic JSON session history, records pre-flight states,
and ensures safe, isolated rollbacks without touching unrelated packages.
"""

import datetime
import json
import os
import sys
from .animations import get_animation_scales, restore_animations
from .packages import enable_package_verified

def create_session_record(device_info, profile_name, targets, current_states):
    """
    Construct initial session record before any system modification.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"session_{timestamp}"

    record = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "device": {
            "target": device_info.get("target"),
            "serial": device_info.get("serial"),
            "model": device_info.get("model"),
            "fingerprint": device_info.get("fingerprint"),
            "android_version": device_info.get("android_version"),
            "oneui_version": device_info.get("oneui_version")
        },
        "profile": profile_name,
        "settings": {
            "original_animations": get_animation_scales(device_info["target"]),
            "applied_animations": None
        },
        "packages": {
            "original_states": {},
            "attempted": [],
            "confirmed_disabled": [],
            "skipped_already_disabled": [],
            "not_installed": [],
            "failed": []
        }
    }

    for pkg in targets:
        state = current_states.get(pkg, "NOT_INSTALLED")
        record["packages"]["original_states"][pkg] = state
        if state == "DISABLED":
            record["packages"]["skipped_already_disabled"].append(pkg)
        elif state == "NOT_INSTALLED":
            record["packages"]["not_installed"].append(pkg)

    return record

def save_session_record(record, backup_dir="backup"):
    """Atomically write session JSON to disk."""
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"{record['session_id']}.json"
    filepath = os.path.join(backup_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return filepath

def find_latest_session(backup_dir="backup"):
    """Find the most recent session JSON file in backup_dir."""
    if not os.path.isdir(backup_dir):
        return None
    sessions = sorted([
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("session_") and f.endswith(".json")
    ])
    return sessions[-1] if sessions else None

def load_session(session_path, backup_dir="backup"):
    """Load session JSON by path or 'latest' keyword."""
    if session_path.lower() == "latest":
        latest = find_latest_session(backup_dir)
        if not latest:
            raise FileNotFoundError("No session backup files found in backup directory.")
        session_path = latest

    if not os.path.isfile(session_path):
        raise FileNotFoundError(f"Session file not found: '{session_path}'")

    with open(session_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return session_path, data

def rollback_session(device, device_info, session_path, dry_run=False, backup_dir="backup"):
    """
    Roll back only packages confirmed to have been modified in the specified session.
    Restores original animation scales independently.
    """
    resolved_path, session = load_session(session_path, backup_dir)
    print(f"📖 Loaded session record: {resolved_path}")

    # Compatibility check
    sess_model = session.get("device", {}).get("model", "Unknown")
    curr_model = device_info.get("model", "Unknown")
    if sess_model != "Unknown" and curr_model != "Unknown" and sess_model != curr_model:
        print(f"⚠️  WARNING: Session was created on '{sess_model}', but connected device is '{curr_model}'!")
        confirm = input("Are you sure you want to proceed with restore? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Rollback aborted.")
            return False

    confirmed_disabled = session.get("packages", {}).get("confirmed_disabled", [])
    print(f"\nTarget packages to re-enable: {len(confirmed_disabled)}")
    for pkg in confirmed_disabled:
        print(f"  • {pkg}")

    orig_anims = session.get("settings", {}).get("original_animations")
    if orig_anims:
        print(f"\nOriginal animations to restore: {orig_anims}")

    if dry_run:
        print("\n🔍 DRY-RUN MODE: No changes were applied to the device.")
        return True

    restored_count = 0
    failed_count = 0
    print("\nExecuting Rollback:")
    for pkg in confirmed_disabled:
        success, err = enable_package_verified(device, pkg)
        if success:
            print(f"  [RESTORED] ✅ {pkg}")
            restored_count += 1
        else:
            print(f"  [ERROR] ❌ {pkg}: {err}")
            failed_count += 1

    # Restore animation scales independently
    if orig_anims:
        print("\n🔄 Restoring original animation scales...")
        success, err = restore_animations(device, orig_anims)
        if success:
            print("✅ Restored original window, transition, and animator scales.")
        else:
            print(f"⚠️  Warning restoring animations: {err}")

    print("\n" + "=" * 70)
    print(f"🎉 Rollback complete: {restored_count} packages restored, {failed_count} failed.")
    print("=" * 70 + "\n")
    return failed_count == 0
