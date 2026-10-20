"""
Package Management & Verification Module
Validates package syntax, parses profiles, queries package state maps,
and performs post-operation verification on every freeze and restore.
"""

import json
import os
import re
from .adb import run_adb

PACKAGE_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")

def validate_package_name(pkg):
    """Return True if package name conforms to strict Android naming syntax."""
    return bool(PACKAGE_REGEX.match(pkg))

def parse_profile(profile_path):
    """
    Parse a profile (either JSON or legacy TXT).
    Returns (profile_metadata: dict, package_list: list).
    """
    if not os.path.isfile(profile_path):
        raise FileNotFoundError(f"Profile file not found: '{profile_path}'")

    if profile_path.endswith(".json"):
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        packages = []
        tiers = data.get("tiers", {})
        for tier_name, tier_pkgs in tiers.items():
            for item in tier_pkgs:
                pkg_name = item.get("package") if isinstance(item, dict) else item
                if pkg_name and validate_package_name(pkg_name):
                    packages.append(pkg_name)
                elif pkg_name:
                    print(f"⚠️  Warning: Invalid package syntax in profile: '{pkg_name}'")

        return data, list(dict.fromkeys(packages))
    else:
        # Legacy TXT format
        packages = []
        with open(profile_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                pkg = cleaned.split("#")[0].strip()
                if validate_package_name(pkg):
                    packages.append(pkg)
                else:
                    print(f"⚠️  Warning: Line {line_num} has invalid package syntax: '{pkg}'")
        return {"name": os.path.basename(profile_path)}, list(dict.fromkeys(packages))

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

def disable_package_verified(device, pkg):
    """
    Disable a package for User 0 and verify via package manager query.
    Returns (success: bool, error_msg: str)
    """
    if not validate_package_name(pkg):
        return False, f"Invalid package name format: '{pkg}'"

    stdout, stderr, code = run_adb(["shell", "pm", "disable-user", "--user", "0", pkg], device, check=False)
    if code != 0:
        return False, stderr or stdout or "Command failed"

    # Post-operation verification: check if package is now in disabled list
    verify_out, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-d", pkg], device, check=False)
    if f"package:{pkg}" in verify_out.splitlines():
        return True, ""

    return False, f"Verification failed: {pkg} was not found in disabled packages after command."

def enable_package_verified(device, pkg):
    """
    Enable a package for User 0 and verify via package manager query.
    Returns (success: bool, error_msg: str)
    """
    if not validate_package_name(pkg):
        return False, f"Invalid package name format: '{pkg}'"

    stdout, stderr, code = run_adb(["shell", "pm", "enable", pkg], device, check=False)
    if code != 0:
        return False, stderr or stdout or "Command failed"

    # Post-operation verification: check if package is now in enabled list
    verify_out, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-e", pkg], device, check=False)
    if f"package:{pkg}" in verify_out.splitlines():
        return True, ""

    return False, f"Verification failed: {pkg} was not found in enabled packages after restore."
