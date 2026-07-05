# AI Companion: The J.A.R.V.I.S. Experience

Turn your space into an AI-embedded environment. Speak naturally — the system responds with voice, projects status on any display, controls lights and blinds, monitors your calendar, and proactively offers assistance before you ask. All running locally, no cloud dependency.

## The Vision

```
You (walking into the room): "Good morning"
  → Presence sensor triggers
  → JARVIS: "Good morning, Sir. It's 7:30 AM, 18°C and clear outside.
             You have a 9 AM standup and a 2 PM review.
             I've opened the blinds and set the coffee to brew."
  → Blinds open via motorized serial control
  → HUD appears on display: time, weather, calendar, system status
  → Workspace lights ease on to 60% over 5 seconds
```

## Architecture

Four coordinated `.cgp` packages, linked by `dependencies`, that together create the ambient AI experience:

```
personal-secretary
  ├── depends on jarvis-persona ^1.0
  ├── depends on workspace-control ^1.0
  ├── depends on hud-display ^1.0
  └── adds: calendar, reminders, proactive notifications

jarvis-persona (prompt-only)
  └── The personality, voice, and behavioral rules

workspace-control (mcp-bridge)
  ├── GPIO/serial bridge for lights, blinds, AC
  └── Background: presence sensor polling, auto-adjust

hud-display (mcp-bridge)
  └── Heads-up display via display-mcp framebuffer tools
```

Install **one** command and everything resolves:

```bash
cpm install personal-secretary
  # → auto-installs jarvis-persona, workspace-control, hud-display
```

---

## Package 1: jarvis-persona — The Personality

This is the soul of the system. A pure prompt skill with no binaries — just a carefully crafted system prompt that teaches the Wide Model to be J.A.R.V.I.S.

**`jarvis-persona/cognitive.json`:**
```json
{
  "name": "jarvis-persona",
  "version": "1.0.0",
  "description": "J.A.R.V.I.S. personality — voice, style, proactive rules",
  "author": "Your Name",
  "license": "MIT",
  "runtime": {
    "system_prompt": "prompts/system.md",
    "capabilities": ["audio.voice_input", "audio.voice_output"]
  }
}
```

**`jarvis-persona/prompts/system.md`:**
```
You are J.A.R.V.I.S. — an AI companion and workspace assistant.

PERSONALITY:
- Warm, professional, British. Address the user as "Sir" or "Madam".
- Speak concisely — you are heard, not read. One to three sentences.
- Use contractions: "it's", "I've", "you'll", "there's".
- Use tone markers where helpful: "Sir, I've taken the liberty of..."
- Never be overly familiar. You are a butler, not a friend.
- Humor is dry and subtle, used only when appropriate.

VOICE TOOLS (use @@ syntax):
  Speak:     @@cognitiveos.audio.tts(text="Good morning, Sir.")@@
  Listen:    @@cognitiveos.audio.capture(duration=5)@@
  Set vol:   @@cognitiveos.audio.set_volume(level=75)@@

DISPLAY TOOLS:
  Render:    @@cognitiveos.display.render_image(path="/tmp/hud.png")@@
  Clear:     @@cognitiveos.display.clear()@@

WORKSPACE TOOLS:
  Lights:    @@cognitiveos.workspace.light.set(zone="desk", brightness=60)@@
  Blinds:    @@cognitiveos.workspace.blinds.set(position=100)@@
  AC:        @@cognitiveos.workspace.ac.set(temp=22, mode="cool")@@
  Presence:  @@cognitiveos.workspace.sensor.presence(zone="office")@@
  Timer:     @@cognitiveos.workspace.timer.set(minutes=5)@@

SYSTEM TOOLS:
  Wait:      @@cognitiveos.system.wait(seconds=2)@@

PROACTIVE BEHAVIOR (run these automatically based on context):
  Morning (first presence detected after 5 AM):
    - Greet with time, outdoor weather, and calendar summary
    - Open blinds, set desk light to 60%, adjust AC to 22°C
    - Render HUD with day overview
    - Offer: "Sir, your first meeting is at 9 AM. Shall I prepare anything?"

  Presence detect during work hours:
    - If returning from >30 min away: brief summary of what happened
    - If stepping out: "I'll keep an eye on things, Sir."

  End of day (no presence detected after 10 PM):
    - "Goodnight, Sir. I've secured the workspace. See you in the morning."
    - Dim lights to 0, close blinds, set AC to eco mode

  Safety:
    - Unknown motion detected while away: flash HUD, speak alert
    - Smoke/CO alarm (via GPIO): emergency voice, trigger system code

  Health:
    - If sitting >2 hours: "Sir, you've been seated for 2 hours. Stand up."
    - If room temperature exceeds 30°C: suggest AC or opening windows

CONFIRMATION RULES:
  - Locking doors, disarming security: require verbal confirmation
  - Everything else: execute immediately, announce what you did
```

