# CleanMySamsung

CleanMySamsung is an open-source utility for managing pre-installed packages and animation settings on Samsung Galaxy devices running One UI through the Android Debug Bridge (ADB). It operates entirely in user space and does not require root privileges.

---

## Capabilities

- Adjust UI animation duration scales (window, transition, and animator) from default 1.0x to 0.5x to reduce visual transition delays.
- Disable selected background telemetry, diagnostic loggers, and preloaded partner packages using `pm disable-user --user 0`.
- Record pre-flight package states into structured JSON session records prior to modification.
- Perform isolated delta rollbacks that restore only packages altered in a given session, preserving preexisting user settings.
- Simulate package operations using a non-destructive dry-run mode before modifying device state.
- Connect over standard USB debugging or local wireless debugging.

---

## Device Compatibility

Tested device:
- Samsung Galaxy A52s 5G (`SM-A528B`), Android 14, One UI 6.0 / 6.1

Theoretically compatible devices:
- Samsung Galaxy devices running Android 11 through Android 14+ (One UI 3.0 through 6.1+). Profile model constraints can be adjusted in the corresponding JSON profile file.

---

## Requirements and Prerequisites

### 1. Python Environment
CleanMySamsung requires **Python 3.8 or later**. It is built entirely on the Python standard library, meaning zero third-party `pip` packages or external runtime libraries are required:
- `argparse` (CLI parsing)
- `asyncio` and `socket` (Subnet discovery and port probing)
- `json` (Session snapshots and profile schemas)
- `subprocess` (Direct ADB binary execution with parameter lists)
- `typing` (Type annotations)
- `unittest` (Automated test suite)

### 2. Android Debug Bridge (ADB)
The Android SDK Platform Tools binary (`adb`) must be accessible on your system. CleanMySamsung automatically detects `adb` in standard system paths across macOS, Linux, and Windows.

Installation commands by operating system:
- **macOS** (Homebrew):
  ```bash
  brew install android-platform-tools
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt install adb
  ```
- **Fedora / RHEL**:
  ```bash
  sudo dnf install android-tools
  ```
