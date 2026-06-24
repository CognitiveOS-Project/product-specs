# Inference Engine API Specification

Version: 1.0.0-draft

## Overview

`coginfer` is the CognitiveOS inference engine. It wraps `llama.cpp` (or equivalent backend) as a child process and exposes an HTTP API for model loading, inference, and resource reporting.

It runs as a supervised process managed by `cognitiveosd`.

## Transport

- **Default:** HTTP on `127.0.0.1:11434` (localhost only, no network exposure)
- **Protocol:** JSON over HTTP
- **Alternative socket:** `/cognitiveos/run/inference.sock` (Unix socket, preferred for low-latency)

## Base API (Ollama-Compatible Subset)

`coginfer` implements a subset of the Ollama API for compatibility with existing MCP tooling and Wide Model runners.

### `POST /api/generate`

Generate a completion from a model.

```json
{
  "model": "gemma-4-2b",
  "prompt": "Show me my photos from last weekend",
  "system": "You are a helpful AI assistant running CognitiveOS.",
  "options": {
    "temperature": 0.7,
    "num_predict": 512,
    "top_k": 40,
    "top_p": 0.9
  },
  "stream": true
}
```

Response (streaming, newline-delimited JSON):

```json
{
  "response": "I'll search your photo library...",
  "done": false
}
{
  "response": " found 3 photos from last weekend.",
  "done": true,
  "context": [1, 2, 3, ...],
  "total_duration": 2345678900,
  "load_duration": 123456789,
  "prompt_eval_count": 42,
  "eval_count": 28,
  "eval_duration": 1234567890
}
```

Non-streaming response:

```json
{
  "response": "I'll search your photo library... found 3 photos from last weekend.",
  "done": true,
  "context": [1, 2, 3, ...],
  "total_duration": 2345678900,
  "eval_count": 28
}
```

### `POST /api/chat`

Chat completion (for conversation-aware models).

```json
{
  "model": "gemma-4-2b",
  "messages": [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "Show me my photos"}
  ],
  "stream": true
}
```

Response: same streaming format as `/api/generate`.

### `GET /api/tags`

List available models.

```json
{
  "models": [
    {
      "name": "raw-model",
      "modified_at": "2026-06-01T00:00:00Z",
      "size": 524288000
    },
    {
      "name": "gemma-4-2b",
      "modified_at": "2026-06-23T14:30:00Z",
      "size": 2147483648
    }
  ]
}
```

### `POST /api/pull`

Download a model from a registry (or local filesystem).

```json
{
  "name": "gemma-4-2b",
  "path": "/cognitiveos/models/wide/active/gemma-4-2b-q4_k_m.gguf",
  "insecure": false
}
```

Response:

```json
{
  "status": "success",
  "digest": "sha256:abc123...",
  "size": 2147483648
}
```

If the model file already exists at the specified path, it is loaded directly (no download).

### `GET /api/ps`

Show running models and their resource usage.

```json
{
  "models": [
    {
      "name": "gemma-4-2b",
      "size": 2147483648,
      "ram_usage_mb": 2048,
      "vram_usage_mb": 1024,
      "processor": "CPU+GPU",
      "gpu_layers": 32,
      "tokens_per_second": 45.2,
      "uptime_seconds": 3600,
      "context_usage_percent": 25
    }
  ]
}
```

### `DELETE /api/delete`

Unload a model and free its resources.

```json
{
  "model": "gemma-4-2b"
}
```

Response: `200 OK`

## CognitiveOS Extensions

### `GET /cognitiveos/status`

Detailed system status for the inference engine.

```json
{
  "status": "ready" | "loading" | "unloaded" | "error",
  "models_loaded": 1,
  "active_model": {
    "name": "gemma-4-2b",
    "path": "/cognitiveos/models/wide/active/model.gguf",
    "quantization": "q4_k_m",
    "ram_usage_mb": 2048,
    "vram_usage_mb": 1024,
    "context_window": 8192,
    "context_used": 2048,
    "tokens_per_second": 45.2
  },
  "raw_model": {
    "loaded": true,
    "path": "/cognitiveos/models/raw/raw-model.gguf",
    "ram_usage_mb": 128
  },
  "hardware": {
    "total_ram_mb": 8192,
    "available_ram_mb": 4096,
    "total_vram_mb": 2048,
    "available_vram_mb": 1024,
    "cpu_cores": 8,
    "cpu_threads": 16,
    "npu_available": true,
    "npu_memory_mb": 1024
  }
}
```

### `GET /cognitiveos/capabilities`