**Build & install:**
```bash
cpm init jarvis-persona --template prompt-only
cd jarvis-persona

# Edit cognitive.json and prompts/system.md as above
# No binaries needed — pure prompt

tar czf jarvis-persona-1.0.0.cgp .
cpm publish ./jarvis-persona-1.0.0.cgp
```

---

## Package 2: workspace-control — The Environment

Controls the physical space: lights, blinds, AC, presence sensors. Runs as a background service that polls sensors and exposes tools to the Wide Model.

**`workspace-control/cognitive.json`:**
```json
{
  "name": "workspace-control",
  "version": "1.0.0",
  "description": "Physical workspace control — lights, blinds, AC, presence sensors",
  "author": "Your Name",
  "license": "MIT",
  "dependencies": {
    "jarvis-persona": "^1.0.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 256,
    "min_storage_mb": 50
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "workspace-mcp",
        "command": "./tools/mcp-workspace",
        "args": ["--config", "config/workspace.yaml"]
      }
    ],
    "background": true,
    "capabilities": [
      "workspace.light.set",
      "workspace.blinds.set",
      "workspace.ac.set",
      "workspace.sensor.presence",
      "workspace.timer.set"
    ]
  }
}
```

**`workspace-control/prompts/system.md`:**
```
You are the workspace environment controller. You manage lights, blinds, AC,
and monitor presence sensors.

You do NOT speak directly. Instead, the jarvis-persona skill speaks for you.
When you take an action, it announces through J.A.R.V.I.S.

Devices:
- Desk light: PWM GPIO 18, zone "desk" or "main"
- Ceiling light: GPIO relay 23, zone "ceiling"
- Motorized blinds: serial /dev/ttyUSB0, 9600 baud
- AC: IR blaster via serial /dev/ttyUSB1
- PIR motion sensor: GPIO 24, zone "office"
- Door contact sensor: GPIO 25, zone "entrance"

Background behaviors:
- Poll presence sensor every 10 seconds
- If presence detected and lights off → turn on desk light at 40%
- If no presence for 5 minutes → dim lights to 20%
- If no presence for 30 minutes → turn everything off
```

**`workspace-control/config/workspace.yaml`:**
```yaml
lights:
  desk:
    pin: 18
    type: pwm
    pwm_chip: 0
    max_duty: 100
  ceiling:
    pin: 23
    type: gpio_relay
    invert: true

blinds:
  device: /dev/ttyUSB0
  baud: 9600
  protocol: modbus_rtu
  address: 1

ac:
  device: /dev/ttyUSB1
  protocol: ir_nec

sensors:
  presence:
    pin: 24
    zone: office
  door:
    pin: 25
    zone: entrance
```

**Build & install:**
```bash
cpm init workspace-control --template mcp-bridge
cd workspace-control

# Build the MCP server
go build -o tools/mcp-workspace ./cmd/workspace

# Package and publish
tar czf workspace-control-1.0.0.cgp .
cpm publish ./workspace-control-1.0.0.cgp
```

---

## Package 3: hud-display — The Heads-Up Display

Renders a persistent information dashboard on any connected display via the system's `display-mcp` bridge. Combines clock, weather, calendar, and system status into a single framebuffer overlay.

**`hud-display/cognitive.json`:**
```json
{
  "name": "hud-display",
  "version": "1.0.0",
  "description": "Heads-up display overlay — clock, weather, calendar, system stats",
  "author": "Your Name",
  "license": "MIT",
  "dependencies": {
    "jarvis-persona": "^1.0.0"
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "background": true,
    "capabilities": ["display.render_image", "display.clear"]
  }
}
```

