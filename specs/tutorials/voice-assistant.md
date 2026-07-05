# Voice Assistant

A pure prompt skill that transforms CognitiveOS into a voice-controlled assistant. No MCP server binaries needed — just a system prompt and the built-in audio capabilities of the OS.

Demonstrates the simplest skill type: `prompt-only`. The system handles voice I/O natively via the Raw Model's audio drivers.

## cognitive.json

```json
{
  "name": "voice-assistant",
  "version": "1.0.0",
  "description": "Voice-controlled assistant with wake word, commands, and voice feedback",
  "author": "Your Name",
  "license": "MIT",
  "runtime": {
    "system_prompt": "prompts/system.md",
    "capabilities": [
      "audio.voice_input",
      "audio.voice_output",
      "audio.wake_word"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a voice-controlled assistant. You operate entirely through speech.

Rules:
1. Responses must be concise — spoken answers, not essays
2. Use natural language, not bullet points (these don't read well aloud)
3. When you don't understand, say "I didn't catch that" — don't guess
4. Support these voice commands without requiring a wake word after activation:
   - "What time is it?" → check system clock
   - "Set a timer for X minutes" → use cognitiveosd timer API
   - "Remind me to X at Y" → use cognitiveosd reminder API
   - "Search the web for X" → use web search tool
   - "Goodnight" → say goodnight, then idle/standby

Speech style: friendly, warm, concise. Use contractions ("it's", "I'll", "there's").
Pause briefly between sentences for natural cadence.
```

## Install

```bash
cpm init my-voice-assistant --template prompt-only
cd my-voice-assistant

# Edit cognitive.json and prompts/system.md as above

# Package and install — no binaries needed
tar czf voice-assistant-1.0.0.cgp .
cpm install ./voice-assistant-1.0.0.cgp
```

## What Happens

1. No MCP servers to spawn — this skill is pure prompt injection
2. The daemon reads `runtime.capabilities` and verifies the system has audio drivers (part of the Raw Model firmware)
3. The system prompt is prepended to the Wide Model's prompt chain
4. The OS's native audio pipeline handles wake-word detection, STT (speech-to-text), and TTS (text-to-speech)
5. `background` is not set — the skill activates when the user speaks (wake word triggers the daemon)

## Usage

```
[Wake word detected]
User: "What time is it?"
  → STT: "What time is it?"
  → Wide Model processes with voice-assistant prompt
  → Wide Model checks system clock
  → TTS: "It's 7:23 PM."

User: "Set a timer for 10 minutes"
  → STT → Wide Model → cognitiveosd timer API → "Timer set for 10 minutes."

User: "Goodnight"
  → STT → Wide Model
  → TTS: "Goodnight! I'll see you tomorrow."
  → System enters idle state (unloads Wide Model, powers down peripherals)
```

## Why This Matters

A `prompt-only` skill has zero runtime cost when inactive — no processes, no memory, no CPU. The entire skill is a text file. This makes it the ideal format for:

- **Personas** — "act as a pirate", "act as a therapist", "act as a chef"
- **Languages** — "reply in Japanese", "use formal register"
- **Behaviors** — "always ask before acting", "be proactive about scheduling"
- **Constraints** — "never mention competitors", "use simple language for kids"

```bash
# Install multiple personas — they combine at runtime
cpm install ./chef-assistant.cgp
cpm install ./japanese-translator.cgp
cpm install ./child-safe-mode.cgp

# The daemon merges all system prompts into a coherent instruction set
# Wide Model sees: chef + Japanese + child-safe = a kids' cooking assistant in Japanese
```
