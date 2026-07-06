# cognitive.json Field Reference

Version: 1.0.0-draft

## Overview

Comprehensive field reference for the `cognitive.json` manifest. Only `name`, `version`, and `description` are required — all other fields are optional. A package without model fields is a prompt/skill/tool package. A package without `download_url` was installed from a non-registry source (npm, git, local file).

---

## Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **yes** | — | Unique package name in reverse-domain notation (e.g. `com.cognitiveos.email-manager`). Pattern: `^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$` |
| `version` | string | **yes** | — | SemVer version string (e.g. `1.2.3`, `1.2.3-rc.1`). Pattern: `^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$` |
| `description` | string | **yes** | — | Human-readable description of the patch |
| `author` | string | no | — | Author or organization name |
| `license` | string | no | `MIT` | SPDX license identifier |
| `download_url` | string (uri) | no | — | Direct download URL for this specific version archive. Set by the registry on publish; not present for packages installed from npm, git, or local files |
| `checksum` | object | no | — | Checksum for integrity verification of the archive blob |
| `source` | object | no | — | Source repository and issue tracker URLs |
| `dependencies` | object | no | — | Map of package names to SemVer version ranges |
| `hardware_requirements` | object | no | — | Minimum hardware specifications for this patch |
| `brain` | object | no | — | Model configuration. Use `raw_model` for self-contained models, `wide_model` for large models with remote weights |
| `runtime` | object | no | — | Runtime configuration for MCP servers and lifecycle |

---

## `checksum` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sha256` | string | no | SHA-256 hex digest of the archive blob. Pattern: `^[a-f0-9]{64}$` |

---

## `source` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repository` | string (uri) | **yes** | Git provider URL (GitHub, GitLab, Bitbucket, or self-hosted) |
| `issues` | string (uri) | **yes** | Issue tracker URL for bug reporting |
| `issues_api` | string (uri) | no | Direct JSON API endpoint for bug queries. Required when provider is not github/gitlab/bitbucket |

---

## `dependencies` Object

Map of package names (`string`) to SemVer version ranges (`string`). Each value is a version range expression:

| Pattern | Example | Meaning |
|---------|---------|---------|
| `^1.2.3` | `^1.2.3` | Compatible with version 1.2.3 (>=1.2.3 <2.0.0) |
| `~1.2.3` | `~1.2.3` | Approximately equivalent to 1.2.3 (>=1.2.3 <1.3.0) |
| `>=1.2.3` | `>=1.2.3` | Version 1.2.3 or higher |
| `*` | `*` | Any version |
| `1.2.3` | `1.2.3` | Exact version |

---

## `hardware_requirements` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `min_ram_mb` | integer | no | Minimum RAM in megabytes |
| `min_storage_mb` | integer | no | Minimum free storage in megabytes |
| `npu_required` | boolean | no | Whether a neural processing unit is required |
| `recommended_npu` | string | no | Recommended NPU architecture (e.g. `hailo-8`, `jetson-orin-nano`) |

---

## `brain` Object

The `brain` object contains model configuration. It supports two model subtypes as well as legacy flat fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_model` | string | no | Legacy field. Base model identifier (e.g. `gemma4:2b`). Prefer `wide_model.base_model` |
| `adapter` | string | no | Legacy field. Path to LoRA adapter or quantized weights file (.gguf). Prefer `wide_model.adapter` |
| `raw_model` | object | no | Self-contained model bundled directly in the archive |
| `wide_model` | object | no | Large model with remote weights downloaded at install time |
| `parameters` | object | no | Default inference parameters shared across all model subtypes |

### `brain.raw_model` Object

For self-contained models where weights are bundled inside the archive (e.g., MCU/ESP32 firmware, tiny-llm binaries, embedding models).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | no | Model type classification (e.g. `firmware`, `tiny-llm`, `embedding`) |
| `weights` | object | no | Weight source configuration (inline weights are implicit when weights is absent or local) |
| `parameters` | object | no | Inference parameters (overrides `brain.parameters` for this model) |

### `brain.wide_model` Object

For large models where weights are downloaded from a remote source at install time (e.g., Gemma, Llama via Hugging Face or the CognitiveOS registry).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_model` | string | no | Base model identifier (e.g. `gemma4:2b`) |
| `adapter` | string | no | Path to LoRA adapter or quantized weights file inside the archive (.gguf) |
| `weights` | object | no | Weight source configuration (typically `weights.remote` for downloaded weights) |
| `parameters` | object | no | Inference parameters (overrides `brain.parameters` for this model) |
| `routing` | object | no | Model selection hints for the daemon. Declares what model this skill prefers; the daemon builds a registry from all installed manifests and sends routing_hints to the Raw Model's validate_prompt RPC for prompt classification |

#### `brain.wide_model.routing` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_id` | string | **yes** | Unique model identifier used by the daemon's model registry (e.g. `gemma4:2b`, `deepseek-coder:6.7b`). The daemon includes this in `routing_hints` sent to the Raw Model for prompt classification |
| `tags` | array of string | no | Classification tags describing when this model should be used (e.g. `["code", "math"]`, `["vision", "image"]`, `["fast", "low-ram"]`). The daemon matches these against prompt intent via the Raw Model's `validate_prompt` RPC |
### `brain.parameters` Object

