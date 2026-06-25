# Raw Model Specification

Version: 1.0.0-draft

## Overview

The Raw Model is the firmware-level inference engine in CognitiveOS. It is the always-on, trusted supervisor that runs at root level — distinct from the Wide Model which runs as an unprivileged `widemodel` user. The Raw Model validates system codes, authorizes unlock codes, enforces hardware audits, and acts as a deterministic guardrail between the human and the Wide Model.

## Architectural Position

```
                    CognitiveOS
┌──────────────────────────────────────────────────┐
│  Human (intent / codes)                          │
│         │                                        │
│         ▼                                        │
│  ┌─────────────────┐     ┌──────────────────┐    │
│  │   Raw Model     │────▶│   Wide Model     │    │
│  │  (root, always) │     │  (widemodel, on-  │    │
│  │  /cognitiveos/  │     │   demand)         │    │
│  │   models/raw/   │     │  /cognitiveos/    │    │
│  │                 │     │   models/wide/    │    │
│  │  Unix socket    │     │   HTTP REST API   │    │
│  │  cograw.sock    │     │   :11434          │    │
│  └────────┬────────┘     └──────────────────┘    │
│           │                                       │
│           ▼                                       │
│  ┌──────────────────────────────────────────────┐ │
│  │         cognitiveosd (daemon)                 │ │
│  │  Routes system codes → Raw Model             │ │
│  │  Routes inference → Wide Model               │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Communication Pathways

| Path | Protocol | Transport | Privilege |
|------|----------|-----------|-----------|
| cli → cognitiveosd | JSON envelope | Unix socket | unpriv |
| cognitiveosd → Raw Model | JSON-RPC 2.0 | Unix socket (`/cognitiveos/run/raw.sock`) | root-owned |
| cognitiveosd → Wide Model | JSON over HTTP | TCP :11434 | unpriv |
| Raw Model → Kernel | syscall | direct | root |

## Raw Model Responsibilities

### 1. System Code Validation

The Raw Model holds the five system codes in a compiled-in lookup table. Codes are never written to the filesystem.

| Code | Validation | Action |
|------|-----------|--------|
| **wake** | Voice or button | Boot Wide Model, start input listener |
| **idle** | Voice or button | Unload Wide Model, cut mic, ultra-low-power |
| **security** | Physical button combo only (cannot be triggered by software) | Kill all processes, cut peripheral power |
| **reset** | Physical button combo only (cannot be triggered by software) | Wipe data partitions, reinstall factory image |
| **unlock** | Voice + numeric code | Authorize paid Wide Model download |

### 2. Code-Based Authentication

For paid cognitive patches and Wide Model downloads, authentication uses a code-based flow:

```
1. Wide Model discovers a paid patch in registry
2. Wide Model requests download via cognitiveosd
3. cognitiveosd forwards to Raw Model
4. Raw Model prompts human via cli: "Premium model requires unlock code. Say or enter code."
5. Human provides code (voice or text)
6. Raw Model validates against the registry server
7. If valid: Raw Model authorizes download and injects credential into the request
8. If invalid: Raw Model logs attempt, retry count, enforces cooldown after 5 failures
```

**Long-term:** This code-based flow may be supplemented or replaced by biometric attestation (face, voice, touch) as described in the [Ephemeral Identity spec](ephemeral-identity.md).

### 3. Hardware Audit Guard

Before any Wide Model load, the Raw Model independently verifies system resources:

1. Reads `/proc/meminfo`, `statfs()`, and device nodes directly
2. Compares against the audit report from cognitiveosd
3. If resources are insufficient: blocks the load and returns error
4. The Wide Model cannot disable, fake, or bypass this audit — it runs in a separate process with no access to the audit logic

### 4. Seccomp and cgroup Enforcement

The Raw Model applies seccomp filters and cgroup limits to all spawned MCP servers and the Wide Model:

- **seccomp profile**: compiled into the Raw Model binary, not loaded from a file
- **cgroup limits**: memory, CPU, disk I/O, and process count per MCP server
- **Enforcement point**: applied at process spawn time by the Raw Model (running as root), before the process ever executes

## Model Format and Location

### File Location

```
/cognitiveos/models/raw/raw-model.gguf
```

### File Protection

The raw model file is protected under standard Linux filesystem permissions:

```
-r--------  root root  /cognitiveos/models/raw/raw-model.gguf
```

- **Owner**: `root:root`
- **Permissions**: `0400` (read-only for root)
- **Mount**: The entire `/cognitiveos/models/raw/` directory is on a read-only filesystem partition (squashfs)
- **Modification**: Only a full firmware update (physical SD card reflash, JTAG, or signed update) can change the raw model file
- The Wide Model (`widemodel` user) has **no read access** — the filesystem permissions prevent it from even reading the raw model file, ensuring the guardrail cannot be inspected or bypassed

### Model Format

- Standard GGUF format (llama.cpp compatible)
- Quantized to Q4_K_M or lower for fast inference on limited hardware
- Must fit entirely in available RAM alongside the kernel and daemon

## Model Catalog

Raw Model GGUF files are distributed through compatible model catalogs:

- **Primary**: `https://github.com/anomalyco/models.dev` or compatible mirror
- **Fallback**: Baked into the distribution image at build time
- **Update mechanism**: Signed firmware updates only — the Raw Model is not updated through the .cgp package system

