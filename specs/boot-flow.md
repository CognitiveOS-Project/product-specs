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
```

The `::wait:` directive blocks inittab execution until `openrc default` completes. TTY lines below it do not execute until all default services have started.

### Phase 2: OpenRC sysinit

```
openrc sysinit
  → devfs          mount /dev
  → dmesg          kernel message buffer
  → mdev           device manager, auto-detect hardware
  → hwdrivers      load hardware drivers
  → modloop        load kernel modules
```

All sysinit services run in dependency order. mdev watches for device hotplug events. hwdrivers loads modules for detected hardware.

### Phase 3: OpenRC boot

```
openrc boot
  → hwclock        sync system clock from RTC
  → modules        load /etc/modules
  → sysctl         apply /etc/sysctl.conf
  → hostname       set hostname from /etc/hostname
  → bootmisc       miscellaneous boot tasks
  → syslog         start system logger
```

Boot services establish system-level configuration before any application services start.

### Phase 4: OpenRC default

This is the critical phase where CognitiveOS services start. Services start in dependency order:

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
  ├── cograw                    [STARTS SECOND]
  │   init script: /etc/init.d/cograw
  │   command: /usr/local/bin/cograw --model /cognitiveos/models/raw/raw-model.gguf
  │   depend: need localmount cpm-boot-deps, keyword -stop
  │   pidfile: /run/cograw.pid
  │   log: /cognitiveos/logs/cograw.log
  │
  │   actions:
  │     1. Load raw-model.gguf into llama.cpp backend
  │     2. Verify model integrity (sha256 checksum)
  │     3. Open Unix socket /cognitiveos/run/raw.sock (permissions 0600)
  │     4. Listen for JSON-RPC 2.0 requests
  │     5. Write PID to /run/cograw.pid
  │
  │   result: raw.sock is available
  │
  ├── coginfer                   [STARTS THIRD]
  │   init script: /etc/init.d/coginfer
  │   command: /usr/local/bin/coginfer --backend cgo --models /cognitiveos/models
  │   depend: need localmount cpm-boot-deps, keyword -stop
  │   pidfile: /run/coginfer.pid
  │   log: /cognitiveos/logs/coginfer.log
  │
  │   actions:
  │     1. Start HTTP server on 127.0.0.1:11434
  │     2. Register handlers: /api/generate, /api/pull, /api/delete, /health
  │     3. Model loaded on-demand (not at startup)
  │     4. Write PID to /run/coginfer.pid
  │
  │   result: HTTP :11434 is available
  │
  ├── acpid                      [STARTS FOURTH]
  │   command: /usr/sbin/acpid
  │   actions:
  │     1. Listen for ACPI power events
  │     2. Handle power button, lid close, thermal events
  │
  │   result: power management active
  │
  ├── cognitiveosd               [STARTS FIFTH]
  │   init script: /etc/init.d/cognitiveosd
  │   command: /usr/local/bin/cognitiveosd
  │   depend: need cograw, after coginfer, before cpm-runtime-deps
  │   pidfile: /run/cognitiveosd.pid
  │   log: /cognitiveos/logs/cognitiveosd.log
  │
  │   actions:
  │     1. Create /cognitiveos/run/ directory (tmpfs)
  │     2. Open Unix socket /cognitiveos/run/daemon.sock
  │     3. Connect to cograw via raw.sock
  │        → net.Dial("unix", "/cognitiveos/run/raw.sock")
  │        → SUCCEEDS because cograw is already running (Phase 4 step 2)
  │     4. Connect to coginfer via HTTP GET /health
  │        → http.Get("http://127.0.0.1:11434/health")
  │        → SUCCEEDS because coginfer is already running (Phase 4 step 3)
  │     5. Read /etc/cognitiveos/config.toml (Phase 3 fix)
  │     6. Apply env var overrides (COGNITIVEOS_*)
  │     7. Apply CLI flag overrides
  │     8. Run Derive() to calculate derived paths
  │     9. Spawn MCP bridge servers (network, audio, display, gpio, serial)
  │    10. Start audit loop (hardware audit every 60s)
  │    11. Write PID to /run/cognitiveosd.pid
  │    12. Enter main event loop (read messages from daemon.sock)
  │
  │   result: daemon.sock is available, all services connected
  │
  └── cpm-runtime-deps           [STARTS SIXTH]
      init script: /etc/init.d/cpm-runtime-deps
      command: /usr/local/bin/cpm install-dependencies --stage runtime
      depend: after cognitiveosd, keyword -start -stop
      one-shot: no PID file, runs once and exits
  
      actions:
        1. Read /var/lib/cpm/queue/ for runtime-stage entries
        2. Install runtime packages (fonts, libraries)
        3. Mark entries as installed
  
      result: runtime dependencies are present
```

