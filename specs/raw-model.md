# Raw Model Specification

Version: 1.0.0-draft

## Overview

The Raw Model is the firmware-level inference engine in CognitiveOS. It is the always-on, trusted supervisor that runs at root level — distinct from the Wide Model which runs as an unprivileged `widemodel` user. The Raw Model validates system codes, authorizes unlock codes, enforces hardware audits, acts as a guardrail between the human and the Wide Model, and classifies prompts via GGUF inference.

The Raw Model is a **hybrid** system:
- **Compiled-in deterministic rules** for system code validation, unlock code verification (RSA), resource auditing, and package request validation — no NN inference involved.
- **NN-based GGUF inference** (via llama.cpp CGo backend) for `validate_prompt` — classifies user prompts as ALLOW/DENY/MODIFY using a small, fast model loaded at startup.

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

### 0. Physical Backdoor Shell Supervision

The Raw Model monitors physical keyboard input for backdoor combos and spawns root shells on demand. This is responsibility **zero** — it runs before any other service, ensuring the backdoor is available even if the AI is compromised.

See [ADR-003](../adr/ADR-003-backdoor-shell.md) for the full specification.

#### Evdev Keyboard Monitoring

- Opens `/dev/input/event*` devices at startup
- Watches `/dev/input/` with `inotify` for hotplug (USB keyboard after boot)
- Ignores virtual input devices (`ID_BUS=VIRTUAL`) to prevent AI injection
- Implements a key sequence state machine for each combo
- On combo match: activates backdoor on both channels

#### Backdoor Channel Activation

**VT2 shell** — Calls `ioctl VT_ACTIVATE` to switch the display to VT2, spawns `/bin/sh` as root. On shell exit, switches back to VT1 (TUI).

**Serial shell** — Ensures `getty` or a Raw Model-spawned shell is running on `/dev/ttyAMA0`. This channel requires no combo — any serial connection gets a root shell (physical access to UART pins implies authority).

#### AI Isolation

The Wide Model, MCP servers, and all other untrusted processes cannot:
- Access `/dev/input/event*` (seccomp + permissions)
- Call `ioctl` on VT devices (seccomp)
- Access `/dev/ttyAMA0` (seccomp + permissions)
- Write to `/dev/uinput` (seccomp)
- Read `/cognitiveos/logs/raw/` (permissions)

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

Distribution images follow this naming convention:

```
cognitiveos-<semver>-<class>-<arch>.<ext>

Examples:
  cognitiveos-0.1.0-standard-x86_64.iso
  cognitiveos-0.1.0-titan-aarch64.img
  cognitiveos-0.1.0-edge-armv7.img
```

The class encodes the hardware tier and determines which raw model is baked at build time:

| Class | Raw Model | Ships wide model? | Initial wide model source |
|-------|-----------|-------------------|---------------------------|
| `titan` | 235B Qwen GGUF | No | None — raw-managed, agent-triggered `.cgp` install |
| `standard` | 1.5B GGUF | Yes | 8B Gemma 4 GGUF in `/cognitiveos/models/wide/active/` at image build time |
| `gateway` | Compiled-in only (no GGUF) | No | Pulled from remote on first boot via first-run wizard |
| `edge` | 0.5B GGUF | Yes | Auto-selected tiny GGUF from `/cognitiveos/models/wide/active/` directory |
| `micro` | Compiled-in only (no GGUF) | No | Remote-only (thin client, pulls from inference proxy) |

The class table is encoded in the distro build scripts. The class is not a runtime value — it determines what is baked into the image at build time.

### Raw Model Boot Configuration

The raw model path is read from `config.toml` at daemon boot time:

```toml
[raw_model]
model = "/cognitiveos/models/raw/raw-model.gguf"
```

