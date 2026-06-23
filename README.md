# CognitiveOS Product Specs

Standards, schemas, and protocol definitions for the CognitiveOS ecosystem.

## Contents

| Path | Description |
|------|-------------|
| `specs/vision.md` | Product vision, design philosophy, and UX scenarios |
| `specs/architecture.md` | System architecture overview and data flow |
| `specs/filesystem-hierarchy.md` | Directory tree, partition layout, persistence rules |
| `specs/mcp-conventions.md` | MCP tool naming, transport, error codes, registration |
| `specs/cognitiveosd-api.md` | Daemon API: message types, startup/shutdown, error codes |
| `specs/cli-spec.md` | CLI/TUI: display modes, keybindings, framebuffer integration |
| `specs/cpm-spec.md` | Package manager: commands, install lifecycle, error handling |
| `specs/inference-api.md` | Inference engine: Ollama-compatible API, model lifecycle |
| `specs/registry-api.md` | Registry REST API: search, download, publish, unlock codes |
| `specs/cgp-format.md` | `.cgp` (Cognitive Patch) distribution format |
| `specs/system-codes.md` | Wake, Idle, Security, Reset, Unlock code definitions |
| `specs/security-model.md` | Trust boundary, process isolation, code integrity, incident response |
| `specs/distro-build-spec.md` | Alpine image build process, partition layout, overlay structure |
| `schemas/cognitive.schema.json` | JSON Schema for cognitive.json manifest |
| `schemas/display-mcp.json` | Tool schema for display-mcp (render_image, render_video, screenshot) |
| `schemas/audio-mcp.json` | Tool schema for audio-mcp (play, capture, tts, volume, mute) |
| `schemas/network-mcp.json` | Tool schema for network-mcp (scan, connect, disconnect, status) |
| `schemas/gpio-mcp.json` | Tool schema for gpio-mcp (pin_read, pin_write, pwm, mode) |
| `schemas/serial-mcp.json` | Tool schema for serial-mcp (list, connect, send, receive) |

## Repos

| Repo | Layer | Description |
|------|-------|-------------|
| [product-specs](https://github.com/CognitiveOS-Project/product-specs) | Architecture | Standards and schemas (this repo) |
| [cognitiveos-distro](https://github.com/CognitiveOS-Project/cognitiveos-distro) | Base OS | Alpine Linux image builder |
| [cognitiveosd](https://github.com/CognitiveOS-Project/cognitiveosd) | Daemon | System daemon, codes, audits |
| [cli](https://github.com/CognitiveOS-Project/cli) | UI | Bubble Tea TUI frontend |
| [cpm](https://github.com/CognitiveOS-Project/cpm) | Package | Package manager |
| [inference](https://github.com/CognitiveOS-Project/inference) | Brain | LLM inference engine |
| [core-mcp-bridges](https://github.com/CognitiveOS-Project/core-mcp-bridges) | Hardware | MCP hardware servers |
| [cgp-template](https://github.com/CognitiveOS-Project/cgp-template) | Dev | .cgp boilerplate |
| [registry-server](https://github.com/CognitiveOS-Project/registry-server) | Infra | Package registry |