Inference parameters shared across models. Each model subtype can override individual values.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `temperature` | number | no | Sampling temperature. Range: 0–2 |
| `num_ctx` | integer | no | Context window size in tokens. Minimum: 512 |

---

## `weights` Object ($defs.weights)

Weight source configuration. A model references weights either inline (bundled in the archive) or remotely (downloaded at install time). The `remote` sub-object defines a download source.

When a model bundles weights directly inside the archive (the `weights/` directory), no `weights` field is needed. The `weights` field is only used when specifying remote sources.

### `weights.remote` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | no | Weight source provider. Enum: `huggingface`, `registry`, `url` |
| `model_id` | string | no | Model identifier at the source (e.g. `google/gemma-4-2b`) |
| `url` | string (uri) | no | Direct download URL for the weight file |
| `filename` | string | no | Expected filename after download (e.g. `gemma-4-2b-Q4_K_M.gguf`) |
| `format` | string | no | Weight file format. Enum: `gguf`, `safetensors`, `pt` |
| `quant` | string | no | Quantization level (e.g. `Q4_K_M`, `Q8_0`) |
| `size_bytes` | integer | no | Expected file size in bytes |

---

## `runtime` Object

Runtime configuration for MCP servers and lifecycle management.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `system_prompt` | string | no | Path to system prompt markdown file (relative to archive root) |
| `tools_root` | string | no | Path to tools directory. Default: `./tools` |
| `mcp_servers` | array | no | MCP server definitions to spawn |
| `background` | boolean | no | Whether this patch runs as a background service (always-listening) |
| `capabilities` | array | no | Declared functional capabilities for package discovery. Enables the registry to return this package when searching by function (e.g., `cpm search display`). Does NOT affect runtime tool routing — that is handled by the daemon's MCP tool registry |

### `runtime.mcp_servers[]` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **yes** | MCP server name |
| `command` | string | **yes** | Path to executable (relative to archive root) |
| `args` | array | no | Command-line arguments (array of strings) |
| `env` | object | no | Environment variables (key-value map) |
| `transport` | string | no | MCP transport protocol. Enum: `stdio`, `http`. Default: `stdio` |

### `runtime.capabilities[]` Array

Array of capability strings for package discovery and dependency resolution. Each string should follow reverse-domain or kebab-case convention:

```
com.cognitiveos.email.send
com.cognitiveos.filesystem.read
image-processing
audio.transcription
```

Capabilities enable the registry to return this package when searching by function (e.g., `cpm search audio.transcription` finds packages that declare that capability). This is the mechanism the Wide Model uses for autonomous discovery: when it needs a function it lacks, it searches the registry for a package declaring the matching capability.

Note: `runtime.capabilities` is for **discovery/install-time matching** only. Runtime tool routing is handled by the daemon's MCP tool registry — MCP servers register their individual tool names (e.g., `cognitiveos.display.render_image`) via `mcp_register`, and the daemon dispatches tool calls to the correct server directly.

---

## Full Example

```json
{
  "name": "com.cognitiveos.email-manager",
  "version": "1.2.3",
  "description": "AI-powered email management skill",
  "author": "CognitiveOS Project",
  "license": "Apache-2.0",
  "download_url": "https://registry.cognitive-os.org/v1/patches/com.cognitiveos.email-manager/1.2.3/download",
  "checksum": {
    "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
  },
  "source": {
    "repository": "https://github.com/cognitiveos/email-manager",
    "issues": "https://github.com/cognitiveos/email-manager/issues"
  },
  "dependencies": {
    "com.cognitiveos.contacts": "^1.0.0",
    "com.cognitiveos.notifications": "^2.3.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 512,
    "min_storage_mb": 100
  },
  "brain": {
    "wide_model": {
      "base_model": "gemma4:2b",
      "adapter": "weights/email-lora-q4.gguf",
      "weights": {
        "remote": {
          "source": "huggingface",
          "model_id": "google/gemma-4-2b",
          "filename": "gemma-4-2b-Q4_K_M.gguf",
          "format": "gguf",
          "quant": "Q4_K_M",
          "size_bytes": 1472583690
        }
      },
      "parameters": {
        "temperature": 0.7,
        "num_ctx": 4096
      }
    }
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "tools_root": "./tools",
    "mcp_servers": [
      {
        "name": "email-imap",
        "command": "tools/mcp-server-email-imap",
        "args": ["--config", "config/imap.json"],
        "transport": "stdio"
      },
      {
        "name": "email-smtp",
        "command": "tools/mcp-server-email-smtp",
        "transport": "stdio"
      }
    ],
    "capabilities": [
      "com.cognitiveos.email.send",
      "com.cognitiveos.email.read",
      "com.cognitiveos.email.search"
    ]
  }
}
```

## Minimal Example

```json
{
  "name": "my-skill",
  "version": "0.1.0",
  "description": "A simple prompt-only skill"
}
```
