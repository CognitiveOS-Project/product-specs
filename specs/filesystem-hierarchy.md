# CognitiveOS Filesystem Hierarchy

Version: 1.0.0-draft

## Overview

The CognitiveOS filesystem is organized around two principles:

1. **The AI owns the filesystem.** There is no user home directory, no `/home/`, no user-accessible paths. All storage belongs to the system.
2. **Partition boundaries enforce safety.** The Raw Model firmware lives on a read-only partition. The Wide Model and patches live on writable storage. The Raw Model cannot be modified from software.

## Directory Tree

```
/cognitiveos/
├── models/
│   ├── raw/                    # Raw Model (read-only, firmware)
│   │   └── raw-model.gguf      # Compiled firmware model
│   └── wide/                   # Global base models (writable)
├── patches/                    # Installed .cgp patches (writable)
│   ├── <package-name>/         # One directory per installed patch
│   │   ├── cognitive.json     # Manifest (copied from archive)
│   │   ├── prompts/
│   │   │   └── system.md
│   │   ├── weights/            # Model weights for this patch
│   │   │   └── <model>.gguf
│   │   └── tools/
│   │       └── mcp-server-*
│   └── <another-package>/
├── run/                        # Runtime state (tmpfs, volatile)
│   ├── daemon.sock             # cognitiveosd Unix socket
│   ├── daemon.pid              # PID file
│   └── mcp/                    # Per-server sockets/PIDs
│       ├── display-mcp.sock
│       ├── audio-mcp.sock
│       └── ...
├── data/                       # Wide Model persistent state (writable)
│   ├── decisions/              # Decision log (prediction-error records)
│   │   └── <year>-<month>.jsonl
│   ├── memory/                 # Vector indices, knowledge graph
│   │   ├── index.db
│   │   └── embeddings/
│   ├── cache/                  # Temporary data (safe to delete)
│   │   ├── downloads/          # Partial .cgp downloads
│   │   └── render/             # Cached framebuffer renders
│   └── state.json              # Current Wide Model state snapshot
├── audit/                      # Resource audit snapshots (writable)
│   ├── current.json            # Latest audit result
│   └── history/                # Historical audit records
│       └── <timestamp>.json
└── logs/                       # System logs (writable, circular)
    ├── cognitiveosd.log
    ├── cpm.log
    ├── inference.log
    └── bridges/
        ├── display-mcp.log
        ├── audio-mcp.log
        └── ...

/etc/cognitiveos/
├── config.toml                 # Base system configuration
└── registries.toml             # Registry sources for cpm
```

## Partition Layout

| Partition | Mount Point | Size | Type | Description |
|-----------|-------------|------|------|-------------|
| `boot` | `/boot` | 256 MB | vfat | Kernel, initramfs, bootloader |
| `root` | `/` | 2-4 GB | ext4/squashfs | Alpine root filesystem (squashfs = read-only; ext4 = writable) |
| `cognitiveos-firmware` | `/cognitiveos/models/raw` | 512 MB | ext4 (read-only) | Raw Model firmware. Mounted ro. Only writable via `reset` code or physical firmware update. |
| `cognitiveos-data` | `/cognitiveos/` (data subdirs) | Rest of disk | ext4 | All writable system data. Created on first boot. |

### Partition Layout for Embedded Devices

For devices with limited flash (MCUs, smart home), the same logical layout compresses:

| Device storage | Partitions |
|---------------|------------|
| < 64 MB flash | Root + cognitiveos-firmware only. Wide Model is remote-only. No patch storage. |
| 64 MB - 512 MB flash | Root + cognitiveos-firmware + small cognitiveos-data (for essential patches only) |
| 512 MB+ | Full layout as above |

## Mount Points and Permissions

| Path | Mount | Writable by | Persistence |
|------|-------|-------------|-------------|
| `/` | Root partition | OS only (squashfs) or read-only | Survives reset |
| `/cognitiveos/models/raw/` | Firmware partition | Physical firmware update only | Always persists |
| `/cognitiveos/models/wide/` | Data partition | inference, cpm | Survives idle, wiped on reset |
| `/cognitiveos/patches/` | Data partition | cpm | Survives idle, wiped on reset |
| `/cognitiveos/run/` | tmpfs | cognitiveosd, MCP servers | Volatile (lost on shutdown) |
| `/cognitiveos/data/` | Data partition | Wide Model, cognitiveosd | Survives idle, wiped on reset |
| `/cognitiveos/audit/` | Data partition | cognitiveosd | Survives idle, wiped on reset |
| `/cognitiveos/logs/` | Data partition | All components | Rotated, survives idle, wiped on reset |
| `/etc/cognitiveos/` | Root partition | Physical access only | Always persists |

## What Survives Each Operation

| Operation | `/cognitiveos/models/raw/` | `/cognitiveos/models/wide/` | `/cognitiveos/patches/` | `/cognitiveos/data/` | `/cognitiveos/run/` |
|-----------|---------------------------|---------------------------|------------------------|---------------------|---------------------|
| Wake/Idle cycle | ✅ | ✅ | ✅ | ✅ | ❌ (flushed) |
| System update (Wide Model swap) | ✅ | Updated | ✅ | ✅ | ❌ (flushed) |
| Security shutdown | ✅ | ✅ | ✅ | ✅ | ❌ (flushed) |
| Reset code | ✅ | ❌ (wiped) | ❌ (wiped) | ❌ (wiped) | ❌ (flushed) |
| Physical firmware flash | Updated | ❌ (wiped) | ❌ (wiped) | ❌ (wiped) | ❌ (flushed) |

## File Naming Conventions

- Log files: `<component>.log` with size-based rotation (default: 5 × 10 MB)
- Audit snapshots: ISO 8601 timestamp (`2026-06-23T14:30:00Z.json`)
- MCP sockets: `<server-name>.sock`
- PID files: `<daemon-name>.pid`
- Model files: `.gguf` format
- Patch archives: `.cgp` extension (tar.gz)

## Minimum Storage Requirements

| Device class | Minimum storage | Notes |
|-------------|-----------------|-------|
| MCU / embedded | 4 MB flash | Raw Model only, no data partition |
| Wearable | 256 MB | Raw Model + small cache, remote Wide Model |
| Smartphone | 8 GB | Full layout with local Wide Model |
| Raspberry Pi | 4 GB SD | Full layout |
| PC / Server | 16 GB | Full layout with multiple Wide Model versions |
