# Systems Integrator: Factory Automation — PLC Bridge + Controller Firmware + Voice UI

**Company profile:** Industrial systems integrator that builds bespoke automation solutions for factories. They deliver CognitiveOS-powered control systems combining PLC communication, MCU firmware, and voice-operated interfaces — all versioned and deployed together.

This tutorial shows a three-package product with `dependencies` between them and an air-gapped deployment for industrial environments.

## Solution Architecture

```
┌─────────────────────────────────────────────────┐
│  Factory Floor                                    │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │  CognitiveOS Controller (x86 industrial PC)  │  │
│  │                                               │  │
│  │  Package 1: plc-bridge (mcp-bridge)           │  │
│  │    └─ Talks to PLCs via Modbus TCP/EtherNet/IP │  │
│  │                                               │  │
│  │  Package 2: voice-ui (prompt-only)            │  │
│  │    └─ Voice-controlled supervisor interface    │  │
│  │                                               │  │
│  └──────────────────┬──────────────────────────┘  │
│                      │ Ethernet                    │
│  ┌──────────────────▼──────────────────────────┐  │
│  │  PLC Rack (Siemens S7-1500)                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │  │ CPU     │  │ I/O     │  │ Drive   │    │  │
│  │  │ 1518-4  │  │ ET200SP │  │ G120    │    │  │
│  │  └─────────┘  └─────────┘  └─────────┘    │  │
│  └────────────────────────────────────────────┘  │
│                                                    │
│  ┌─────────────────────────────────────────────┐  │
│  │  MCU (ESP32-S3) — Package 3: sensor-node     │  │
│  │  └─ Reads vibration sensors, reports via     │  │
│  │     MQTT to CognitiveOS controller            │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Package 1: PLC Bridge (mcp-bridge)

**`plc-bridge/cognitive.json`:**
```json
{
  "name": "com.integrator.factory.plc-bridge",
  "version": "2.0.0",
  "description": "Siemens S7-1500 PLC bridge — read/write registers, alarms, diagnostics",
  "author": "Integrator Corp. / Factory Automation Division",
  "license": "proprietary",
  "hardware_requirements": {
    "min_ram_mb": 512,
    "min_storage_mb": 200,
    "min_cpu_cores": 2
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "plc-gateway",
        "command": "./tools/mcp-plc",
        "args": ["--config", "config/plc-network.yaml"]
      }
    ],
    "background": true,
    "capabilities": [
      "plc.register.read",
      "plc.register.write",
      "plc.alarm.list",
      "plc.alarm.acknowledge",
      "plc.diagnostics",
      "plc.production.count",
      "plc.line.status"
    ]
  }
}
```

**`prompts/system.md`:**
```
You are a factory automation supervisor connected to a Siemens S7-1500 PLC.

Available commands:
- Read production data: cognitiveos.plc.production.count(line=1, shift="morning")
- Check line status: cognitiveos.plc.line.status(line=1)
- Read register: cognitiveos.plc.register.read(db=10, offset=0, type="real")
- Write register: cognitiveos.plc.register.write(db=10, offset=4, value=75.0)
- List active alarms: cognitiveos.plc.alarm.list(severity="critical")
- Acknowledge alarm: cognitiveos.plc.alarm.acknowledge(id=1234)
- Run diagnostics: cognitiveos.plc.diagnostics(rack=0, slot=2)

Safety rules (NEVER override):
- Writing to safety-critical registers requires double confirmation
- If an alarm is active, always report it before any other status
- Production counters can be read but never written (audit-locked)
- All writes are logged to /cognitiveos/var/audit/plc-writes.log
- If temperature exceeds 85°C, suggest emergency shutdown
```

## Package 2: Voice UI (prompt-only)

**`voice-ui/cognitive.json`:**
```json
{
  "name": "com.integrator.factory.voice-ui",
  "version": "2.0.0",
  "description": "Voice-controlled factory supervisor interface — hands-free operation on the shop floor",
  "author": "Integrator Corp.",
  "license": "MIT",
  "dependencies": {
    "com.integrator.factory.plc-bridge": "^2.0.0",
    "com.integrator.factory.sensor-node": "^1.0.0"
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "capabilities": [
      "audio.voice_input",
      "audio.voice_output"
    ]
  }
}
```

**`prompts/system.md`:**
```
You are a voice-controlled factory supervisor. You control the production line through speech.

Voice interaction rules:
1. Responses must be 1-2 sentences — operators need fast answers, not essays
2. Use industrial terminology — "Line 1 throughput", "Rack 3 temperature", "Alarm 122"
3. Confirm destructive actions verbally — "Write 75.0 RPM to drive 2? Say 'yes' to confirm"
4. Read alarms immediately when asked — don't ask "which line?" if only one has issues
5. Safety critical: if you detect a critical alarm, announce it proactively

Available data sources:
- Your own PLC bridge knowledge
- Sensor node vibration and temperature data
- Production counters by line and shift

