"""
Session State Tracking & Delta Rollback Module
Author: Mike Kipruto (https://mike.co.ke)

Maintains atomic JSON session history, records pre-flight states,
and ensures safe, isolated rollbacks without touching unrelated packages.
"""

import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from .animations import get_animation_scales, restore_animations
from .packages import enable_package_verified, validate_package_name

SESSION_ID_REGEX = re.compile(r"^session_[a-zA-Z0-9_]+$")

class SessionError(RuntimeError):
    """Base exception for session operations."""
    pass

class SessionValidationError(SessionError):
    """Raised when a session file has invalid syntax, structure, or unsafe content."""
    pass

def validate_session_data(data: Any) -> None:
    """
    Validate the structure and contents of loaded session JSON.
    Rejects malformed data, unknown structures, or invalid package names.
    """
    if not isinstance(data, dict):
        raise SessionValidationError("Session data must be a JSON object.")

    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID_REGEX.match(session_id):
        raise SessionValidationError(f"Invalid or unsafe session_id format: '{session_id}'")

    device = data.get("device")
    if not isinstance(device, dict):
        raise SessionValidationError("Session record missing valid 'device' block.")

    packages = data.get("packages")
    if not isinstance(packages, dict):
        raise SessionValidationError("Session record missing valid 'packages' block.")

    # Validate package lists
    for key in ("confirmed_disabled", "attempted", "skipped_already_disabled"):
        pkg_list = packages.get(key, [])
        if not isinstance(pkg_list, list):
            raise SessionValidationError(f"Field 'packages.{key}' must be a list.")
        for pkg in pkg_list:
            if not isinstance(pkg, str) or not validate_package_name(pkg):
                raise SessionValidationError(f"Invalid package name in packages.{key}: '{pkg}'")

def create_session_record(
    device_info: Dict[str, Any],
    profile_name: str,
    targets: List[str],
    current_states: Dict[str, str]
) -> Dict[str, Any]:
    """
    Construct initial session record before any system modification.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"session_{timestamp}"

    record: Dict[str, Any] = {
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
            "original_animations": get_animation_scales(device_info.get("target")),
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

def save_session_record(record: Dict[str, Any], backup_dir: str = "backup") -> str:
    """
    Atomically write session JSON to disk using temporary file replacement.
    Prevents path traversal and incomplete writes.
    """
    session_id = record.get("session_id", "")
    if not isinstance(session_id, str) or not SESSION_ID_REGEX.match(session_id):
        raise SessionValidationError(f"Invalid session_id: '{session_id}'")

    os.makedirs(backup_dir, exist_ok=True)
    filename = f"{session_id}.json"
    filepath = os.path.join(backup_dir, filename)
    tmp_filepath = os.path.join(backup_dir, f"{filename}.tmp_{os.getpid()}")

    try:
        with open(tmp_filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_filepath, filepath)
    finally:
        if os.path.exists(tmp_filepath):
            try:
                os.remove(tmp_filepath)
            except OSError:
                pass

    return filepath

def find_latest_session(backup_dir: str = "backup") -> Optional[str]:
    """Find the most recent valid session JSON file in backup_dir."""
    if not os.path.isdir(backup_dir):
        return None
    sessions = sorted([
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("session_") and f.endswith(".json") and not f.endswith(".tmp")
    ])
    return sessions[-1] if sessions else None

def load_session(session_path: str, backup_dir: str = "backup") -> Tuple[str, Dict[str, Any]]:
    """
    Load and validate session JSON by path or 'latest' keyword.
    Ensures file exists, is valid JSON, and adheres to the session schema.
    """
    if session_path.lower() == "latest":
        latest = find_latest_session(backup_dir)
        if not latest:
            raise FileNotFoundError("No session backup files found in backup directory.")
        session_path = latest

    if not os.path.isfile(session_path):
        raise FileNotFoundError(f"Session file not found: '{session_path}'")

    with open(session_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise SessionValidationError(f"Malformed JSON in session file '{session_path}': {exc}") from exc

    validate_session_data(data)
    return session_path, data

def rollback_session(
    device: str,
    device_info: Dict[str, Any],
    session_path: str,
    dry_run: bool = False,
    backup_dir: str = "backup"
) -> bool:
    """
    Roll back only packages confirmed to have been modified in the specified session.
    Restores original animation scales independently.
    Returns True if all attempted rollbacks succeeded, False otherwise.
    """
    resolved_path, session = load_session(session_path, backup_dir)
    print(f"Loaded session record: {resolved_path}")

    # Multi-field identity verification: model, serial, and fingerprint
    sess_device = session.get("device", {})
    sess_model = sess_device.get("model", "Unknown")
    curr_model = device_info.get("model", "Unknown")
    sess_serial = sess_device.get("serial", "Unknown")
    curr_serial = device_info.get("serial", "Unknown")

    identity_warning = False
    warning_reasons: List[str] = []

    if sess_model != "Unknown" and curr_model != "Unknown":
        if sess_model != curr_model:
            identity_warning = True
            warning_reasons.append(f"Model mismatch (session: '{sess_model}', current: '{curr_model}')")
    else:
        identity_warning = True
        warning_reasons.append(f"Model verification incomplete (session: '{sess_model}', current: '{curr_model}')")

    if sess_serial != "Unknown" and curr_serial != "Unknown":
        if sess_serial != curr_serial:
            identity_warning = True
            warning_reasons.append(f"Serial mismatch (session: '{sess_serial}', current: '{curr_serial}')")
    elif sess_serial != "Unknown" and curr_serial == "Unknown":
        identity_warning = True
        warning_reasons.append(f"Device serial could not be queried to verify session serial '{sess_serial}'")

    if identity_warning:
        print("WARNING: Device identity check flagged potential inconsistency:")
        for r in warning_reasons:
            print(f"  - {r}")
        confirm = input("Do you wish to proceed with restoration anyway? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Rollback aborted.")
            return False

    confirmed_disabled: List[str] = session.get("packages", {}).get("confirmed_disabled", [])
    print(f"\nTarget packages to re-enable: {len(confirmed_disabled)}")
    for pkg in confirmed_disabled:
        print(f"  - {pkg}")

    orig_anims = session.get("settings", {}).get("original_animations")
    if orig_anims and isinstance(orig_anims, dict):
        print(f"\nOriginal animations to restore: {orig_anims}")

    if dry_run:
        print("\nDRY-RUN MODE: Preview completed. Zero changes were applied to the device.")
        return True

    restored_count = 0
    failed_count = 0
    print("\nExecuting Rollback:")
    for pkg in confirmed_disabled:
        success, err = enable_package_verified(device, pkg)
        if success:
            print(f"  [RESTORED] {pkg}")
            restored_count += 1
        else:
            print(f"  [FAILED] {pkg}: {err}")
            failed_count += 1

    # Restore animation scales independently if valid
    if orig_anims and isinstance(orig_anims, dict):
        print("\nRestoring original animation scales...")
        success, err = restore_animations(device, orig_anims)
        if success:
            print("Restored original window, transition, and animator scales.")
        else:
            print(f"Warning restoring animations: {err}")

    print("\n" + "=" * 70)
    print(f"Rollback complete: {restored_count} packages restored, {failed_count} failed.")
    print("=" * 70 + "\n")

    return failed_count == 0
