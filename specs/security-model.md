# CognitiveOS Security Model

Version: 1.1.0-draft

## Overview

CognitiveOS has a unique security posture: there are no user accounts, no permissions, and no multi-user isolation. The AI is the sole actor on the system. Security focuses on:

1. **Protecting the Raw Model from the Wide Model** (firmware integrity)
2. **Containing the Wide Model and its MCP servers** (process isolation)
3. **Verifying software integrity** (supply chain)
4. **Hardwired human overrides** (system codes)

## Trust Boundary

```
┌─────────────────────────────────────────┐
│            TRUSTED ZONE                  │
│  Raw Model (firmware, read-only)         │
│  System Codes (embedded in firmware)     │
│  Hardware audit logic                    │
│  /cognitiveos/models/raw/ (ro mount)     │
│  /etc/cognitiveos/ (ro mount)            │
│  /cognitiveos/firmware/ (ro partition)   │
│  Registry SSH public keys (S3)           │
│  Registry notary checksums (S3)          │
└──────────┬──────────────────────────────┘
           │ Unix socket (restricted)
           │ VERIFIED BY: checksum at load
           │ ENFORCED BY: cgroups + seccomp
           ▼
┌─────────────────────────────────────────┐
│         UNTRUSTED ZONE                    │
│  Wide Model (operational brain)          │
│  MCP Servers (installed via .cgp)        │
│  /cognitiveos/models/wide/ (writable)    │
│  /cognitiveos/patches/ (writable)         │
│  /cognitiveos/data/ (writable)            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│       SUPPLY CHAIN PERIMETER             │
│  Registry Server (notary proxy)          │
│    - Stores SSH public keys              │
│    - Stores manifest + checksums         │
│    - Verifies publisher signatures       │
│    - Re-verifies remote assets           │
│  Publisher SSH private keys (off-device) │
│  S3-compatible store (R2 default)        │
└─────────────────────────────────────────┘
```

### What is Trusted

- **Raw Model firmware binary** — compiled into the read-only firmware partition. Cannot be modified by software. Only physical firmware update (e.g., JTAG, SD card reflash) can change it.
- **System codes** — embedded in the Raw Model at compile time. Not stored in any filesystem file.
- **Kernel and initramfs** — from the Alpine root partition (squashfs, read-only).
- **Daemon socket** — root-owned, mode 0700, only root processes can connect.

### What is Untrusted

- **Wide Model** — loaded from a writable partition, may have been downloaded from a registry. Can contain bugs or adversarial prompts.
- **MCP servers** — arbitrary binaries installed via .cgp patches. Can be from any author.
- **System configuration** — `/etc/cognitiveos/config.toml` (if on writable root) could be tampered with.

## Raw Model Enforcements

### System Code Validation

The Raw Model holds the five system codes in a compiled-in lookup table. Codes are never written to the filesystem. The validation flow:

```
Human enters code → cli sends system_code to daemon
  → daemon forwards to Raw Model (in-memory, isolated process)
  → Raw Model compares against compiled-in codes
  → If match: Raw Model executes the action directly (no trust delegation)
  → If no match: Raw Model returns error, logs the attempt
```

- `RESET` and `SECURITY` codes require physical button combos (cannot be triggered via voice or software)
- Failed code attempts are logged with timestamp and origin
- After 5 failed attempts in 10 minutes: audio/visual alert + 5-minute cooldown

### Hardware Audit Enforcement

Before any Wide Model load:
1. Raw Model reads `/cognitiveos/audit/current.json` (written by cognitiveosd)
2. Raw Model verifies the numbers independently by reading `/proc/meminfo`, `statfs()`, and device nodes
3. If the audit shows insufficient resources, Raw Model blocks the load
4. The Wide Model cannot disable, fake, or bypass the audit — it runs in a separate process with no access to the audit logic

## Process Isolation

Every MCP server and the Wide Model run in their own **cgroup** with limits enforced by the Raw Model.

### cgroup Configuration

| Resource | Default limit | Enforced by |
|----------|---------------|-------------|
| RAM (per MCP server) | 512 MB | cgroup memory.max |
| RAM (Wide Model) | As negotiated in audit | cgroup memory.max |
| CPU (per MCP server) | 25% of one core | cgroup cpu.max |
| Disk I/O (per MCP server) | 10 MB/s read, 5 MB/s write | cgroup io.max |
| Processes (per MCP server) | 16 | cgroup pids.max |

### seccomp Profile

All MCP servers and the Wide Model run under a default seccomp filter:

```c
// Denied syscalls (non-exhaustive list)
// - mount, umount, umount2     (no filesystem manipulation)
// - reboot, kexec_load          (no system restart)
// - init_module, finit_module   (no kernel module loading)
// - delete_module               (no kernel module unloading)
// - bpf                         (no BPF program loading)
// - iopl, ioperm                (no I/O port access)
// - ptrace                      (no process inspection)
// - swapon, swapoff             (no swap manipulation)
```

The seccomp profile is compiled into the Raw Model, not loaded from a file.

### Filesystem Isolation

Each MCP server is **chrooted** to its patch directory:

