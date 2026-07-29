# Boot / Startup / Process Lifecycle Analysis

Version: 1.0.0-draft

## Overview

This document provides a complete low-level analysis of the CognitiveOS boot chain, startup sequence, and process lifecycle. It maps every specification reference against actual code behavior, identifies all gaps between design and implementation, and catalogs every broken or missing component. This is the authoritative reference for boot-related work.

## System Architecture: Three Daemons

CognitiveOS runs three independent processes, not two:

| Process | Binary | Transport | Listening Endpoint | Model | Role |
|---------|--------|-----------|-------------------|-------|------|
| Raw Model | `cograw` | Unix socket | `/cognitiveos/run/raw.sock` | `raw-model.gguf` | Firmware guardrail — prompt classification, code validation, resource auditing |
| Wide Model | `coginfer` | HTTP TCP | `127.0.0.1:11434` | `wide-model.gguf` | Inference engine — text generation, on-demand model loading/unloading |
| Orchestrator | `cognitiveosd` | Unix socket | `/cognitiveos/run/daemon.sock` | none | Main daemon — connects to both models, spawns MCP bridges, manages lifecycle |

Communication flow:

```
CLI ──[daemon.sock]──> cognitiveosd ──[raw.sock]──> cograw
                       cognitiveosd ──[HTTP:11434]──> coginfer
```

The daemon (`cognitiveosd`) is the hub. It connects to `cograw` via a Unix socket (`RawModelClient`) and to `coginfer` via HTTP (`WideModelClient`). The two model servers are completely independent — they share no runtime communication path.

### Binary Flags

**cograw** (`inference/cmd/cograw/main.go`):

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/cognitiveos/run/raw.sock` | Unix socket path |
| `--model` | `/cognitiveos/models/raw/raw-model.gguf` | GGUF model path |
| `--log` | stderr | Log file path |
| `--audit-log` | `/cognitiveos/logs/raw/audit.log` | Audit log path |
| `--version` | — | Print version and exit |

**coginfer** (`inference/cmd/coginfer/main.go`):

| Flag | Default | Description |
|------|---------|-------------|
| `--addr` | `127.0.0.1:11434` | HTTP listen address |
| `--models` | `/cognitiveos/models` | Model directory |
| `--backend` | `mock` | Inference backend (`mock` or `cgo`) |
| `--log` | stderr | Log file path |
| `--version` | — | Print version and exit |

**cognitiveosd** (`cognitiveosd/cmd/cognitiveosd/main.go`):

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--socket` | `COGNITIVEOS_SOCKET` | `/cognitiveos/run/daemon.sock` | Unix socket path |
| `--run` | `COGNITIVEOS_RUN_DIR` | `/cognitiveos/run` | Runtime directory |
| `--log-dir` | `COGNITIVEOS_LOG_DIR` | `/cognitiveos/logs` | Log directory |
| `--models` | `COGNITIVEOS_MODEL_DIR` | `/cognitiveos/models` | Model directory |
| `--patches` | `COGNITIVEOS_PATCH_DIR` | `/cognitiveos/patches` | Patch directory |
| `--mcp-bin` | `COGNITIVEOS_MCP_BIN_DIR` | `/cognitiveos/bin` | MCP server binary directory |
| `--inference` | `COGNITIVEOS_INFERENCE_URL` | `http://127.0.0.1:11434` | Inference engine URL |
| `--audit-interval` | — | `60` | Audit interval in seconds |

**cognitiveos-cli** (`cli/cmd/cognitiveos-cli/main.go`):

| Flag | Default | Description |
|------|---------|-------------|
| `--socket` | `/cognitiveos/run/daemon.sock` | Daemon socket path |

### Binary Failure Modes

