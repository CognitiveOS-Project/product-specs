# Boot Flow Specification

Version: 1.0.0-draft

## Overview

This document specifies the complete boot flow for CognitiveOS across all deployment methods. It defines the exact sequence of processes, socket creation, dependency ordering, and steady-state behavior. Every step is traceable to a specific binary, init script, or configuration file.

See also: `specs/boot-startup-analysis.md` for the gap analysis between specs and current code.

## ISO Boot Flow (Bare-Metal / VM)

### Phase 1: Kernel and OpenRC Initialization

```
Power On
  → BIOS/U-Boot loads kernel from boot partition
  → Linux kernel boots, mounts rootfs (squashfs)
  → Kernel executes /sbin/init (busybox)
  → busybox reads /etc/inittab
```

inittab executes in order:

```
::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default
tty1::respawn:/usr/local/bin/coginit --bare-metal
ttyS0::respawn:/usr/local/bin/coginit --bare-metal
tty2::respawn:/sbin/getty 38400 tty2
::ctrlaltdel:/sbin/reboot
::shutdown:/sbin/openrc shutdown
```

The `::wait:` directive blocks inittab execution until `openrc default` completes. TTY lines below it do not execute until all default services have started.

### Phase 2: OpenRC sysinit (System Services Only)

```
openrc sysinit
  → devfs          mount /dev
  → dmesg          kernel message buffer
  → mdev           device manager, auto-detect hardware
  → hwdrivers      load hardware drivers
  → modloop        load kernel modules
```

All sysinit services run in dependency order. mdev watches for device hotplug events. hwdrivers loads modules for detected hardware. OpenRC handles only **system-level services** (networking, hardware, logging). CognitiveOS application services are managed by `coginit`.

### Phase 3: OpenRC boot (System Services Only)

```
openrc boot
  → hwclock        sync system clock from RTC
  → modules        load /etc/modules
  → sysctl         apply /etc/sysctl.conf
  → hostname       set hostname from /etc/hostname
  → bootmisc       miscellaneous boot tasks
  → syslog         start system logger
```

Boot services establish system-level configuration before any application services start. No CognitiveOS services run here.

### Phase 4: OpenRC default (System Services Only)

The `openrc default` phase starts only system services (acpid, cpm-boot-deps). CognitiveOS services (cograw, coginfer, cognitiveosd) are started by `coginit` — not by OpenRC.

```
openrc default
  │
  ├── cpm-boot-deps              [STARTS FIRST]
  │   init script: /etc/init.d/cpm-boot-deps
  │   command: /usr/local/bin/cpm install-dependencies --stage boot
  │   depend: keyword -stop
  │   one-shot: no PID file, runs once and exits
  │
  │   actions:
  │     1. Read /var/lib/cpm/queue/ for boot-stage entries
  │     2. Install system packages (kernel modules, firmware)
  │     3. Mark entries as installed
  │
  │   result: boot-stage system dependencies are present
  │
  ├── acpid                      [STARTS SECOND]
  │   command: /usr/sbin/acpid
  │   actions:
  │     1. Listen for ACPI power events
  │     2. Handle power button, lid close, thermal events
  │
  │   result: power management active
  │
  └── cpm-runtime-deps           [STARTS THIRD]
      init script: /etc/init.d/cpm-runtime-deps
      command: /usr/local/bin/cpm install-dependencies --stage runtime
      depend: keyword -start -stop
      one-shot: no PID file, runs once and exits
  
      actions:
        1. Read /var/lib/cpm/queue/ for runtime-stage entries
        2. Install runtime packages (fonts, libraries)
        3. Mark entries as installed
  
      result: runtime dependencies are present
```

### Phase 5: coginit (Unified PID 1)

After `openrc default` completes, inittab continues to TTY lines. `coginit --bare-metal` starts on tty1 as PID 1:

