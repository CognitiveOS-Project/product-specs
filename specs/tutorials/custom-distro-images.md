# Building Custom CognitiveOS Distro Images

This tutorial covers building bootable CognitiveOS images from source — ISOs for desktops and VMs, SD card images for Raspberry Pi, Docker containers for development, and portable tarballs for offline builds. You will learn to customize packages, overlay files, and models for your target hardware.

## Overview

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  FETCH   │───►│ COMPILE  │───►│ OVERLAY  │───►│  IMAGE   │───►│   SIGN   │
│          │    │          │    │          │    │          │    │          │
│ clone    │    │ make     │    │ copy     │    │ mkimage  │    │ sha256   │
│ repos    │    │ binaries │    │ + models │    │ (ISO/RPi)│    │ + GPG    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**Prerequisites:**
- Alpine Linux host with `apk` and `alpine-conf` (for native builds)
- OR Docker (for containerized builds)
- Go 1.24+ (for compiling Go components)
- Git

## Quick Start

```bash
# Clone the distro builder
gh repo clone CognitiveOS-Project/cognitiveos-alpine-distro
cd cognitiveos-alpine-distro

# Build x86_64 ISO (standard class)
make iso

# Test in QEMU
qemu-system-x86_64 -cdrom output/cognitiveos-*.iso -m 4G -enable-kvm
```

Output goes to `output/`. Run `make clean` to remove build artifacts.

## Step 1: Choose a Class

The class defines your target hardware tier. Each class determines which Alpine packages are installed, which models are baked in, and which architectures are supported.

| Class | RAM | Storage | Arch | Raw Model | Wide Model | Use Case |
|-------|-----|---------|------|-----------|------------|----------|
| **standard** | >=8 GB | >=16 GB | x86_64 | 1.5B GGUF | 8B Gemma 4 (baked) | Desktop/PC, VM testing |
| **gateway** | >=4 GB | >=8 GB | x86_64 | Compiled-in (no GGUF) | Remote on first boot | Network relay/proxy node |
| **edge** | >=2 GB | >=4 GB | aarch64, armv7 | 0.5B GGUF | Tiny (auto-selected) | Raspberry Pi 3/4/5 |
| **micro** | >=512 MB | >=1 GB | armv7 | Compiled-in (no GGUF) | Remote-only (thin client) | Raspberry Pi Zero 2 W |
| **titan** | >=16 GB | >=64 GB | aarch64 | 235B Qwen GGUF | None (remote/.cgp) | Full AI server with GPU |

```bash
# Quick class selection
make iso                  # standard class, x86_64
make rpi                  # edge class, aarch64
make gateway              # gateway class, x86_64
make micro                # micro class, armv7
make titan                # titan class, aarch64 (requires self-hosted runner)
```

Or build any class/arch combination directly:

```bash
make release-variant ARCH=x86_64 CLASS=gateway
make release-variant ARCH=aarch64 CLASS=edge
make release-variant ARCH=armv7 CLASS=micro
```

### What Each Class Means

**standard** — The default desktop/PC experience. Bakes in both a Raw Model (1.5B for prompt classification) and a Wide Model (8B Gemma 4 for general inference). Includes audio (ALSA), display (mpv), WiFi (wpa_supplicant), and GPIO (libgpiod).

**gateway** — A network relay node. No GGUF models baked in — the Raw Model is entirely compiled-in (deterministic rules only). The Wide Model is fetched remotely on first boot. Includes network tools (nmap, curl, iputils) but no audio/display.

**edge** — Raspberry Pi / ARM SBC class. Small Raw Model (0.5B) for prompt classification. Tiny Wide Model auto-selected. Runs on Pi 3/4/5 with linux-rpi kernel.

**micro** — Ultra-thin embedded client (RPi Zero 2 W). No GGUF models, compiled-in rules only. Minimal packages (9 total — no audio, no display, no squashfs tools). Thin client that talks to a remote Wide Model.

**titan** — Full-blown AI server with GPU. Massive 235B Raw Model GGUF. No local Wide Model — all inference is remote. Requires >=16 GB RAM, >=4 GB VRAM, >=64 GB storage.

## Step 2: Build the Image

### Build an ISO (x86_64)

```bash
make iso
```

This runs the full pipeline:
1. `build-binaries.sh` — clones repos, compiles all Go components
2. `build-overlay.sh` — assembles the root filesystem overlay
3. `build-image.sh` — generates the ISO using Alpine's `mkimage`

Output: `output/cognitiveos-<version>-standard-x86_64.iso`