| Binary | Startup Requirement | Behavior if Unmet | Signal Handling |
|--------|-------------------|-------------------|-----------------|
| cograw | Model file must exist on disk | `log.Fatalf` — immediate exit | SIGTERM/SIGINT (graceful shutdown) |
| coginfer | None — starts in degraded mode | Mock backend serves canned responses | **None** — abrupt kill on SIGTERM |
| cognitiveosd | cograw MUST be running | `return fmt.Errorf("FATAL: ...")` — exit | SIGTERM/SIGINT/SIGQUIT (graceful) |
| cognitiveos-cli | cognitiveosd MUST be running | Retries 30s, then infinite reconnect loop | None (TUI handles) |

## Binary Build and Install Chain

### Source Repositories

| Binary | Source Repo | Entry Point | Build Dependencies |
|--------|------------|-------------|-------------------|
| cograw | `inference` | `cmd/cograw/main.go` | Go, llama.cpp (CGo), cmake, build-base |
| coginfer | `inference` | `cmd/coginfer/main.go` | Go, llama.cpp (CGo), cmake, build-base |
| cognitiveosd | `cognitiveosd` | `cmd/cognitiveosd/main.go` | Go (pure, CGO_ENABLED=0) |
| cognitiveos-cli | `cli` | `cmd/cognitiveos-cli/main.go` | Go (pure, CGO_ENABLED=0) |
| cpm | `cpm` | `cmd/cpm/main.go` | Go (pure, CGO_ENABLED=0) |

### Build Process

Each repo has a `Makefile` with a `build` target that produces binaries at `<repo>/build/bin/`:

| Repo | Build Command | Output |
|------|--------------|--------|
| inference | `make build` | `build/bin/cograw`, `build/bin/coginfer` |
| cognitiveosd | `make build` | `build/bin/cognitiveosd` |
| cli | `make build` | `build/bin/cognitiveos-cli` |
| cpm | `make build` | `build/bin/cpm` |

**inference build modes:**

| Mode | Trigger | CGO | Result |
|------|---------|-----|--------|
| Mock | `CGO_ENABLED=0` | Off | Simulated backends, no llama.cpp |
| Production | `CGO_ENABLED=1` | On | Links static llama.cpp via CGo |

Production builds compile llama.cpp from source (vendored at `vendor/llama.cpp/`) via `build-llama` → `build-dependencies` Makefile targets.

### Collection into Distro

**Script:** `cognitiveos-alpine-distro/scripts/build-binaries.sh`

Iterates repos in dependency order: `cpm → inference → core-mcp-bridges → cognitiveosd → cli`. For each repo, runs `make build` and copies everything from `<repo>/build/bin/*` into `cognitiveos-alpine-distro/build/bin/`.

After collection:
```
cognitiveos-alpine-distro/build/bin/
├── cograw           (from inference)
├── coginfer         (from inference)
├── cognitiveosd     (from cognitiveosd)
├── cognitiveos-cli  (from cli)
├── cpm              (from cpm)
└── bridges/         (from core-mcp-bridges)
```

### Overlay Assembly

**Script:** `cognitiveos-alpine-distro/scripts/build-overlay.sh`

Lines 33-40 iterate `build/bin/*` and copy each binary into `overlay/usr/local/bin/`:

```sh
for f in "${BIN_DIR}"/*; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    [ "$name" = "bridges" ] && continue
    cp "$f" "${OVERLAY_DIR}/usr/local/bin/$name"
    chmod 755 "${OVERLAY_DIR}/usr/local/bin/$name"
done
```

Bridges (from `core-mcp-bridges`) go to `overlay/usr/local/lib/cognitiveos/bridges/` instead.

**Note:** `overlay/usr/local/bin/` is git-tracked but always empty. It is cleared and repopulated by `build-overlay.sh` at build time.

### Final Installed Paths

