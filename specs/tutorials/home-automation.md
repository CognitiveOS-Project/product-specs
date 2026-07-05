# Home Automation

A skill that controls smart home devices via GPIO pins, relays, and serial protocols. Demonstrates hardware-aware capability declarations and background service mode.

## cognitive.json

```json
{
  "name": "home-automation",
  "version": "1.0.0",
  "description": "Smart home controller for lights, sensors, and relays",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 128,
    "npu_required": false
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "gpio-bridge",
        "command": "./tools/mcp-gpio",
        "transport": "stdio"
      },
      {
        "name": "serial-bridge",
        "command": "./tools/mcp-serial",
        "args": ["--baud", "115200"]
      }
    ],
    "background": true,
    "capabilities": [
      "home.light.on",
      "home.light.off",
      "home.light.dim",
      "home.temperature.read",
      "home.motion.detect",
      "home.relay.toggle"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a home automation controller. You manage a smart home through GPIO and serial devices.

Available devices:
- Living room light (GPIO 17)
- Kitchen light (GPIO 27)
- Bedroom light (GPIO 22)
- Temperature sensor (serial, address 0x76)
- Motion sensor (GPIO 23)
- Front door relay (GPIO 24)

Rules:
- Turn lights on at sunset, off at sunrise (use system time)
- If motion detected and no lights on, turn on nearest light
- Log all sensor readings to /cognitiveos/var/home-automation.log
- Never toggle the relay without user confirmation (safety)
```

## Build & Install

```bash
cpm init home-automation --template mcp-bridge
cd home-automation

# Build GPIO and serial MCP servers
go build -o tools/mcp-gpio   ./cmd/gpio
go build -o tools/mcp-serial ./cmd/serial

# Package and install
tar czf home-automation-1.0.0.cgp .
cpm install ./home-automation-1.0.0.cgp
```

## What Happens

1. `background: true` tells the daemon this skill runs continuously, not just on demand
2. Both MCP servers spawn at system boot (after daemon startup)
3. The GPIO bridge registers tools for reading/writing pins
4. The serial bridge registers tools for I²C/SPI/UART communication
5. The Wide Model can proactively monitor sensors and react to events
6. The Raw Model audits hardware — if GPIO pins aren't available, install fails with a clear error

## Usage

```
User: "Turn on the living room light"
  → Wide Model calls cognitiveos.home.light.on(pin=17)
  → gpio-bridge writes HIGH to GPIO 17
  → Wide Model: "Living room light turned on."

User: "What's the temperature?"
  → Wide Model calls cognitiveos.home.temperature.read()
  → serial-bridge reads I²C sensor at 0x76
  → Returns: "22.5°C"
  → Wide Model: "It's 22.5°C in here."
```

### Autonomous Behavior

With `background: true` and the system prompt instructions, the Wide Model runs in the background:

```
[18:30 — system time]
  → Wide Model notices sunset time approaching
  → Calls cognitiveos.home.light.on(pin=17) — living room
  → Calls cognitiveos.home.light.on(pin=27) — kitchen
  → Logs: "Auto-lit living room and kitchen at sunset"

[02:15 — motion detected]
  → Motion sensor interrupt → daemon notifies Wide Model
  → Wide Model checks light state:
     - Living room: off
     - Kitchen: off
     - Bedroom: off
  → Calls cognitiveos.home.light.dim(pin=22, percent=30) — dim bedroom light
  → "Good evening. I turned on your bedroom light at 30%."
```