```
coginit (PID 1, on /dev/tty1)
  │
  │  1. Mount virtual filesystems (/proc, /sys, /dev, /run, /tmp, /dev/pts)
  │
  │  2. Start signal handler (SIGINT/SIGTERM graceful shutdown)
  │
  │  3. Configure loopback network interface
  │
  │  4. Create runtime directories (/cognitiveos/run, /cognitiveos/logs)
  │
  │  5. Install boot-stage dependencies
  │     /usr/local/bin/cpm install-dependencies --stage boot
  │
  │  6. Start engines in order with supervision:
  │
  │     6a. Start cograw (background, supervised)
  │         /usr/local/bin/cograw --model <path> --socket /cognitiveos/run/raw.sock
  │         → wait for raw.sock (10s timeout)
  │         → supervision: auto-restart on crash (500ms delay)
  │
  │     6b. Start coginfer (background, supervised)
  │         /usr/local/bin/coginfer --backend cgo --models /cognitiveos/models
  │         → wait for HTTP :11434/health (15s timeout)
  │         → supervision: auto-restart on crash (500ms delay)
  │
  │     6c. Start cognitiveosd (background, supervised)
  │         /usr/local/bin/cognitiveosd
  │         → wait for daemon.sock (10s timeout)
  │         → supervision: auto-restart on crash (500ms delay)
  │
  │  7. Install runtime-stage dependencies
  │     /usr/local/bin/cpm install-dependencies --stage runtime
  │
  │  8. Start backdoor monitor (keyboard combos + serial)
  │
  │  9. TUI supervision loop
  │     forever:
  │       open /dev/tty1
  │       exec cognitiveos-cli
  │       wait for CLI exit
  │       restart after 500ms
  │
  │  CLI connects to daemon.sock → TUI renders
  │  "CognitiveOS ready"
```

### Phase 6: Steady State

```
System is ready for human interaction:

  tty1: coginit(CLI) TUI (primary interface)
  ttyS0: coginit(CLI) TUI (serial console)
  tty2: getty login prompt (debug/admin access)
```

Running processes (bare-metal):

```
PID 1: coginit (/dev/tty1)
├── /usr/local/bin/cograw              (raw.sock, supervised)
├── /usr/local/bin/coginfer            (HTTP :11434, supervised)
├── /usr/local/bin/cognitiveosd        (daemon.sock, supervised)
└── /usr/local/bin/cognitiveos-cli     (on tty1, supervised)
```

Running processes (Docker):

```
PID 1: cognitiveos-cli (exec'd by coginit)
  (background, adopted from coginit before exec):
    /usr/local/bin/cograw              (raw.sock)
    /usr/local/bin/coginfer            (HTTP :11434)
    /usr/local/bin/cognitiveosd        (daemon.sock)
```

coginit supervises all CognitiveOS processes on bare-metal. If any service crashes:

| Service that crashes | Behavior |
|---------------------|----------|
| cograw | Supervised goroutine restarts in 500ms. cognitiveosd reconnects |
| coginfer | Supervised goroutine restarts in 500ms. cognitiveosd reconnects |
| cognitiveosd | Supervised goroutine restarts in 500ms. CLI reconnects |
| cognitiveos-cli | TUI supervision loop restarts in 500ms |

In Docker mode, supervision only operates during the startup window (before CLI exec). After `syscall.Exec`, the CLI replaces coginit as PID 1. Docker's `--restart=always` policy should be used for production deployments.

### Shutdown Flow

```
SIGTERM/SIGINT received (docker stop, power button, reboot)
  → coginit forwards SIGTERM to all children
  → cognitiveos-cli: TUI cleanup, exit
  → coginfer: graceful shutdown (Unload, close HTTP)
  → cograw: graceful shutdown, close raw.sock
  → cognitiveosd: graceful shutdown, close daemon.sock, kill MCP bridges
  → coginit (Docker): exits → container stops
  → coginit (Bare-metal): calls syscall.Reboot(POWER_OFF) → system powers off
```

Signal propagation during shutdown:

```
SIGTERM → cograw:           graceful shutdown, close raw.sock, free model
SIGTERM → coginfer:         graceful shutdown (Unload, close HTTP)
SIGTERM → cognitiveosd:     graceful shutdown, close daemon.sock, kill MCP bridges
SIGTERM → cognitiveos-cli:  TUI cleanup, restore terminal
```

---

## Docker Boot Flow

Docker uses `coginit` as PID 1 (via `ENTRYPOINT ["/usr/local/bin/coginit"]`). See **coginit — Unified PID 1** below for the full Docker mode boot sequence.

---

## Socket Timeline