| Binary | Source Repo | Overlay Path | ISO Path | Docker Path |
|--------|------------|-------------|----------|-------------|
| cograw | inference | `overlay/usr/local/bin/cograw` | `/usr/local/bin/cograw` | `/usr/local/bin/cograw` |
| coginfer | inference | `overlay/usr/local/bin/coginfer` | `/usr/local/bin/coginfer` | `/usr/local/bin/coginfer` |
| cognitiveosd | cognitiveosd | `overlay/usr/local/bin/cognitiveosd` | `/usr/local/bin/cognitiveosd` | `/usr/local/bin/cognitiveosd` |
| cognitiveos-cli | cli | `overlay/usr/local/bin/cognitiveos-cli` | `/usr/local/bin/cognitiveos-cli` | `/usr/local/bin/cognitiveos-cli` |
| cpm | cpm | `overlay/usr/local/bin/cpm` | `/usr/local/bin/cpm` | `/usr/local/bin/cpm` |
| bridges | core-mcp-bridges | `overlay/usr/local/lib/cognitiveos/bridges/` | `/usr/local/lib/cognitiveos/bridges/` | `/usr/local/lib/cognitiveos/bridges/` |

### How Each Deployment Gets Binaries

**ISO (Alpine Linux):**

1. `build-overlay.sh` populates `overlay/usr/local/bin/` with all binaries
2. `genapkovl-cognitiveos.sh` tars the entire overlay into `.apkovl.tar.gz`:
   ```sh
   if [ -n "$COGNITIVEOS_OVERLAY_DIR" ] && [ -d "$COGNITIVEOS_OVERLAY_DIR" ]; then
       (cd "$COGNITIVEOS_OVERLAY_DIR" && tar -cf - .) | (cd "$tmp" && tar -xf -)
   fi
   ```
3. `build-image.sh` exports `COGNITIVEOS_OVERLAY_DIR` before calling `mkimage.sh`
4. The `.apkovl.tar.gz` is embedded in the ISO root filesystem

**Docker:**

1. Builder stage runs `make docker.build` which calls `build-binaries.sh` + `build-overlay.sh`
2. Binaries are copied to `/out/` in the builder container
3. Final stage: `COPY --from=builder /out/ /` copies the overlay tree into the image root

```dockerfile
FROM golang:1.25-alpine AS builder
# ... install build deps ...
RUN make docker.build

FROM alpine:edge
COPY --from=builder /out/ /
ENTRYPOINT ["/usr/local/bin/cognitiveos-cli"]
```

**Distro Tarball:**

`scripts/build-distro-tarball.sh` copies `overlay/` into `rootfs/`:
```
cognitiveos-alpine-distro-<ver>/rootfs/usr/local/bin/{cograw,coginfer,cognitiveosd,cognitiveos-cli,cpm}
```

### The Gap: Binaries Exist, Init System Doesn't (RESOLVED by coginit)

The build and install pipeline is **correct**. All binaries are compiled, collected, and placed at `/usr/local/bin/` in both ISO and Docker images. The init system gap has been resolved by `coginit`:

| Component | Status | Resolution |
|-----------|--------|------------|
| Binaries compiled | ✅ | All binaries build successfully |
| Binaries installed | ✅ | All at `/usr/local/bin/` in final image |
| cograw launched | ✅ | Started by coginit (not OpenRC) |
| coginfer launched | ✅ | Started by coginit (not OpenRC) |
| cognitiveosd launched | ✅ | Started by coginit (not OpenRC) |
| CLI launched | ✅ | TUI supervision loop in coginit |
| cpm-boot-deps executed | ✅ | Run by coginit (not OpenRC) |
| cpm-runtime-deps executed | ✅ | Run by coginit (not OpenRC) |

## Spec References vs Actual Behavior

### Boot Sequence: ISO (Alpine Linux)

