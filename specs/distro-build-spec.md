# CognitiveOS Distribution Build Specification

Version: 1.0.0-draft

## Overview

`cognitiveos-distro` produces bootable system images based on Alpine Linux. The build process compiles all CognitiveOS components, assembles them into an Alpine overlay, and generates platform-specific images.

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
| Base OS | Alpine Linux (edge or latest stable) |
| Kernel | linux-lts (x86_64), linux-rpi (aarch64) |
| Init system | OpenRC (Alpine default) |
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

### Mandatory Packages

```
# Base system
alpine-base
busybox
openrc
linux-lts (or linux-rpi)

# Hardware support
alsa-utils
alsa-lib
iw
wpa_supplicant
dhcpcd
libgpiod
gpiod-tools
kbd

# Media (framebuffer)
fbv
mpv
fbi

# Filesystem
dosfstools
e2fsprogs
squashfs-tools
```

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
| Raw Model | (model file) | `raw-model.gguf` | `/cognitiveos/models/raw/` |
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
│   │       └── raw-model.gguf     # Raw Model binary
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
- Go 1.22+
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

```bash
for repo in cpm cognitiveosd cli inference core-mcp-bridges; do
  cd $repo
  CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o ../build/bin/ ./cmd/...
  cd ..
done
```

Binaries are statically linked (CGO_ENABLED=0) for maximum portability across architectures.

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

cp build/raw-model.gguf        overlay/cognitiveos/models/raw/
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
  --packages "$(cat packages.x86_64)" \
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
  --packages "$(cat packages.aarch64)" \
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

## Build Scripts

The `cognitiveos-distro` repo provides:

```
cognitiveos-distro/
├── Makefile              # Top-level build automation
├── packages.x86_64       # Package list for x86_64
├── packages.aarch64      # Package list for ARM64
├── packages.armv7        # Package list for ARMv7
├── overlay/              # Filesystem overlay (above)
├── configs/
│   ├── inittab
│   ├── config.toml
│   └── registries.toml
├── scripts/
│   ├── build-binaries.sh   # Step 2: compile all Go binaries
│   ├── build-overlay.sh    # Step 3: assemble overlay
│   ├── build-iso.sh        # Step 4: x86_64 ISO
│   ├── build-rpi.sh        # Step 4: RPi SD card
│   └── sign.sh             # Step 5: checksums + GPG
├── docker/
│   └── Dockerfile.build    # Cross-compilation container
└── README.md
```

### Makefile Targets

```makefile
all: iso rpi

iso:            # Build x86_64 ISO
rpi:            # Build Raspberry Pi SD card image
clean:          # Remove build artifacts
distclean:      # Remove build artifacts + downloaded deps
docker:         # Build the cross-compilation Docker image
shell:          # Start an interactive shell in the build container
checksums:      # Generate SHA-256 checksums for all images
sign:           # GPG-sign all images
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
   d. Loads Raw Model from /cognitiveos/models/raw/raw-model.gguf
   e. Scans /cognitiveos/patches/ for installed patches
   f. Reads /cognitiveos/models/wide/active/ for Wide Model
   g. Spawns MCP servers for installed patches
   h. Reports "CognitiveOS ready" to CLI
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

## Versioning

Distribution images are versioned as:

```
cognitiveos-<version>-<target>.iso
cognitiveos-<version>-<target>.img
```

Where `<version>` follows SemVer (e.g., `v0.1.0`) and `<target>` is the platform (`x86_64`, `rpi4`, `rpi-zero`).

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