Both ISO and Docker follow the same socket creation order (orchestrated by coginit):

```
Time    Event                           Socket/Port
─────────────────────────────────────────────────────
T+0.0s  cograw starts
T+1.5s  cograw opens raw.sock           /cognitiveos/run/raw.sock
T+1.5s  coginit continues
T+1.5s  coginfer starts
T+2.0s  coginfer opens HTTP             127.0.0.1:11434
T+2.0s  coginit continues
T+2.0s  cognitiveosd starts
T+2.5s  cognitiveosd connects to raw.sock   → OK
T+2.5s  cognitiveosd connects to HTTP       → OK
T+3.0s  cognitiveosd opens daemon.sock   /cognitiveos/run/daemon.sock
T+3.0s  CLI starts (ISO: tty1 respawn; Docker: exec)
T+3.0s  CLI connects to daemon.sock      → OK
T+3.0s  CLI renders TUI
T+3.0s  "CognitiveOS ready"
```

Total boot time to "ready": ~3 seconds (assuming model loads in ~1.5s).

---

## Socket Permissions and Ownership

| Socket | Path | Permissions | Owner | Group |
|--------|------|------------|-------|-------|
| raw.sock | `/cognitiveos/run/raw.sock` | 0600 | root | root |
| daemon.sock | `/cognitiveos/run/daemon.sock` | 0600 | root | root |
| HTTP :11434 | `127.0.0.1:11434` | TCP (localhost only) | — | — |

All sockets are bound to localhost or filesystem paths with restrictive permissions. No external network access is required for inter-process communication.

---

## Error Handling During Boot

### cograw fails to start (model missing)

```
ISO (coginit bare-metal):
  → cograw exits immediately (log.Fatalf since model missing)
  → coginit logs failure, supervision goroutine restarts in 500ms
  → raw.sock never appears (10s timeout)
  → coginit continues — cognitiveosd starts, tries raw.sock
  → cognitiveosd: FATAL exit (raw model unavailable)
  → coginit restarts cognitiveosd (supervision), it fails again
  → System stuck in restart loop — each try: cograw fails, cognitiveosd fails
  → CLI starts (TUI supervision loop), shows "Connecting..." (daemon.sock absent)
  → Admin must fix model path and reboot

Docker (coginit):
  → Same startup sequence as ISO
  → After timeout: coginit execs CLI anyway (best effort)
  → CLI shows error, retries indefinitely
  → Container must be restarted with corrected config
```

### coginfer fails to start

```
ISO (coginit bare-metal):
  → coginfer exits or HTTP never responds
  → coginit logs warning, supervision restarts in 500ms
  → cognitiveosd starts, connects to raw.sock (OK)
  → HTTP check gets connection refused → WARNING, continues degraded
  → System operates with raw model only (guardrail active, no inference)
  → CLI renders "Wide Model unavailable"

Docker (coginit):
  → Same as ISO — coginit continues degraded, execs CLI
  → System runs in degraded mode
```

### cognitiveosd fails to start

```
ISO (coginit bare-metal):
  → cognitiveosd exits immediately
  → coginit supervision restarts in 500ms
  → daemon.sock never appears (10s timeout)
  → CLI starts (TUI supervision), connects... waits... "Connecting..."
  → System cycles: cognitiveosd starts, fails, restarts, fails
  → If transient failure: system recovers on next restart attempt

Docker (coginit):
  → Same startup sequence
  → After timeout: coginit execs CLI anyway
  → CLI shows error, retries indefinitely
```

### All services healthy, CLI disconnects

```
ISO (coginit bare-metal):
  → CLI exits (Ctrl+D, crash)
  → coginit TUI supervision loop: wait 500ms, restart
  → New CLI process starts
  → Connects to daemon.sock (still running)
  → TUI renders, user resumes

Docker (coginit):
  → CLI exits
  → coginit already exec'd into CLI, so PID 1 exits
  → Container stops (no respawn in Docker)
  → Docker orchestration must restart container
```

---

## coginit — Unified PID 1 (Implemented)

### Vision

`coginit` is a compiled Go binary that replaces the fragile shell-based init chain (`tini` + `docker-init.sh` for Docker, `busybox init` + OpenRC + inittab for bare-metal) with a single, auditable executable. It standardizes the CognitiveOS boot sequence across all deployment environments.

