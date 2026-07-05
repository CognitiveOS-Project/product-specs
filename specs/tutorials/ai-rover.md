# AI-Controlled Rover

Build an AI-powered robot that you control by talking to it. No Python scripts, no manual GPIO tool calls — just natural language. The Wide Model (local LLM) translates your words into MCP tool calls that spin the motors, read sensors, and speak back to you.

## How It Works

```
You: "Drive forward for 2 seconds"
      │
      ▼
cognitiveos-cli ──Unix socket──► cognitiveosd daemon
                                      │
                                      ▼
                               Wide Model (local LLM)
                                      │
                            "I need to set PWM on GPIO 12 and 13,
                             wait 2 seconds, then stop."
                                      │
                            @@cognitiveos.gpio.pwm(pin=12, duty_cycle=75)@@
                            @@cognitiveos.gpio.pwm(pin=13, duty_cycle=75)@@
                            @@cognitiveos.gpio.pin_write(pin=5, value=1)@@
                            @@cognitiveos.gpio.pin_write(pin=6, value=0)@@
                            @@cognitiveos.system.wait(seconds=2)@@
                            @@cognitiveos.gpio.pwm(pin=12, duty_cycle=0)@@
                            @@cognitiveos.gpio.pwm(pin=13, duty_cycle=0)@@
                                      │
                                      ▼
                               cognitiveosd daemon
                           parses @@toolCall(arg=val)@@
                           routes to gpio-mcp process
                                      │
                                      ▼
                               gpio-mcp (Go binary)
                           writes /sys/class/gpio and /sys/class/pwm
                                      │
                                      ▼
                               L298N motor driver
                           motors spin → robot moves!
```

## Phase 1: Hardware

| Component | Spec | Purpose |
|-----------|------|---------|
| Raspberry Pi 5 | 8 GB RAM | Runs the LLM, daemon, and MCP bridges |
| MicroSD card | 64 GB+ (A2 class) or NVMe SSD | OS and model storage |
| 2WD/4WD chassis kit | DC motors + wheels | Robot body |
| L298N motor driver | Dual H-bridge | Converts GPIO signals to motor power |
| Power bank | USB-C PD, 5V 5A | Powers the Pi |
| Battery pack | 2× 18650 Li-ion (7.4V) | Powers the L298N and motors |
| HC-SR04 (optional) | Ultrasonic distance sensor | Obstacle detection |
| USB microphone + speaker (optional) | Any USB audio device | Voice control |

**⚠️ Safety:** The L298N and motors draw far more current than the Pi's 5V rail can supply. Always use a **separate battery pack** for the motors. If the Pi browns out, the filesystem may corrupt.

## Phase 2: Wiring

The `gpio-mcp` bridge controls motors by writing to `/sys/class/gpio` (digital pins) and `/sys/class/pwm` (PWM speed control). The pin numbers below are the **chip-relative GPIO numbers** used by the sysfs interface on RPi 5 (BCM2712).

| Function | GPIO Pin | Sysfs Path | L298N Terminal |
|----------|----------|------------|----------------|
| Left motor speed (PWM) | 12 | `/sys/class/pwm/pwmchip2/pwm0/duty_cycle` | ENA |
| Left motor forward | 5 | `/sys/class/gpio/gpio5/value` | IN1 |
| Left motor reverse | 6 | `/sys/class/gpio/gpio6/value` | IN2 |
| Right motor speed (PWM) | 13 | `/sys/class/pwm/pwmchip2/pwm1/duty_cycle` | ENB |
| Right motor forward | 19 | `/sys/class/gpio/gpio19/value` | IN3 |
| Right motor reverse | 26 | `/sys/class/gpio/gpio26/value` | IN4 |
| HC-SR04 Trigger (optional) | 17 | `/sys/class/gpio/gpio17/value` | Trigger pin |
| HC-SR04 Echo (optional) | 27 | `/sys/class/gpio/gpio27/value` | Echo pin (via voltage divider!) |

**Wiring steps:**

1. Connect motor wires to L298N OUT1/OUT2 (left) and OUT3/OUT4 (right)
2. Connect 7.4V battery pack to L298N `12V` and `GND`
3. Connect Pi GPIO 12 → L298N ENA, GPIO 5 → IN1, GPIO 6 → IN2
4. Connect Pi GPIO 13 → L298N ENB, GPIO 19 → IN3, GPIO 26 → IN4
5. **Connect all GND terminals together** (Pi ground, L298N ground, battery ground)
6. Power the Pi from the USB-C power bank (never from the L298N 5V output)