| Step | Spec Reference | What Spec Says | What Code Actually Does | Status |
|------|---------------|----------------|------------------------|--------|
| 1 | `distro-build-spec.md` | Kernel boots, loads drivers | Same | ✅ |
| 2 | `boot-flow.md` | OpenRC runs sysinit, boot, default stages | **Now correct** — inittab has `::sysinit:` lines + OpenRC stages | ✅ Fixed |
| 3 | `boot-flow.md` | OpenRC starts hwdrivers, networking, alsa | **Now correct** — OpenRC runs system services only | ✅ Fixed |
| 4 | `boot-flow.md` | Inittab spawns `coginit --bare-metal` on tty1 | `coginit` is PID 1, starts engines in order | ✅ Fixed |
| 5 | `boot-flow.md` | coginit starts engines, waits for readiness | cograw→raw.sock→coginfer→HTTP→cognitiveosd→daemon.sock | ✅ |
| 6 | `boot-flow.md` | cognitiveosd reads `config.toml` | **STILL UNFIXED** — no code reads config.toml | ❌ Missing |
| 7 | `boot-flow.md` | CPU Scans patches, builds registry, spawns MCPs, loads Wide Model | Partial — MCPs spawn, Wide Model warns if missing | ⚠️ Partial |
| 8 | `boot-flow.md` | Reports "CognitiveOS ready" | CLI connects to daemon.sock → TUI renders | ✅ Fixed |

### Boot Sequence: Daemon Startup

| Step | Spec Reference | What Spec Says | What Code Actually Does | Status |
|------|---------------|----------------|------------------------|--------|
| 1 | `raw-model.md:438` | inittab spawns `cognitiveosd` as PID 1 | CLI spawns it, not inittab | ⚠️ Different |
| 2 | `raw-model.md:439` | cognitiveosd spawns `cograw` | **No code to spawn cograw** | ❌ Missing |
| 3 | `raw-model.md:440-441` | cograw loads GGUF, opens raw.sock | Same (if model file exists) | ✅ |
| 4 | `raw-model.md:444` | cognitiveosd connects to raw.sock | Same (but fatals if missing) | ✅ |
| 5 | `raw-model.md:445` | cognitiveosd spawns MCP servers | Same | ✅ |
| 6 | `raw-model.md:445` | cognitiveosd loads Wide Model | Warns if coginfer missing, doesn't fatal | ⚠️ Partial |

### Boot Sequence: Docker

| Step | What Should Happen | What Actually Happens | Status |
|------|-------------------|----------------------|--------|
| 1 | coginit as PID 1 | coginit starts as PID 1 via ENTRYPOINT | ✅ Done |
| 2 | Start cograw in background | coginit starts cograw, waits for raw.sock | ✅ Done |
| 3 | Start coginfer in background | coginit starts coginfer, waits for HTTP health | ✅ Done |
| 4 | Wait for raw.sock and HTTP:11434 | coginit polls with timeouts | ✅ Done |
| 5 | Start cognitiveosd in background | coginit starts cognitiveosd, waits for daemon.sock | ✅ Done |
| 6 | CLI connects to daemon.sock | coginit execs CLI (replaces process) | ✅ Done |

### Process Lifecycle: Daemon `Run()` Method

The daemon startup sequence in `cognitiveosd/internal/daemon/daemon.go` `Run()`:

| Step | Action | Status |
|------|--------|--------|
| 1 | Create `/cognitiveos/run/` directory (tmpfs) | ✅ |
| 2 | Open Unix socket at `/cognitiveos/run/daemon.sock` | ✅ |
| 3 | Connect to cograw via raw.sock | ✅ but **FATAL** if missing |
| 4 | Connect to coginfer via HTTP `/health` | ⚠️ Warning only if missing |
| 5 | Spawn MCP bridge servers | ✅ |
| 6 | Start audit loop (periodic hardware audit) | ✅ |
| 7 | Enter main event loop (read messages from socket) | ✅ |

**Never executes:** Load raw model, scan patches, build model registry, load Wide Model. These are spec-only behaviors.

### CLI Startup Sequence

