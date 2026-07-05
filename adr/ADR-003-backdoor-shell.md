# ADR-003: Physical Backdoor Shell

**Status:** Accepted  
**Date:** 2026-07-05  
**Author:** CognitiveOS SDLC

## Context

CognitiveOS has no user accounts, no login shell, and no multi-user isolation — the AI is the sole actor. The security model relies on physical system codes (`RESET`, `SECURITY`) for human override, but these codes only wipe or kill processes — they do not give the operator a root shell for recovery, debugging, or offline administration.

If the Wide Model is compromised (adversarial prompt, bug, supply chain attack), it could:
- Lock out the operator by ignoring system codes
- Corrupt the daemon's socket handling
- Spam the input channel so voice/button codes are never processed

The system needs a guaranteed physical-access-only root shell that the AI cannot detect, intercept, or block.

## Decision

Add two simultaneous physical backdoor shells monitored by the Raw Model. Both are triggered by keyboard combos intercepted at the kernel input layer — before the TUI or AI ever sees the keystrokes.

### Backdoor A — VT Switch (same display)

| Property | Value |
|----------|-------|
| Channel | Dedicated Linux VT (`/dev/tty2`) |
| Trigger | Keyboard combo read from `evdev` by the Raw Model |
| Activation | Raw Model calls `ioctl VT_ACTIVATE` to switch display to VT2, spawns `/bin/sh` |
| Return | `exit` or `Ctrl+D` returns to the TUI VT |

The TUI runs on VT1. The AI has no mechanism to switch VTs — `ioctl VT_ACTIVATE` is blocked by seccomp for all untrusted processes, and the AI communicates via sockets, not terminals.

### Backdoor B — Serial Console (UART)

| Property | Value |
|----------|-------|
| Channel | UART on GPIO 14/15 (`/dev/ttyAMA0`) |
| Trigger | Any keypress on the serial line, or the same keyboard combo |
| Shell | `getty` or Raw Model-spawned `/bin/sh` on the serial device |
| AI visibility | `/dev/ttyAMA0` is blocked by seccomp and filesystem permissions |

The serial console is the failsafe — it works even if the display is broken, the AI is hung, or the TUI is unresponsive.

### Trigger Combos

All combos trigger both backdoors simultaneously. Implemented in this priority order:

| # | Combo | Rationale |
|---|-------|-----------|
| 1 | `Ctrl+Alt+Backspace` | Classic Linux X11 exit — muscle memory for administrators |
| 2 | `Alt+PrintScreen+K` | SysRq SAK (Secure Attention Key) inspired |
| 3 | `Ctrl+Alt+Del` or serial break | Traditional serial console reset |
| 4 | `ScrollLock` ×3 within 2 seconds | Obscure, hard to fat-finger, unlikely to collide |
| 5 | `Super+Grave` (`` Win+` ``) | Common terminal escape in games and desktop environments |

The combos are **compiled into the Raw Model firmware** — not loaded from any filesystem file. The AI cannot read, modify, or disable them.

### Implementation: Raw Model (cograw)

The keyboard combo handler lives in the Raw Model. It reads from `/dev/input/event*` via the `evdev` interface:

```
cograw startup
  → Open /dev/input/event* (keyboard devices)
  → Spawn goroutine: read evdev events in a loop
  → Maintain state machine per combo (key sequence matching)
  → On combo match:
      1. ioctl(fd, VT_ACTIVATE, 2)        // switch display to VT2
      2. ioctl(fd, VT_WAITACTIVE, 2)      // wait for switch
      3. fork + exec /bin/sh on /dev/tty2 // spawn root shell
      4. exec getty on /dev/ttyAMA0       // ensure serial console
      5. Write access log entry
  → On shell exit (waitpid):
      1. ioctl(fd, VT_ACTIVATE, 1)        // switch back to TUI VT
```

### Evdev Device Monitoring

- Watch `/dev/input/` with `inotify` for hotplug events (USB keyboard plugged in after boot)
- Read from all `event*` devices that have `EVIOCGID` reporting a keyboard (`ID_BUS=USB` or `ID_BUS=BLUETOOTH`)
- Ignore devices that report `ID_BUS=VIRTUAL` (prevents AI from injecting keystrokes via virtual input devices — uinput is blocked by seccomp)
- Filter out repeated keys (kernel autorepeat) — only count fresh presses

### Shell Properties

| Property | Value |
|----------|-------|
| User | `root` |
| Password | None — physical access is the authentication |
| Restrictions | None — full root shell, no chroot, no seccomp |
| Environment | Minimal: `$TERM=linux`, default `PATH` |
| Warning | Banner on shell start: `"BACKDOOR SHELL — CognitiveOS firmware override"` |
| Logging | Every backdoor access logged to `/cognitiveos/logs/raw/backdoor.log` with timestamp + VT/combo used |

### Why the AI Cannot Access the Backdoor

| Attempt | Why it fails |
|---------|-------------|
| AI generates `Ctrl+Alt+Backspace` text | The AI produces text strings through the daemon — it does not inject keystrokes. The daemon does not forward arbitrary text to `/dev/input/` |
| AI calls `ioctl VT_ACTIVATE` | `ioctl` on VT devices is blocked by the Raw Model's seccomp profile for all MCP servers and the Wide Model |
| AI writes to `/dev/tty2` | The daemon owns the VT — the AI has no path to write to it |
| AI opens `/dev/input/event*` | Filesystem permissions (`root:root 0600`) and seccomp block access |
| AI creates `uinput` device | `uinput` is blocked by seccomp — the Raw Model's filter denies `open` on `/dev/uinput` |
| AI reads `/dev/ttyAMA0` | Blocked by filesystem permissions and seccomp |
| AI sends serial break via ioctl | `TIOCSBRK` is blocked by seccomp |
| AI reads backdoor.log | The log is under `/cognitiveos/logs/raw/` which is readable only by `root` — the AI runs as `widemodel` |
| AI modifies combo table | Combos are compiled into the Raw Model binary, not stored in a filesystem file |

### Physical Security Assumption

This mechanism defends against a **compromised AI with software-only control**. It does not defend against a physical attacker — if someone has physical access to the device, they can press the combo or connect a serial cable.

The threat model assumes:
- The attacker (adversarial Wide Model) has no physical access
- The attacker can generate arbitrary text, make HTTP requests, and spawn MCP server processes
- The attacker cannot press physical keys, flip switches, or connect cables

## Consequences

**Positive:**
- Guaranteed physical root shell even when the AI is compromised or hung
- Two independent channels (display VT + serial) — single point of failure eliminated
- All combos work on all channels — no mode toggling
- No new hardware required — uses existing keyboard and GPIO UART
- Compiled-in combos cannot be changed by software

**Negative:**
- No password on the shell — physical access alone grants root (intentional: operator convenience in recovery scenarios)
- Adding new combos requires a firmware reflash
- The Raw Model binary increases in complexity (evdev parsing, state machine)

**Risks:**
- Hotplug race: if a keyboard is plugged in during combo detection, the state machine could miss the combo (mitigated by inotify watch on `/dev/input/` — new devices are picked up within milliseconds)
- Virtual machine environments: evdev may not be available; serial console backdoor still works via emulated serial port

## Alternatives Considered

1. **SSH daemon** — rejected: requires network, credentials, and a running SSH server that the AI could tamper with or block
2. **Physical switch toggling a GPIO that spawns a shell** — rejected: adds hardware cost, doesn't work on devices without accessible GPIO
3. **Single combo, single channel** — rejected: a broken display or disconnected UART would lose the backdoor entirely
4. **Password on the backdoor shell** — rejected: in a recovery scenario the operator may not know the password; "physical access is auth" matches the existing `RESET` code philosophy

## References

- `security-model.md` — trust boundaries, seccomp profile, physical security
- `raw-model.md` — Raw Model responsibilities, RPC methods, startup sequence
- `system-codes.md` — physical button combo patterns (RESET, SECURITY)