**HC-SR04 note:** The Echo pin outputs 5V, but the Pi's GPIO is 3.3V tolerant. Use a voltage divider (2KΩ + 1KΩ resistors) between Echo and GPIO 27, or risk damaging the Pi.

## Phase 3: Install CognitiveOS

```bash
# 1. Download the aarch64 CognitiveOS image
# From cognitiveos-distro releases:
wget https://github.com/CognitiveOS-Project/cognitiveos-distro/releases/latest/download/cognitiveos-rpi-aarch64.img.xz

# 2. Flash to SD card
xz -d cognitiveos-rpi-aarch64.img.xz
sudo dd if=cognitiveos-rpi-aarch64.img of=/dev/sdX bs=4M status=progress

# 3. Insert SD card into Pi and power on
# The system boots into cognitiveos-cli automatically
```

**First boot sequence:**
1. U-Boot → Linux kernel → OpenRC starts services
2. `cognitiveosd` daemon starts, opens `/cognitiveos/run/daemon.sock`
3. Daemon spawns core MCP bridges: `gpio-mcp`, `audio-mcp`, `display-mcp`, `network-mcp`, `serial-mcp`
4. Daemon runs hardware audit (RAM, storage, CPU cores)
5. Daemon loads the Wide Model from `/cognitiveos/models/wide/active/`
6. `cognitiveos-cli` connects to daemon socket, displays the TUI
7. **"CognitiveOS ready"** appears on screen

**Verify bridges are running:**
```bash
# From the cognitiveos-cli, press Ctrl+D to enter diagnostic mode,
# or check via the daemon's status endpoint.
# The daemon auto-spawns gpio-mcp, audio-mcp, display-mcp, network-mcp, serial-mcp
# Each runs as a cgroup-isolated child process with memory/CPU limits.
```

## Phase 4: Create the Rover Skill Package

The robot control logic lives in a `.cgp` package. The system prompt teaches the Wide Model how to use GPIO tools, and the `cognitive.json` declares the hardware requirements.

```bash
# Scaffold on a development machine (or directly on the Pi)
cpm init rover-controller --template mcp-bridge
cd rover-controller
```

**`cognitive.json`:**
```json
{
  "name": "rover-controller",
  "version": "1.0.0",
  "description": "AI-controlled rover — drive, steer, read distance sensors",
  "author": "Your Name",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/your-org/rover-controller",
    "issues": "https://github.com/your-org/rover-controller/issues"
  },
  "hardware_requirements": {
    "min_ram_mb": 4096,
    "min_storage_mb": 512
  },
  "runtime": {
    "system_prompt": "prompts/system.md"
  }
}
```

**`prompts/system.md`:**
```
You are an AI robot controller. You control a two-wheeled rover using GPIO pins.

AVAILABLE MOTOR PINS:
  Left motor speed (PWM):  pin 12 (0-100 duty cycle)
  Left motor forward:      pin 5 (write 1)
  Left motor reverse:      pin 6 (write 1)
  Right motor speed (PWM): pin 13 (0-100 duty cycle)
  Right motor forward:     pin 19 (write 1)
  Right motor reverse:     pin 26 (write 1)
  Distance sensor trigger: pin 17
  Distance sensor echo:    pin 27

TOOL SYNTAX (use exactly as shown):
  @@cognitiveos.gpio.pwm(pin=<number>, duty_cycle=<0-100>)@@
  @@cognitiveos.gpio.pin_write(pin=<number>, value=<0|1>)@@
  @@cognitiveos.gpio.pin_read(pin=<number>)@@
  @@cognitiveos.gpio.mode(pin=<number>, mode=<input|output>)@@
  @@cognitiveos.system.wait(seconds=<number>)@@

MOVEMENT RECIPES:
  Forward: PWM both motors 75, both forward pins HIGH, both reverse LOW
  Reverse: PWM both motors 50, both forward LOW, both reverse HIGH
  Turn left: left PWM 0, right PWM 75, right forward HIGH
  Turn right: right PWM 0, left PWM 75, left forward HIGH
  Stop: all PWM 0, all direction pins LOW

DISTANCE SENSING RECIPE:
  1. Set trigger pin 17 as output, echo pin 27 as input
  2. Write trigger HIGH for 10 microseconds, then LOW
  3. Read echo pin — pulse width in microseconds / 58 = distance in cm
  (The Wide Model can approximate this timing)

SAFETY RULES:
  - Never set PWM above 80 indoors (too fast for close quarters)
  - If distance < 20 cm, stop all motors immediately
  - Always stop motors before changing direction
  - When the user says "stop" or "halt", stop all motors IMMEDIATELY
```