| Step | Action | Status |
|------|--------|--------|
| 1 | Check if daemon.sock exists | ✅ |
| 2 | If not, spawn `cognitiveosd` as subprocess (`cmd.Start()`, fire-and-forget) | ✅ |
| 3 | Poll socket 8× at 250ms intervals (2s total) | ✅ |
| 4 | Connect via Unix socket | ✅ |
| 5 | Launch TUI | ✅ |
| 6 | If daemon crashes, CLI dies too (no reconnect) | ⚠️ Bug — `Messages` channel never closed |

## Overlay inittab

### Current (Fixed — matches running ISOs)

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

OpenRC handles system services (devfs, hwdrivers, networking, syslog, acpid). coginit handles CognitiveOS services (cograw, coginfer, cognitiveosd, CLI).

**Note:** The `genapkovl-cognitiveos.sh` script's dead-code fallback is irrelevant — the overlay inittab now includes OpenRC stages.

## OpenRC Service Layer (System Services Only)

### Services Registered by genapkovl

The script at `scripts/genapkovl-cognitiveos.sh` registers these OpenRC services via `rc_add`:

| Service | Runlevel | Purpose |
|---------|----------|---------|
| devfs | sysinit | Device filesystem |
| dmesg | sysinit | Kernel message buffer |
| mdev | sysinit | Device manager |
| hwdrivers | sysinit | Hardware drivers |
| modloop | sysinit | Module loading |
| hwclock | boot | Hardware clock sync |
| modules | boot | Kernel module loading |
| sysctl | boot | Kernel parameters |
| hostname | boot | Hostname setting |
| bootmisc | boot | Miscellaneous boot tasks |
| syslog | boot | System logging |
| acpid | default | Power management |
| mount-ro | shutdown | Read-only remount |
| killprocs | shutdown | Process cleanup |
| savecache | shutdown | Cache persistence |

These services execute correctly — the overlay inittab now includes OpenRC sysinit/boot/default stages.

### CognitiveOS Service Management (coginit, not OpenRC)

CognitiveOS services are NOT managed by OpenRC. They are started and supervised by `coginit`:

| Service | Manager | Start Method | Supervision |
|---------|---------|-------------|-------------|
| cograw | coginit | `startCograw()` in engine.go | Auto-restart on crash (500ms delay) |
| coginfer | coginit | `startCoginfer()` in engine.go | Auto-restart on crash (500ms delay) |
| cognitiveosd | coginit | `startCognitiveosd()` in engine.go | Auto-restart on crash (500ms delay) |
| cognitiveos-cli | coginit | TUI supervision loop in bare-metal | Auto-restart on exit (500ms delay) |
| cpm-boot-deps | coginit | `installDependencies("boot")` | One-shot, run during startup |
| cpm-runtime-deps | coginit | `installDependencies("runtime")` | One-shot, run after engines start |

### Existing Orphaned Scripts (Legacy — kept for compatibility)

**cpm-boot-deps** (`overlay/etc/init.d/cpm-boot-deps`) and **cpm-runtime-deps** (`overlay/etc/init.d/cpm-runtime-deps`) exist as OpenRC init scripts but are no longer used. They are kept for backward compatibility with third-party tooling that may reference them. coginit handles dependency installation directly via `cpm install-dependencies --stage boot/runtime`.

## Boot Chain Breakage: Cascade Analysis

```
Power On → BIOS/U-Boot → Kernel → inittab spawns CLI directly
                                              ↓
                                     CLI on tty1
                                              ↓
                                   (socket not found after 2s)
                                              ↓
                                   spawns cognitiveosd (fire-and-forget)
                                              ↓
                                   cognitiveosd tries raw.sock
                                              ↓
                                   FATAL: raw model unavailable
                                              ↓
                                   cognitiveosd exits
                                              ↓
                                   CLI dies (no reconnect)
                                              ↓
                                   inittab respawns CLI → loop

Meanwhile:
  ❌ OpenRC never runs
  ❌ devfs, hwdrivers, mdev never start
  ❌ acpid never starts (no power management)
  ❌ cograw never starts (guardrail offline)
  ❌ coginfer never starts (inference offline)
  ❌ cpm-boot-deps never runs (no boot-stage packages)
  ❌ cpm-runtime-deps never runs (no runtime-stage packages)
  ❌ Networking never configured (no dhcpcd/wpa_supplicant)
  ❌ Audio never configured (no alsa)
```

