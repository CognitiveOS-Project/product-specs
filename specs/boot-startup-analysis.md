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

### The Gap: Binaries Exist, Init System Doesn't

The build and install pipeline is **correct**. All 5 binaries are compiled, collected, and placed at `/usr/local/bin/` in both ISO and Docker images. The gap is purely in the init system:

| Component | Status |
|-----------|--------|
| Binaries compiled | ✅ All 5 binaries build successfully |
| Binaries installed | ✅ All at `/usr/local/bin/` in final image |
| CLI launched | ✅ inittab respawns CLI on tty1 |
| cograw launched | ❌ No OpenRC init script |
| coginfer launched | ❌ No OpenRC init script |
| cognitiveosd launched | ⚠️ CLI spawns it as fire-and-forget subprocess |
| cpm-boot-deps executed | ❌ Script exists but never registered in runlevel |
| cpm-runtime-deps executed | ❌ Script exists but never registered in runlevel |

## Spec References vs Actual Behavior

### Boot Sequence: ISO (Alpine Linux)

| Step | Spec Reference | What Spec Says | What Code Actually Does | Status |
|------|---------------|----------------|------------------------|--------|
| 1 | `distro-build-spec.md:369-371` | Kernel boots, loads drivers | Same | ✅ |
| 2 | `distro-build-spec.md:372` | OpenRC runs sysinit, boot, default stages | **Missing** — inittab has no `::sysinit:` lines | ❌ Broken |
| 3 | `distro-build-spec.md:373` | OpenRC starts hwdrivers, networking, alsa | **Missing** — no OpenRC invocation | ❌ Broken |
| 4 | `distro-build-spec.md:374` | Inittab spawns CLI on tty1 | CLI appears but before services are ready | ⚠️ Premature |
| 5 | `distro-build-spec.md:375-376` | CLI connects to daemon.sock; spawns daemon if missing | Same (fire-and-forget via `cmd.Start()`) | ✅ |
| 6 | `distro-build-spec.md:381` | cognitiveosd loads raw model from `config.toml` | **No code reads config.toml** | ❌ Missing |
| 7 | `distro-build-spec.md:382-386` | Scans patches, builds registry, spawns MCPs, loads Wide Model | Partial — MCPs spawn, Wide Model warns if missing | ⚠️ Partial |
| 8 | `distro-build-spec.md:387` | Reports "CognitiveOS ready" | **Never reached** — fatal exit at step 6 | ❌ Broken |

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
| 1 | tini as PID 1 | cognitiveos-cli is PID 1 | ❌ Missing |
| 2 | Start cograw in background | Never started | ❌ Missing |
| 3 | Start coginfer in background | Never started | ❌ Missing |
| 4 | Wait for raw.sock and HTTP:11434 | No waiting logic | ❌ Missing |
| 5 | Start cognitiveosd in background | CLI tries to start daemon, which fatals | ❌ Broken |
| 6 | CLI connects to daemon.sock | Container dies | ❌ Broken |

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

## Overlay inittab: Current vs Required

### Current (Broken)

```
# CognitiveOS
tty1::respawn:/usr/local/bin/cognitiveos-cli
ttyS0::respawn:/usr/local/bin/cognitiveos-cli
tty2::respawn:/sbin/getty 38400 tty2
```

This overlay has **3 lines** and **disables the entire OpenRC service layer**. No `::sysinit:`, `::wait:`, or `::shutdown:` directives exist. OpenRC never runs.

### Required (Fixed)

```
::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default
tty1::respawn:/usr/local/bin/cognitiveos-cli
ttyS0::respawn:/usr/local/bin/cognitiveos-cli
tty2::respawn:/sbin/getty 38400 tty2
::ctrlaltdel:/sbin/reboot
::shutdown:/sbin/openrc shutdown
```

This adds 5 lines that invoke OpenRC at each boot stage, enabling hardware initialization, service dependency ordering, and clean shutdown.

### Why the Overlay Breaks OpenRC

