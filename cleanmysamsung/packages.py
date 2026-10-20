"""
Package Management & Verification Module
Author: Mike Kipruto (https://mike.co.ke)

Validates package syntax, parses profiles, queries package state maps,
and performs post-operation verification on every disable and restore operation.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .adb import run_adb

PACKAGE_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")

def validate_package_name(pkg: str) -> bool:
    """Return True if package name conforms to strict Android naming syntax."""
    if not isinstance(pkg, str):
        return False
    return bool(PACKAGE_REGEX.match(pkg.strip()))

def parse_profile(profile_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse a package profile (JSON schema or line-delimited TXT).
    Returns (profile_metadata: dict, validated_package_list: list).
    """
    if not os.path.isfile(profile_path):
        raise FileNotFoundError(f"Profile file not found: '{profile_path}'")

    if profile_path.endswith(".json"):
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        packages: List[str] = []
        tiers = data.get("tiers", {})
        if not isinstance(tiers, dict):
            raise ValueError("Profile tiers must be a dictionary.")

        for tier_name, tier_pkgs in tiers.items():
            if not isinstance(tier_pkgs, list):
                continue
            for item in tier_pkgs:
                pkg_name = item.get("package") if isinstance(item, dict) else item
                if isinstance(pkg_name, str) and validate_package_name(pkg_name):
                    packages.append(pkg_name.strip())
                elif pkg_name:
                    print(f"Warning: Invalid package syntax in profile: '{pkg_name}'")

        return data, list(dict.fromkeys(packages))
    else:
        # Line-delimited TXT format
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
                    print(f"Warning: Line {line_num} has invalid package syntax: '{pkg}'")
        return {"name": os.path.basename(profile_path)}, list(dict.fromkeys(packages))

def get_package_state_map(device: Optional[str]) -> Dict[str, str]:
    """
    Query User 0 package state map.
    Returns dict: { package_name: 'ENABLED' | 'DISABLED' }
    """
    stdout_all, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0"], device, check=True)
    stdout_dis, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-d"], device, check=True)

    all_pkgs: Set[str] = set(line.replace("package:", "").strip() for line in stdout_all.splitlines() if line.strip())
    disabled_pkgs: Set[str] = set(line.replace("package:", "").strip() for line in stdout_dis.splitlines() if line.strip())

    state_map: Dict[str, str] = {}
    for pkg in all_pkgs:
        state_map[pkg] = "DISABLED" if pkg in disabled_pkgs else "ENABLED"
    return state_map

def disable_package_verified(device: Optional[str], pkg: str) -> Tuple[bool, str]:
    """
    Disable a package for User 0 and verify actual state via package manager query.
    Returns (success: bool, error_msg: str)
    """
    if not validate_package_name(pkg):
        return False, f"Invalid package name format: '{pkg}'"

    stdout, stderr, code = run_adb(["shell", "pm", "disable-user", "--user", "0", pkg], device, check=False)
    if code != 0:
        return False, stderr or stdout or f"Command failed with exit code {code}"

    # Post-operation verification: check if package is actually in disabled list
    verify_out, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-d", pkg], device, check=False)
    matching_lines = [line.strip() for line in verify_out.splitlines()]
    if f"package:{pkg}" in matching_lines:
        return True, ""

    return False, f"Verification failed: {pkg} was not confirmed disabled after execution."

def enable_package_verified(device: Optional[str], pkg: str) -> Tuple[bool, str]:
    """
    Enable a package for User 0 and verify actual state via package manager query.
    Returns (success: bool, error_msg: str)
    """
    if not validate_package_name(pkg):
        return False, f"Invalid package name format: '{pkg}'"

    stdout, stderr, code = run_adb(["shell", "pm", "enable", pkg], device, check=False)
    if code != 0:
        return False, stderr or stdout or f"Command failed with exit code {code}"

    # Post-operation verification: check if package is actually in enabled list
    verify_out, _, _ = run_adb(["shell", "pm", "list", "packages", "--user", "0", "-e", pkg], device, check=False)
    matching_lines = [line.strip() for line in verify_out.splitlines()]
    if f"package:{pkg}" in matching_lines:
        return True, ""

    return False, f"Verification failed: {pkg} was not confirmed enabled after execution."