### Build a Raspberry Pi Image (aarch64)

```bash
make rpi
```

Output: `output/cognitiveos-<version>-edge-aarch64.img`

For other ARM variants:
```bash
make release-variant ARCH=armv7 CLASS=edge     # ARMv7 edge
make release-variant ARCH=armv7 CLASS=micro    # ARMv7 micro (RPi Zero)
make release-variant ARCH=aarch64 CLASS=titan  # ARM64 titan (needs GPU runner)
```

### Build a Docker Image

```bash
# Dev image (mock backend, no real inference)
make docker.dev

# Production image (real inference, with models)
make docker-release-arch ARCH=x86_64 CLASS=standard

# Push to GHCR
make docker-push-arch ARCH=x86_64 CLASS=standard
```

### Build Everything

```bash
make all    # iso + rpi + checksums + sign
```

## Step 3: Customize Packages

Package lists are files named `packages.<class>-<arch>` in the repo root. Each file contains one Alpine package name per line.

### View the Default Package List

```bash
cat packages.standard-x86_64
```

Output:
```
alpine-base
busybox
openrc
linux-lts
kbd
dosfstools
e2fsprogs
squashfs-tools
acpid
alsa-utils
alsa-lib
iw
wpa_supplicant
dhcpcd
libgpiod
mpv
```

### Create a Custom Package List

Copy an existing list and modify it:

```bash
cp packages.standard-x86_64 packages.standard-x86_64-custom
```

Add packages (one per line):

```
alpine-base
busybox
openrc
linux-lts
kbd
dosfstools
e2fsprogs
squashfs-tools
acpid
alsa-utils
alsa-lib
iw
wpa_supplicant
dhcpcd
libgpiod
mpv
# Custom additions:
nmap
curl
python3
nodejs
```

Build with your custom list:

```bash
make release-variant ARCH=x86_64 CLASS=standard PACKAGES_FILE=packages.standard-x86_64-custom
```

### Variant Package Matrix

| Package | standard | gateway | titan | edge | micro |
|---------|:---:|:---:|:---:|:---:|:---:|
| alpine-base | Yes | Yes | Yes | Yes | Yes |
| linux-lts | Yes | Yes | — | — | — |
| linux-rpi | — | — | Yes | Yes | Yes |
| alsa-utils | Yes | — | Yes | Yes | — |
| mpv | Yes | — | — | — | — |
| iw | Yes | Yes | Yes | Yes | — |
| wpa_supplicant | Yes | Yes | Yes | Yes | — |
| libgpiod | Yes | Yes | Yes | Yes | — |
| kbd | Yes | — | Yes | Yes | Yes |
| nmap | — | Yes | — | — | — |
| curl | — | Yes | — | — | — |

## Step 4: Customize the Overlay

The `overlay/` directory mirrors the target root filesystem. Everything here is merged into the Alpine root at image build time.

### Overlay Structure

```
overlay/
├── etc/
│   ├── hostname                      # "cognitiveos"
│   ├── inittab                       # Boot sequence (coginit as PID 1)
│   ├── cognitiveos/
│   │   ├── config.toml               # System configuration
│   │   └── registries.toml           # Registry URLs
│   └── init.d/
│       ├── cpm-boot-deps             # OpenRC: boot-stage dependencies
│       └── cpm-runtime-deps          # OpenRC: runtime dependencies
├── cognitiveos/
│   ├── models/raw/                   # Raw Model GGUF goes here
│   ├── models/wide/active/           # Wide Model GGUF goes here
│   ├── run/                          # tmpfs at runtime (daemon.sock, PID files)
│   ├── patches/                      # Installed .cgp packages
│   └── data/                         # Writable data (logs, cache, memory)
├── usr/local/bin/
│   ├── coginit                       # PID 1 supervisor
│   ├── cognitiveosd                  # System daemon
│   ├── cognitiveos-cli               # TUI
│   ├── coginfer                      # Inference server
│   ├── cograw                        # Raw model server
│   └── cpm                           # Package manager
└── usr/local/lib/cognitiveos/bridges/
    ├── audio                         # ALSA audio bridge
    ├── display                       # Framebuffer display bridge
    ├── gpio                          # GPIO control bridge
    ├── network                       # WiFi network bridge
    ├── package                       # Package management bridge
    └── serial                        # Serial UART bridge
```

### Customize System Config

Edit `overlay/etc/cognitiveos/config.toml`:

```toml
[system]
hostname = "my-cognitiveos"        # Custom hostname
timezone = "America/New_York"      # Custom timezone
autologin = true

[inference]
idle_timeout_seconds = 600         # Keep models loaded longer
backend = "cgo"                    # "cgo" for real, "mock" for testing
endpoint = "http://127.0.0.1:11434"

[raw_model]
model = "/cognitiveos/models/raw/raw-model.gguf"

[daemon]
socket_path = "/cognitiveos/run/daemon.sock"
audit_interval_seconds = 60
mcp_bin_dir = "/usr/local/lib/cognitiveos/bridges"

[network]
default_interface = "wlan0"
auto_connect = true
wpa_supplicant_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"

[audio]
default_sink = "default"
default_source = "default"
volume = 80                        # Custom default volume

[display]
framebuffer_device = "/dev/fb0"
media_player = "mpv"
image_viewer = "mpv"
```

### Customize the Boot Sequence

Edit `overlay/etc/inittab`:

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

- `tty1` and `ttyS0` both spawn `coginit --bare-metal` (the unified PID 1 supervisor)
- `tty2` is a debug login shell (accessible via Ctrl+Alt+F2)
- `::wait:` blocks until OpenRC finishes booting system services

### Add Custom Configuration Files

Place any config files in the appropriate overlay path:

```bash
# Custom wpa_supplicant config
cp my-wpa.conf overlay/etc/wpa_supplicant/wpa_supplicant.conf

# Custom MOTD
echo "Welcome to my CognitiveOS build" > overlay/etc/motd

# Custom sysctl settings
mkdir -p overlay/etc/sysctl.d
echo "net.core.somaxconn = 1024" > overlay/etc/sysctl.d/99-custom.conf
```

## Step 5: Add Custom MCP Bridges

MCP bridges are executables placed in `overlay/usr/local/lib/cognitiveos/bridges/`. The daemon scans this directory at startup and spawns each executable as an MCP server.

### Place a Bridge Binary

```bash
# Build your bridge
cd my-bridge-repo && make build

# Copy to the overlay
cp build/bin/my-bridge ../cognitiveos-alpine-distro/overlay/usr/local/lib/cognitiveos/bridges/
chmod +x ../cognitiveos-alpine-distro/overlay/usr/local/lib/cognitiveos/bridges/my-bridge
```

### How Bridges Are Discovered

The daemon reads `mcp_bin_dir` from `config.toml`:

```toml
[daemon]
mcp_bin_dir = "/usr/local/lib/cognitiveos/bridges"
```

Every executable in that directory is spawned as an MCP server process. Each bridge gets its own Unix socket under `/cognitiveos/run/mcp/<name>.sock`.

### Add System Dependencies for Your Bridge

If your bridge needs Alpine packages, add them to the package list:

```bash
# Add Python for a Python-based bridge
echo "python3" >> packages.standard-x86_64

# Add Node.js for a JS-based bridge
echo "nodejs" >> packages.standard-x86_64
```

## Step 6: Bake in Models

Models are optionally downloaded during the overlay build step. Control this with the `DOWNLOAD_MODELS` environment variable.

### Default Behavior (No Models)

```bash
make iso
# Output: SKIP: model download disabled (set DOWNLOAD_MODELS=1 to enable)
```

### Download Models During Build

```bash
DOWNLOAD_MODELS=1 make iso
```

This downloads the default models for your class:

| Class | Raw Model | Wide Model |
|-------|-----------|------------|
| standard | `qwen2.5-1.5b-instruct-gguf` | `gemma-4-8b-instruct-gguf` |
| edge | `qwen2.5-0.5b-instruct-gguf` | `tiny-llm-gguf` |
| gateway | (none — compiled-in) | (none — remote) |
| micro | (none — compiled-in) | (none — remote) |
| titan | `qwen2.5-235b-instruct-gguf` | (none — remote) |

Models are placed at:
- Raw Model: `overlay/cognitiveos/models/raw/raw-model.gguf` (permissions 0400)
- Wide Model: `overlay/cognitiveos/models/wide/active/model.gguf`

### Manual Model Placement

If you prefer to place models manually (e.g., from a local file):

```bash
# Place the model before building
cp my-model.gguf overlay/cognitiveos/models/wide/active/model.gguf
chmod 0400 overlay/cognitiveos/models/wide/active/model.gguf

# Build without downloading
make iso
```

### Model Download Requires Network

The download uses `cpm download-weights` which queries the HuggingFace API. If you're building offline, skip the download and place models manually.

## Step 7: Test in QEMU

### Test an ISO