### Phase 5: TTY and CLI

```
openrc default completes (::wait returns)
  → inittab continues to TTY lines
  → tty1::respawn:/usr/local/bin/cognitiveos-cli
  → ttyS0::respawn:/usr/local/bin/cognitiveos-cli
  → tty2::respawn:/sbin/getty 38400 tty2
```

cognitiveos-cli starts on tty1:

```
1. Check if /cognitiveos/run/daemon.sock exists
   → YES (cognitiveosd created it in Phase 4)
   → Skip daemon spawning

2. Connect to daemon.sock via Unix socket
   → dials /cognitiveos/run/daemon.sock
   → succeeds on first attempt (daemon is ready)

3. Send status_request to get current daemon state
   → receives daemon status (models loaded, patches installed, etc.)

4. Launch Bubble Tea TUI
   → initialize terminal, set alternate screen buffer
   → create model with initial state = Idle

5. Display: "CognitiveOS ready" (idle screen)
   → shows system status, model info, ready prompt

6. Enter main event loop
   → keyboard input → send to daemon → render response
```

### Phase 6: Steady State

```
System is ready for human interaction:

  tty1: cognitiveos-cli TUI (primary interface)
  ttyS0: cognitiveos-cli TUI (serial console)
  tty2: getty login prompt (debug/admin access)
```

Running processes:

```
PID 1: busybox init
├── /usr/local/bin/cograw              (raw.sock)
├── /usr/local/bin/coginfer            (HTTP :11434)
├── /usr/local/bin/cognitiveosd        (daemon.sock)
├── /usr/local/bin/cognitiveos-cli     (tty1)
├── /usr/local/bin/cognitiveos-cli     (ttyS0)
├── /sbin/getty                        (tty2)
├── /usr/sbin/acpid
└── /usr/sbin/syslogd
```

OpenRC monitors all backgrounded services. If cograw crashes, OpenRC respawns it. If cognitiveosd crashes, OpenRC respawns it (and the CLI reconnects on next poll).

### Shutdown Flow

```
User presses power button (or types reboot)
  → acpid catches ACPI event, runs /etc/acpi/actions/powerbtn.sh
  → triggers inittab: ::ctrlaltdel:/sbin/reboot
  → inittab: ::shutdown:/sbin/openrc shutdown
  → openrc shutdown:
      → savecache       save package cache
      → killprocs       send SIGTERM to all services
      → mount-ro        remount filesystems read-only
  → Kernel unmounts, powers off
```

Signal propagation during shutdown:

```
SIGTERM → cograw:   graceful shutdown, close raw.sock, free model
SIGTERM → coginfer: graceful shutdown (Phase 4 fix), unload model, close HTTP
SIGTERM → cognitiveosd: graceful shutdown, close daemon.sock, kill MCP bridges
SIGTERM → cognitiveos-cli: Bubble Tea cleanup, restore terminal
```

---

## Docker Boot Flow

### Container Startup

```
docker run cognitiveos:<variant>
  → Docker creates container from image layer
  → tini starts as PID 1 (from ENTRYPOINT ["/sbin/tini", "--"])
  → tini executes: /usr/local/bin/entrypoint.sh (from CMD)
```

### Entrypoint Script Sequence

