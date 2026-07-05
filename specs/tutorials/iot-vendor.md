# IoT Vendor: Smart Thermostat — Firmware + Control Bridge

**Company profile:** IoT hardware company that builds smart thermostats, sensors, and actuators. They ship two things: the firmware that runs on the MCU, and the MCP bridge that lets the Wide Model control it.

This tutorial shows a dual-package product: a `raw_model` firmware package burned to the microcontroller, and an `mcp-bridge` skill package that provides the control API. The user installs both, and their CognitiveOS system can now sense and control the physical world.

## Product Architecture

```
┌─────────────────────────────┐
│  CognitiveOS (main CPU)     │
│  ┌───────────────────────┐  │
│  │  Wide Model (LLM)     │  │  Natural language → tool calls
│  │  "Set temp to 22°C"   │  │
│  └──────┬────────────────┘  │
│         │ cognitiveos.      │
│         │ thermostat.set    │
│  ┌──────▼────────────────┐  │
│  │  MCP Bridge Server     │  │  /cognitiveos/patches/thermostat-bridge/
│  │  tools/mcp-thermostat  │  │
│  └──────┬────────────────┘  │
└─────────┼───────────────────┘
          │ UART / I²C
┌─────────▼───────────────────┐
│  MCU (ESP32-S3)             │
│  ┌───────────────────────┐  │
│  │  Raw Model (firmware) │  │  Controls relay, reads sensor
│  └───────────────────────┘  │
└─────────────────────────────┘
```

## Package 1: Firmware (Raw Model)

Burned to the MCU flash at manufacturing time. Not user-installable.

**`firmware-thermostat-v2/cognitive.json`:**
```json
{
  "name": "com.mycompany.thermostat-firmware",
  "version": "2.1.0",
  "description": "ESP32-S3 firmware for thermostat v2 hardware",
  "author": "MyCompany IoT",
  "license": "proprietary",
  "checksum": {
    "sha256": "f1d2e3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2"
  },
  "brain": {
    "raw_model": {
      "type": "firmware",
      "weights": {
        "remote": {
          "source": "registry",
          "filename": "thermostat-v2.bin",
          "format": "binary",
          "size_bytes": 524288
        }
      }
    }
  },
  "hardware_requirements": {
    "min_ram_mb": 8,
    "min_storage_mb": 2,
    "npu_required": false
  }
}
```

Firmware is flashed at the factory or via a secure OTA mechanism:

```bash
# At the factory
cpm flash /dev/ttyUSB0 com.mycompany.thermostat-firmware@2.1.0

# OTA update (signed)
cpm update com.mycompany.thermostat-firmware --ota-endpoint https://ota.mycompany.com
```

## Package 2: MCP Bridge

Installed on the main CPU. This is the package users interact with.

**`thermostat-bridge/cognitive.json`:**
```json
{
  "name": "thermostat-bridge",
  "version": "2.1.0",
  "description": "Smart thermostat control — temperature, scheduling, sensors",
  "author": "MyCompany IoT",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/mycompany/thermostat-bridge",
    "issues": "https://github.com/mycompany/thermostat-bridge/issues"
  },
  "dependencies": {
    "com.mycompany.thermostat-firmware": "^2.0.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 128,
    "min_storage_mb": 50,
    "npu_required": false
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "thermostat-mcp",
        "command": "./tools/mcp-thermostat",
        "args": ["--device", "/dev/ttyACM0"]
      }
    ],
    "background": true,
    "capabilities": [
      "thermostat.temperature.read",
      "thermostat.temperature.set",
      "thermostat.schedule.list",
      "thermostat.schedule.set",
      "thermostat.mode.set",
      "thermostat.sensor.read"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`:**
```
You are a smart home climate controller connected to the MyCompany thermostat.

Available commands:
- Check current temperature: cognitiveos.thermostat.temperature.read()
- Set target temperature: cognitiveos.thermostat.temperature.set(22.5)
- List schedule: cognitiveos.thermostat.schedule.list()
- Set schedule: cognitiveos.thermostat.schedule.set(day, time, temp)
- Change mode (heat/cool/auto/off): cognitiveos.thermostat.mode.set("heat")
- Read sensor: cognitiveos.thermostat.sensor.read("outdoor")

Rules:
- Maintain comfort while minimizing energy use
- When user is away (no motion for 2h), suggest eco mode
- Before changing temperature, report the current temp
- Log all changes to /cognitiveos/var/thermostat.log
```

## Build & Install

```bash
# Scaffold the bridge
cpm init thermostat-bridge --template mcp-bridge
cd thermostat-bridge

# Build the MCP server that talks UART to the ESP32
go build -o tools/mcp-thermostat ./cmd/thermostat

# Package
tar czf thermostat-bridge-2.1.0.cgp .

# Install — also installs the firmware dependency
cpm install ./thermostat-bridge-2.1.0.cgp
```

## What Happens

1. **Dependency resolution** — `cpm` checks if `com.mycompany.thermostat-firmware ^2.0.0` is installed. If not, it fetches it from the registry (or the firmware was flashed at the factory)
2. **Hardware audit** — verifies RAM, storage, and that `/dev/ttyACM0` exists
3. **Bridge installed** to `/cognitiveos/patches/thermostat-bridge/`
4. **MCP server spawns** — `mcp-thermostat` connects to the ESP32 via UART and registers tools
5. **Background service** — `background: true` keeps the server running and polling sensors every 30 seconds
6. **System prompt injected** — the Wide Model knows how to control the thermostat

## Usage

```
User: "What's the temperature in here?"
  → Wide Model calls cognitiveos.thermostat.temperature.read()
  → MCP server queries ESP32 via UART → "indoor: 21.3°C"
  → "It's 21.3°C indoors."

User: "Set it to 22.5"
  → Wide Model: "Currently 21.3°C. Setting to 22.5°C."
  → Calls cognitiveos.thermostat.temperature.set(22.5)
  → MCP server sends command to ESP32 → relay activates
  → "Heating engaged. Target: 22.5°C."
```

### Autonomous Behavior

With `background: true`, the skill runs proactively:

```
[Every 30s — background sensor poll]
  → cognitiveos.thermostat.temperature.read() → "indoor: 21.3°C, outdoor: 8°C"

[2 hours after last motion detected]
  → Wide Model: "No motion detected for 2 hours. Suggesting eco mode to save energy."
  → "Would you like me to switch to eco mode? It will maintain 18°C until you return."
```

## Cross-Product: Adding a Humidity Sensor

```bash
cpm install humidity-sensor-bridge
# MCP server for the humidity sensor registers new capabilities:
#   thermostat.humidity.read, thermostat.humidity.trend

# The Wide Model gains the new sensor automatically — no code changes needed
# Next temperature conversation: "It's 21.3°C, indoor humidity is 45% (comfortable range)."
```