What hardware acceleration is available.

```json
{
  "backends": {
    "cpu": true,
    "cuda": true,
    "vulkan": false,
    "npu": false,
    "metal": false
  },
  "preferred_backend": "cuda",
  "max_model_size_mb": 4096,
  "supported_quantizations": ["q4_0", "q4_k_m", "q5_k_m", "q8_0"],
  "max_context_window": 32768
}
```

### Resource Negotiation

When cognitiveosd requests a model load, the inference engine checks resources and negotiates if necessary.

#### Standard Load Flow

```
cognitiveosd → POST /api/negotiate (or wide_model_load via socket)
  {
    "model_path": "/cognitiveos/models/wide/active/model.gguf",
    "params": { "temperature": 0.7, "num_ctx": 8192 }
  }
```

Success response:

```json
{
  "status": "ok",
  "model_info": {
    "loaded": "gemma-4-2b-q4_k_m.gguf",
    "ram_usage_mb": 2048,
    "tokens_per_second": 45.2
  }
}
```

Insufficient resources response:

```json
{
  "status": "error",
  "error": {
    "code": "E_INSUFFICIENT_RESOURCES",
    "message": "Model requires 4096 MB RAM, 2048 MB available"
  },
  "alternatives": [
    {
      "model": "gemma-4-2b-q4_0.gguf",
      "ram_usage_mb": 1536,
      "performance_tokens_per_second": 32.1
    },
    {
      "model": "gemma-4-2b-q2_k.gguf",
      "ram_usage_mb": 1024,
      "performance_tokens_per_second": 25.0
    },
    {
      "suggestion": "use_remote",
      "message": "Offload inference to a remote server"
    }
  ]
}
```

cognitiveosd can then choose an alternative or inform the human.

#### Unload Flow

```
cognitiveosd → DELETE /api/delete { "model": "gemma-4-2b" }
→ 200 OK
→ RAM freed: 2048 MB
```

## Model Lifecycle

### States

```
UNLOADED → LOADING → READY → (inference) → READY → UNLOADING → UNLOADED
                        ↓                          ↓
                     ERROR ← (recover) ←───────────┘
```

### Transitions

| Transition | Trigger | Action |
|-----------|---------|--------|
| UNLOADED → LOADING | `POST /api/negotiate` accepted | Allocate memory, load model file into RAM/VRAM |
| LOADING → READY | Model loaded successfully | Start accepting inference requests |
| LOADING → ERROR | Load failed (OOM, corrupt file) | Return error with alternatives |
| READY → UNLOADING | `DELETE /api/delete` or idle timeout | Free memory, close model handle |
| UNLOADING → UNLOADED | Unload complete | Return freed memory to OS |
| READY → ERROR | Runtime error (GPU crash, OOM) | Attempt recovery; if fails, report to daemon |
| ERROR → UNLOADED | Recovery impossible | Force unload |
| ERROR → READY | Recovery possible | Reload model with fallback params |

### Idle Timeout

If the Wide Model receives no inference requests for 5 minutes, coginfer automatically:
1. Snapshots the model state (context, session data)
2. Unloads the model from RAM/VRAM
3. Reports to cognitiveosd: "Wide Model unloaded due to idle timeout"
4. Reserves model file handle for fast reload (< 500 ms)

The 5-minute timeout is configurable in `/etc/cognitiveos/config.toml`:

```toml
[inference]
idle_timeout_seconds = 300
```

## Error Codes

| Code | Description |
|------|-------------|
| `E_MODEL_NOT_FOUND` | Model file not found at specified path |
| `E_MODEL_LOAD_FAILED` | Model file corrupt or incompatible |
| `E_OOM` | Out of memory (RAM or VRAM) |
| `E_BACKEND_UNAVAILABLE` | Requested backend (CUDA/Vulkan) not available |
| `E_TIMEOUT` | Inference request timed out |
| `E_INVALID_PARAMS` | Invalid inference parameters |
| `E_INTERNAL` | Unexpected internal error |

## Logging

- Log file: `/cognitiveos/logs/inference.log`
- Format: `ISO-8601 [LEVEL] <message>`
- Levels: DEBUG, INFO, WARN, ERROR

## Healthcheck

```
GET /health
→ 200 OK
{
  "status": "healthy" | "degraded" | "unhealthy",
  "uptime_seconds": 3600,
  "models_loaded": 1,
  "last_error": null,
  "ram_usage_percent": 45
}
```

cognitiveosd checks this endpoint every 30 seconds. If healthcheck fails, cognitiveosd attempts to restart coginfer.