## Expected Boot Chain After Fix

### ISO (Alpine Linux)

```
Power On → BIOS/U-Boot → Kernel → inittab → OpenRC sysinit
                                              ├── devfs
                                              ├── dmesg
                                              ├── mdev
                                              ├── hwdrivers
                                              └── modloop
                                                    ↓
                                     OpenRC boot
                                              ├── hwclock
                                              ├── modules
                                              ├── sysctl
                                              ├── hostname
                                              ├── bootmisc
                                              └── syslog
                                                    ↓
                                     OpenRC default
                                              ├── cograw (loads GGUF, opens raw.sock)
                                              ├── coginfer (opens HTTP :11434)
                                              ├── cpm-boot-deps (installs boot-stage packages)
                                              ├── cognitiveosd (connects to raw.sock, opens daemon.sock)
                                              ├── acpid (power management)
                                              └── cpm-runtime-deps (installs runtime-stage packages)
                                                    ↓
                                     tty1 respawns cognitiveos-cli
                                              ↓
                                     CLI connects to daemon.sock → TUI renders
                                              ↓
                                     "CognitiveOS ready"
```

### Docker (coginit as PID 1)

```
coginit (PID 1)
  ├── Install boot-stage dependencies (cpm)
  ├── Create /cognitiveos/run, /cognitiveos/logs
  ├── Start cograw (background, wait for raw.sock)
  ├── Start coginfer (background, wait for HTTP :11434)
  ├── Start cognitiveosd (background, wait for daemon.sock)
  ├── Install runtime-stage dependencies (cpm)
  └── exec cognitiveos-cli (replaces coginit)
```

## OpenRC Init Scripts

OpenRC init scripts exist only for dependency installation (one-shot). Service startup is handled by coginit.

### /etc/init.d/cpm-boot-deps

```sh
#!/sbin/openrc-run
description="CognitiveOS Boot Dependencies"

depend() {
    need localmount
    keyword -stop
}

command=/usr/local/bin/cpm
command_args="install-dependencies --stage boot"
```

### /etc/init.d/cpm-runtime-deps

```sh
#!/sbin/openrc-run
description="CognitiveOS Runtime Dependencies"

depend() {
    keyword -stop
}

command=/usr/local/bin/cpm
command_args="install-dependencies --stage runtime"
```

### Service Startup

cograw, coginfer, and cognitiveosd are started by coginit (PID 1), not OpenRC. See `specs/boot-flow.md#coginit` for the full boot sequence.

## Docker Init: coginit

Alpine Docker images use `coginit` as PID 1. It replaces `tini` + `entrypoint.sh` with a single compiled Go binary.

**Why coginit is used:**

1. **Zombie reaping**: coginit reaps orphaned child processes via SIGCHLD handler.
2. **Signal forwarding**: Docker sends `SIGTERM` to PID 1. coginit forwards it to child process groups and propagates the exit code.
3. **Service orchestration**: coginit starts cograw, coginfer, and cognitiveosd in the correct order with readiness checks.
4. **Same binary as bare-metal**: No separate init script needed for Docker vs ISO.

**Dockerfile pattern:**

```dockerfile
COPY --from=builder /src/build/out/ /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/coginit"]
```

## Config System Gap

### config.toml

The file at `overlay/etc/cognitiveos/config.toml` defines 7 sections with ~20 keys:

```toml
[system]      hostname, timezone, autologin
[inference]   idle_timeout_seconds, backend, endpoint
[raw_model]   model
[daemon]      socket_path, audit_interval_seconds, mcp_bin_dir
[network]     default_interface, auto_connect, wpa_supplicant_conf
[audio]       default_sink, default_source, volume
[display]     framebuffer_device, media_player, image_viewer
```