```bash
make iso

# Boot in QEMU with KVM acceleration
qemu-system-x86_64 \
  -cdrom output/cognitiveos-*-standard-x86_64.iso \
  -m 4G \
  -enable-kvm \
  -nographic

# Without KVM (slower)
qemu-system-x86_64 \
  -cdrom output/cognitiveos-*-standard-x86_64.iso \
  -m 4G \
  -nographic
```

The system boots through:
1. Alpine Linux kernel
2. OpenRC init (sysinit → boot → default)
3. `coginit --bare-metal` on tty1 (PID 1 supervisor)
4. CPM installs boot-stage dependencies
5. `cograw` starts (Raw Model server)
6. `coginfer` starts (Wide Model inference)
7. `cognitiveosd` starts (system daemon)
8. `cognitiveos-cli` launches (TUI)

### Test an RPi Image

```bash
make rpi

# Test with QEMU aarch64 emulation
qemu-system-aarch64 \
  -M virt \
  -cpu cortex-a72 \
  -m 4G \
  -bios /usr/share/qemu/edk2-aarch64-code.fd \
  -drive if=none,file=output/cognitiveos-*-edge-aarch64.img,id=hd0 \
  -device virtio-blk-device,drive=hd0 \
  -nographic
```

Note: aarch64 QEMU emulation is significantly slower than native. Expect longer boot times.

### Test with Docker (Fastest)

```bash
# Dev image — no models, mock backend
make docker.dev
docker run -it cognitiveos-dev

# Production image — with models
make docker-release-arch ARCH=x86_64 CLASS=standard
docker run -it cognitiveos:standard-x86_64
```

The Docker image is the fastest way to test since it skips the mkimage step.

## Step 8: The Distro Tarball

The tarball is a portable, self-contained distribution package. Build the tarball on any machine, then produce the final bootable image on an Alpine host.

### Build the Tarball

```bash
make distro-tarball
```

Output: `output/cognitiveos-alpine-distro-<version>-<class>-<arch>.tar.gz`

### What's Inside

```
cognitiveos-alpine-distro-<version>/
├── rootfs/              # Complete overlay (all files from overlay/)
├── packages.txt         # Package list for this variant
├── VERSION              # Build metadata
└── scripts/
    ├── build-image.sh   # Image builder script
    └── sign.sh          # Checksum/signing script
```

### Use the Tarball on Another Machine

```bash
# Copy to an Alpine host
scp output/cognitiveos-alpine-distro-*.tar.gz alpine-host:~/

# Extract and build
ssh alpine-host
tar xzf cognitiveos-alpine-distro-*.tar.gz
cd cognitiveos-alpine-distro-*
sudo ./scripts/build-image.sh --profile x86_64 --class standard --version v1.0.0
```

This decouples compilation from image generation — useful for air-gapped builds or when you need a specific Alpine version for mkimage.

## Step 9: Cross-Compilation

### CGO_ENABLED Settings

| Setting | Use Case | Inference |
|---------|----------|-----------|
| `CGO_ENABLED=1` (default) | Production builds | Real llama.cpp via CGo |
| `CGO_ENABLED=0` | Dev/test builds | Mock backend |

```bash
# Production build (real inference)
CGO_ENABLED=1 make iso

# Dev build (mock backend, faster)
CGO_ENABLED=0 make iso
```

### Cross-Compilation with QEMU

ARM images built on x86_64 use QEMU user-mode emulation:

```bash
# This works on x86_64 — builds ARM image via QEMU
make rpi  # aarch64 via QEMU
make release-variant ARCH=armv7 CLASS=edge  # armv7 via QEMU
```

Build times:
- x86_64 native: ~5-10 minutes
- aarch64 via QEMU: ~15-30 minutes
- armv7 via QEMU: ~40-60 minutes

CI timeout is set to 180 minutes to accommodate slow cross-compilation.

### Docker Buildx for Multi-Arch

```bash
# Build for a specific platform
docker buildx build --platform linux/arm64 \
  --build-arg CGO_ENABLED=1 \
  -f docker/release/edge-aarch64/Dockerfile \
  -t cognitiveos:edge-aarch64 \
  --load .
```

## Step 10: Docker Development Workflow

### Interactive Build Shell

```bash
make shell
```

This builds the `cognitiveos-builder` container and opens an interactive shell with all sibling repos mounted:

```bash
docker run --rm -it \
    -v "$(pwd)/../cpm:/src/cpm" \
    -v "$(pwd)/../cognitiveosd:/src/cognitiveosd" \
    -v "$(pwd)/../cli:/src/cli" \
    -v "$(pwd)/../inference:/src/inference" \
    -v "$(pwd)/../core-mcp-bridges:/src/core-mcp-bridges" \
    -w /workspace \
    cognitiveos-builder /bin/sh
```

