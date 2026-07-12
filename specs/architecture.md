# CognitiveOS Architecture

## Overview

CognitiveOS is an intent-centric, AI-native operating system. The human speaks or types what they want. The AI handles everything. No apps, no browsers, no permission layers.

```
+-------------------------------------------------------------+
|                     CognitiveOS                              |
+-------------------------------------------------------------+
|  UI Layer         |  cli (Go/Bubble Tea TUI)                 |
|                   |  Direct Framebuffer Media (fbv/mpv)      |
+-------------------+-----------------------------------------+
|  Daemon Layer     |  cognitiveosd (system daemon)            |
|                   |  - 5 System Codes                         |
|                   |  - Resource audits                        |
|                   |  - MCP supervisor                         |
+-------------------+-----------------------------------------+
|  Package Layer    |  cpm (Cognitive Package Manager)         |
|                   |  .cgp format                             |
+-------------------+-----------------------------------------+
|  Brain Layer      |  Raw Model (local, firmware-level)       |
|                   |  Wide Model (operational, upgradeable)    |
+-------------------+-----------------------------------------+
|  Hardware Layer   |  core-mcp-bridges                        |
|                   |  (display, audio, network, GPIO, serial) |
+-------------------+-----------------------------------------+
|  Base OS          |  Hardened Linux (Alpine primary, Ubuntu/Red Hat planned) |
|                   |  - Custom /etc/inittab (no login)         |
|                   |  - Single-process root                    |
|                   |  - No desktop environment                 |
+-------------------------------------------------------------+
```

## Layer Descriptions

### 1. Base OS (Linux)

Hardened Linux distribution. Alpine Linux is the current primary implementation, with Ubuntu and Red Hat variants planned (see [Multi-OS Strategy](distro-build-spec.md#multi-os-strategy)).

Current build (Alpine) provides:

- **No multi-user** — root is the only actor
- **No display manager** — no X11, no Wayland, no window manager
- **No app runtime** — no Zygote, no Android Runtime, no JVM
- **Direct framebuffer** — `/dev/fb0` for media output
- **ALSA** — direct audio hardware access

Boot sequence:
1. Kernel loads hardware drivers
2. `/etc/inittab` skips login, spawns `cognitiveos-cli` directly on tty1
3. `cognitiveos-cli` starts, connects to `cognitiveosd`

### 2. Hardware Layer (core-mcp-bridges)

Thin MCP servers that wrap Linux system tools:

| Capability | Tool | MCP Server |
|-----------|------|------------|
| Show image | fbv / fbi | display-mcp |
| Play video | mpv (drm mode) | display-mcp |
| Capture mic | ALSA (arecord) | audio-mcp |
| Play audio | ALSA (aplay) | audio-mcp |
| Network scan | iwconfig | network-mcp |
| GPIO control | libgpiod / sysfs | gpio-mcp |
| Serial comm | /dev/tty* | serial-mcp |

### 3. Brain Layer

**Raw Model** (firmware):
- Always-on, always-local
- Runs on minimal hardware (MCU-class sufficient)
- Handles: wake word detection, system code validation, hardware audit loop
- Stateless — no memory, no learning
- Compiled into base firmware image
- See [Raw Model Specification](raw-model.md) for full details

**Wide Model** (operational):
- Can be local or remote
- Handles: intent parsing, task execution, tool orchestration
- Upgradeable from distributed catalog
- Can be swapped at runtime by Raw Model
- May require unlock code for premium versions
- See [Ephemeral Identity](ephemeral-identity.md) for long-term biometric vision

### 4. Package Layer (cpm + .cgp)

`cpm` manages the lifecycle of `.cgp` (Cognitive Patch) files — self-contained skill packages.

A `.cgp` contains:
- `cognitive.json` — manifest with version, dependencies, hardware requirements
- `prompts/` — system prompt and templates
- `tools/` — MCP server binaries
- `weights/` — optional model adapters

### 5. Daemon Layer (cognitiveosd)

The central system daemon:
- Implements the 5 system codes
- Runs hardware audits (disk, RAM, CPU)
- Supervises all MCP server processes
- Routes human input to the Wide Model
- Manages Wide Model lifecycle

### 6. UI Layer (cli)

Thin Bubble Tea TUI:
- Minimal text prompt ("Listening...")
- Voice and text input
- Direct framebuffer overlay for media
- Connects to cognitiveosd via Unix socket
- Stateless — can crash and restart safely

## Data Flow

```
Human speaks → audio-mcp captures → cognitiveosd receives
  → Raw Model validates (wake word?)
    → [if wake] Wide Model processes intent
      → Wide Model calls MCP tools
        → tool output returned to human via TUI
```

## Device Scaling

| Device | Raw Model | Wide Model | Storage |
|--------|-----------|------------|---------|
| Smartphone | On-chip MCU | Local (llama.cpp) | Flash |
| Watch | On-chip MCU | Remote (LAN server) | Minimal |
| Raspberry Pi | Main CPU thread | Local | SD card |
| PC/Server | Embedded | Local (GPU) | SSD |
| TV | Embedded | Remote (LAN server) | Flash |
| AC/MCU | Dedicated MCU | Remote (cloud/LAN) | <1 MB |

## Recommended Hardware

See [Hardware Recommendations](hardware.md) for a curated list of tested platforms for each deployment role (Wide Model inference, Raw Model edge, MCP bridges, and industrial nodes).