### Design Principles

1. **Compiled, not interpreted** — Go binary eliminates shell quoting, missing commands, and CRLF issues
2. **Dual-boot detection** — auto-detects Docker vs bare-metal at runtime
3. **Coexists with OpenRC** — handles only CognitiveOS services; OpenRC handles system services (networking, logging, hardware)
4. **Same startup order** — identical service sequence in both environments
5. **PID 1 responsibilities** — zombie reaping, signal handling, process supervision

### Environment Detection

```
coginit starts as PID 1
  → checks /.dockerenv, /run/.containerenv, $container env var
  → if container detected: Docker mode
  → else: bare-metal mode
```

### Docker Mode (replaces tini + docker-init.sh)

```
coginit (PID 1)
  │
  │  1. Start signal reaper (SIGCHLD, SIGINT, SIGTERM)
  │
  │  2. Install boot-stage dependencies
  │     /usr/local/bin/cpm install-dependencies --stage boot
  │
  │  3. Create runtime directories
  │     mkdir -p /cognitiveos/run /cognitiveos/logs
  │
  │  4. Start cograw (background)
  │     /usr/local/bin/cograw --model ... --socket ... &
  │     → cograw handles mock fallback internally (--backend flag)
  │
  │  5. Wait for raw.sock
  │     polling /cognitiveos/run/raw.sock (10s timeout)
  │
  │  6. Start coginfer (background)
  │     /usr/local/bin/coginfer --backend cgo --models ... &
  │
  │  7. Wait for HTTP :11434/health
  │     polling with 200ms timeout (15s timeout)
  │
  │  8. Start cognitiveosd (background)
  │     /usr/local/bin/cognitiveosd &
  │
  │  9. Wait for daemon.sock
  │     polling /cognitiveos/run/daemon.sock (10s timeout)
  │
  │  10. Install runtime-stage dependencies
  │      /usr/local/bin/cpm install-dependencies --stage runtime
  │
  │  11. Exec CLI (replaces coginit process)
  │      syscall.Exec("/usr/local/bin/cognitiveos-cli")
  │      → CLI becomes PID 1's replacement
  │      → CLI connects to daemon.sock
  │      → TUI renders: "CognitiveOS ready"
```

### Bare-Metal Mode (coexists with OpenRC)

```
coginit (PID 1, started by inittab or kernel init=/sbin/coginit)
  │
  │  1. Mount virtual filesystems (/proc, /sys, /dev, /run, /tmp, /dev/pts)
  │
  │  2. Start signal reaper (SIGCHLD, SIGINT, SIGTERM)
  │
  │  3. Configure loopback network
  │
  │  4. Install boot-stage dependencies
  │     /usr/local/bin/cpm install-dependencies --stage boot
  │
  │  5. Start cograw (background)
  │
  │  6. Wait for raw.sock
  │
  │  7. Start coginfer (background)
  │
  │  8. Wait for HTTP :11434/health
  │
  │  9. Start cognitiveosd (background)
  │
  │  10. Wait for daemon.sock
  │
  │  11. Install runtime-stage dependencies
  │      /usr/local/bin/cpm install-dependencies --stage runtime
  │
  │  12. TUI supervision loop
  │      forever:
  │        open /dev/tty1
  │        exec cognitiveos-cli with TTY
  │        wait for CLI exit
  │        log exit reason
  │        restart after 500ms
```

### Service Startup Order (Both Environments)

```
1. cpm install-dependencies --stage boot
2. cograw → wait raw.sock
3. coginfer → wait HTTP health
4. cognitiveosd → wait daemon.sock
5. cpm install-dependencies --stage runtime
6. cognitiveos-cli (exec in Docker, supervised in bare-metal)
```

### Process Tree

**Docker:**
```
coginit (PID 1, replaced by CLI after exec)
  └── cognitiveos-cli (PID 2, exec'd)
        └── connected to daemon.sock

  Background processes (forked by coginit):
    cograw       (listening on raw.sock)
    coginfer     (listening on HTTP :11434)
    cognitiveosd (listening on daemon.sock)
```

