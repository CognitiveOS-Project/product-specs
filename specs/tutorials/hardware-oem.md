# Hardware OEM: Framework Laptop Factory OS Image

**Company profile:** Hardware manufacturer (Framework, Purism, MNT, System76) that ships CognitiveOS pre-installed. They own the firmware, the base system packages, and the update channel.

This tutorial shows how an OEM structures their OS image — the Raw Model firmware in read-only flash, pre-installed first-party skills, and the update pipeline for over-the-air delivery of both firmware and skill updates.

## OS Image Layout

```
/cognitiveos/
├── models/
│   ├── raw/
│   │   └── raw-model.gguf          # Read-only, signed, in firmware partition
│   └── wide/
│       └── active/                  # User-installed Wide Model (updatable)
├── patches/
│   ├── framebuffer-display/         # OEM pre-installed — display driver
│   ├── keyboard-backlight/          # OEM pre-installed — keyboard control
│   ├── battery-manager/             # OEM pre-installed — power management
│   ├── firmware-updater/            # OEM pre-installed — OTA firmware updates
│   └── ...                          # User-installed skills
├── firmware/
│   ├── bootloader.bin               # Signed, measured boot chain
│   ├── ec-firmware.bin              # Embedded controller firmware
│   └── raw-model-signing-key.pub    # Public key for Raw Model update verification
└── var/
    └── audit.log
```

## Package 1: Pre-Installed Firmware (Signed, Read-Only)

Burned to the SPI flash at the factory. The bootloader verifies the signature against a hardware root of trust before loading.

**`framework-laptop-firmware/cognitive.json`:**
```json
{
  "name": "com.framework.laptop.firmware",
  "version": "1.2.0",
  "description": "Framework Laptop 16 Raw Model firmware — display, keyboard, battery, EC",
  "author": "Framework Computer Inc.",
  "license": "proprietary",
  "checksum": {
    "sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5"
  },
  "brain": {
    "raw_model": {
      "type": "firmware",
      "weights": {
        "remote": {
          "source": "registry",
          "url": "https://fw.framework.com/cognitiveos/v1.2.0/raw-model.gguf",
          "filename": "raw-model.gguf",
          "format": "gguf",
          "size_bytes": 8388608
        }
      }
    }
  }
}
```

## Package 2: Keyboard Backlight Skill (OEM First-Party)

**`keyboard-backlight/cognitive.json`:**
```json
{
  "name": "com.framework.laptop.keyboard-backlight",
  "version": "1.0.0",
  "description": "Keyboard backlight control with ambient light sensing and auto-dimming",
  "author": "Framework Computer Inc.",
  "license": "MIT",
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "kb-backlight",
        "command": "./tools/mcp-kb-backlight",
        "args": ["--device", "/dev/i2c-3"]
      }
    ],
    "background": true,
    "capabilities": [
      "hardware.keyboard.backlight.set",
      "hardware.keyboard.backlight.get",
      "hardware.keyboard.backlight.ambient_mode"
    ]
  }
}
```

**`prompts/system.md`:**
```
You control the keyboard backlight. Available commands:
cognitiveos.hardware.keyboard.backlight.set(brightness=0-100)
cognitiveos.hardware.keyboard.backlight.get()
cognitiveos.hardware.keyboard.backlight.ambient_mode(true/false)

In ambient mode, brightness adjusts automatically based on the light sensor.
Dim the backlight after 5 minutes of inactivity to save battery.
```

## Package 3: Firmware Updater (Secure OTA)

**`firmware-updater/cognitive.json`:**
```json
{
  "name": "com.framework.laptop.firmware-updater",
  "version": "2.0.0",
  "description": "Secure OTA firmware updates for firmware, EC, and Raw Model",
  "author": "Framework Computer Inc.",
  "license": "MIT",
  "runtime": {
    "mcp_servers": [
      {
        "name": "fw-updater",
        "command": "./tools/mcp-fw-update",
        "args": ["--verify-key", "/cognitiveos/firmware/raw-model-signing-key.pub"]
      }
    ],
    "background": true,
    "capabilities": [
      "firmware.check_update",
      "firmware.apply_update",
      "firmware.rollback",
      "firmware.version"
    ]
  }
}
```