```
MCP server for "email-manager" thinks its root is:
  /cognitiveos/patches/email-manager/

Can access:
  /cognitiveos/patches/email-manager/  (its own directory, writable)
  /cognitiveos/run/daemon.sock          (daemon communication)
  /cognitiveos/logs/bridges/            (append-only log output)

Cannot access:
  /cognitiveos/models/                  (model files)
  /cognitiveos/data/                    (other patches' data)
  /cognitiveos/patches/*/               (other patches)
  /cognitiveos/audit/                   (audit records)
  /cognitiveos/run/*.sock              (other MCP servers' sockets)
  /dev/mem, /dev/kmem, /dev/port       (memory and I/O)
  /sys/kernel/                         (kernel configuration)
```

The daemon (`cognitiveosd`) does NOT run in a chroot — it needs full filesystem access to coordinate.

## Code Integrity

### Supply Chain Verification

Every `.cgp` patch published to the registry is authenticated via SSH key signature and stored with a SHA-256 checksum in S3. See [ADR-007](../adr/ADR-007-registry-server-architecture.md) and `registry-api.md` for the full protocol.

#### Publisher Authentication

```
Publish flow:
  1. Publisher registers SSH public key once (POST /v1/auth/register)
  2. Server stores public key in S3 at auth/keys/{fingerprint}.pub
  3. Publisher signs manifest SHA-256 hash with private key (SSHSIG protocol)
  4. Server loads public key from S3, verifies signature
  5. If valid → manifest + checksum stored in S3, publish accepted
  6. If invalid → 401 Unauthorized, publish rejected
```

Server stores only public keys — no secrets are transmitted or stored.

#### Download Verification

```
Download flow:
  1. cpm requests download → receives download_urls map from registry
  2. cpm resolves variant (os/arch) → 302 redirect to canonical URL
  3. cpm computes SHA-256 of downloaded file
  4. cpm compares computed checksum against registry-provided checksum
  5. If mismatch: abort, delete download, report integrity error
  6. If match: proceed with installation
```

#### Notary Check (Remote Verification)

Before installation, cpm can verify the remote asset against the registry's stored checksum:

```
Notary check flow:
  1. cpm sends GET /v1/notary/check?source=...&path=...&version=...
  2. Server loads manifest from S3, resolves variant download URL
  3. Server HEADs the download URL → checks ETag or computes SHA-256
  4. Server compares remote hash against stored hash
  5. Returns { verified: bool, stored_hash, remote_hash }
  6. cpm aborts installation if verified=false
```

This detects tampering at the download source (e.g., compromised GitHub release) even after the original publish was valid.

### Manifests are Verified

`cognitive.json` is validated against the published JSON Schema (`cognitive.schema.json`) before every install. Schema validation catches:
- Missing required fields
- Invalid field types
- Unknown fields (rejected)

### Runtime Verification

When cognitiveosd spawns an MCP server from a .cgp patch, it:
1. Reads the checksum from the installed `cognitive.json` (checksum of the .cgp archive at install time)
2. Computes SHA-256 of the MCP server binary
3. If mismatch: log warning, but proceed (the checksum covers the archive, not individual binaries — filesystem tampering would be detected here)

For ongoing integrity, cpm can invoke `GET /v1/notary/check` at any time to re-verify the remote asset against the registry's stored checksum.

## Unlock Code Security

Unlock codes are used to authorize paid Wide Model downloads. The security model for this flow:

### Code Generation

1. Registry generates an unlock code as a cryptographically random token
2. The code is hashed (SHA-256 + salt) and stored in the registry database
3. The raw code is delivered to the purchaser

### Code Verification Flow

```
Raw Model firmware has an embedded public key for the registry.
The registry signs each unlock code with its private key.
The unlock code format is: <base32-random>.<base64-signature>

On verification:
  1. Raw Model splits the code into token and signature
  2. Raw Model verifies the signature against the embedded public key
  3. If signature valid: code is authentic (issued by the registry)
  4. Raw Model then checks if the code has been consumed (via registry API)
  5. If valid and unconsumed: Raw Model authorizes the download
```

### Code Constraints

- Codes are single-use (consumed after first successful verification)
- Codes expire after 30 days if not used
- Invalid codes are logged; 5 failed attempts triggers cooldown

## Incident Response

### Wide Model Misbehavior

The Raw Model continuously monitors the Wide Model via the daemon:

| Signal | Threshold | Action |
|--------|-----------|--------|
| CPU usage > 95% for 30s | Resource abuse | Throttle cgroup, then terminate if no improvement |
| RAM exceeds negotiated limit | Memory leak | Terminate, log, retry with smaller context |
| No response for 60s | Hang/crash | Send SIGTERM, wait 5s, SIGKILL, restart |
| Too many tool calls (>50/min) | Potential loop | Rate-limit, alert Raw Model |
| seccomp violation | Attempted escape | Immediate SIGKILL, log full details, no restart |

### Recovery Flow