Models are selected by size and quantization to match the target hardware:

| Distro Variant | Max Raw Model Size | Recommended Quantization | Target Hardware |
|---|---|---|---|
| cognitiveos-raspberry-pi | 500 MB | Q4_K_M | Pi 5 / CM4 (8GB) |
| cognitiveos-x86_64 | 1 GB | Q4_K_M | x86_64 with 8GB+ RAM |
| cognitiveos-jetson | 2 GB | Q4_K_M | Jetson Orin NX/Nano (16GB) |

## Distro Image Variants

Each CognitiveOS distribution image is named after its target Raw Model:

```
cognitiveos-<model-variant>-<arch>.iso

Examples:
  cognitiveos-raspberry-pi-0.5b-aarch64.iso
  cognitiveos-x86_64-1.5b-amd64.iso
  cognitiveos-jetson-3b-aarch64.iso
```

The Raw Model is baked into the distribution image at build time — it is not downloaded on first boot. This ensures the system can function without network connectivity.

## Implementation: cograw

### Binary Location

```
/cognitiveos/bin/cograw
```

### Process Model

- Started by `cognitiveosd` at boot (before any MCP servers or Wide Model)
- Runs as `root` — drop privileges not needed since it is the trusted supervisor
- Always-on: never terminates unless the system shuts down
- Single-threaded, non-blocking I/O loop
- Memory footprint: model size + ~200 MB overhead

### Transport Protocol

JSON-RPC 2.0 over Unix socket at `/cognitiveos/run/raw.sock`.

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "validate_code",
  "params": {
    "code": "security",
    "origin": "cli"
  }
}

// Success response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "valid",
    "action": "proceed"
  }
}

// Error response
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": "E_INVALID_CODE",
    "message": "system code not recognized"
  }
}
```

### RPC Methods

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `validate_system_code` | `{code, origin}` | `{status, action}` | Validate a system code and return the action to take |
| `check_unlock_code` | `{code, patch_name}` | `{status, message}` | Validate an unlock code for a paid patch |
| `audit_resources` | `{requested_mb}` | `{available, total, allowed}` | Check if enough resources are available for a Wide Model load |
| `healthcheck` | `{}` | `{status, model_loaded}` | Return whether the Raw Model is running and ready |
| `version` | `{}` | `{version, model, quant}` | Return Raw Model version and loaded model info |

### LLM Integration

The Raw Model uses the same Go+llama.cpp bindings as coginfer but with a stripped-down interface:

```
llama.cpp CGo bindings
  → Load model at startup
  → Inference on demand (single-prompt, no streaming)
  → Unload only on shutdown
```

- No streaming — all inference is request-response
- No chat history — stateless, each call is independent
- No model swapping — single model loaded at boot, never changed
- Context window: 1024 tokens (small, fast)

## Startup Sequence

```
1. Kernel boots, mounts read-only partitions
2. /etc/inittab spawns cognitiveosd as PID 1
3. cognitiveosd spawns /cognitiveos/bin/cograw
4. cograw loads /cognitiveos/models/raw/raw-model.gguf
5. cograw opens Unix socket /cognitiveos/run/raw.sock
6. cognitiveosd connects to raw.sock, verifies healthcheck
7. cognitiveosd spawns MCP servers and Wide Model (if configured)
8. System is ready
```

## Future: Biometric Attestation

Long-term, the Raw Model may incorporate biometric authentication:

1. Human presents biometric (face, voice, touch)
2. Raw Model captures sensor data via direct hardware access
3. Raw Model matches against stored biometric template (stored in read-only firmware partition)
4. Raw Model generates a short-lived signed attestation token
5. The attestation is presented to remote services as proof of identity
6. The token is discarded after the transaction — no persistent identity

This is documented separately in the [Ephemeral Identity spec](ephemeral-identity.md).

## Security Properties

| Property | Mechanism |
|----------|-----------|
| **Tamper resistance** | Read-only firmware partition, signed updates |
| **Isolation from Wide Model** | Unix filesystem perms (`root:root 0400`), separate process |
| **Supply chain integrity** | GGUF checksum verified at image build time |
| **Auditability** | All code validation attempts logged to `/cognitiveos/logs/raw/` |
| **Cooldown enforcement** | 5 failed unlock attempts → 5-minute lockout, logged |
| **Physical override** | Reset/Security codes require physical button combo |

## See Also

- [Architecture](architecture.md) — overall system architecture
- [System Codes](system-codes.md) — code types and their handlers
- [Security Model](security-model.md) — trust boundaries and isolation
- [Inference API](inference-api.md) — Wide Model inference (coginfer)
- [Ephemeral Identity](ephemeral-identity.md) — long-term biometric vision