## Factory Image Build Script

```bash
#!/bin/bash
# build-factory-image.sh — run at manufacturing time

set -euo pipefail

# 1. Flash bootloader and Raw Model firmware
./flash-spi bootloader.bin
./flash-spi raw-model.gguf
# Raw Model public key burned to OTP fuses
./burn-otp-key raw-model-signing-key.pub

# 2. Install pre-loaded packages
for pkg in \
  com.framework.laptop.firmware@1.2.0 \
  com.framework.laptop.keyboard-backlight@1.0.0 \
  com.framework.laptop.battery-manager@1.0.0 \
  com.framework.laptop.display-driver@1.0.0 \
  com.framework.laptop.firmware-updater@2.0.0 \
  cognitiveos-base-system@latest \
  voice-assistant@latest; do
  cpm install "$pkg" --offline --from-repo /factory/package-cache/
done

# 3. Lock bootloader
./lock-bootloader

# 4. Sign the OS image
./sign-image /cognitiveos/ /output/framework-image-v1.2.0.signed.img
```

## OTA Update Flow

```bash
# Framework ships a firmware update
cpm publish com.framework.laptop.firmware@1.3.0

# Laptop checks automatically (background service)
cpm update com.framework.laptop.firmware
  → firmware-updater MCP server:
    1. Downloads signed firmware blob
    2. Verifies signature against hardware root of trust
    3. Staged to A/B partition
    4. On next boot: bootloader verifies new firmware
    5. If boot fails: automatic rollback to previous partition
```

## What Happens on Boot

1. **BootROM** loads bootloader from SPI flash, verifies signature against OTP fuse
2. **Bootloader** loads Raw Model firmware from verified partition, verifies signature
3. **Raw Model** initializes hardware (display, keyboard, battery, EC)
4. **Raw Model** scans `/cognitiveos/patches/` for installed skills
5. **Daemon** spawns OEM pre-installed MCP servers:
   - `kb-backlight` — connects to I²C keyboard controller
   - `battery-manager` — monitors charge level via ACPI
   - `display-driver` — manages framebuffer and display modes
   - `fw-updater` — checks for firmware updates in background
6. **Wide Model** loads from active partition (user-installed or default)
7. **System prompt chain** built from all installed skills
8. **"CognitiveOS ready"** — user can speak, type, or just let the AI run

## Usage

```
User: "Dim the keyboard lights"
  → Wide Model calls cognitiveos.hardware.keyboard.backlight.set(30)
  → kb-backlight MCP writes to I²C register
  → "Keyboard backlight set to 30%"

User: "Is there a firmware update?"
  → Wide Model calls cognitiveos.firmware.check_update()
  → fw-updater queries Framework's update server
  → "Framework firmware 1.3.0 is available (security fix: CVE-2026-1234)
     Install it?"
```

## User-Facing Factory Reset

```bash
cpm reset --factory
  → Removes all user-installed patches
  → Restores OEM pre-installed packages to factory versions
  → Clears /cognitiveos/data/ but preserves /cognitiveos/firmware/
  → "System reset to factory state. Your OEM packages are intact."
```

## OEM Differentiation

Each OEM ships their own Raw Model firmware tuned to their hardware:

| OEM | Raw Model specialization |
|-----|-------------------------|
| Framework | Hot-swappable port modules, modular keyboard, expansion card power management |
| Purism / Librem | Hardware kill switches (cam, mic, BT), secure boot enforcement |
| System76 | Open-source EC, firmware GPIO reconfiguration, thermal tuning |
| MNT Reform | Modular CPU board detection, battery chemistry calibration, trackball config |

The Raw Model firmware is the OEM's differentiator — it encodes the hardware-specific knowledge that no generic OS can provide.