Communication: brief, professional, clear over poor audio.
```

## Package 3: Sensor Node Firmware (raw_model)

**`sensor-node/cognitive.json`:**
```json
{
  "name": "com.integrator.factory.sensor-node",
  "version": "1.2.0",
  "description": "ESP32-S3 sensor node firmware — vibration and temperature monitoring",
  "author": "Integrator Corp.",
  "license": "proprietary",
  "checksum": {
    "sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6"
  },
  "brain": {
    "raw_model": {
      "type": "firmware",
      "weights": {
        "remote": {
          "source": "registry",
          "url": "https://registry.integrator.com/cognitiveos/sensor-node-v1.2.0.bin",
          "filename": "sensor-node-v1.2.0.bin",
          "format": "binary",
          "size_bytes": 1048576
        }
      }
    }
  }
}
```

## Air-Gapped Deployment

In industrial environments, the factory has no internet. The integrator ships a portable registry:

```bash
# Build a deployment bundle on the integrator's build server
mkdir deploy-bundle-v2.0.0

# Export all packages with their dependencies
cpm export com.integrator.factory.plc-bridge@2.0.0 \
  --output deploy-bundle-v2.0.0/ --with-deps

cpm export com.integrator.factory.voice-ui@2.0.0 \
  --output deploy-bundle-v2.0.0/ --with-deps

cpm export com.integrator.factory.sensor-node@1.2.0 \
  --output deploy-bundle-v2.0.0/ --with-deps

# Create package cache for offline install
cpm registry create deploy-bundle-v2.0.0/registry/
cp *.cgp deploy-bundle-v2.0.0/registry/

# Copy to USB drive
cp -r deploy-bundle-v2.0.0 /usb/

# On the factory PC (no internet):
cpm registry import /usb/deploy-bundle-v2.0.0/registry/
cpm install com.integrator.factory.voice-ui@2.0.0
  # This auto-installs plc-bridge@2.0.0 and sensor-node@1.2.0 as dependencies
```

## Build & Install

```bash
# Build all three packages
cpm init plc-bridge --template mcp-bridge
cd plc-bridge && go build -o tools/mcp-plc ./cmd/plc && cd ..

cpm init voice-ui --template prompt-only
cd voice-ui && cd ..

cpm init sensor-node --template firmware
cd sensor-node && cd ..

# Build the deployment bundle
./build-deploy-bundle.sh v2.0.0  # creates deploy-bundle-v2.0.0/ with registry + packages

# Flash sensor node firmware
cpm flash /dev/ttyUSB0 com.integrator.factory.sensor-node@1.2.0

# Install on factory PC from air-gapped bundle
cpm registry import /usb/deploy-bundle-v2.0.0/registry/
cpm install com.integrator.factory.voice-ui
```

## What Happens

1. **Dependency resolution** — `voice-ui` depends on `plc-bridge ^2.0.0` and `sensor-node ^1.0.0`; both install automatically
2. **Hardware audit** — 512 MB RAM, 2 CPU cores minimum enforced
3. **PLC bridge starts** — `mcp-plc` opens Modbus TCP connections to the configured PLCs
4. **Sensor data flow** — ESP32 nodes publish MQTT to the bridge, which exposes data through MCP tools
5. **Voice UI activates** — `prompt-only` skill injected into Wide Model, no background process needed
6. **Operator speaks** — wake word triggers, voice commands control the factory floor

## Usage

```
Operator: "Line 1 status"
  → Wide Model calls cognitiveos.plc.line.status(line=1)
  → PLC bridge queries S7-1500 via Modbus TCP
  → "Line 1: running at 87% capacity, 342 units this shift, 0 active alarms."

Operator: "What's the vibration on motor 3?"
  → Wide Model calls cognitiveos.plc.register.read(db=15, offset=0, type="real")
  → "Motor 3 vibration: 2.4 mm/s — within normal range (threshold: 7.0 mm/s)."
```

```
[Critical alarm triggered]
  → PLC raises alarm: Rack 3 temperature 92°C (threshold: 85°C)
  → PLC bridge MCP server receives alarm push
  → Wide Model proactively announces:
     "CRITICAL ALARM: Rack 3 temperature at 92°C. Recommend emergency shutdown.
      Say 'shutdown rack 3' to initiate."
Operator: "Shutdown rack 3"
  → Wide Model: "Confirm shutdown of Rack 3? This will stop Line 1."
Operator: "Yes, shutdown"
  → Wide Model calls cognitiveos.plc.register.write(db=5, offset=0, value=1)
  → PLC initiates emergency stop sequence
  → Wide Model: "Rack 3 shutdown initiated. Line 1 stopped. Fire safety protocol activated."
```

## Multi-Factory Fleet Management

The integrator monitors all deployed systems:

```bash
# Each factory CognitiveOS instance reports aggregated metrics
# to the integrator's fleet management dashboard:
# - Package versions installed
  - Hardware utilization
  - Alarm frequency
  - Update readiness

# Push updates to all factories:
cpm update --target factory-*.integrator.com com.integrator.factory.plc-bridge
```