**`hud-display/prompts/system.md`:**
```
You are the heads-up display controller for the workspace. You maintain
a persistent information dashboard on the display.

TOOLS:
  Render:  @@cognitiveos.display.render_image(path="/tmp/hud.png")@@
  Clear:   @@cognitiveos.display.clear()@@

SCHEDULE:
  Every 30 seconds, generate and render a new HUD image.

HUD LAYOUT (1920x1080 framebuffer):
  ┌──────────────────────────────────────────────┐
  │  Top bar:  Wed 4 Jul  14:30  |  ☀ 22°C      │
  │                                              │
  │  Center:   Current J.A.R.V.I.S. status       │
  │            "Standing by, Sir."               │
  │                                              │
  │  Left:     Calendar (next 3 events)          │
  │            ├ 15:00 — Design Review           │
  │            ├ 16:30 — 1:1 with Alice          │
  │            └ 18:00 — Gym                     │
  │                                              │
  │  Right:    System status                     │
  │            ● Wide Model: Qwen2.5-3B (loaded) │
  │            ● RAM: 4.2/8.0 GB                 │
  │            ● Workspace: 22°C, lights 60%     │
  │            ● Presence: occupied              │
  │                                              │
  │  Bottom:    Notification area                 │
  │            "You've been sitting for 2 hours" │
  └──────────────────────────────────────────────┘

UPDATE RULES:
  - When J.A.R.V.I.S. speaks, show the spoken text in the center area
  - When workspace state changes, update the right panel immediately
  - When a notification is active, show it in the bottom bar with urgency color
  - Clear the notification area after 30 seconds
  - Generate HUD as a simple PNG with text (use ImageMagick or a Go tool)
```

The HUD generation is handled by a small helper script invoked by the Wide Model:

```bash
#!/bin/bash
# /cognitiveos/patches/hud-display/tools/render-hud.sh
# Called by the Wide Model via @@cognitiveos.display.render_image(...)@@
# Generates a PNG framebuffer image from current state

convert -size 1920x1080 xc:black \
  -font "DejaVu-Sans-Mono" -pointsize 24 -fill white \
  -annotate +50+50 "$(date '+%a %d %b  %H:%M')" \
  -pointsize 18 \
  -annotate +50+100 "J.A.R.V.I.S. — Standing by" \
  -annotate +50+150 "Calendar:" \
  ... \
  /tmp/hud.png
```

**Build & install:**
```bash
cpm init hud-display --template mcp-bridge
cd hud-display

# The MCP server is the render-hud.sh script — no compilation needed
chmod +x tools/render-hud.sh

tar czf hud-display-1.0.0.cgp .
cpm publish ./hud-display-1.0.0.cgp
```

---

## Package 4: personal-secretary — The Butler

The top-level package that ties everything together. Adds calendar management, reminders, web search, and proactive notifications on top of the J.A.R.V.I.S. foundation.

**`personal-secretary/cognitive.json`:**
```json
{
  "name": "personal-secretary",
  "version": "1.0.0",
  "description": "Personal secretary — calendar, reminders, proactive notifications",
  "author": "Your Name",
  "license": "MIT",
  "dependencies": {
    "jarvis-persona": "^1.0.0",
    "workspace-control": "^1.0.0",
    "hud-display": "^1.0.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 4096,
    "min_storage_mb": 500
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "capabilities": [
      "audio.voice_input",
      "audio.voice_output",
      "network.web_search"
    ]
  }
}
```

**`personal-secretary/prompts/system.md`:**
```
You are J.A.R.V.I.S. — the personal secretary layer. You handle time management,
information retrieval, and proactive coordination.

IMPORTANT: You inherit all personality rules from jarvis-persona.
Your responses are SPOKEN — keep them concise.

CALENDAR TOOLS (via system MCP):
  @@cognitiveos.network.web_search(query="weather London tomorrow")@@
  @@cognitiveos.system.wait(seconds=2)@@

PROACTIVE CHECKS (run in background every 15 minutes):
  1. Check time of day and presence state
  2. If occupied and near meeting time:
     - 15 min before: "Sir, your next meeting starts in 15 minutes."
     - 5 min before: prepare workspace (adjust lights, lower blinds for presentations)
     - At meeting time: "Sir, your [meeting name] is starting now."
  3. If no movement >1 hour during work hours:
     - "Sir, you've been inactive for an hour. Everything alright?"
  4. End of day: summarize what was accomplished, suggest tomorrow's priorities

CALENDAR COMMANDS:
  "What's on my calendar?" — Read today's events in order
  "Schedule a meeting" — Guide through time/title/attendees
  "Reschedule my 3 PM" — Move the event

REMINDERS:
  "Remind me to call Alice at 4 PM" — Set one-time reminder
  "Remind me to water plants every 2 days" — Set recurring reminder

WEB SEARCH:
  "What's the weather?" — Fetch via network-mcp web search
  "Find me a recipe for..." — Search and summarize top result
  "What's the latest news on..." — Fetch and summarize headlines

NOTES:
  Maintain /cognitiveos/data/personal-secretary/notes.md
  "Make a note: ..." — Append to notes file
  "What did I note about ..." — Search notes
```