**Bare-Metal:**
```
coginit (PID 1)
  ├── cograw           (background, listening on raw.sock)
  ├── coginfer         (background, listening on HTTP :11434)
  ├── cognitiveosd     (background, listening on daemon.sock)
  └── cognitiveos-cli  (foreground on /dev/tty1, supervised)
```

### Supervision Architecture

`coginit` owns all process lifecycles. It is the single supervisor — no other component restarts processes.

#### Why coginit, not cognitiveosd?

cognitiveosd is the application daemon (AI coordination, MCP servers, system codes). If cognitiveosd is hung or crashed, the CLI must still restart. Putting CLI supervision in cognitiveosd creates a dependency chain:

```
cognitiveosd supervises CLI → CLI dead when cognitiveosd hung (worse)
coginit supervises CLI      → CLI alive regardless of cognitiveosd state (better)
```

coginit is PID 1 in bare-metal mode, starts before all engines, and has no dependency on any other component being healthy.

#### Supervision hierarchy

```
coginit (PID 1)
  ├── cograw           (restart on crash)
  ├── coginfer         (restart on crash)
  ├── cognitiveosd     (restart on crash)
  └── cognitiveos-cli  (restart on crash, 500ms delay)
```

#### Communication vs supervision

| Concern | Mechanism | Owner |
|---------|-----------|-------|
| CLI ↔ cognitiveosd data | daemon.sock (bidirectional JSON) | cognitiveosd |
| CLI process restart | TUI supervision loop | coginit |
| cognitiveosd process restart | Process supervision | coginit |
| Engine process restart | Process supervision | coginit |

cognitiveosd communicates with the CLI via daemon.sock (JSON messages). It does NOT supervise the CLI — that is coginit's responsibility.

#### Failure matrix

| Failure | What happens | Recovery |
|---------|-------------|----------|
| CLI crashes | coginit detects via waitpid | Restart in 500ms |
| cognitiveosd crashes | coginit detects | Restart cognitiveosd, CLI reconnects |
| cognitiveosd hung | CLI restarts anyway | CLI alive, shows "Connecting..." |
| cograw/coginfer crash | coginit detects | Restart engines, cognitiveosd reconnects |
| coginit crashes | System halt | Unavoidable for PID 1 |

### Signal Handling

**Docker:**
```
docker stop
  → Docker sends SIGTERM to PID 1 (coginit)
  → coginit forwards SIGTERM to all children
  → cognitiveos-cli: TUI cleanup, exit
  → coginfer: graceful shutdown (Unload, close HTTP)
  → cograw: graceful shutdown
  → cognitiveosd: graceful shutdown, close daemon.sock
  → coginit exits
  → Container stops
```

**Bare-Metal:**
```
SIGTERM/SIGINT received
  → coginit forwards SIGTERM to all children
  → cognitiveos-cli: TUI cleanup, exit
  → coginfer: graceful shutdown
  → cograw: graceful shutdown
  → cognitiveosd: graceful shutdown
  → coginit calls syscall.Reboot(LINUX_REBOOT_CMD_POWER_OFF)
  → System powers off
```

### What coginit Does NOT Handle

| Concern | Owner | Reason |
|---------|-------|--------|
| System services (networking, logging, hardware) | OpenRC | OS-level, distro-specific |
| Mock mode detection | cograw | Internal --backend flag |
| Application logic (system codes, MCP bridges) | cognitiveosd | Application-level |
| Package management | cpm | Standalone tool |

### Build

```bash
# Static binary, no dynamic dependencies
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -ldflags '-extldflags "-static"' -o coginit .
```

### Flags

| Flag | Description |
|------|-------------|
| `--docker` | Force Docker mode (auto-detected by default) |
| `--bare-metal` | Force bare-metal mode (auto-detected by default) |
| `--version` | Print version and exit |

---

## References

| Document | Topic |
|----------|-------|
| `specs/boot-startup-analysis.md` | Gap analysis, binary flags, failure modes |
| `specs/distro-build-spec.md:366-390` | Original boot sequence specification |
| `specs/raw-model.md:434-447` | Daemon startup and cograw lifecycle |
| `specs/cognitiveosd-api.md:530-542` | Daemon startup sequence |
| `specs/cli-spec.md:15-24` | CLI startup and daemon connection |
| `specs/architecture.md:49-53` | Architecture boot overview |