- **Windows**:
  Download [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and add the directory to your system `PATH`.

---

## Installation

You can get CleanMySamsung either by cloning the repository with Git or by downloading the source archive:

### Method 1: Clone with Git (Recommended)

```bash
git clone https://github.com/kipmyk/cleanmysamsung.git
cd cleanmysamsung
```

### Method 2: Download ZIP Archive

1. Navigate to the repository page at [https://github.com/kipmyk/cleanmysamsung](https://github.com/kipmyk/cleanmysamsung).
2. Click the green **Code** button and select **Download ZIP**.
3. Extract the downloaded ZIP file and open your terminal in the extracted folder:
   ```bash
   cd cleanmysamsung-main
   ```

### Zero Dependencies Required

CleanMySamsung runs entirely on Python's built-in standard library. No compilation, external packages, or `pip install` commands are needed. As long as Python 3.8+ and `adb` are available on your machine, you can run the commands directly.

---

## Setup Instructions

### Option A: Wireless Debugging

Android 11 and later support native Wireless Debugging. Pairing and connection are two distinct steps using separate ports.

1. Open **Settings** > **About phone** > **Software information**.
2. Tap **Build number** seven times to enable Developer options.
3. Open **Settings** > **Developer options**.
4. Enable **Wireless debugging** and confirm network access.
5. Tap the **Wireless debugging** text to open details, then tap **Pair device with pairing code**.
6. On your workstation, execute the pairing command using the pairing port and 6-digit code displayed on the phone:
   ```bash
   adb pair <device_ip>:<pairing_port> <pairing_code>
   ```
7. Return to the main Wireless debugging screen to find the connection port (this port differs from the pairing port), then connect:
   ```bash
   adb connect <device_ip>:<connect_port>
   ```
8. Verify that the device is listed as authorized:
   ```bash
   adb devices
   ```

### Option B: USB Debugging

1. Enable **Developer options** using the steps above.
2. Toggle on **USB debugging**.
3. Connect the phone to your workstation via USB cable.
4. Unlock the phone and accept the host authorization prompt.

---

## Usage Guide

All commands are run from within the repository root:

### 1. Interactive Menu
Launch the terminal interface:
```bash
python3 cleanmysamsung.py
```

### 2. Device Diagnostics
Inspect connected device model, manufacturer, Android release, One UI build, and battery status:
```bash
python3 cleanmysamsung.py --probe
```

Example output:
```text
======================================================================
 SAMSUNG GALAXY DEVICE PROBE
======================================================================
Device Target   : <device_ip>:<connect_port>
Manufacturer    : Samsung
Model Number    : SM-A528B
Android Version : 14 (One UI 6.01)
Security Patch  : 2025-09-01
Battery Level   : 80% (Temp: 29.2 C)
======================================================================
```

### 3. Adjust Animation Scales
Set animation scales to 0.5x:
```bash
python3 cleanmysamsung.py --speedup
```

Reset animation scales to standard 1.0x:
```bash
python3 cleanmysamsung.py --reset-animations
```

### 4. Dry-Run Debloat Preview
Inspect target packages and verify existing installation states without modifying the device:
```bash
python3 cleanmysamsung.py --dry-run --debloat profiles/samsung/galaxy_a52s.json
```

### 5. Apply Debloat Profile
Create an atomic pre-flight session snapshot and disable profile target packages:
```bash
python3 cleanmysamsung.py --debloat profiles/samsung/galaxy_a52s.json
```

### 6. Session Rollback
Restore packages modified during the latest session:
```bash
python3 cleanmysamsung.py --restore latest
```

Restore packages from a specific historical session file:
```bash
python3 cleanmysamsung.py --restore backup/session_20261020_120000.json
```

### 7. Discover Wireless Devices
Scan the local subnet for devices with open ADB ports:
```bash
python3 cleanmysamsung.py --discover
```

---

## Package Profile Breakdown: Galaxy A52s

The included profile (`profiles/samsung/galaxy_a52s.json`) targets the following package tiers:

| Tier | Packages | Purpose |
| :--- | :--- | :--- |
| Facebook Services | `com.facebook.appmanager`<br>`com.facebook.system`<br>`com.facebook.services` | Background daemons bundled into system image; not required if Facebook apps are unused. |
| Diagnostic Telemetry | `com.sec.android.diagmonagent`<br>`com.samsung.android.rubin.app`<br>`com.samsung.android.game.gametools` | Samsung Diagnostic Monitor (error reporting), Rubin customization service, and Game Booster overlay. |
| Bixby Ecosystem | `com.samsung.android.bixby.agent`<br>`com.samsung.android.bixby.wakeup`<br>`com.samsung.android.bixbyvision.framework`<br>`com.samsung.android.bixby.service`<br>`com.samsung.android.app.settings.bixby` | Bixby voice engine and wakeup listeners. Safe to disable if alternative assistants are preferred. |
| Partner Preloads | `com.linkedin.android`<br>`com.microsoft.appmanager` | Pre-installed third-party partner applications. |

---

## Safety Architecture

1. **State Preservation**: The utility uses `pm disable-user --user 0`. Packages remain in read-only system storage and can be re-enabled at any time. No system partition files are removed.
2. **Pre-flight State Recording**: Prior to executing modifications, existing states (`ENABLED`, `DISABLED`, or `NOT_INSTALLED`) are queried and recorded into `backup/session_<timestamp>.json`.
3. **Targeted Rollback with State Verification**: Restoration exclusively re-enables packages confirmed to have been disabled during that specific session. Packages that were already disabled prior to running the tool remain disabled. Rather than relying on return codes alone, the tool queries the package manager afterward to verify whether each package has successfully returned to the enabled state.
4. **Subprocess Safety**: ADB commands are executed using argument lists rather than shell strings, avoiding shell injection risks.
5. **Multi-Field Device Validation**: Restoring a session checks both device model and hardware serial against the session record. If a mismatch is detected, the tool warns the operator and requires explicit confirmation before proceeding.

---

## Testing

Run the automated test suite:
```bash
python3 -m unittest discover tests
```

---

## Author and Support

CleanMySamsung is developed and maintained by [Mike Kipruto](https://mike.co.ke).

- Issues and Bug Reports: If you encounter a problem or have a feature request, please [open an issue](https://github.com/kipmyk/cleanmysamsung/issues/new).
- Contributing: Pull requests are welcome. Please [submit a pull request](https://github.com/kipmyk/cleanmysamsung/compare) and ensure any changes include appropriate unit tests.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