The Wide Model is **not** selected by config — it is chosen at runtime by the Raw Model routing hint (see [Multi-Model Routing](#multi-model-routing)).

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
- Two main responsibilities:
  - **JSON-RPC server**: dispatches RPC methods over Unix socket (system codes, unlock, audit, resource checks, prompt validation, package validation)
  - **Evdev monitor** (planned, see ADR-003): reads keyboard input, detects backdoor combos, spawns shells — not yet implemented in the current codebase
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

| Method | Params | Returns | Description | Uses GGUF? |
|--------|--------|---------|-------------|-----------|
| `validate_system_code` | `{code, origin}` | `{status, action}` | Validate a system code and return the action to take | No — compiled-in deterministic |
| `check_unlock_code` | `{code, patch_name}` | `{status, message}` | Validate an unlock code for a paid patch (RSA signature) | No — compiled-in deterministic |
| `audit_resources` | `{requested_mb}` | `{available, total, allowed}` | Check if enough resources are available for a Wide Model load | No — reads /proc/meminfo |
| `healthcheck` | `{}` | `{status, model_loaded}` | Return whether the Raw Model is running and ready | No |
| `version` | `{}` | `{version, model, quant}` | Return Raw Model version and loaded model info | No |
| `validate_prompt` | `{prompt, routing_hints}` | `{action, modified_prompt, reason, model}` | Classify user prompt as ALLOW/DENY/MODIFY using GGUF inference, optionally returning a model routing hint | **Yes** — runs inference on the GGUF model via llama.cpp |
| `validate_package_request` | `{operation, package_name, version, manifest_metadata}` | `{status, reason, command}` | Validate a package management operation against OS rules and security conditions | No — compiled-in deterministic |

### 5. Package Request Validation

The Raw Model validates all package management operations initiated by the Wide Model. This is a **compiled-in deterministic check** — it does **not** use the GGUF model or any NN inference. The GGUF is only used for `validate_prompt` classification (see [GGUF Model Usage](#gguf-model-usage)).

#### Validation Rules

| Rule | Operations | Action |
|------|-----------|--------|
| Manifest has `raw_model` field | install | Deny with reason "raw_model packages cannot be auto-installed" |
| Package is critical system component (`cognitiveosd`, `raw-model`, `base-os`) | install, remove, update | Deny with reason "critical system package" |
| Rate limit exceeded (>5 operations / 5 min) | all | Deny with reason "rate limit exceeded" |
| Disk space insufficient for install | install, update | Deny with reason "insufficient disk space" |
| Registry not in allowlist | install, update | Deny with reason "registry not allowed" |
| Read-only (search, list, info) with no violations | read-only | Approved (rate limit still enforced) |

#### RPC Schema

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "validate_package_request",
  "params": {
    "operation": "install",
    "package_name": "photo-viewer",
    "version": "1.0.0",
    "manifest_metadata": {
      "has_raw_model": false,
      "disk_space_mb": 128,
      "registry": "registry.cognitiveos.org",
      "is_critical": false
    }
  }
}
```

**Response (approved):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "approved",
    "reason": "",
    "command": "cpm install photo-viewer"
  }
}
```

**Response (denied):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "denied",
    "reason": "raw_model packages cannot be auto-installed",
    "command": ""
  }
}
```

#### Rate Limiting

- Counter per package operation type, reset every 5 minutes
- Threshold: 5 operations total across all types
- On exceed: return denied with remaining cooldown time
- Counter stored in-memory by the Raw Model (no persistence needed — a restart resets the counter, which is acceptable for rate limiting)

### GGUF Model Usage

The Raw Model loads a small GGUF at startup via the llama.cpp CGo backend. This model serves a single purpose: **classifying user prompts** in the `validate_prompt` RPC.

```
llama.cpp CGo bindings
  → Load model at startup (verifyModel: backend.Load)
  → Inference on demand via classifyPrompt (backend.Generate)
  → Unload only on shutdown
```

- `verifyModel()` is called at startup — if the GGUF cannot be loaded, the system halts with `"System halted. Please reflash firmware."`
- `classifyPrompt()` runs inference with temperature=0 to classify the input as ALLOW, DENY, or MODIFY
- The GGUF is **not** used for any other RPC — system codes, unlock codes, resource audits, and package validation all use compiled-in deterministic rules
- No streaming — all inference is request-response
- No chat history — stateless, each call is independent
- No model swapping — single model loaded at boot, never changed
- Context window: 1024 tokens (small, fast)

## Multi-Model Routing

The Raw Model supports dynamic Wide Model routing. When the daemon sends a `validate_prompt` request, it includes a `routing_hints` map describing all installed models and their tags. The Raw Model's GGUF inference classifies the prompt and may return a `model` field identifying the best model for the task.

### Flow

```
1. Daemon builds modelRegistry from installed .cgp manifests (brain.wide_model.routing)
2. Daemon sends validate_prompt with {prompt, routing_hints: {model_id: [tags...], ...}}
3. Raw Model classifies prompt, returns {action, modified_prompt, reason, model}
4. If model != "":
   a. Daemon unloads current Wide Model (if loaded)
   b. Daemon loads the target model from its GGUF path
   c. System prompt is merged: base_prompt → patch1_prompt → ... → model_prompt
5. If model == "":
   a. Daemon keeps the current Wide Model loaded
```

### Routing Hints Schema

```json
{
  "routing_hints": {
    "gemma4:2b": ["general", "chat"],
    "deepseek-coder:6.7b": ["code", "math", "reasoning"],
    "llama3:8b": ["general", "creative"]
  }
}
```

### Response with model routing

```json
{
  "action": "allow",
  "model": "deepseek-coder:6.7b"
}
```

### Model Registry

The daemon builds its model registry at startup and updates it whenever a `.cgp` package is installed or removed. Each registry entry maps a `model_id` to:

- `model_id`: Unique model identifier (from `brain.wide_model.routing.model_id`)
- `tags`: Classification tags (from `brain.wide_model.routing.tags`)
- `gguf_path`: Resolved path to the GGUF weights file

The registry is passed to the Raw Model as `routing_hints` on every `validate_prompt` call.

### System Prompt Merging

When a model is loaded (including hot-swap), system prompts are merged in order:

1. Base system prompt (`/cognitiveos/etc/base-prompt.md`)
2. System prompts from all installed patches with `runtime.system_prompt`, sorted by install order
3. The target model's own system prompt (from `brain.wide_model.adapter` directory)

The merged prompt is set as the Wide Model's system prompt on load.

### Config Note

The config.toml only contains `[raw_model]` — the wide model path is never in config:

```toml
[raw_model]
model = "/cognitiveos/models/raw/raw-model.gguf"
```

The Wide Model is chosen at runtime by the Raw Model routing hint.

## Startup Sequence

```
1. Kernel boots, mounts read-only partitions
2. /etc/inittab spawns cognitiveosd as PID 1
3. cognitiveosd spawns /cognitiveos/bin/cograw
4. cograw loads /cognitiveos/models/raw/raw-model.gguf into llama.cpp backend (`verifyModel`)
5. cograw opens Unix socket /cognitiveos/run/raw.sock
6. cograw opens /dev/input/event* devices, starts evdev monitor *(planned, see ADR-003)*
7. cograw spawns getty on /dev/ttyAMA0 for serial backdoor *(planned, see ADR-003)*
8. cognitiveosd connects to raw.sock, verifies healthcheck
9. cognitiveosd spawns MCP servers and Wide Model (if configured)
10. System is ready
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
| **Backdoor shell isolation** | Evdev monitoring in firmware; keyboard combos compiled-in; shell channels blocked from AI by seccomp + permissions |

## See Also

- [Architecture](architecture.md) — overall system architecture
- [System Codes](system-codes.md) — code types and their handlers
- [Security Model](security-model.md) — trust boundaries and isolation
- [Inference API](inference-api.md) — Wide Model inference (coginfer)
- [Ephemeral Identity](ephemeral-identity.md) — long-term biometric vision
- [ADR-003](../adr/ADR-003-backdoor-shell.md) — physical backdoor shell specification