**Build and install:**
```bash
# No MCP server binary needed — the rover uses the system's gpio-mcp bridge
# which is auto-started by the daemon. The skill is pure prompt.

tar czf rover-controller-1.0.0.cgp .
cpm install ./rover-controller-1.0.0.cgp
```

## Phase 5: Drive with AI

Once the package is installed, the system prompt is injected into the Wide Model's prompt chain. You now control the rover through natural language in `cognitiveos-cli`.

### Basic Movement

```
You: "Drive forward at 75 percent speed"
  → Wide Model generates:
     @@cognitiveos.gpio.pwm(pin=12, duty_cycle=75)@@
     @@cognitiveos.gpio.pwm(pin=13, duty_cycle=75)@@
     @@cognitiveos.gpio.pin_write(pin=5, value=1)@@
     @@cognitiveos.gpio.pin_write(pin=6, value=0)@@
     @@cognitiveos.gpio.pin_write(pin=19, value=1)@@
     @@cognitiveos.gpio.pin_write(pin=26, value=0)@@
  → Daemon parses the @@toolCall@@ blocks, routes each to gpio-mcp
  → gpio-mcp writes PWM duty cycles and GPIO values via sysfs
  → Both motors spin forward at 75%
  → "Driving forward at 75% speed."
```

```
You: "Turn left"
  → Wide Model:
     @@cognitiveos.gpio.pwm(pin=12, duty_cycle=0)@@
     @@cognitiveos.gpio.pin_write(pin=5, value=0)@@
     @@cognitiveos.gpio.pin_write(pin=6, value=0)@@
     @@cognitiveos.gpio.pwm(pin=13, duty_cycle=75)@@
     @@cognitiveos.gpio.pin_write(pin=19, value=1)@@
     @@cognitiveos.gpio.pin_write(pin=26, value=0)@@
  → Left motor stops, right motor spins forward
  → Rover pivots left
```

```
You: "Stop"
  → Wide Model:
     @@cognitiveos.gpio.pwm(pin=12, duty_cycle=0)@@
     @@cognitiveos.gpio.pwm(pin=13, duty_cycle=0)@@
     @@cognitiveos.gpio.pin_write(pin=5, value=0)@@
     @@cognitiveos.gpio.pin_write(pin=6, value=0)@@
     @@cognitiveos.gpio.pin_write(pin=19, value=0)@@
     @@cognitiveos.gpio.pin_write(pin=26, value=0)@@
  → All motors stop
```

### Timed Movement

```
You: "Drive straight for 3 seconds, then stop"
  → Wide Model:
     @@cognitiveos.gpio.pwm(pin=12, duty_cycle=75)@@
     @@cognitiveos.gpio.pwm(pin=13, duty_cycle=75)@@
     (forward pins set HIGH...)
     @@cognitiveos.system.wait(seconds=3)@@
     @@cognitiveos.gpio.pwm(pin=12, duty_cycle=0)@@
     @@cognitiveos.gpio.pwm(pin=13, duty_cycle=0)@@
     (all direction pins LOW...)
  → Rover drives forward for exactly 3 seconds
  → The tool loop supports up to 10 chained tool calls per response
```

### Obstacle Avoidance (with HC-SR04)

```
You: "Check for obstacles and drive forward if clear"
  → Wide Model:
     @@cognitiveos.gpio.mode(pin=17, mode=output)@@
     @@cognitiveos.gpio.mode(pin=27, mode=input)@@
     @@cognitiveos.gpio.pin_write(pin=17, value=1)@@
     @@cognitiveos.system.wait(seconds=0.00001)@@
     @@cognitiveos.gpio.pin_write(pin=17, value=0)@@
     @@cognitiveos.gpio.pin_read(pin=27)@@
  → (reads echo, estimates distance ~45 cm — within safe range)
  → @@cognitiveos.gpio.pwm(pin=12, duty_cycle=75)@@  (drive forward)
  → "Path is clear. Distance ahead: approximately 45 cm. Driving forward."
```

## Phase 6: Voice Control

Add the `audio-mcp` bridge (auto-started by the daemon) for voice I/O.

**`cognitive.json`** adds capabilities:
```json
{
  "runtime": {
    "capabilities": [
      "audio.voice_input",
      "audio.voice_output"
    ]
  }
}
```

**Updated system prompt additions:**
```
You can also use voice tools:
  @@cognitiveos.audio.tts(text="Hello, I am the rover")@@  ← speaks aloud
  @@cognitiveos.audio.capture(duration=5)@@                ← listens for 5 seconds

When using voice:
  - Announce what you're doing before doing it ("Driving forward.")
  - Read sensor values aloud ("Distance: 45 centimeters.")
  - If you don't understand audio input, say "I didn't catch that"
```

