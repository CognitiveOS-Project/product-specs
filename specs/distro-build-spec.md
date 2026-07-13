# CognitiveOS Distribution Build Specification

Version: 1.0.0-draft

## Overview

`cognitiveos-alpine-distro` produces bootable system images. The primary implementation uses Alpine Linux, with Ubuntu and Red Hat variants planned. The build process compiles all CognitiveOS components, assembles them into an OS overlay, and generates platform-specific images.

## Supported Targets

| Target | Architecture | Image type | Use case |
|--------|-------------|------------|----------|
| `iso` | x86_64 | Bootable ISO | Desktop/VM testing, QEMU, PC install |
| `rpi` | aarch64 | SD card image | Raspberry Pi 3/4/5 |
| `rpi-zero` | armv7 | SD card image | Raspberry Pi Zero 2 W |
| `embedded` | aarch64 | Raw partition image | Embedded devices with eMMC |

## Base Image

| Property | Value |
|----------|-------|
| Base OS | Alpine Linux (edge) — Ubuntu and Red Hat variants planned (see [Multi-OS Strategy](#multi-os-strategy)) |
| Kernel | linux-lts (x86_64), linux-rpi (aarch64) |
| Init system | OpenRC (Alpine default) — systemd for Ubuntu/Red Hat variants |
| Root filesystem | squashfs (read-only) or ext4 (writable developer mode) |

## Partition Layout

### Standard Layout (≥ 4 GB storage)

| Partition | Size | FS | Mount | Type | Description |
|-----------|------|----|-------|------|-------------|
| `p1` (boot) | 256 MB | vfat | `/boot` | Primary | Kernel, initramfs, config.txt (RPi) |
| `p2` (root) | 2 GB | squashfs | `/` | Primary | Alpine root + CognitiveOS base binaries |
| `p3` (firmware) | 512 MB | ext4, ro | `/cognitiveos/models/raw` | Primary | Raw Model + system codes (read-only) |
| `p4` (data) | Remaining | ext4 | `/cognitiveos/data` | Extended | All writable data |

### Minimal Layout (< 4 GB, embedded)

| Partition | Size | FS | Mount | Description |
|-----------|------|----|-------|-------------|
| `p1` (boot+root) | Remaining | squashfs | `/` | Combined kernel + root. No separate boot. |
| `p2` (firmware) | 128 MB | ext4, ro | `/cognitiveos/models/raw` | Raw Model only |
| (no data partition) | — | — | — | Wide Model is remote-only on minimal devices |

## Alpine Packages
### Class Model Mapping
The profile class defines the hardware tier and determines which raw model is baked into the image and which wide model ships as the default.

| Class | RAM | VRAM | Storage | OS/Arch | Raw Model | Wide Model | CI buildable |
|-------|-----|------|---------|---------|-----------|------------|:---:|
| `titan` | ≥16 GB | ≥4 GB | ≥64 GB | linux/arm64 | 235B Qwen GGUF | None — remote/`.cgp` | No |
| `standard` | ≥8 GB | — | ≥16 GB | linux/amd64 | 1.5B GGUF | 8B Gemma 4 (baked) | Yes |
| `gateway` | ≥4 GB | — | ≥8 GB | linux/amd64 | Compiled-in (no GGUF) | Remote on first boot | Yes |
| `edge` | ≥2 GB | — | ≥4 GB | linux/arm64, linux/armv7 | 0.5B GGUF | Tiny (auto-selected) | Slow (QEMU) |
| `micro` | ≥512 MB | — | ≥1 GB | linux/armv7 | Compiled-in (no GGUF) | Remote-only (thin client) | Slow (QEMU) |

**Distribution Note:**
- **Docker images** for all classes can be built in CI (x86_64 native, ARM via QEMU).
- **Bootable images** (ISO/SD card) for `titan` require dedicated hardware or self-hosted runners due to size and build complexity.
- **Validation** in CI is performed using the mock backend. Real hardware validation is performed post-distribution.

### Variant Package Matrix
 
Package sets are defined per variant (`packages.<class>-<arch>`).
 
| Package | standard-x86_64 | gateway-x86_64 | titan-aarch64 | edge-aarch64 | edge-armv7 | micro-armv7 |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| `alpine-base` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `busybox` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `openrc` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `linux-lts` | ✓ | ✓ | — | — | — | — |
| `linux-rpi` | — | — | ✓ | ✓ | ✓ | ✓ |
| `raspberrypi-bootloader` | — | — | ✓ | ✓ | ✓ | ✓ |
| `raspberrypi-firmware` | — | — | ✓ | ✓ | ✓ | ✓ |
| `alsa-utils` | ✓ | — | ✓ | ✓ | ✓ | — |
| `alsa-lib` | ✓ | — | ✓ | ✓ | ✓ | — |
| `iw` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `wpa_supplicant` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `dhcpcd` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `libgpiod` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `kbd` | ✓ | — | ✓ | ✓ | ✓ | — |
| `mpv` | ✓ | — | ✓ | — | — | — |
| `dosfstools` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `e2fsprogs` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `squashfs-tools` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `acpid` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `fbv` | — | — | ✓ | ✓ | ✓ | — |
| `fbi` | — | — | ✓ | ✓ | ✓ | — |
| `gpiod-tools` | — | — | ✓ | ✓ | ✓ | — |
| `iputils` | — | ✓ | — | — | — | — |
| `curl` | — | ✓ | — | — | — | — |
| `nmap` | — | ✓ | — | — | — | — |


### Excluded Packages

```
# Intentionally excluded (no desktop environment)
xorg-server
xorg-xinit
wayland
weston
firefox
chromium
xterm
alpine-desktop
xfce4
mate
gnome
kde
```

## CognitiveOS Packages

These components are compiled and injected into the overlay:

| Package | Source repo | Build output | Installed to |
|---------|-------------|--------------|-------------|
| cognitiveosd | cognitiveosd | `cognitiveosd` binary | `/usr/local/bin/` |
| cognitiveos-cli | cli | `cognitiveos-cli` binary | `/usr/local/bin/` |
| coginfer | inference | `coginfer` binary | `/usr/local/bin/` |
| cpm | cpm | `cpm` binary | `/usr/local/bin/` |
| display-mcp | core-mcp-bridges | `display-mcp` binary | `/usr/local/lib/cognitiveos/bridges/` |
| audio-mcp | core-mcp-bridges | `audio-mcp` binary | `/usr/local/lib/cognitiveos/bridges/` |
| network-mcp | core-mcp-bridges | `network-mcp` binary | `/usr/local/lib/cognitiveos/bridges/` |
| gpio-mcp | core-mcp-bridges | `gpio-mcp` binary | `/usr/local/lib/cognitiveos/bridges/` |
| serial-mcp | core-mcp-bridges | `serial-mcp` binary | `/usr/local/lib/cognitiveos/bridges/` |
| Raw Model | (model file) | `raw-model.gguf` | `/cognitiveos/models/raw/` | Used by cograw for `validate_prompt` NN-based prompt classification; loaded into llama.cpp at boot |
| System configs | (generated) | various | `/etc/cognitiveos/`, `/etc/inittab` |

## Overlay Structure

The overlay directory is merged into the Alpine root filesystem at image build time:

```
overlay/
├── etc/
│   ├── inittab                    # Custom: boots directly into cognitiveos-cli
│   ├── cognitiveos/
│   │   ├── config.toml            # Base system configuration
│   │   └── registries.toml        # Default registry sources
│   ├── apk/
│   │   └── repositories           # Alpine package repos
│   ├── hostname                   # Set to "cognitiveos"
│   └── motd                       # Empty (no login message)
├── cognitiveos/
│   ├── models/
│   │   └── raw/
│   │       └── raw-model.gguf     # Raw Model GGUF (loaded by cograw at boot for prompt classification)
│   └── patches/                   # Empty directory, populated at runtime
└── usr/
    └── local/
        ├── bin/
        │   ├── cognitiveosd
        │   ├── cognitiveos-cli
        │   ├── coginfer
        │   └── cpm
        └── lib/
            └── cognitiveos/
                └── bridges/
                    ├── display-mcp
                    ├── audio-mcp
                    ├── network-mcp
                    ├── gpio-mcp
                    └── serial-mcp
```

### inittab Entry

The critical boot configuration:

```
# CognitiveOS — boot directly into the TUI as root
tty1::respawn:/usr/local/bin/cognitiveos-cli

# Serial console (for embedded/headless)
ttyS0::respawn:/usr/local/bin/cognitiveos-cli

# Emergency recovery shell (Ctrl+Alt+F2)
tty2::respawn:/sbin/getty 38400 tty2
```

## Build Process

### Prerequisites

```bash
# Host system requirements
- Linux (x86_64 or aarch64)
- Docker (for cross-architecture builds)
- Go 1.24+
- make
- git
- Alpine mkimage tools (apk-tools-static, mkimage)
```

### Build Steps

#### Step 1: Fetch Dependencies

```bash
git clone https://github.com/CognitiveOS-Project/cpm.git
git clone https://github.com/CognitiveOS-Project/cognitiveosd.git
git clone https://github.com/CognitiveOS-Project/cli.git
git clone https://github.com/CognitiveOS-Project/inference.git
git clone https://github.com/CognitiveOS-Project/core-mcp-bridges.git
```

#### Step 2: Compile CognitiveOS Binaries

Each repo builds independently using its own `Makefile` and `scripts/build.sh`:

```bash
for repo in cpm cognitiveosd cli inference core-mcp-bridges; do
  cd $repo
  make build
  cd ..
done
```

Binaries are placed in each repo's `build/bin/` directory. The `cognitiveos-alpine-distro` repository then collects them from sibling directories during overlay assembly. Each repo manages its own build environment — Go installation, llama.cpp compilation (inference), and bridge compilation (core-mcp-bridges).

#### Step 3: Prepare Overlay

```bash
mkdir -p overlay/usr/local/bin overlay/usr/local/lib/cognitiveos/bridges overlay/cognitiveos/models/raw overlay/etc/cognitiveos

cp build/bin/cognitiveosd      overlay/usr/local/bin/
cp build/bin/cognitiveos-cli   overlay/usr/local/bin/
cp build/bin/coginfer          overlay/usr/local/bin/
cp build/bin/cpm               overlay/usr/local/bin/
cp build/bin/display-mcp       overlay/usr/local/lib/cognitiveos/bridges/
cp build/bin/audio-mcp         overlay/usr/local/lib/cognitiveos/bridges/
cp build/bin/network-mcp       overlay/usr/local/lib/cognitiveos/bridges/
cp build/bin/gpio-mcp          overlay/usr/local/lib/cognitiveos/bridges/
cp build/bin/serial-mcp        overlay/usr/local/lib/cognitiveos/bridges/

# Download raw model GGUF via cpm download-weights
# <model-id> is the Hugging Face repo + filename (e.g., "CognitiveOS/raw-model-v1")
build/bin/cpm download-weights <model-id> --kind raw --output overlay/cognitiveos/models/raw/raw-model.gguf
chmod 0400 overlay/cognitiveos/models/raw/raw-model.gguf
chown root:root overlay/cognitiveos/models/raw/raw-model.gguf
cp configs/inittab             overlay/etc/inittab
cp configs/config.toml         overlay/etc/cognitiveos/
cp configs/registries.toml     overlay/etc/cognitiveos/
```

#### Step 4: Generate Image

**ISO (x86_64):**

```bash
mkimage \
  --profile cognitiveos \
  --tag edge \
  --arch x86_64 \
  --repository https://dl-cdn.alpinelinux.org/alpine/edge/main \
  --repository https://dl-cdn.alpinelinux.org/alpine/edge/community \
  --outdir ./output \
  --overlay ./overlay \
  --packages "$(cat packages.standard-x86_64)" \
  --kernel-flavors lts \
  --media iso
```

**SD Card (Raspberry Pi):**

```bash
mkimage \
  --profile cognitiveos \
  --tag edge \
  --arch aarch64 \
  --repository https://dl-cdn.alpinelinux.org/alpine/edge/main \
  --repository https://dl-cdn.alpinelinux.org/alpine/edge/community \
  --outdir ./output \
  --overlay ./overlay \
  --packages "$(cat packages.edge-aarch64)" \
  --kernel-flavors rpi \
  --media sdcard
```

#### Step 5: Sign and Verify

```bash
# Generate image checksum
sha256sum output/cognitiveos-*.iso > output/cognitiveos-<version>.iso.sha256

# Sign with build key (optional, for verified boot)
gpg --detach-sign output/cognitiveos-*.iso
```

## Per-Repo Builds

Each Go repository is independently buildable via a consistent interface:

| Repo | Makefile targets | Build output |
|------|-----------------|--------------|
| `cpm` | `build`, `test`, `lint`, `clean` | `build/bin/cpm` |
| `cognitiveosd` | `build`, `test`, `lint`, `clean` | `build/bin/cognitiveosd` |
| `cli` | `build`, `test`, `lint`, `clean` | `build/bin/cognitiveos-cli` |
| `inference` | `build`, `test`, `lint`, `clean`, `build-llama` | `build/bin/cognitiveos-inference`, `build/bin/cograw` |
| `core-mcp-bridges` | `build`, `test`, `lint`, `clean` | `build/bin/audio`, `build/bin/display`, `build/bin/gpio`, `build/bin/network`, `build/bin/serial`, `build/bin/package` |

Each repo also provides `scripts/build.sh` as a self-contained bootstrap script (installs Go, llama.cpp, etc.) for environments without a pre-installed toolchain.

### CI/CD
 
Each Go repo has its own `.github/workflows/ci.yml` that runs `make build`, `make test`, `make lint`, and `go vet` on push/PR to `main`.

The `cognitiveos-alpine-distro` repository provides its own CI pipeline (`ci.yml`) that performs:
- **ShellCheck**: Static analysis of all scripts in `scripts/`.
- **Syntax Validation**: `sh -n` checks on all `.sh` files to ensure no syntax errors.
- **Binary Verification**: Runs `make verify-repos` to ensure all dependent Go repos build from source.
- **Image Build**: Runs `make docker.dev` to build the development runtime image. This job is triggered on every push to `main` and every pull request to ensure the build environment remains functional.


## Build Scripts (Orchestrator)

The `cognitiveos-alpine-distro` repo orchestrates the per-repo builds:

```
cognitiveos-alpine-distro/
├── Makefile              # Top-level build automation (orchestrator)
├── packages.*            # Package list per variant (e.g. packages.standard-x86_64)
├── overlay/              # Filesystem overlay (above)
├── configs/
│   ├── inittab
│   ├── config.toml
│   └── registries.toml
├── scripts/
│   ├── build-binaries.sh   # Step 2: invoke each repo's make build, collect binaries
│   ├── build-overlay.sh    # Step 3: assemble overlay
│   ├── build-image.sh      # Step 4: x86_64 ISO / RPi image
│   ├── build-distro-tarball.sh  # Build portable distro tarball
│   └── sign.sh             # Step 5: checksums + GPG
├── docker/
│   ├── dev/
│   │   └── Dockerfile      # Dev runtime image for CI verification
│   ├── release/
│   │   └── <variant>/      # Variant-specific Dockerfiles (e.g. release/standard-x86_64/Dockerfile)
│   └── Dockerfile.build    # Cross-compilation container (uses per-repo Makefiles)
└── README.md
```

### Makefile Targets

```makefile
all: iso rpi checksums sign

iso:            # Build x86_64 ISO (depends on install-local)
rpi:            # Build Raspberry Pi SD card image (depends on install-local)
install-local:  # Orchestrate per-repo builds + assemble overlay
distro-tarball: # Build portable distro tarball (overlay + binaries)
docker:         # Build the cross-compilation Docker image (cognitiveos-builder)
docker.dev:         # Build dev runtime image (x86_64 only, CGO_ENABLED=0)
release-variant:    # Build release assets (tarball + image) for specific variant
docker-release-arch: # Build variant Docker image using buildx (CGO_ENABLED=1)
docker-push-arch:    # Push variant Docker image to GHCR
checksums:      # Generate SHA-256 checksums for all images
sign:           # GPG-sign all images
clean:          # Remove build artifacts
distclean:      # Remove build artifacts + downloaded deps
```

## First Boot Sequence

```
1. Hardware powers on
2. U-Boot/BIOS loads kernel from boot partition
3. Linux kernel boots, loads drivers
4. init (busybox) runs /etc/init.d/rcS → OpenRC boot
5. OpenRC starts services (hwdrivers, networking, alsa)
6. /etc/inittab fires tty1 → respawn:/usr/local/bin/cognitiveos-cli
7. CLI starts, connects to /cognitiveos/run/daemon.sock
8. If daemon not running: CLI spawns cognitiveosd as subprocess
9. cognitiveosd:
   a. Creates /cognitiveos/run/ directory (tmpfs)
   b. Opens Unix socket
   c. Runs initial hardware audit
   d. Loads Raw Model from config.toml `[raw_model].model` path (default /cognitiveos/models/raw/raw-model.gguf)
   e. Scans /cognitiveos/patches/ for installed patches
   f. Builds model registry from installed .cgp manifests (`brain.wide_model.routing`)
    g. Reads `/cognitiveos/patches/base/weights/` for initial Wide Model (fallback if no model registry entry)

   h. Spawns MCP servers for installed patches
   i. Reports "CognitiveOS ready" to CLI
10. CLI displays idle screen: "ready"
11. System is ready for human interaction
```

## Developer Build (Non-Image)

For development without building a full image:

```bash
# On an existing Alpine Linux system:
make install-local
```

This copies all binaries to `/usr/local/bin/`, installs configs, and sets up the runtime directories. Useful for testing on a real Alpine installation or Docker container.

## Docker Image
 
A lightweight Docker image is provided for development, testing, and headless deployment. Images are built per variant using dedicated Dockerfiles in `docker/release/<variant>/Dockerfile`.
 
```bash
# Build a variant release image (e.g. standard-x86_64)
make docker-release-arch ARCH=x86_64 CLASS=standard
 
# Run — full TUI experience
docker run -it cognitiveos:0.1.0-standard-x86_64
```


The Docker image uses the same overlay as the bootable ISO but skips the mkimage step. All binaries, configs, and default directory structure are baked in.

### Entrypoint

The image entrypoint is `/usr/local/bin/cognitiveos-cli`. On startup the CLI:

1. Checks for the daemon Unix socket at `/cognitiveos/run/daemon.sock`
2. If absent, spawns `cognitiveosd` as a child subprocess
3. Waits up to 15 seconds for the socket to appear
4. Connects and renders the Bubble Tea TUI

No shell scripts, init systems, or supervisor processes are involved — the CLI manages the daemon lifecycle directly. When the CLI exits (Ctrl+D), it signals the daemon child and waits for clean shutdown.

### Limitations

- The Docker image uses `coginfer --backend mock` by default — no real LLM runs inside the container
- No Raw Model GGUF is bundled (no `/cognitiveos/models/raw/raw-model.gguf`)
- Hardware audit reports container-constrained resources (no real GPU, NPU, or peripheral access)
- The Wide Model must be remote (via network-accessible inference endpoint) or pulled at runtime

Despite these limitations, the full TUI, daemon state machine, MCP tool registration, and message protocol work identically to a bootable image.

## Versioning

Distribution images follow the naming convention:

```
cognitiveos-<semver>-<class>-<arch>.<ext>
```

Where:
- `<semver>` — SemVer version (e.g., `0.1.0`, `0.1.0-rc.1`)
- `<class>` — Hardware tier class (see [raw-model.md](raw-model.md#distro-image-variants))
- `<arch>` — Target architecture (`x86_64`, `aarch64`, `armv7`)
- `<ext>` — Image format (`iso`, `img`)

Examples:
```
cognitiveos-0.1.0-standard-x86_64.iso
cognitiveos-0.1.0-titan-aarch64.img
cognitiveos-0.1.0-edge-armv7.img
```

### Config.toml

Only `[raw_model]` is specified in config.toml — the Wide Model is chosen at runtime by the Raw Model routing hint:

```toml
[raw_model]
model = "/cognitiveos/models/raw/raw-model.gguf"
```

There is no `[wide_model]` section. The initial Wide Model on first boot is discovered by scanning `/cognitiveos/patches/base/weights/` for any `.gguf` file shipped with the image. After `.cgp` packages are installed, the model registry (built from `cognitive.json` manifests) drives model selection.

Images also embed a build manifest at `/etc/cognitiveos/image-manifest.json`:

```json
{
  "image_version": "0.1.0",
  "build_date": "2026-06-23T14:30:00Z",
  "alpine_version": "edge",
  "kernel": "6.12-lts",
  "cognitiveos_components": {
    "cognitiveosd": "0.1.0",
    "cli": "0.1.0",
    "coginfer": "0.1.0",
    "cpm": "0.1.0"
  },
  "raw_model": {
    "name": "raw-model-v1",
    "size_bytes": 524288000,
    "sha256": "abc123..."
  }
}
```

## Multi-OS Strategy

### Vision

CognitiveOS will support multiple Linux distributions as base images. Each distribution is maintained as a separate repository forked from `cognitiveos-alpine-distro`:

| Repository | Base OS | Status |
|-----------|---------|--------|
| `cognitiveos-alpine-distro` | Alpine Linux | Current (primary) |
| `cognitiveos-ubuntu-distro` | Ubuntu LTS | Planned |
| `cognitiveos-redhat-distro` | RHEL / Fedora | Planned |

### What Transfers Across Forks

The following are OS-agnostic and shared across all distro forks:

- **CGP format** and `cognitive.json` manifest schema
- **`cpm`** package manager (already supports `apk`, `npm`, `pip`, `cargo`, `go`, `git`)
- **All Go component repos** (`cognitiveosd`, `cli`, `inference`, `core-mcp-bridges`)
- **Overlay structure** (`/cognitiveos/`, `/etc/cognitiveos/`, `/usr/local/bin/`)
- **Partition layout** (boot, root, firmware, data)
- **Class model mapping** (titan, standard, gateway, edge, micro)
- **Docker release workflow pattern** (per-variant Dockerfiles, GHCR push)

### What Is Distro-Specific

Each fork owns its own:

| Component | Description | Example |
|-----------|-------------|---------|
| `packages.<class>-<arch>` files | OS-specific package names | `alpine-base` → `ubuntu-minimal` |
| `bootstrap-*.sh` script | Package installation script | `apk add` → `apt-get install` |
| Runtime Dockerfile stage | Base image selection | `FROM alpine:edge` → `FROM ubuntu:24.04` |
| Image builder | OS-specific mkimage tooling | Alpine mkimage → debootstrap → live-build |
| Init system | Service management | OpenRC (Alpine) → systemd (Ubuntu) |

### What Does NOT Transfer

Alpine-specific build scripts stay in `cognitiveos-alpine-distro` only:

- `scripts/build-image.sh` (uses Alpine's `mkimage.sh`)
- `scripts/genapkovl-cognitiveos.sh` (Alpine overlay format)
- `scripts/mkimg.cognitiveos.sh` (Alpine mkimage profile)

### Package File Convention

The `packages.<class>-<arch>` naming convention is preserved across all forks. Only the package names inside change:

```
# Alpine (cognitiveos-alpine-distro)
packages.standard-x86_64:
  alpine-base, busybox, openrc, linux-lts, alsa-utils, ...

# Ubuntu (cognitiveos-ubuntu-distro) — future
packages.standard-x86_64:
  ubuntu-minimal, systemd, linux-generic, alsa-utils, ...

# Red Hat (cognitiveos-redhat-distro) — future
packages.standard-x86_64:
  redhat-release, systemd, kernel, alsa-utils, ...
```

### cpm Manager Support

`cpm/internal/manager/manager.go` already dispatches to the correct system package manager based on the `manager` field in `hardware_dependencies.packages`:

| Manager | Command | Distro |
|---------|---------|--------|
| `apk` | `apk add` | Alpine |
| `apt` | `apt-get install` | Ubuntu/Debian |
| `dnf` | `dnf install` | RHEL/Fedora |
| `npm`, `pip`, `cargo`, `go`, `git` | Language-specific | Cross-distro |