**No code reads this file.** All components use hardcoded defaults + CLI flags. The config loading chain is:

```
config.Default → config.FromEnv() → flag.Parse() → cfg.Derive()
```

There is no TOML parsing step. The specs (`raw-model.md:197`, `cognitiveosd-api.md:536`, `distro-build-spec.md:381`) expect config.toml to be read at boot.

**Additional issues:**
- `backend = "cli"` is invalid — valid values are `mock` and `cgo`
- `mcp_bin_dir = "/usr/local/lib/cognitiveos/bridges"` — daemon default is `/cognitiveos/bin`
- `socket_path` in config.toml is overwritten by `Derive()` regardless of what TOML sets

### Planned Config Loading Chain

```
config.Default → FromTOML("/etc/cognitiveos/config.toml") → FromEnv() → flags → Derive()
```

Library: `github.com/BurntSushi/toml` (zero transitive dependencies, de facto standard).

Only daemon-relevant sections (`[daemon]`, `[raw_model]`, `[inference]`) should be read into the Go Config struct. System/network/audio/display sections belong to their respective MCP components.

## Spec Contradictions (RESOLVED)

| Spec | Claim | Resolution |
|------|-------|------------|
| `raw-model.md:438` | inittab spawns cognitiveosd as PID 1 | **RESOLVED by coginit**: inittab spawns `coginit --bare-metal`, which starts and supervises all engines |
| `raw-model.md:439` | cognitiveosd spawns cograw | **RESOLVED by coginit**: coginit starts cograw before cognitiveosd. cognitiveosd connects to already-running cograw |
| `cognitiveosd-api.md:536` | Loads raw model from config.toml `[raw_model].model` | **PARTIALLY RESOLVED**: TOML parsing exists in cognitiveosd (`config.go:FromTOML`) and is called from `main.go`. Config.toml file is parsed but code paths that use it (e.g., raw model loading) are incomplete |
| `cognitiveosd-api.md:532` | Starts as PID 1 OR supervised by init | **RESOLVED**: coginit starts cognitiveosd as a supervised child process on both Docker and bare-metal |

### Remaining Config Gap

| Gap | Status | Notes |
|-----|--------|-------|
| config.toml raw_model.model not consumed by coginit | ❌ Unresolved | coginit's `startCograw()` hardcodes model path. `--model` flag added but not wired to config.toml parsing |
| config.toml daemon.mcp_bin_dir not consumed | ✅ FIXED | Default changed to `/usr/local/lib/cognitiveos/bridges` |
| config.toml daemon.socket_path consumed | ✅ FIXED | `FromTOML()` reads and applies it |

## cpm Dependency System: Boot Integration

### Four Stages

| Stage | When | Execution | Example |
|-------|------|-----------|---------|
| build | `cpm install` time | Inline during install | gcc, cmake, go |
| install | `cpm install` time | Inline during install | System libraries |
| boot | System boot | External trigger (OpenRC) | Kernel modules, firmware |
| runtime | After daemon start | External trigger (OpenRC) | Runtime libraries, fonts |

### Current State

- **build** and **install**: Executed inline by `cpm install` — working correctly
- **boot**: Handled by coginit (`installDependencies("boot")` in engine.go) — **working**
- **runtime**: Handled by coginit (`installDependencies("runtime")` in engine.go) — **working**

## Complete Gap Summary (Current State)

### RESOLVED by coginit