```
You (speaking): "Drive forward slowly"
  → Mic captures audio → STT → Wide Model
  → "Driving forward at 30% speed."
  → @@cognitiveos.gpio.pwm(pin=12, duty_cycle=30)@@
  → @@cognitiveos.audio.tts(text="Driving forward at 30 percent.")@@
  → Rover moves, speaker announces the action
```

## Phase 7: Safety and Emergency Shutdown

The rover has three layers of safety:

| Layer | Mechanism | Response Time |
|-------|-----------|---------------|
| 1. Software | System prompt "stop immediately" instruction + tool loop | Next LLM generation cycle (~1-3s) |
| 2. System code | Say "security" to trigger Raw Model emergency shutdown | Immediate (Raw Model bypasses LLM) |
| 3. Physical | Hardware kill switch on the 18650 battery line | Instant (cut power to motors) |

**Layer 2 — System code:**
```bash
# At any time, speak or type:
"security"
  → cognitiveos-cli sends system_code("security") to daemon
  → Daemon bypasses Wide Model entirely
  → Sends mcp_shutdown to all MCP servers
  → Pulls all GPIO pins LOW via gpioset
  → "Emergency shutdown complete. Motors stopped."
```

## Under the Hood: The Tool Call Pipeline

Here's exactly what happens when you say "drive forward":

```
1. CLI sends your text as {"type": "input_forward", "data": "drive forward"}
   over Unix socket /cognitiveos/run/daemon.sock

2. Daemon receives the message in handleInputForward()
   → Calls processPrompt("drive forward")

3. processPrompt() calls wmClient.Generate("drive forward", tool_support=true)
   → HTTP POST to local inference engine at http://127.0.0.1:11434/api/generate

4. Wide Model responds with text containing @@cognitiveos.gpio.pwm(...)@@
   and other @@toolCall()@@ blocks

5. Daemon's parseToolCalls() regex-extracts each @@...@@ block
   → [cognitiveos.gpio.pwm, cognitiveos.gpio.pin_write, ...]

6. For each tool call, daemon calls mcpMgr.Invoke(server="gpio-mcp",
   method="cognitiveos.gpio.pwm", params={pin: 12, duty_cycle: 75})
   → Routes via JSON-RPC 2.0 over gpio-mcp's stdin pipe

7. gpio-mcp receives the request, writes /sys/class/pwm/pwmchip2/pwm0/duty_cycle
   → Linux kernel updates the PWM hardware register
   → L298N receives PWM signal → motors spin

8. gpio-mcp responds → daemon feeds results back to LLM for next iteration
   (tool loop runs up to 10 iterations per user message)

9. Final response sent back to CLI as {"type": "output_deliver", "data": "..."}
   → CLI displays "Driving forward at 75% speed." on screen
```

## Choosing a Model

On a Raspberry Pi 5 (8 GB), choose a highly quantized model that leaves room for MCP processes:

| Model | Params | Quant | RAM Usage | Quality | Real-time? |
|-------|--------|-------|-----------|---------|------------|
| Qwen2.5-1.5B | 1.5B | Q4_K_M | ~1.2 GB | Good | ✅ Yes |
| Llama-3.2-3B | 3B | Q4_K_M | ~2.4 GB | Better | ⚠️ Slight delay |
| Qwen2.5-3B | 3B | Q4_K_M | ~2.4 GB | Better | ⚠️ Slight delay |
| Phi-3-mini | 3.8B | Q4_K_M | ~3.0 GB | Best | ❌ Too slow for real-time |

Install a model:
```bash
# Via inference engine API
cpm install qwen2.5-1.5b --template gguf-model
# Or pull directly
curl -X POST http://127.0.0.1:11434/api/pull \
  -d '{"name": "qwen2.5-1.5b-q4_k_m.gguf", "path": "/cognitiveos/models/wide/active/"}'
```

## Extensions

Once the basic rover works, extend it:

| Addition | What You Need | New Capability |
|----------|---------------|----------------|
| Camera | USB camera + `vision-mcp` bridge | "Drive toward the red ball" |
| GPS module | UART GPS + `serial-mcp` bridge | "Navigate to coordinates 37.7749, -122.4194" |
| Robotic arm | Servo motors + `gpio-mcp` PWM | "Pick up the object in front of you" |
| LCD display | HDMI display + `display-mcp` bridge | "Show speed and battery on screen" |
| Mapping | LiDAR + serial bridge | "Map this room and drive without hitting anything" |
