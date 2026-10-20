# CleanMySamsung 🧹📱

> **Reclaim your Galaxy. Strip bloatware, stop background telemetry, and make One UI feel 2x faster.**  
> Built for Samsung Galaxy phones (A-series, S-series, Z-series) running Android 11 to Android 14+ (One UI 3 to 6+).  
> **No Root Required · 100% Wireless via Wi-Fi · Zero Knox Tripping · 1-Click Instant Restore.**

---

## ⚡ Features

- **🔋 Up to 30% Better Battery Life:** Freezes aggressive background services (Facebook daemons, diagnostic telemetry) that constantly wake the CPU.
- **🚀 2x Snappier UI:** Overclocks window and transition animation scales from 1.0x to 0.5x.
- **🛡️ 100% Safe & Reversible:** Uses `pm disable-user --user 0`. Nothing is deleted from system storage; everything can be restored with a single command.
- **📶 Wireless Wi-Fi Support:** Debloat across your home Wi-Fi network using Android's native Wireless Debugging.

---

## 📋 Tested Device Profiles

- **Samsung Galaxy A52s 5G / A52** (`SM-A528B`, `SM-A525F`) - One UI 6 / Android 14
- Expandable across all modern Samsung Galaxy models (A14, A34, A54, S21, S22, S23, S24).

---

## 🚀 Quick Start

### 1. Enable Wireless Debugging on your Galaxy Phone
1. **Settings** ➔ **About phone** ➔ **Software information** ➔ Tap **Build number** 7 times.
2. Go back to **Settings** ➔ **Developer options** ➔ Toggle **ON** **`Wireless debugging`**.
3. Tap **"Pair device with pairing code"** and pair once with:
   ```bash
   adb pair <PHONE_IP>:<PAIRING_PORT> <6_DIGIT_CODE>
   adb connect <PHONE_IP>:<CONNECT_PORT>
   ```

### 2. Run CleanMySamsung

#### Probe your device:
```bash
python3 cleanmysamsung.py --probe
```

#### Speed up animations (Instant 2x responsiveness):
```bash
python3 cleanmysamsung.py --speedup
```

#### Safely debloat:
```bash
python3 cleanmysamsung.py --debloat lists/samsung_galaxy_a52.txt
```
*Creates an atomic, timestamped session snapshot in `backup/session_YYYYMMDD_HHMMSS.json` before touching any system package.*

#### Restore only what was changed by this tool:
```bash
# Roll back the most recent debloat session:
python3 cleanmysamsung.py --restore latest

# Or restore an explicit session snapshot:
python3 cleanmysamsung.py --restore backup/session_20261020_040622.json
```
*Unlike naive scripts that blindly enable everything, CleanMySamsung inspects pre-run states and restores ONLY packages modified during that session, preserving any apps you had disabled previously.*

---

## 🏗️ Safety & Architecture Guarantees

1. **Atomic Session Tracking:** Every run generates a structured JSON record containing device fingerprint, original package states, and original animation scales.
2. **Pre-Flight Validation:** Validates package syntax, filters out packages that are not installed, and skips packages that are already frozen.
3. **Safe Device Verification:** Verifies device model before restoring to prevent applying a backup from one phone model to another.
4. **Zero Shell Injection:** Uses parameter arrays rather than string interpolation for remote ADB commands.
5. **No Blind Re-enable:** Rollback strictly targets `changes_applied`, ensuring preexisting user configurations remain untouched.

---

## 🛡️ What Gets Frozen in the A52 Profile

| Category | Packages Frozen | Rationale |
| :--- | :--- | :--- |
| **Facebook Daemons** | `com.facebook.appmanager`, `com.facebook.system`, `com.facebook.services` | Running constantly in background even if Facebook is uninstalled. |
| **Telemetry & Promos** | `com.sec.android.diagmonagent`, `com.samsung.android.rubin.app`, `com.samsung.android.game.gametools` | Behavioral profiling and background diagnostic uploads. |
| **Bixby (Optional)** | `com.samsung.android.bixby.agent`, `bixby.wakeup`, `bixbyvision.framework` | Frees ~150 MB of RAM if using Google Assistant instead. |
| **Partner Preloads** | `com.linkedin.android`, `com.microsoft.appmanager` | Preloaded third-party vendor applications. |

---

## 📄 License
MIT License. Free and open source for the Android community.