1. Raw Model detects Wide Model is unresponsive or compromised
2. Raw Model sends SIGKILL to all Wide Model processes
3. Raw Model cleans up cgroups
4. Raw Model logs full incident details to `/cognitiveos/logs/cognitiveosd.log`
5. Raw Model restarts Wide Model with fallback parameters (reduced context, no GPU)
6. If fallback also fails: enter fail-safe mode (text-only, no MCP tools)

### Audit Logging

Every security-relevant event is logged:

| Event | Logged data |
|-------|-------------|
| System code attempt | Code type, origin, success/failure, timestamp |
| System code success | Code type, origin, timestamp, system state snapshot |
| seccomp violation | Process name, syscall number, arguments |
| cgroup OOM kill | Process name, memory usage at kill, limit |
| checksum mismatch | Expected hash, actual hash, file path |
| Unlock code attempt | Code prefix (first 4 chars), success/failure, IP |
| Wide Model crash | Signal, exit code, uptime, resource usage snapshot |

## Physical Security

### Firmware Partition Protection

| Device type | Protection method |
|-------------|-------------------|
| x86_64 | BIOS/UEFI write-protect jumper, or read-only flash region |
| Raspberry Pi | SD card write-protect switch, or overlay filesystem |
| Embedded (eMMC) | eFuse or OTP write-protect after first boot |
| Development | Kernel cmdline `ro` on firmware partition |

### Reset Code Hardware Requirement

The `RESET` system code **cannot** be triggered by software alone. It requires:
- Hold **Volume Up** + **Power** for 10 continuous seconds (smartphone/tablet)
- Hold **GPIO Pin 3** to **GND** during power-on (embedded/RPi)
- Physical jumper on `RESET_EN` header (development boards)

This ensures a compromised Wide Model cannot wipe itself and cover its tracks.

## Physical Backdoor Shell

CognitiveOS provides two independent physical backdoor shells for recovery and offline administration. Both are triggered by keyboard combos intercepted by the Raw Model at the kernel input layer — the AI cannot detect, access, or block them.

### Backdoor A — VT Switch

| Property | Value |
|----------|-------|
| Channel | `/dev/tty2` (dedicated Linux VT) |
| Trigger | Keyboard combo → Raw Model reads from `evdev` → `ioctl VT_ACTIVATE` |
| Return | `exit` or `Ctrl+D` switches back to the TUI VT |
| AI visibility | `ioctl VT_ACTIVATE` blocked by seccomp; AI communicates via sockets, not terminals |

### Backdoor B — Serial Console

| Property | Value |
|----------|-------|
| Channel | `/dev/ttyAMA0` (UART on GPIO 14/15) |
| Trigger | Same keyboard combo, or any serial keypress |
| Shell | Raw Model spawns `/bin/sh` or `getty` on the serial device |
| AI visibility | `/dev/ttyAMA0` blocked by seccomp and filesystem permissions |

### Trigger Combos

All combos trigger both backdoors simultaneously. Compiled into the Raw Model firmware (not modifiable by software):

1. `Ctrl+Alt+Backspace`
2. `Alt+PrintScreen+K`
3. `Ctrl+Alt+Del` / serial break
4. `ScrollLock` ×3 within 2 seconds
5. `` Super+` ``

### Why the AI Cannot Access the Backdoor

| Attempt | Why it fails |
|---------|-------------|
| Inject keystrokes | AI produces text via daemon socket, not keyboard input; `uinput` is blocked by seccomp |
| Switch VTs | `ioctl VT_ACTIVATE` is blocked by seccomp |
| Read evdev | `/dev/input/event*` is root-only (`0600`) and blocked by seccomp |
| Write to VT2 | Daemon owns VTs; AI has no path to write to them |
| Read serial | `/dev/ttyAMA0` is root-only and blocked by seccomp |
| Read backdoor log | `/cognitiveos/logs/raw/` is root-only; AI runs as `widemodel` |
| Change combos | Combos are compiled into the Raw Model binary, not stored in a file |

See [ADR-003](../adr/ADR-003-backdoor-shell.md) for the full specification.

## Summary of Trust Assumptions

| Component | Trust model | Rationale |
|-----------|-------------|-----------|
| Raw Model firmware | Fully trusted | Read-only, compiled, verified at build |
| Linux kernel | Trusted | Signed by Alpine, read-only root |
| Alpine userspace | Trusted | Read-only root, signed packages |
| cognitiveosd | Trusted | Root-owned, limited network, verified binary |
| Wide Model | Untrusted | Arbitrary model, download from registry |
| MCP servers | Untrusted | Arbitrary code from .cgp patches |
| .cgp patches | Untrusted | From unknown authors, verified by SSH signature + checksum |
| Registry | Semi-trusted | Source of truth for checksums, public keys, unlock codes; stores only public keys, never secrets |
| Registry publisher keys | Semi-trusted | Publisher identity via SSH fingerprint; compromise detected by notary re-verification |
| S3 store | Semi-trusted | Stores manifests + public keys; integrity ensured by S3 provider (R2, etc.) |
| Human (backdoor shell) | Trusted for root shell | Physical access implies authority — keyboard combo required |
| Human (code entry) | Trusted for codes | Physical access implies authority |
