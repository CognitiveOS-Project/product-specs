# CognitiveOS Tutorials

Real-world examples showcasing the CognitiveOS package ecosystem.

## Index

| Tutorial | Template | What it demonstrates |
|----------|----------|---------------------|
| [Photo Viewer](photo-viewer.md) | `mcp-bridge` | Skill with an MCP server binary that renders images to the display |
| [YouTube Learner](youtube-learner.md) | `mcp-bridge` | Skill that fetches video transcripts, analyzes content, and saves learnings |
| [Coder Tool](coder-tool.md) | `mcp-bridge` | Multi-server skill that compiles, lints, and analyzes source code |
| [Home Automation](home-automation.md) | `mcp-bridge` | GPIO/serial bridge that controls lights, sensors, and relays |
| [Email Manager](email-manager.md) | `mcp-bridge` | Full email client with IMAP/SMTP MCP servers and system prompt instructions |
| [Voice Assistant](voice-assistant.md) | `prompt-only` | Pure prompt skill that turns the system into a voice-controlled assistant |
| [Study Buddy](study-buddy.md) | `gguf-model` | Flashcard/quiz generator backed by a locally-downloaded embedding model |
| [AI Model Publisher](ai-model-publisher.md) | `gguf-model` | Distributing a GGUF model with multi-quantization variants and unlock codes |
| [IoT Vendor](iot-vendor.md) | `firmware` + `mcp-bridge` | Dual-package product: MCU firmware + MCP bridge for smart thermostat |
| [SaaS CRM](saas-crm.md) | `mcp-bridge` | Salesforce CRM integration with OAuth2, keystore, and audit logging |
| [Dev Tools Company](dev-tools-company.md) | `mcp-bridge` | Proprietary static analyzer with license server and CI/CD integration |
| [EdTech Company](edtech-company.md) | `gguf-model` + `mcp-bridge` | Khan Academy offline tutor with curriculum decks and spaced repetition |
| [Hardware OEM](hardware-oem.md) | `firmware` + multi-package | Framework Laptop factory OS image with signed firmware and OTA updates |
| [Systems Integrator](systems-integrator.md) | `full` stack | Factory automation: PLC bridge + voice UI + sensor node firmware, air-gapped |
| [AI Rover](ai-rover.md) | `mcp-bridge` | AI-controlled robot: GPIO motor control, distance sensing, voice commands, emergency shutdown |
| [AI Companion](ai-companion.md) | multi-package | J.A.R.V.I.S.-style ambient AI: voice personality, workspace control, HUD, proactive secretary — 4 coordinated packages |
| [Download Weights](download-weights.md) | — | Downloading GGUF/safetensors models directly from Hugging Face Hub with `cpm download-weights` |

## How CognitiveOS Makes These Possible

Every tutorial follows the same flow:

1. **Scaffold** with `cpm init --template <type>`
2. **Declare** MCP servers and capabilities in `cognitive.json`
3. **Write** the system prompt that instructs the Wide Model
4. **Build** any required MCP server binaries
5. **Install** with `cpm install` — the daemon handles spawning, registration, and lifecycle

The Wide Model (the system's LLM) autonomously decides when to call each tool based on the user's natural-language request. No explicit routing, no API glue code — just declare what your skill can do, and the AI figures out the rest.
