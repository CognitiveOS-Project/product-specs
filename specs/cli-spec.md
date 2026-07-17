# CLI Specification

Version: 1.0.0-draft

## Overview

`cognitiveos-cli` is the human interface to CognitiveOS. It is a terminal user interface (TUI) that replaces the traditional desktop environment. It runs on tty1 (spawned by `/etc/inittab`) and connects to `cognitiveosd` via Unix socket.

The CLI is **thin** — it captures input and displays output. All intelligence and state live in cognitiveosd and the Wide Model. The CLI can crash and restart without affecting system stability.

## Connection

### Socket

- **Path:** `/cognitiveos/run/daemon.sock`
- **Protocol:** JSON-over-Unix-stream (see cognitiveosd-api.md)

### Startup

1. CLI starts on tty1
2. Renders idle screen
3. Connects to daemon socket (retries every second for 30 seconds, then shows error)
4. Sends `status_request` to get current daemon state
5. Enters main event loop

### Reconnection

If the connection to cognitiveosd is lost:
1. Display frozen state with message: "Connecting..."
2. Retry connection every second
3. After 30 seconds of failure: display "Daemon unavailable. Check system."
4. Continue retrying indefinitely

## Display Modes

The CLI renders in one of the following modes. Transitions between modes are instantaneous — no animations or transitions that could be mistaken for responsiveness.

### 1. Idle Mode

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

### 2. Listening Mode

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

#### Voice Input

When the user presses `/`:
1. CLI sends `input_forward` with `mode: "voice"` to cognitiveosd
2. cognitiveosd routes to audio-mcp → starts capture
3. CLI displays: `[ Listening... ]` with a waveform animation
4. On silence detection (1s) or manual stop (Enter): audio sent to Wide Model
5. Wide Model returns transcript in `output_deliver`
6. Transcript displayed as text, user confirms before execution
7. User confirms (Enter) or edits

### 3. Processing Mode

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

### 4. Responding Mode

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

### 5. Media Mode

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

### 6. Error Mode

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

### 7. Code Entry Mode

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

## Keybindings

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

## Framebuffer Integration

The CLI does not own the framebuffer. It renders to the terminal (tty1). When media needs to be displayed:

1. CLI receives `output_deliver` with `content_type: "media"`
2. CLI renders a minimized overlay bar (3 lines at bottom of screen)
3. CLI instructs display-mcp to take over the framebuffer
4. display-mcp renders the image/video to `/dev/fb0`
5. CLI listens for commands in the overlay bar
6. On `close_media`:
   - CLI instructs display-mcp to release the framebuffer
   - CLI redraws the full TUI
   - Terminal content is restored (the TUI handles this)

## Output Rendering Rules

### Text
- Render verbatim in the TUI text area
- Line wrapping at terminal width
- Scrollable if output exceeds screen height (Shift+Up/Down to scroll)

### Lists
- Detect markdown-style lists in output
- Render with numbered bullets

### Code Blocks
- Detect markdown code fences in output
- Render with monospace font and background highlight

### Tables
- Detect markdown-style tables in output
- Render with aligned columns

### URLs
- Detect URLs in output
- Render underlined (if terminal supports it)
- Not clickable (no browser to open them in)

## Crash Recovery

The CLI is designed to crash safely:

1. If CLI crashes, the daemon continues running
2. `/etc/inittab` respawns the CLI automatically (Alpine's `respawn` flag on the inittab entry)
3. On restart, CLI connects to daemon → receives current status → renders appropriate screen
4. Any in-progress operation continues in the background (daemon handles it)

### Inittab Entry

```
tty1::respawn:/usr/local/bin/cognitiveos-cli
```

## Error States

| State | Cause | CLI behavior |
|-------|-------|-------------|
| Daemon unreachable | cognitiveosd crashed | Retry forever, show "Connecting..." |
| Daemon rejects connection | Socket permission error | Show "Permission denied. Check socket." Exit. |
| MCP server unavailable | display-mcp crashed | Show "Display unavailable." Text-only mode. |
| Audio device unavailable | No mic | Show "Microphone not found." Text-only mode. |
| Wide Model not loaded | inference error | Show "AI engine not available." Try reload. |