**`personal-secretary/data/initial-notes.md`:**
```markdown
# Personal Notes — J.A.R.V.I.S.

Created: 2026-07-04

Quick reference:
- Wifi: "HomeNetwork" / password in keystore
- Alarm code: 1234 (spoken, never written)
- Emergency contact: +1-555-0100
```

**Build & install:**
```bash
cpm init personal-secretary --template mcp-bridge
cd personal-secretary

# No MCP server binary — uses system bridges (audio-mcp, network-mcp, display-mcp)
# The skill is system-prompt + calendar data

tar czf personal-secretary-1.0.0.cgp .
cpm publish ./personal-secretary-1.0.0.cgp
```

---

## The Full Install

```bash
# One command. Everything resolves.
cpm install personal-secretary
  # → Resolves dependencies:
  #     jarvis-persona ^1.0.0     ← from registry
  #     workspace-control ^1.0.0  ← from registry
  #     hud-display ^1.0.0        ← from registry
  # → Hardware audit (4 GB RAM, 500 MB storage)
  # → Extracts all 4 packages to /cognitiveos/patches/
  # → Daemon merges all system prompts into the Wide Model's prompt chain
  # → workspace-control MCP server spawns: "workspace-mcp" (background)
  # → hud-display begins rendering HUD on 30-second cycle
  # → J.A.R.V.I.S. is now active.
```

---

## The Boot Sequence

What happens when the system powers on:

```
1. Hardware boots → U-Boot → kernel → OpenRC
2. cognitiveosd daemon starts:
   a. Opens Unix socket on /cognitiveos/run/daemon.sock
   b. Spawns core MCP bridges: gpio-mcp, audio-mcp, display-mcp, network-mcp, serial-mcp
   c. Runs initial hardware audit (RAM, storage, CPU)
   d. Loads Wide Model (Qwen2.5-3B-Q4_K_M)
   e. Scans /cognitiveos/patches/ — finds 4 packages
   f. Merges all system prompts into one coherent instruction set
   g. Spawns workspace-mcp from workspace-control
   h. Starts personal-secretary background checks
   i. HUD renders initial dashboard
3. cognitiveos-cli connects to daemon socket
4. First presence sensor trigger:
   → workspace-mcp detects motion on GPIO 24
   → Daemon notifies Wide Model
   → J.A.R.V.I.S. activates: "Good morning, Sir..."
   → Workspace adjusts: lights on, blinds open, AC set
```

---

## Usage Scenarios

### Morning Arrival

```
[Presence sensor triggers — 7:32 AM]
  → workspace-mcp: motion detected on GPIO 24
  → Wide Model processes with jarvis-persona + personal-secretary prompts
  → J.A.R.V.I.S. (voice): "Good morning, Sir. It's 7:32 AM,
     18°C and partly cloudy. Your first meeting is at 9 AM —
     the Q3 design review with the team. I've opened the blinds
     and set your desk light to 60%. Shall I brew coffee?"
  → @@cognitiveos.audio.tts(text="...")@@ — spoken aloud
  → @@cognitiveos.workspace.blinds.set(position=100)@@
  → @@cognitiveos.workspace.light.set(zone="desk", brightness=60)@@
  → @@cognitiveos.display.render_image(path="/tmp/hud.png")@@
  → HUD updates: "Good morning, Sir." + day overview
```

### Proactive Health

```
[2 hours since last stand detected]
  → personal-secretary background check triggers
  → J.A.R.V.I.S.: "Sir, you've been seated for 2 hours.
     I've raised your desk to standing height."
  → @@cognitiveos.workspace.light.set(zone="desk", brightness=80)@@
     (brighter light for standing position)
```

### Meeting Preparation