```
entrypoint.sh:
  │
  │  Step 1: Process boot-stage system dependencies
  │  /usr/local/bin/cpm install-dependencies --stage boot
  │  → Installs kernel modules, firmware, etc.
  │
  │  Step 2: Create runtime directories
  │  mkdir -p /cognitiveos/run /cognitiveos/logs
  │
  │  Step 3: Start cograw in background
  │  /usr/local/bin/cograw --model /cognitiveos/models/raw/raw-model.gguf &
  │  COGRAW_PID=$!
  │  → Forks cograw into background
  │  → cograw loads GGUF model into llama.cpp
  │  → cograw opens /cognitiveos/run/raw.sock
  │  → cograw writes /run/cograw.pid
  │
  │  Step 4: Wait for raw.sock
  │  for i in $(seq 1 30); do
  │      [ -S /cognitiveos/run/raw.sock ] && break
  │      sleep 0.2
  │  done
  │  → raw.sock appears after ~1-2s (model load time)
  │  → 30s timeout prevents infinite wait
  │
  │  Step 5: Start coginfer in background
  │  /usr/local/bin/coginfer --backend cgo --models /cognitiveos/models &
  │  COGINFER_PID=$!
  │  → Forks coginfer into background
  │  → coginfer starts HTTP server on 127.0.0.1:11434
  │  → No model loaded yet (on-demand)
  │
  │  Step 6: Wait for HTTP :11434
  │  for i in $(seq 1 30); do
  │      wget -q --spider http://127.0.0.1:11434/health 2>/dev/null && break
  │      sleep 0.2
  │  done
  │  → HTTP available after ~0.5s
  │
  │  Step 7: Start cognitiveosd in background
  │  /usr/local/bin/cognitiveosd &
  │  DAEMON_PID=$!
  │  → cognitiveosd creates /cognitiveos/run/ directory
  │  → cognitiveosd opens /cognitiveos/run/daemon.sock
  │  → cognitiveosd connects to raw.sock (succeeds — cograw running)
  │  → cognitiveosd connects to HTTP :11434 (succeeds — coginfer running)
  │  → cognitiveosd spawns MCP bridges
  │  → cognitiveosd starts audit loop
  │
  │  Step 8: Wait for daemon.sock
  │  for i in $(seq 1 30); do
  │      [ -S /cognitiveos/run/daemon.sock ] && break
  │      sleep 0.2
  │  done
  │  → daemon.sock appears after ~1-2s
  │
  │  Step 9: Process runtime-stage system dependencies
  │  /usr/local/bin/cpm install-dependencies --stage runtime
  │  → Installs runtime fonts, libraries, etc.
  │
  │  Step 10: Exec CLI
  │  exec /usr/local/bin/cognitiveos-cli
  │  → Replaces entrypoint.sh shell process
  │  → CLI becomes direct child of tini
  │  → CLI connects to daemon.sock
  │  → TUI renders: "CognitiveOS ready"
```

### Docker Process Tree

```
tini (PID 1)
  └── cognitiveos-cli (PID 2, exec'd from entrypoint.sh)
        └── connected to daemon.sock

  Background processes (forked by entrypoint.sh, inherited by tini):
    cograw      (listening on raw.sock)
    coginfer    (listening on HTTP :11434)
    cognitiveosd (listening on daemon.sock)
```

When entrypoint.sh calls `exec cognitiveos-cli`, the shell process is replaced by the CLI binary. The background processes (cograw, coginfer, cognitiveosd) become orphaned children of the original shell. Since the shell was replaced by exec, tini (PID 1) inherits these orphans as its direct children. Tini reaps any zombies and forwards signals to the process group.

### Docker Shutdown Flow

```
docker stop cognitiveos
  → Docker sends SIGTERM to PID 1 (tini)
  → tini forwards SIGTERM to child process group
  → cognitiveos-cli receives SIGTERM
  → Bubble Tea handles cleanup, restores terminal, exits
  → tini waits for child to exit
  → tini propagates exit code to Docker
  → Docker sends SIGKILL to remaining processes after timeout (default 10s)
  → cograw, coginfer, cognitiveosd receive SIGKILL
  → Container stops
```