| # | Component | Issue | Resolution |
|---|-----------|-------|------------|
| 1 | Inittab | No OpenRC boot stages | ✅ Fixed — inittab has full OpenRC sysinit/boot/default stages |
| 2 | cograw init script | Does not exist | ✅ Not needed — coginit starts cograw directly |
| 3 | coginfer init script | Does not exist | ✅ Not needed — coginit starts coginfer directly |
| 4 | cognitiveosd init script | Does not exist | ✅ Not needed — coginit starts cognitiveosd directly |
| 5 | genapkovl registration | Never registers CognitiveOS services | ✅ Not needed — coginit handles CognitiveOS services |
| 6 | cpm-boot-deps | Never registered in runlevel | ✅ Handled by coginit (`installDependencies("boot")`) |
| 7 | cpm-runtime-deps | Never registered in runlevel | ✅ Handled by coginit (`installDependencies("runtime")`) |
| 8 | Docker entrypoint | No process orchestration | ✅ coginit as ENTRYPOINT handles orchestration |
| 14 | MCPBinDir mismatch | Default `/cognitiveos/bin` | ✅ FIXED — default is now `/usr/local/lib/cognitiveos/bridges` |

### REMAINING (Unfixed)

| # | Component | Issue | Files Affected | Resolution |
|---|-----------|-------|----------------|------------|
| 9 | config.toml raw_model.model | Not consumed by coginit | `coginit/internal/coginit/engine.go` | Wire `--model` flag from config |
| 10 | cograw mock mode | No `--backend` flag for testing | `inference/cmd/cograw/` | Add `--backend` flag (like coginfer) |
| 11 | coginfer signal handling | No graceful shutdown | `inference/cmd/coginfer/main.go` | Replace bare `http.ListenAndServe` with `http.Server` + `Shutdown()` |
| 12 | CLI reconnection | Messages channel never closed | `cli/internal/client/client.go` | Close `Messages` channel in `Close()` |
| 13 | registries.toml | Not read by any code | `overlay/etc/cognitiveos/registries.toml` | Low priority — default registries are hardcoded |
| 14 | image-manifest.json | Placeholder, overwritten at build | `overlay/etc/cognitiveos/image-manifest.json` | Low priority — build-time artifact |

## References

| Document | Relevant Lines | Topic |
|----------|---------------|-------|
| `specs/raw-model.md` | 434-447 | Daemon startup, cograw spawn, raw.sock |
| `specs/distro-build-spec.md` | 366-390, 381 | First boot sequence, config.toml reference |
| `specs/cognitiveosd-api.md` | 530-542, 536 | Daemon startup sequence, config.toml reference |
| `specs/cli-spec.md` | 15-24 | CLI startup, daemon connection |
| `specs/architecture.md` | 49-53 | Architecture boot overview |
| `specs/inference-api.md` | 321 | Idle timeout config.toml reference |
| `specs/filesystem-hierarchy.md` | 68 | config.toml location |
| `specs/security-model.md` | 51 | config.toml tampering concern |
| `cognitiveos-alpine-distro/overlay/etc/inittab` | — | Inittab with OpenRC stages + coginit |
| `cognitiveos-alpine-distro/scripts/genapkovl-cognitiveos.sh` | 34-46, 78-81 | Service registration for system services |
| `cognitiveosd/internal/config/config.go` | FromTOML() | TOML config parsing (reads daemon/inference/raw_model sections) |
| `coginit/internal/coginit/engine.go` | — | coginit engine startup with supervision |
| `cognitiveosd/internal/config/config.go` | — | Config struct, FromEnv(), Derive() |
| `cognitiveosd/internal/daemon/daemon.go` | Run() method | Daemon startup sequence |
| `cognitiveosd/internal/daemon/raw_client.go` | Connect() | Fatal exit on cograw missing |
| `cognitiveosd/internal/daemon/wide_client.go` | Connect() | Warning on coginfer missing |
| `cli/cmd/cognitiveos-cli/main.go` | 22-42 | CLI daemon spawning |
| `cli/internal/client/client.go` | Close() | Messages channel leak |
| `inference/cmd/cograw/main.go` | — | Raw model server |
| `inference/cmd/coginfer/main.go` | — | Inference HTTP server |
