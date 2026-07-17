# CLI Specification

Version: 1.1.0-draft

## Overview

`cognitiveos-cli` is the human interface to CognitiveOS. It operates in two modes:

- **TUI mode** (default): Interactive terminal user interface with 7 display modes, keyboard shortcuts, and voice input. Replaces the traditional desktop environment.
- **CLI mode** (`--cmd`): Non-interactive command-line interface for scripting, automation, and pipes. Sends a command, prints the response, and exits.

Both modes use the same `internal/client` package to communicate with `cognitiveosd` via Unix socket. The binary is **thin** — it captures input and displays output. All intelligence and state live in cognitiveosd and the Wide Model. Either interface can crash and restart without affecting system stability.

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/cognitiveos/run/daemon.sock` | Daemon socket path |
| `--tui` | `false` | Launch interactive TUI (same as default) |
| `--cmd <text>` | — | Send command, print response, exit (non-interactive) |
| `--json` | `false` | Print full JSON envelope (requires `--cmd`) |
| `--version` | — | Print version and exit |
| `--help` | — | Print usage |

### Usage

```
cognitiveos-cli                        # Launch TUI (default)
cognitiveos-cli --tui                  # Launch TUI (explicit)
cognitiveos-cli --cmd "what time"      # CLI: print plain text response
cognitiveos-cli --cmd "show photos" --json  # CLI: print full JSON envelope
cognitiveos-cli --version              # Print version
```

## Connection

### Socket

- **Path:** `/cognitiveos/run/daemon.sock`
- **Protocol:** JSON-over-Unix-stream (see cognitiveosd-api.md)

### Startup (TUI Mode)

1. CLI starts on tty1
2. Renders idle screen
3. Connects to daemon socket (retries every second for 30 seconds, then shows error)
4. Sends `status_request` to get current daemon state
5. Enters main event loop

### Startup (CLI Mode)

1. Connects to daemon socket
2. Sends `input_forward` with the command text
3. Waits for `output_deliver` response (30 second timeout)
4. Prints response (plain text or JSON)
5. Exits with code 0 on success, 1 on error

### Reconnection (TUI Mode)

If the connection to cognitiveosd is lost:
1. Display frozen state with message: "Connecting..."
2. Retry connection every second
3. After 30 seconds of failure: display "Daemon unavailable. Check system."
4. Continue retrying indefinitely

---

## TUI Mode

The interactive terminal interface with 7 display modes.

### Display Modes

The TUI renders in one of the following modes. Transitions between modes are instantaneous — no animations or transitions that could be mistaken for responsiveness.

#### 1. Idle Mode

The default state when no interaction is occurring.

```
┌────────────────────────────────┐
│                                │
│         CognitiveOS            │
│                                │
│           ● ready              │
│                                │
│                                │
│    (press / to speak,          │
│     type anything to begin)    │
│                                │
└────────────────────────────────┘
```

- Output: The word "ready" next to a small indicator dot
- No cursor (nothing to type at)
- Press any printable character → switches to listening mode with that character pre-filled
- Press `/` → starts voice capture

#### 2. Listening Mode

Active input state.

```
┌────────────────────────────────┐
│  > Show me my photos from last │
│  > weekend ▊                    │
│                                │
│                                │
│                                │
│                                │
│   [Enter] send  [Esc] cancel  │
└────────────────────────────────┘
```

- Text input with visible cursor (`▊`)
- Prompt prefix: `> `
- Keybindings active (see below)
- Voice input alternative: shows waveform placeholder when capturing

##### Voice Input

When the user presses `/`:
1. CLI sends `input_forward` with `mode: "voice"` to cognitiveosd
2. cognitiveosd routes to audio-mcp → starts capture
3. CLI displays: `[ Listening... ]` with a waveform animation
4. On silence detection (1s) or manual stop (Enter): audio sent to Wide Model
5. Wide Model returns transcript in `output_deliver`
6. Transcript displayed as text, user confirms before execution
7. User confirms (Enter) or edits

#### 3. Processing Mode

The Wide Model is processing the request.

```
┌────────────────────────────────┐
│  > Show me my photos from last │
│  > weekend                      │
│                                │
│         Working...              │
│                                │
│                                │
│   [Ctrl+C] cancel              │
└────────────────────────────────┘
```

- Shows "Working..." with a simple spinner (dots cycling: `.`, `..`, `...`)
- No text input accepted
- Cancel via `Ctrl+C`: sends cancellation to daemon

#### 4. Responding Mode

The Wide Model is returning output.

```
┌────────────────────────────────┐
│  > Show me my photos from last │
│  > weekend                      │
│                                │
│  Here are your photos from     │
│  last weekend:                 │
│                                │
│  [Showing 3 photos]            │
│                                │
│  "Next" to continue,           │
│  "Close" to dismiss            │
│  ─────────────────────         │
│  > ▊                           │
└────────────────────────────────┘
```

- Wide Model text output displayed verbatim
- New input prompt at bottom: `> ▊`
- If media is included: transitions to Media Mode

#### 5. Media Mode

Framebuffer overlay active (image or video playing).

```
┌────────────────────────────────┐
│        [FRAMEBUFFER]           │
│                                │
│       (image/video)            │
│                                │
│                                │
│  ┌────────────────────────┐   │
│  │ > ▊                     │   │
│  └────────────────────────┘   │
│  "next" "close" "save"        │
└────────────────────────────────┘
```

- TUI minimized to a small overlay bar at the bottom
- Framebuffer takes over the display for media
- User can type commands in the overlay bar
- Commands: `next`, `previous`, `close`, `save`, `zoom`
- On `close`: framebuffer released, TUI returns to full screen

#### 6. Error Mode

Something went wrong.

```
┌────────────────────────────────┐
│  > Show me my photos from last │
│  > weekend                      │
│                                │
│  ┌────────────────────────┐   │
│  │  ⚠ Error               │   │
│  │                        │   │
│  │  No photos found for   │   │
│  │  that date range.      │   │
│  └────────────────────────┘   │
│                                │
│  Try: "Show me all photos"    │
│  > ▊                           │
└────────────────────────────────┘
```

- Error message in a bordered box
- Suggested corrective action below
- User can type a new command immediately

#### 7. Code Entry Mode

Entering a system code (visually distinct to prevent accidental input).

```
┌────────────────────────────────┐
│                                │
│    ⚠ System Code Required     │
│                                │
│    Enter unlock code:          │
│    ▊●●●●-●●●●                  │
│                                │
│    [Enter] submit              │
│    [Esc] cancel                │
│                                │
└────────────────────────────────┘
```

- Distinct visual theme (different color/highlight)
- Input is masked (shown as `●`)
- Used for: `unlock` code entry
- `wake`/`idle`/`security`/`reset` codes use dedicated hardware buttons or simple voice commands

### Keybindings

| Key | Context | Action |
|-----|---------|--------|
| `Enter` | Listening | Submit input |
| `Esc` | Any | Cancel current / return to idle |
| `Ctrl+C` | Any | Cancel current operation |
| `Ctrl+D` | Idle | Shutdown confirmation then system_code `idle` |
| `Ctrl+Alt+S` | Any | system_code `security` (immediate) |
| `/` | Idle / Listening | Start voice capture |
| `Tab` | Responding | Cycle through action buttons |
| `Enter` | Responding (on button) | Execute selected action |
| `Up/Down` | Listening | Scroll input history |
| `Ctrl+L` | Any | Redraw screen |

### Framebuffer Integration

The TUI does not own the framebuffer. It renders to the terminal (tty1). When media needs to be displayed:

1. TUI receives `output_deliver` with `content_type: "media"`
2. TUI renders a minimized overlay bar (3 lines at bottom of screen)
3. TUI instructs display-mcp to take over the framebuffer
4. display-mcp renders the image/video to `/dev/fb0`
5. TUI listens for commands in the overlay bar
6. On `close_media`:
   - TUI instructs display-mcp to release the framebuffer
   - TUI redraws the full screen
   - Terminal content is restored (the TUI handles this)

### Output Rendering Rules

#### Text
- Render verbatim in the TUI text area
- Line wrapping at terminal width
- Scrollable if output exceeds screen height (Shift+Up/Down to scroll)

#### Lists
- Detect markdown-style lists in output
- Render with numbered bullets

#### Code Blocks
- Detect markdown code fences in output
- Render with monospace font and background highlight

#### Tables
- Detect markdown-style tables in output
- Render with aligned columns

#### URLs
- Detect URLs in output
- Render underlined (if terminal supports it)
- Not clickable (no browser to open them in)

### Crash Recovery

The TUI is designed to crash safely:

1. If TUI crashes, the daemon continues running
2. `/etc/inittab` respawns the TUI automatically (Alpine's `respawn` flag on the inittab entry)
3. On restart, TUI connects to daemon → receives current status → renders appropriate screen
4. Any in-progress operation continues in the background (daemon handles it)

#### Inittab Entry

```
tty1::respawn:/usr/local/bin/cognitiveos-cli
```

---

## CLI Mode

Non-interactive command-line interface for scripting and automation.

### Behavior

1. Connects to daemon socket
2. Sends `input_forward` with the command text
3. Waits for `output_deliver` response
4. Prints response and exits

### Output Formats

#### Plain Text (default)

```
$ cognitiveos-cli --cmd "what time is it"
The time is 3:42 PM.
```

Extracts the `content` field from the `output_deliver` payload and prints it to stdout.

#### JSON (`--json`)

```
$ cognitiveos-cli --cmd "what time is it" --json
{
  "type": "output_deliver",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "from": "cognitiveosd",
  "timestamp": "2026-07-16T15:42:00Z",
  "payload": {
    "content": "The time is 3:42 PM."
  }
}
```

Prints the full JSON envelope to stdout. Useful for parsing with `jq` or other tools.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (connection failed, timeout, invalid flags) |

### Timeouts

- Connection: retries for 30 seconds, then fails
- Response: waits 30 seconds for `output_deliver`, then times out

### Examples

```bash
# Simple query
cognitiveos-cli --cmd "check my email"

# Pipe to jq
cognitiveos-cli --cmd "system status" --json | jq '.payload'

# Use in a script
if cognitiveos-cli --cmd "verify package photo-viewer" 2>/dev/null; then
    echo "Package verified"
fi

# Capture response
response=$(cognitiveos-cli --cmd "what time is it")
echo "AI says: $response"
```

### Limitations

- No voice input (text only)
- No media rendering (text output only)
- No interactive editing (single command, single response)
- No history or session state
- No TUI display modes

---

## Error States

| State | Cause | TUI behavior | CLI behavior |
|-------|-------|-------------|--------------|
| Daemon unreachable | cognitiveosd crashed | Retry forever, show "Connecting..." | Exit with error after 30s |
| Daemon rejects connection | Socket permission error | Show "Permission denied. Check socket." Exit. | Exit with error |
| MCP server unavailable | display-mcp crashed | Show "Display unavailable." Text-only mode. | Print text response |
| Audio device unavailable | No mic | Show "Microphone not found." Text-only mode. | N/A (no voice in CLI) |
| Wide Model not loaded | inference error | Show "AI engine not available." Try reload. | Exit with error |
| Response timeout | Wide Model too slow | Processing spinner continues | Exit with error after 30s |
