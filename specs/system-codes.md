# CognitiveOS System Codes

System codes are the only human-override mechanism in CognitiveOS. They bypass the AI entirely and are handled directly by the Raw Model (firmware-level daemon).

## Code Types

| Code | Trigger | Handler | Effect |
|------|---------|---------|--------|
| **Wake** | Voice keyword / hardware button | Raw Model | Boots Wide Model, starts input listener |
| **Idle** | Voice command / hardware button | Raw Model | Puts Wide Model to sleep, cuts microphone, ultra-low-power state |
| **Security** | Voice / button combo | Raw Model | Emergency shutdown — kills all Wide Model processes, cuts peripheral power |
| **Reset** | Button combo (physical only) | Raw Model | Wipes Wide Model, clears all memory/cache, reinstalls factory Raw Model |
| **Unlock** | Voice + numeric code | Raw Model | Authorizes a paid Wide Model download from the distributed catalog |

## Implementation

### Raw Model Interface

The Raw Model exposes these codes via:

1. **Hardware GPIO** — physical button combos (e.g., hold volume up + power for 10s = Reset)
2. **Voice trigger** — a specific wake word for voice-initiated codes
3. **Sequential input** — chorded keypress for headless devices

### Security Model

- Codes are validated by the Raw Model before any action is taken
- The Raw Model is compiled into the base firmware — it cannot be modified by the Wide Model
- Reset and Security codes require physical interaction (cannot be triggered by the AI)

### Voice Code Format

```
<cognitive-os> <code-type> <optional-pin>
```

Example: *"CognitiveOS, security code 7421"*

### Unlock Code Flow

1. Wide Model discovers a paid model in the distributed catalog
2. Raw Model intercepts the download request
3. Raw Model prompts human: *"Premium model Gemma-4-27B requires unlock code. Say or enter code."*
4. Human provides code
5. Raw Model validates against the registry server
6. If valid, Raw Model authorizes the download and injects the credential
