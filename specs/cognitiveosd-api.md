# cognitiveosd API Specification

Version: 1.0.0-draft

## Overview

`cognitiveosd` is the central daemon of CognitiveOS. It runs as PID 1 (or a supervised system service) and exposes a Unix socket for inter-component communication.

This document specifies the wire protocol that all components (cli, cpm, inference, MCP servers) use to communicate with the daemon.

## Transport

- **Socket:** `/cognitiveos/run/daemon.sock`
- **Type:** Unix stream socket
- **Protocol:** JSON-over-socket (newline-delimited JSON, one message per line)
- **Encoding:** UTF-8
- **Max message size:** 1 MB (messages exceeding this are rejected with `E_TOO_LARGE`)

## Message Envelope

Every message sent to or from cognitiveosd uses this envelope:

```json
{
  "type": "<message_type>",
  "id": "<uuid>",
  "timestamp": "<ISO-8601>",
  "from": "<component_id>",
  "payload": { }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Message type (see below) |
| `id` | UUID v4 | Unique message identifier for request-response correlation |
| `timestamp` | ISO 8601 | Message creation time |
| `from` | string | Source component identifier (e.g., `cli`, `cpm`, `display-mcp`, `wide-model`) |
| `payload` | object | Type-specific payload |

### Response Envelope

```json
{
  "type": "<response_type>",
  "id": "<uuid>",        // Same ID as the request
  "timestamp": "<ISO-8601>",
  "from": "cognitiveosd",
  "payload": {
    "status": "ok" | "error",
    "error": {                // Only present on error
      "code": "E_<code>",
      "message": "<human-readable>"
    },
    "data": { }               // Response data
  }
}
```

## Message Types

### 1. Input/Output — Human ↔ Wide Model

#### `input_forward` (cli → daemon)

Forward human speech or text to the Wide Model.

```json
{
  "type": "input_forward",
  "id": "a1b2c3d4-...",
  "timestamp": "2026-06-23T14:30:00Z",
  "from": "cli",
  "payload": {
    "mode": "text" | "voice",
    "content": "Show me my photos from last weekend",
    "context": {
      "session_id": "sess_abc123",
      "device": "smartphone"
    }
  }
}
```

Response:

```json
{
  "type": "input_accepted",
  "id": "a1b2c3d4-...",
  "from": "cognitiveosd",
  "payload": {
    "status": "ok"
  }
}
```

The daemon routes this to the Wide Model. Wide Model responses arrive as `output_deliver` messages.

#### `output_deliver` (daemon → cli)

Wide Model response delivered to the UI.

```json
{
  "type": "output_deliver",
  "id": "e5f6g7h8-...",
  "from": "cognitiveosd",
  "payload": {
    "session_id": "sess_abc123",
    "content": "Here are your photos from last weekend:",
    "content_type": "text" | "media" | "tool_result",
    "media": {
      "type": "image" | "video" | "audio",
      "paths": ["/cognitiveos/data/cache/render/photo1.jpg"],
      "render_command": "framebuffer" | "audio_out"
    },
    "actions": [
      { "label": "Close", "command": "close_media" }
    ]
  }
}
```

The cli processes `content_type`:
- `text` — Display text in TUI
- `media` — Yield TUI, instruct display-mcp to render
- `tool_result` — Display tool execution result

### 2. System Codes

#### `system_code` (cli/hardware → daemon)

Trigger one of the 5 system codes.

```json
{
  "type": "system_code",
  "id": "b2c3d4e5-...",
  "from": "cli",
  "payload": {
    "code": "wake" | "idle" | "security" | "reset" | "unlock",
    "unlock_code": "XXXX-XXXX",      // Only for type "unlock"
    "origin": "voice" | "keyboard" | "gpio"
  }
}
```

Response:

```json
{
  "type": "code_accepted",
  "id": "b2c3d4e5-...",
  "from": "cognitiveosd",
  "payload": {
    "status": "ok",
    "effect": "<description of what will happen>"
  }
}
```

On `security` and `reset`, the daemon SHALL respond before executing (response sent, then process terminates). On `wake`, `idle`, and `unlock`, the daemon SHALL execute the action and respond.

### 3. MCP Registration — Tools

#### `mcp_register` (MCP server → daemon)

Sent by an MCP server on startup to announce its capabilities.

```json
{
  "type": "mcp_register",
  "id": "c3d4e5f6-...",
  "from": "display-mcp",
  "payload": {
    "server": {
      "name": "display-mcp",
      "version": "1.0.0",
      "transport": "stdio",
      "pid": 1234
    },
    "tools": [
      {
        "name": "cognitiveos.display.render_image",
        "description": "Render an image file to the primary display framebuffer",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": { "type": "string" }
          },
          "required": ["path"]
        }
      }
    ]
  }
}
```

Response:

```json
{
  "type": "mcp_registered",
  "id": "c3d4e5f6-...",
  "from": "cognitiveosd",
  "payload": {
    "status": "ok",
    "server_id": "display-mcp",
    "registered_tools": ["cognitiveos.display.render_image"]
  }
}
```

#### `mcp_unregister` (MCP server → daemon)

Sent by an MCP server before graceful shutdown.

```json
{
  "type": "mcp_unregister",
  "from": "display-mcp",
  "payload": {
    "reason": "idle_timeout" | "update" | "shutdown"
  }
}
```

### 4. Tool Invocation — Wide Model ↔ MCP

#### `mcp_invoke` (daemon → MCP server)

The daemon receives a tool call from the Wide Model and forwards it to the appropriate MCP server.

```json
{
  "type": "mcp_invoke",
  "id": "d4e5f6a7-...",
  "from": "cognitiveosd",
  "payload": {
    "tool": "cognitiveos.display.render_image",
    "arguments": {
      "path": "/cognitiveos/data/cache/render/photo1.jpg"
    },
    "session_id": "sess_abc123"
  }
}
```

#### `mcp_result` (MCP server → daemon)

Tool execution result returned to the daemon, then forwarded to the Wide Model.

```json
{
  "type": "mcp_result",
  "id": "d4e5f6a7-...",       // Same ID as mcp_invoke
  "from": "display-mcp",
  "payload": {
    "status": "ok" | "error",
    "error": {
      "code": "E_NOT_FOUND",
      "message": "File not found"
    },
    "content": [
      {
        "type": "text",
        "text": "Image rendered to framebuffer"
      }
    ]
  }
}
```

### 5. Resource Audits

#### `audit_request` (cli/internal → daemon)

Request a hardware resource audit.

```json
{
  "type": "audit_request",
  "from": "cli",
  "payload": {}
}
```

#### `audit_report` (daemon → cli/Wide Model)

Current resource snapshot.

```json
{
  "type": "audit_report",
  "from": "cognitiveosd",
  "payload": {
    "timestamp": "2026-06-23T14:30:00Z",
    "resources": {
      "ram": {
        "total_mb": 8192,
        "available_mb": 4096,
        "used_by_ai_mb": 2048
      },
      "storage": {
        "total_mb": 32768,
        "available_mb": 12288,
        "patches_mb": 512,
        "models_mb": 4096
      },
      "cpu": {
        "cores": 8,
        "load_percent": 35
      },
      "npu": {
        "available": true,
        "model": "NPU-v3",
        "memory_mb": 1024
      },
      "network": {
        "connected": true,
        "interface": "wlan0",
        "signal_percent": 80
      }
    }
  }
}
```

### 6. Wide Model Lifecycle — inference Engine

#### `wide_model_load` (daemon → inference)

Request to load a Wide Model.

```json
{
  "type": "wide_model_load",
  "from": "cognitiveosd",
  "payload": {
    "model_path": "/cognitiveos/models/wide/active/model.gguf",
    "params": {
      "temperature": 0.7,
      "num_ctx": 8192,
      "gpu_layers": 32
    }
  }
}
```

Response:

```json
{
  "type": "wide_model_loaded",
  "from": "inference",
  "payload": {
    "status": "ok" | "error",
    "error": {
      "code": "E_INSUFFICIENT_RESOURCES",
      "message": "Not enough RAM to load this model. Requires 4 GB, available 2 GB."
    },
    "model_info": {
      "loaded": "gemma-4-2b-q4_k_m.gguf",
      "ram_usage_mb": 2048,
      "tokens_per_second": 45.2
    }
  }
}
```

#### `wide_model_unload` (daemon → inference)

Request to unload the current Wide Model.

```json
{
  "type": "wide_model_unload",
  "from": "cognitiveosd",
  "payload": {
    "reason": "idle" | "swap" | "security" | "reset"
  }
}
```

Response:

```json
{
  "type": "wide_model_unloaded",
  "from": "inference",
  "payload": {
    "status": "ok",
    "ram_freed_mb": 2048
  }
}
```

#### Resource Negotiation Flow

When inference receives a load request but resources are tight, it initiates negotiation:

1. inference → cognitiveosd: `{"type": "wide_model_load", "payload": {...}}`
2. cognitiveosd runs `audit` internally
3. cognitiveosd → inference:
   - If resources sufficient: `wide_model_loaded` with `status: "ok"`
   - If resources insufficient but can free (e.g., kill non-essential patches): `{"type": "negotiate", "payload": {"can_free_mb": 1024, "by_killing": ["optional-patch"]}}`
   - If resources insufficient and cannot free: `wide_model_loaded` with `status: "error", code: "E_INSUFFICIENT_RESOURCES"`

### 7. Status and Health

#### `status_request` (cli → daemon)

```json
{
  "type": "status_request",
  "from": "cli",
  "payload": {}
}
```

Response:

```json
{
  "type": "status_response",
  "from": "cognitiveosd",
  "payload": {
    "state": "idle" | "listening" | "processing" | "idle_requested" | "security",
    "uptime_seconds": 86400,
    "wide_model": {
      "status": "loaded" | "unloaded" | "loading" | "error",
      "name": "gemma-4-2b"
    },
    "patches_installed": 3,
    "mcp_servers_active": 4
  }
}
```

## Error Codes

| Code | Description | When |
|------|-------------|------|
| `E_UNKNOWN_TYPE` | Unknown message type | Type field doesn't match any handler |
| `E_TOO_LARGE` | Message exceeds 1 MB limit | Payload too large |
| `E_INVALID_PAYLOAD` | Payload schema validation failed | Missing or malformed fields |
| `E_UNAUTHORIZED` | Component not authorized for this action | cli tries system_code `security` without valid code |
| `E_SERVER_NOT_FOUND` | MCP server not registered | mcp_invoke to unknown server |
| `E_TOOL_NOT_FOUND` | Tool not found in server's registry | mcp_invoke to unknown tool |
| `E_INSUFFICIENT_RESOURCES` | Not enough hardware resources | wide_model_load rejected |
| `E_INTERNAL` | Unexpected daemon error | Bug or system failure |
| `E_SHUTDOWN` | Daemon is shutting down | All requests rejected during shutdown |

## Startup Sequence

1. cognitiveosd starts as PID 1 (or supervised by init)
2. Creates `/cognitiveos/run/` directory (tmpfs)
3. Opens Unix socket at `/cognitiveos/run/daemon.sock`
4. Runs initial hardware audit → writes `/cognitiveos/audit/current.json`
5. Loads Raw Model (from `/cognitiveos/models/raw/`)
6. Scans `/cognitiveos/patches/` for installed patches
7. Spawns MCP servers for each installed patch's `runtime.mcp_servers`
8. Loads Wide Model (from `/cognitiveos/models/wide/active/`)
9. Sends `output_deliver` to cli: "CognitiveOS ready"
10. Enters main event loop

## Shutdown Sequence

1. Daemon receives shutdown signal (SIGTERM or system_code `security`/`idle`)
2. Stops accepting new messages
3. Sends `{"type": "shutdown_notice", "reason": "..."}` to all connected components
4. Sends `wide_model_unload` to inference
5. Sends `mcp_unregister` to each running MCP server → waits for acknowledgement (2s timeout then SIGTERM)
6. Closes Unix socket
7. Unmounts `/cognitiveos/run/` (tmpfs)
8. If `security` code: powers off peripherals
9. If `idle` code: suspends to low-power state
10. If `reset` code: wipes data partitions, reboots

## Security

- The socket `/cognitiveos/run/daemon.sock` is owned by root:root with permissions `0700`
- Only processes running as root can connect
- System code validation is performed by the Raw Model before the daemon acts
- The daemon does not listen on any network interface