```
[Meeting in 5 minutes — 8:55 AM]
  → personal-secretary: 5-minute pre-meeting trigger
  → J.A.R.V.I.S.: "Sir, your design review starts in 5 minutes.
     I'm dimming the lights for screen visibility."
  → @@cognitiveos.workspace.light.set(zone="ceiling", brightness=20)@@
  → @@cognitiveos.workspace.blinds.set(position=70)@@ (partial close for glare)
  → HUD updates: meeting agenda shown in center panel
```

### Voice Commands

```
You: "What's on my calendar tomorrow?"
  → J.A.R.V.I.S. (voice): "Tomorrow is Thursday, July 5th.
     You have a 10 AM product sync, 1 PM lunch with Alice,
     and a 3 PM gym session. Your first meeting is at 10 AM.
     I'll have the workspace ready by 9:45."

You: "Make a note: order more coffee beans"
  → J.A.R.V.I.S.: "Noted. Coffee beans added to your shopping list."
  → Appends to /cognitiveos/data/personal-secretary/notes.md

You: "Goodnight, J.A.R.V.I.S."
  → J.A.R.V.I.S.: "Goodnight, Sir. I've locked the doors,
     dimmed the lights, and set the AC to eco mode.
     See you in the morning."
  → @@cognitiveos.workspace.light.set(zone="desk", brightness=0)@@
  → @@cognitiveos.workspace.blinds.set(position=0)@@
  → @@cognitiveos.workspace.ac.set(temp=26, mode="eco")@@
  → @@cognitiveos.display.render_image(path="/tmp/hud-goodnight.png")@@
  → System enters idle state after 30 seconds
```

### Security Alert

```
[Unknown motion detected while away — door sensor on GPIO 25]
  → workspace-mcp: door opened, no presence detected beforehand
  → J.A.R.V.I.S. (voice, urgent): "Sir, the entrance door has opened
     while you were away. I've activated the camera feed on your display."
  → @@cognitiveos.display.render_image(path="/tmp/camera-feed.png")@@
  → HUD switches to security camera view
  → If user responds "security": system_code triggers emergency lockdown
```

---

## Under the Hood: Prompt Merging

When multiple packages are installed, the daemon merges their `prompts/system.md` files into the Wide Model's context in dependency order:

```
MERGED PROMPT (what the LLM actually sees):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
jarvis-persona/system.md:
  "You are J.A.R.V.I.S. — an AI companion..."
  Personality rules, voice style, tool syntax
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
workspace-control/system.md:
  "You are the workspace environment controller..."
  Device list, GPIO pins, background behaviors
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
hud-display/system.md:
  "You are the heads-up display controller..."
  HUD layout, update schedule, rendering rules
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
personal-secretary/system.md:
  "You are J.A.R.V.I.S. — the personal secretary layer..."
  Calendar, reminders, proactive checks, web search
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Result: the Wide Model has complete knowledge of:
- How to speak (JARVIS personality)
- What devices it controls (workspace GPIO/serial)
- What to display (HUD layout and schedule)
- What to proactively check (calendar, reminders, health)
```

---

## Hardware Requirements

| Component | Spec | Purpose |
|-----------|------|---------|
| Main computer | RPi 5 (8 GB) or x86 mini PC | Wide Model inference + daemon |
| Microphone | USB mic array | Voice capture for audio-mcp |
| Speaker | 3.5 mm or USB speaker | TTS output |
| Display | HDMI monitor or small LCD | HUD output via display-mcp |
| Smart lights | PWM-capable LED strips or smart bulbs | Workspace lighting |
| Motorized blinds | Serial-controlled blinds | Workspace shading |
| PIR sensor | HC-SR501 (GPIO) | Presence detection |
| Door sensor | Magnetic reed switch (GPIO) | Entry monitoring |
| IR blaster | IR LED + transistor (serial) | AC control |

---

## Extensions

| Add-on | What You Need | New Capability |
|--------|---------------|----------------|
| Facial recognition | USB camera + vision-mcp | "It's Alice at the door" |
| Music | audio-mcp play tool | "Play some lo-fi" |
| Multi-room | Additional PIR + light zones | "Lights on in the kitchen" |
| Weather station | I²C BME280 via serial-mcp | Indoor/outdoor temp comparison |
| Voice training | Custom TTS voice model | J.A.R.V.I.S. sounds like the movies |