The `genapkovl-cognitiveos.sh` script (lines 34-46) has a **dead-code fallback** that generates a correct standard Alpine inittab with OpenRC stages. However, the overlay directory contains `etc/inittab`, which is copied into the image first. Since the file already exists when the fallback check runs (`if [ ! -f "$tmp"/etc/inittab ]`), the fallback is **never executed**.

The overlay inittab takes precedence and contains only the 3-line CognitiveOS snippet, completely replacing the standard Alpine inittab.

## OpenRC Service Layer

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

**None of these services actually execute** because the overlay inittab never invokes OpenRC.

### Services NOT Registered (Missing)

| Service | Required Runlevel | Purpose | Status |
|---------|------------------|---------|--------|
| cograw | default | Raw Model guardrail server | ❌ Script does not exist |
| coginfer | default | Wide Model inference server | ❌ Script does not exist |
| cognitiveosd | default | Main daemon orchestrator | ❌ Script does not exist |
| cpm-boot-deps | default | Install boot-stage system packages | ⚠️ Script exists but never registered |
| cpm-runtime-deps | default | Install runtime-stage system packages | ⚠️ Script exists but never registered |

### Existing Orphaned Scripts

**cpm-boot-deps** (`overlay/etc/init.d/cpm-boot-deps`):

```sh
#!/sbin/openrc-run
description="CognitiveOS Boot-Stage Dependency Collector"

depend() {
    before cognitiveosd
    keyword -stop
}

start() {
    ebegin "Installing boot-stage dependencies"
    /usr/local/bin/cpm install-dependencies --stage boot
    eend $?
}
```

Runs before cognitiveosd. Calls `cpm install-dependencies --stage boot` to install system packages needed at boot. Never executes because it is never registered in any runlevel.

**cpm-runtime-deps** (`overlay/etc/init.d/cpm-runtime-deps`):

```sh
#!/sbin/openrc-run
description="CognitiveOS Runtime-Stage Dependency Collector"

depend() {
    after cognitiveosd
    keyword -start -stop
}

start() {
    ebegin "Processing runtime dependency queue"
    /usr/local/bin/cpm install-dependencies --stage runtime
    eend $?
}

stop() {
    return 0
}
```

Runs after cognitiveosd. Calls `cpm install-dependencies --stage runtime`. Never executes because it is never registered in any runlevel.

Both scripts reference `cognitiveosd` in their `depend()` functions, but no `cognitiveosd` OpenRC init script exists.

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

### Docker (with tini)

```
tini (PID 1) → entrypoint.sh
                ├── mkdir -p /cognitiveos/run /cognitiveos/logs
                ├── Start cograw (background, wait for raw.sock)
                ├── Start coginfer (background, wait for HTTP :11434)
                ├── Start cognitiveosd (background, wait for daemon.sock)
                └── exec cognitiveos-cli
```

## Missing OpenRC Init Scripts

Three init scripts must be created:

### /etc/init.d/cograw (Planned)

```sh
#!/sbin/openrc-run
description="CognitiveOS Raw Model Guardrail Server"

depend() {
    need localmount
    keyword -stop
}

command=/usr/local/bin/cograw
command_args="--model /cognitiveos/models/raw/raw-model.gguf"
command_background=true
pidfile=/run/cograw.pid
output_log=/cognitiveos/logs/cograw.log
error_log=${output_log}
```

### /etc/init.d/coginfer (Planned)

```sh
#!/sbin/openrc-run
description="CognitiveOS Wide Model Inference Server"

depend() {
    need localmount
    keyword -stop
}

command=/usr/local/bin/coginfer
command_args="--backend cgo --models /cognitiveos/models"
command_background=true
pidfile=/run/coginfer.pid
output_log=/cognitiveos/logs/coginfer.log
error_log=${output_log}
```

### /etc/init.d/cognitiveosd (Planned)