Inside the container:
```bash
# Build all binaries
make docker.build

# Run tests
make -C /src/cpm test
make -C /src/cognitiveosd test
```

### Build the Builder Image

```bash
make docker
```

The builder image (`Dockerfile.build`) is a `golang:1.26-alpine` container with git, cmake, build-base, and make. It compiles all CognitiveOS components and assembles the overlay.

### Build a Dev Runtime Image

```bash
make docker.dev
```

The dev image uses `CGO_ENABLED=0` (mock backend). Two-stage build:
1. Builder stage: compiles all Go binaries
2. Runtime stage: Alpine with standard packages + built overlay

Entry point: `/usr/local/bin/coginit`

## Makefile Reference

| Target | Description |
|--------|-------------|
| `make all` | Build ISO + RPi + checksums + sign |
| `make iso` | Build x86_64 standard ISO |
| `make rpi` | Build aarch64 edge RPi image |
| `make gateway` | Build gateway class x86_64 image |
| `make micro` | Build micro class armv7 image |
| `make titan` | Build titan class aarch64 image |
| `make release-variant ARCH=<arch> CLASS=<class>` | Build any class/arch combination |
| `make docker` | Build the builder image |
| `make docker.dev` | Build dev runtime image (mock backend) |
| `make docker-release-arch ARCH=<arch> CLASS=<class>` | Build production Docker image |
| `make docker-push-arch ARCH=<arch> CLASS=<class>` | Push Docker image to GHCR |
| `make shell` | Interactive shell in builder container |
| `make install-local` | Build binaries + assemble overlay (no image) |
| `make distro-tarball` | Build portable tarball |
| `make release` | Alias for `distro-tarball` |
| `make checksums` | Generate SHA-256 checksums |
| `make sign` | Generate checksums + GPG signatures |
| `make clean` | Remove build/, output/, ISOs, images |
| `make distclean` | Clean + remove cache/, work/ |
| `make deps` | Check for docker and make |
| `make verify-repos` | Clone repos fresh and verify builds |
| `make publish-cgp` | Pack + publish .cgp packages to registry |
| `make publish-all` | Publish all component .cgp packages |

## Troubleshooting

### `build-binaries.sh` fails to clone a repo

Ensure you have network access and the repo exists:

```bash
# Test SSH access
ssh -T git@github.com

# Test HTTPS access
git ls-remote https://github.com/CognitiveOS-Project/cpm.git
```

If behind a proxy, configure git:
```bash
git config --global http.proxy http://proxy:port
git config --global https.proxy http://proxy:port
```

### `mkimage` fails

The image generator requires Alpine Linux. If you're on a non-Alpine host, the build falls back to Docker automatically:

```bash
# If native mkimage fails, ensure Docker is running
docker info
```

### ARM build is very slow

Cross-compilation via QEMU user-mode is expected to be slow:
- armv7: ~40-60 minutes (CI timeout: 180 minutes)
- aarch64: ~15-30 minutes

For faster ARM builds, use a native ARM machine or a self-hosted runner.

### Model download fails

If `DOWNLOAD_MODELS=1` fails:
1. Check network connectivity
2. Ensure `cpm` binary is built and in `build/bin/`
3. Check HuggingFace API availability
4. Fall back to manual model placement (see Step 6)

### ISO boots but no TUI appears

The TUI launches after `coginit` starts all services. Check the boot sequence:
1. OpenRC must complete `::wait:/sbin/openrc default`
2. `coginit --bare-metal` must start on tty1
3. If using serial console: check `ttyS0`

For debugging, switch to tty2 (Ctrl+Alt+F2) for a login shell.

### Docker image has no inference

The dev image (`docker.dev`) uses `CGO_ENABLED=0` with a mock backend. This is by design for development. For real inference, use a production Docker image:

```bash
make docker-release-arch ARCH=x86_64 CLASS=standard
```

## Related Tutorials

- [CGP Lifecycle](cgp-lifecycle.md) — package lifecycle (create → publish → install)
- [Sandboxed CGP Development](sandboxed-cgp-development.md) — local CGP development and testing
- [Download Weights](download-weights.md) — fetching GGUF models from HuggingFace
- [CPM Workflow](cpm-workflow.md) — CPM command reference
- [AI Rover](ai-rover.md) — example: flashing an RPi image for an AI robot
- [Hardware OEM](hardware-oem.md) — example: factory image builds for OEM hardware
