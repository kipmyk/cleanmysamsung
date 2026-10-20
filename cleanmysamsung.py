#!/usr/bin/env python3
"""
CleanMySamsung: Samsung Galaxy Package Management & Animation Utility
Author: Mike Kipruto (https://mike.co.ke/contact)

Non-root utility for managing pre-installed packages and UI animations
on Samsung Galaxy devices running One UI.
"""

import argparse
import sys
from typing import Optional

from cleanmysamsung.adb import select_device
from cleanmysamsung.device import probe_device, check_profile_compatibility
from cleanmysamsung.animations import speedup_animations, restore_animations, get_animation_scales
from cleanmysamsung.packages import parse_profile, get_package_state_map, disable_package_verified
from cleanmysamsung.sessions import create_session_record, save_session_record, rollback_session
from cleanmysamsung.discovery import run_network_discovery

def apply_profile(device: str, profile_path: str, dry_run: bool = False, backup_dir: str = "backup") -> bool:
    """
    Apply a package profile with pre-flight checks, compatibility validation,
    session recording, and post-operation verification.
    Returns True if operations succeeded, False otherwise.
    """
    dev_info = probe_device(device)
    profile_meta, targets = parse_profile(profile_path)

    compatible, warning = check_profile_compatibility(dev_info, profile_meta)
    if not compatible:
        print(f"COMPATIBILITY WARNING: {warning}")
        confirm = input("Do you wish to proceed anyway? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Operation aborted.")
            return False

    current_states = get_package_state_map(device)
    session_record = create_session_record(dev_info, profile_path, targets, current_states)

    to_disable = [pkg for pkg in targets if current_states.get(pkg) == "ENABLED"]
    skipped = session_record["packages"]["skipped_already_disabled"]
    not_installed = session_record["packages"]["not_installed"]

    print("-" * 70)
    print(f"Pre-flight inspection for [{profile_meta.get('profile_name', profile_path)}]:")
    print(f"  - Ready to disable      : {len(to_disable)}")
    print(f"  - Already disabled (skip): {len(skipped)}")
    print(f"  - Not installed (skip)  : {len(not_installed)}")
    print("-" * 70)

    if not to_disable:
        print("All target packages in this profile are already disabled or not installed. No changes needed.")
        return True

    print("\nProposed Changes:")
    for pkg in to_disable:
        print(f"  - {pkg}")

    if dry_run:
        print("\nDRY-RUN MODE: Preview completed. Zero changes were applied to the device.\n")
        return True

    session_file = save_session_record(session_record, backup_dir)
    print(f"\nSession state recorded: {session_file}")

    print("\nExecuting Changes (with Post-Verification):")
    for pkg in to_disable:
        session_record["packages"]["attempted"].append(pkg)
        success, err = disable_package_verified(device, pkg)
        if success:
            print(f"  [DISABLED] {pkg}")
            session_record["packages"]["confirmed_disabled"].append(pkg)
        else:
            print(f"  [FAILED] {pkg}: {err}")
            session_record["packages"]["failed"].append({"package": pkg, "error": err})

    save_session_record(session_record, backup_dir)

    confirmed_count = len(session_record["packages"]["confirmed_disabled"])
    failed_count = len(session_record["packages"]["failed"])

    print("\n" + "=" * 70)
    print(f"Complete: Confirmed {confirmed_count}/{len(to_disable)} packages disabled.")
    if failed_count > 0:
        print(f"Notice: {failed_count} package operations failed.")
    print(f"Session file: {session_file}")
    print("To roll back changes from this session:")
    print(f"  python3 cleanmysamsung.py --restore {session_file}")
    print("=" * 70 + "\n")

    return failed_count == 0

def interactive_menu(device: str) -> None:
    """Interactive terminal dashboard."""
    while True:
        dev_info = probe_device(device)
        print("Select an action:")
        print("  [1] Speed up animations (Set to 0.5x)")
        print("  [2] Apply Galaxy A52s Profile (profiles/samsung/galaxy_a52s.json)")
        print("  [3] Dry-Run Profile Preview (Simulate without modifying device)")
        print("  [4] Restore last session (Rollback verified changes)")
        print("  [5] Reset animations back to default (1.0x)")
        print("  [6] Scan network for wireless Samsung devices")
        print("  [7] Exit")

        choice = input("\nEnter choice [1-7]: ").strip()
        if choice == "1":
            speedup_animations(device, "0.5")
        elif choice == "2":
            apply_profile(device, "profiles/samsung/galaxy_a52s.json", dry_run=False)
        elif choice == "3":
            apply_profile(device, "profiles/samsung/galaxy_a52s.json", dry_run=True)
        elif choice == "4":
            rollback_session(device, dev_info, "latest")
        elif choice == "5":
            speedup_animations(device, "1.0")
        elif choice == "6":
            run_network_discovery()
        elif choice == "7":
            print("Exiting.")
            break
        else:
            print("Invalid choice, please select 1-7.\n")
        input("Press Enter to continue...")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CleanMySamsung - Package management and performance optimizer for Samsung Galaxy devices"
    )
    parser.add_argument("-s", "--device", help="Specific ADB device target (e.g. 192.168.1.100:5555)")
    parser.add_argument("--probe", action="store_true", help="Inspect device specifications and animation settings")
    parser.add_argument("--speedup", action="store_true", help="Set animation scales to 0.5x for faster UI transitions")
    parser.add_argument("--reset-animations", action="store_true", help="Reset animation scales to default 1.0x")
    parser.add_argument("--debloat", metavar="PROFILE", help="Apply package profile (JSON or TXT)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate profile application without modifying packages")
    parser.add_argument("--restore", metavar="SESSION_FILE", help="Roll back changes from a session JSON or 'latest'")
    parser.add_argument("--discover", action="store_true", help="Scan local network for wireless Samsung devices")

    args = parser.parse_args()

    if args.discover:
        run_network_discovery()
        return

    target_device = select_device(args.device)

    if args.probe:
        probe_device(target_device)
    elif args.speedup:
        success, _, err = speedup_animations(target_device, "0.5")
        if not success:
            sys.exit(f"Failed to update animations: {err}")
    elif args.reset_animations:
        success, _, err = speedup_animations(target_device, "1.0")
        if not success:
            sys.exit(f"Failed to reset animations: {err}")
    elif args.debloat:
        ok = apply_profile(target_device, args.debloat, dry_run=args.dry_run)
        if not ok:
            sys.exit(1)
    elif args.restore:
        dev_info = probe_device(target_device)
        ok = rollback_session(target_device, dev_info, args.restore, dry_run=args.dry_run)
        if not ok:
            sys.exit(1)
    else:
        interactive_menu(target_device)

if __name__ == "__main__":
    main()
