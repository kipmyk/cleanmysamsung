#!/usr/bin/env python3
"""
CleanMySamsung (CLI Entry Point)
Safe, modular, non-root debloater and performance optimizer for Samsung Galaxy devices.
"""

import argparse
import sys

from cleanmysamsung.adb import select_device
from cleanmysamsung.device import probe_device, check_profile_compatibility
from cleanmysamsung.animations import speedup_animations, restore_animations, get_animation_scales
from cleanmysamsung.packages import parse_profile, get_package_state_map, disable_package_verified
from cleanmysamsung.sessions import create_session_record, save_session_record, rollback_session
from cleanmysamsung.discovery import run_network_discovery

def apply_profile(device, profile_path, dry_run=False, backup_dir="backup"):
    """
    Apply a debloat profile with pre-flight checks, compatibility validation,
    atomic session creation, and post-operation verification.
    """
    dev_info = probe_device(device)
    profile_meta, targets = parse_profile(profile_path)

    # Check compatibility
    compatible, warning = check_profile_compatibility(dev_info, profile_meta)
    if not compatible:
        print(f"⚠️  COMPATIBILITY WARNING: {warning}")
        confirm = input("Do you wish to proceed anyway? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Operation aborted.")
            return

    current_states = get_package_state_map(device)
    session_record = create_session_record(dev_info, profile_path, targets, current_states)

    to_disable = [pkg for pkg in targets if current_states.get(pkg) == "ENABLED"]
    skipped = session_record["packages"]["skipped_already_disabled"]
    not_installed = session_record["packages"]["not_installed"]

    print("-" * 70)
    print(f"Pre-flight inspection for [{profile_meta.get('profile_name', profile_path)}]:")
    print(f"  • Ready to freeze       : {len(to_disable)}")
    print(f"  • Already frozen (skip) : {len(skipped)}")
    print(f"  • Not installed (skip)  : {len(not_installed)}")
    print("-" * 70)

    if not to_disable:
        print("💡 All target packages in this profile are already frozen or not installed. Zero changes needed.")
        return

    print("\nProposed Changes:")
    for pkg in to_disable:
        print(f"  ❄️  {pkg}")

    if dry_run:
        print("\n🔍 DRY-RUN MODE: Preview completed. Zero changes were applied to your device.\n")
        return

    # Persist session state record before modifications
    session_file = save_session_record(session_record, backup_dir)
    print(f"\n💾 Atomic session state created: {session_file}")

    print("\nExecuting Changes (with Post-Verification):")
    for pkg in to_disable:
        session_record["packages"]["attempted"].append(pkg)
        success, err = disable_package_verified(device, pkg)
        if success:
            print(f"  [FROZEN & VERIFIED] ✅ {pkg}")
            session_record["packages"]["confirmed_disabled"].append(pkg)
        else:
            print(f"  [FAILED] ❌ {pkg} ➔ {err}")
            session_record["packages"]["failed"].append({"package": pkg, "error": err})

    # Update session record on disk with verified outcomes
    save_session_record(session_record, backup_dir)

    print("\n" + "=" * 70)
    print(f"🎉 Complete! Confirmed {len(session_record['packages']['confirmed_disabled'])}/{len(to_disable)} packages frozen.")
    print(f"📄 Session file: {session_file}")
    print(f"💡 To safely roll back ONLY the changes from this run:")
    print(f"   python3 cleanmysamsung.py --restore {session_file}")
    print("=" * 70 + "\n")

def interactive_menu(device):
    """Interactive terminal dashboard."""
    while True:
        dev_info = probe_device(device)
        print("Select an action:")
        print("  [1] Speed up animations (Set to 0.5x)")
        print("  [2] Apply Galaxy A52s Debloat Profile (profiles/samsung/galaxy_a52s.json)")
        print("  [3] Dry-Run Debloat Preview (Simulate without touching device)")
        print("  [4] Restore last session (Rollback verified changes)")
        print("  [5] Reset animations back to default (1.0x)")
        print("  [6] Scan network for other wireless Android devices")
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
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.\n")
        input("Press Enter to continue...")

def main():
    parser = argparse.ArgumentParser(description="CleanMySamsung - Verified Android & One UI Debloater")
    parser.add_argument("-s", "--device", help="Specific ADB device target (e.g. 192.168.1.98:40689)")
    parser.add_argument("--probe", action="store_true", help="Inspect device specifications and animation settings")
    parser.add_argument("--speedup", action="store_true", help="Set animation scales to 0.5x for instant responsiveness")
    parser.add_argument("--reset-animations", action="store_true", help="Reset animation scales to default 1.0x")
    parser.add_argument("--debloat", metavar="PROFILE", help="Apply debloat profile (JSON or TXT)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate debloat without modifying any packages")
    parser.add_argument("--restore", metavar="SESSION_FILE", help="Safely roll back changes from a session JSON or 'latest'")
    parser.add_argument("--discover", action="store_true", help="Scan local network for wireless Android devices")

    args = parser.parse_args()

    if args.discover:
        run_network_discovery()
        return

    target_device = select_device(args.device)

    if args.probe:
        probe_device(target_device)
    elif args.speedup:
        speedup_animations(target_device, "0.5")
    elif args.reset_animations:
        speedup_animations(target_device, "1.0")
    elif args.debloat:
        apply_profile(target_device, args.debloat, dry_run=args.dry_run)
    elif args.restore:
        dev_info = probe_device(target_device)
        rollback_session(target_device, dev_info, args.restore, dry_run=args.dry_run)
    else:
        interactive_menu(target_device)

if __name__ == "__main__":
    main()