```sh
#!/sbin/openrc-run
description="CognitiveOS Daemon"

depend() {
    need cograw
    after coginfer
    before cpm-runtime-deps
    keyword -stop
}

command=/usr/local/bin/cognitiveosd
command_background=true
pidfile=/run/cognitiveosd.pid
output_log=/cognitiveos/logs/cognitiveosd.log
error_log=${output_log}
```

### Planned Dependency Chain

```
cograw → coginfer → cpm-boot-deps → cognitiveosd → cpm-runtime-deps
```

### Planned genapkovl Registration

```sh
rc_add cograw default
rc_add coginfer default
rc_add cpm-boot-deps default
rc_add cognitiveosd default
rc_add cpm-runtime-deps default
```

## Docker Init: tini

Alpine Docker images have no init system by default. `tini` is available in the Alpine community repository (`apk add tini`, installs to `/sbin/tini`).

**Why tini is required:**

1. **Zombie reaping**: Without tini, orphaned child processes become zombies because the app (as PID 1) doesn't call `wait()`.
2. **Signal forwarding**: Docker sends `SIGTERM` to PID 1. Tini forwards it to the child process group and propagates the exit code.
3. **Portability**: Baked-in tini works in Docker, Kubernetes, podman, and any OCI runtime. The `docker run --init` flag only works with Docker engine.

**Planned Dockerfile pattern:**