With Phase 4 fixes (coginfer signal handling):

```
docker stop cognitiveos
  → Docker sends SIGTERM to PID 1 (tini)
  → tini forwards SIGTERM to process group
  → cognitiveos-cli: Bubble Tea cleanup, exit
  → coginfer: trap SIGTERM, call Unload(), close HTTP, exit
  → cograw: already has signal handling, graceful shutdown
  → cognitiveosd: already has SIGTERM handling, graceful shutdown
  → tini propagates exit code
  → Container stops cleanly (no SIGKILL needed)
```

---

## Socket Timeline

Both ISO and Docker follow the same socket creation order:

```
Time    Event                           Socket/Port
─────────────────────────────────────────────────────
T+0.0s  cograw starts
T+1.5s  cograw opens raw.sock           /cognitiveos/run/raw.sock
T+1.5s  entrypoint continues (ISO: OpenRC continues)
T+1.5s  coginfer starts
T+2.0s  coginfer opens HTTP             127.0.0.1:11434
T+2.0s  entrypoint continues (ISO: cpm-boot-deps runs)
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
ISO:
  → OpenRC marks cograw as failed
  → cognitiveosd starts, tries to connect to raw.sock
  → raw.sock does not exist
  → cognitiveosd: FATAL: raw model unavailable — system cannot operate safely
  → cognitiveosd exits
  → OpenRC marks cognitiveosd as failed
  → cpm-runtime-deps skipped (depends on cognitiveosd)
  → tty1 respawns CLI, CLI spawns daemon, daemon fails again → loop

Docker:
  → entrypoint.sh: cograw exits immediately
  → Wait loop: raw.sock never appears (30s timeout)
  → entrypoint.sh continues anyway (best effort)
  → cognitiveosd starts, tries to connect to raw.sock
  → cognitiveosd: FATAL exit
  → daemon.sock never appears (30s timeout)
  → entrypoint.sh execs CLI anyway
  → CLI tries to connect to daemon.sock, fails
  → CLI shows error, retries indefinitely
```

### coginfer fails to start

```
ISO:
  → OpenRC marks coginfer as failed
  → cognitiveosd starts, connects to raw.sock (OK)
  → cognitiveosd tries HTTP GET /health on :11434
  → HTTP connection refused
  → cognitiveosd: WARNING — Wide Model unavailable, running in degraded mode
  → cognitiveosd continues (non-fatal)
  → System operates with raw model only (guardrail active, no inference)

Docker:
  → entrypoint.sh: coginfer exits immediately
  → Wait loop: HTTP never responds (30s timeout)
  → entrypoint.sh continues anyway
  → cognitiveosd starts, HTTP check warns (non-fatal)
  → System runs in degraded mode
```

### cognitiveosd fails to start

```
ISO:
  → OpenRC marks cognitiveosd as failed
  → cpm-runtime-deps skipped
  → tty1 respawns CLI
  → CLI checks daemon.sock — not found
  → CLI spawns cognitiveosd as subprocess (fire-and-forget)
  → If same failure: CLI shows error, retries
  → If different failure (e.g., transient): system recovers

Docker:
  → entrypoint.sh: cognitiveosd exits immediately
  → Wait loop: daemon.sock never appears (30s timeout)
  → entrypoint.sh execs CLI anyway
  → CLI tries daemon.sock, fails
  → CLI shows error, retries indefinitely
```

### All services healthy, CLI disconnects

```
ISO:
  → OpenRC respawns CLI on tty1
  → New CLI process starts
  → Connects to daemon.sock (still running)
  → TUI renders, user resumes

Docker:
  → CLI exits
  → entrypoint.sh already exec'd, so tini sees child exit
  → Container stops (no respawn in Docker)
  → User must docker run again
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

### Signal Handling

**Docker:**
```
docker stop
  → Docker sends SIGTERM to PID 1 (coginit)
  → coginit forwards SIGTERM to all children
  → cognitiveos-cli: Bubble Tea cleanup, exit
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
  → cognitiveos-cli: Bubble Tea cleanup, exit
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
