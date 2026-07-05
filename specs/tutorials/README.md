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

## How CognitiveOS Makes These Possible

Every tutorial follows the same flow:

1. **Scaffold** with `cpm init --template <type>`
2. **Declare** MCP servers and capabilities in `cognitive.json`
3. **Write** the system prompt that instructs the Wide Model
4. **Build** any required MCP server binaries
5. **Install** with `cpm install` — the daemon handles spawning, registration, and lifecycle

The Wide Model (the system's LLM) autonomously decides when to call each tool based on the user's natural-language request. No explicit routing, no API glue code — just declare what your skill can do, and the AI figures out the rest.