```dockerfile
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/local/bin/cognitiveos-cli"]
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

## Spec Contradictions

| Spec | Claim | Conflicts With |
|------|-------|---------------|
| `raw-model.md:438` | inittab spawns cognitiveosd as PID 1 | `distro-build-spec.md:374` (CLI spawned by inittab), `cli-spec.md:20` (CLI on tty1), `architecture.md:51` (inittab skips login, spawns CLI) |
| `raw-model.md:439` | cognitiveosd spawns cograw | Code assumes cograw is already running (fatal exit if not) |
| `cognitiveosd-api.md:536` | Loads raw model from config.toml `[raw_model].model` | Code has no TOML parsing |
| `cognitiveosd-api.md:532` | Starts as PID 1 OR supervised by init | CLI spawns it as a subprocess (neither PID 1 nor init-supervised) |

### Recommended Resolution

| Contradiction | Resolution |
|--------------|------------|
| PID 1 vs CLI-spawned | **Follow distro-build-spec**: inittab spawns CLI, CLI spawns daemon. This matches the code and the original vision (`gemini-conversation.md`). |
| Daemon spawns cograw | **Follow init system approach**: OpenRC starts cograw before cognitiveosd. No code change needed. Simpler, follows Linux conventions. |
| config.toml reading | **Implement TOML parsing**: Align code with specs. |

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
- **boot**: `cpm-boot-deps` script exists but never registered in runlevel — **broken**
- **runtime**: `cpm-runtime-deps` script exists but never registered in runlevel — **broken**

### Fix Required

1. Register `cpm-boot-deps` and `cpm-runtime-deps` in the `default` OpenRC runlevel via `genapkovl`
2. Ensure dependency ordering: `cograw → coginfer → cpm-boot-deps → cognitiveosd → cpm-runtime-deps`

## Complete Gap Summary

### Critical (System Cannot Boot)

| # | Component | Issue | Files Affected |
|---|-----------|-------|----------------|
| 1 | Inittab | No OpenRC boot stages | `overlay/etc/inittab` |
| 2 | cograw init script | Does not exist | Should be `/etc/init.d/cograw` |
| 3 | coginfer init script | Does not exist | Should be `/etc/init.d/coginfer` |
| 4 | cognitiveosd init script | Does not exist | Should be `/etc/init.d/cognitiveosd` |
| 5 | genapkovl registration | Never registers CognitiveOS services | `scripts/genapkovl-cognitiveos.sh` |

### High (Functionality Broken)

| # | Component | Issue | Files Affected |
|---|-----------|-------|----------------|
| 6 | cpm-boot-deps | Never registered in runlevel | `overlay/etc/init.d/cpm-boot-deps` |
| 7 | cpm-runtime-deps | Never registered in runlevel | `overlay/etc/init.d/cpm-runtime-deps` |
| 8 | Docker entrypoint | No process orchestration | All 7 Dockerfiles |
| 9 | config.toml | Not read by any code | `cognitiveosd/internal/config/` |

### Medium (Reliability)

| # | Component | Issue | Files Affected | Resolution |
|---|-----------|-------|----------------|------------|
| 10 | cograw mock mode | No `--backend` flag for testing | `inference/cmd/cograw/` | Add `--backend` flag (like coginfer) |
| 11 | coginfer signal handling | No graceful shutdown | `inference/cmd/coginfer/main.go` | Replace bare `http.ListenAndServe` with `http.Server` + `Shutdown()` |
| 12 | CLI reconnection | Messages channel never closed | `cli/internal/client/client.go` | Close `Messages` channel in `Close()` |
| 13 | config.Derive() | Overwrites --socket flag | `cognitiveosd/internal/config/config.go` | Add `socketPathExplicit` bool, skip overwrite if set |
| 14 | MCPBinDir mismatch | Config default `/cognitiveos/bin` vs actual `/usr/local/lib/cognitiveos/bridges` | `cognitiveosd/internal/config/config.go` | Change default to `/usr/local/lib/cognitiveos/bridges` |

### Low (Polish)

| # | Component | Issue | Files Affected |
|---|-----------|-------|----------------|
| 15 | registries.toml | Not read by any code | `overlay/etc/cognitiveos/registries.toml` |
| 16 | image-manifest.json | Placeholder, overwritten at build | `overlay/etc/cognitiveos/image-manifest.json` |

## Resolved Decisions

The following design decisions have been made:

| Decision | Resolution |
|----------|-----------|
| PID 1 vs CLI-spawned | **Follow distro-build-spec**: inittab spawns CLI, CLI spawns daemon. Matches code and original vision. |
| Daemon spawns cograw | **Follow init system approach**: OpenRC starts cograw before cognitiveosd. No code change needed. Simpler, follows Linux conventions. |
| config.toml reading | **Implement TOML parsing**: Align code with specs using `BurntSushi/toml`. |
| Docker missing model handling | **Option A — degraded mode**: Entrypoint detects missing GGUF, logs warning, starts cograw with `--backend mock`, continues with coginfer and cognitiveosd. System operates in degraded mode (guardrail active, no inference). |
| cograw backend selection | **Add `--backend` flag**: Currently compile-time only via build tags. Add runtime flag (like coginfer) to support mock mode for Docker degraded mode and testing. |
| Docker health check tool | **BusyBox wget**: Available in all Alpine images by default. Works for plain HTTP on `127.0.0.1`. No package change needed. |

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
| `cognitiveos-alpine-distro/overlay/etc/inittab` | — | Current broken inittab |
| `cognitiveos-alpine-distro/scripts/genapkovl-cognitiveos.sh` | 34-46, 78-81 | Dead-code fallback, service registration |
| `cognitiveos-alpine-distro/overlay/etc/init.d/cpm-boot-deps` | — | Orphaned boot dependency script |
| `cognitiveos-alpine-distro/overlay/etc/init.d/cpm-runtime-deps` | — | Orphaned runtime dependency script |
| `cognitiveos-alpine-distro/overlay/etc/cognitiveos/config.toml` | — | Orphaned config file |
| `cognitiveosd/internal/config/config.go` | — | Config struct, FromEnv(), Derive() |
| `cognitiveosd/internal/daemon/daemon.go` | Run() method | Daemon startup sequence |
| `cognitiveosd/internal/daemon/raw_client.go` | Connect() | Fatal exit on cograw missing |
| `cognitiveosd/internal/daemon/wide_client.go` | Connect() | Warning on coginfer missing |
| `cli/cmd/cognitiveos-cli/main.go` | 22-42 | CLI daemon spawning |
| `cli/internal/client/client.go` | Close() | Messages channel leak |
| `inference/cmd/cograw/main.go` | — | Raw model server |
| `inference/cmd/coginfer/main.go` | — | Inference HTTP server |
