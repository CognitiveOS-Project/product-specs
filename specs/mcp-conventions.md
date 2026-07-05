# CognitiveOS MCP Conventions

Version: 1.0.0-draft

## Overview

All CognitiveOS hardware and tool bridges use the **Model Context Protocol (MCP)** as the standard interface between the Wide Model and device capabilities. This document defines CognitiveOS-specific conventions layered on top of the base MCP specification.

MCP specification reference: https://modelcontextprotocol.io (latest stable)

## Transport

### Stdio (Preferred)

CognitiveOS MCP servers default to **stdio transport**. The daemon (`cognitiveosd`) spawns each MCP server as a child process and communicates over stdin/stdout.

```bash
cognitiveosd → spawn → display-mcp --stdio
                           ← JSON-RPC over stdin/stdout →
```

Stdio is preferred because:
- No port allocation or conflicts
- Process lifecycle tied to daemon supervision
- Simple sandboxing (per-process cgroups)
- Works on headless and embedded devices

### HTTP (Alternative)

Use HTTP transport when:
- The MCP server runs on a different machine (e.g., Wide Model on LAN server)
- The MCP server is a shared network resource
- The server cannot be refactored to stdio

HTTP servers expose SSE or Streamable HTTP per the MCP spec. Port range: `18000-18100`.

### Validated Tools

Some tool domains are marked as **validated** — the daemon intercepts calls to these tools and sends a `validate_package_request` RPC to the Raw Model before forwarding to the MCP server. This ensures every operation is checked against OS rules and security conditions.

| Domain | Validation | Reason |
|--------|-----------|--------|
| `cognitiveos.package` | All operations | Package misuse can break the system; every install/remove/update/search/list/info must be authorized |

Read-only operations (search, list, info) skip manifest metadata fetch but still require Raw Model validation for rate limiting.

See [cognitiveosd-api.md](cognitiveosd-api.md#8-package-management) for the full validation flow.

## Tool Naming

All CognitiveOS MCP tools follow a reverse-domain naming scheme:

```
cognitiveos.<domain>.<action>
```

### Domains

| Domain | MCP Server | Examples |
|--------|------------|---------|
| `cognitiveos.display` | display-mcp | `cognitiveos.display.render_image` |
| `cognitiveos.audio` | audio-mcp | `cognitiveos.audio.play`, `cognitiveos.audio.capture` |
| `cognitiveos.network` | network-mcp | `cognitiveos.network.scan`, `cognitiveos.network.connect` |
| `cognitiveos.gpio` | gpio-mcp | `cognitiveos.gpio.pin_read`, `cognitiveos.gpio.pin_write` |
| `cognitiveos.serial` | serial-mcp | `cognitiveos.serial.send`, `cognitiveos.serial.receive` |
| `cognitiveos.filesystem` | cognitiveosd (built-in) | `cognitiveos.filesystem.list`, `cognitiveos.filesystem.read` |
| `cognitiveos.contacts` | cognitiveosd (built-in) | `cognitiveos.contacts.search` |
| `cognitiveos.system` | cognitiveosd (built-in) | `cognitiveos.system.audit`, `cognitiveos.system.status` |
| `cognitiveos.package` | package-mcp (validated) | `cognitiveos.package.search`, `cognitiveos.package.list`, `cognitiveos.package.install` |

### Rules

1. Tool names use lowercase only
2. Domain segments use singular nouns
3. Actions use imperative verbs (`render`, `play`, `capture`, `send`)
4. Custom patches use their own domain prefix: `<publisher>.<patch-name>.<action>`

## Tool Metadata

Every MCP tool must expose the following metadata in its tool definition:

```json
{
  "name": "cognitiveos.display.render_image",
  "description": "Render an image file to the primary display framebuffer",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Absolute path to the image file"
      }
    },
    "required": ["path"]
  }
}
```

### Required fields

- `name` — Fully qualified tool name (per naming convention above)
- `description` — Clear, single-sentence description of what the tool does
- `inputSchema` — JSON Schema describing all parameters

### Optional but encouraged

- `outputSchema` — JSON Schema of the return value
- `examples` — Array of example invocations
- `cost` — Estimated resource cost (see below)

## Resource Cost Annotations

Tools should optionally declare resource cost hints so the Wide Model can make informed decisions:

```json
{
  "name": "cognitiveos.network.scan",
  "annotations": {
    "cost": {
      "time_ms": 3000,
      "battery_impact": "medium",
      "network_required": true
    }
  }
}
```

## Error Conventions

All tools return errors using a standard envelope:

### Success

```json
{
  "content": [
    {
      "type": "text",
      "text": "<result data>"
    }
  ]
}
```

### Error

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "ERROR:<error_code>:<human-readable message>"
    }
  ]
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| `E_NOT_FOUND` | File, device, or resource not found |
| `E_PERMISSION` | Operation not permitted (should not occur in CognitiveOS, but reserved) |
| `E_BUSY` | Resource is busy (e.g., display already in use) |
| `E_INVALID_PARAM` | Invalid or missing parameter |
| `E_HARDWARE` | Hardware error (device not connected, driver failure) |
| `E_TIMEOUT` | Operation timed out |
| `E_INTERNAL` | Unexpected internal error |

## Registration with cognitiveosd

MCP servers must register with cognitiveosd on startup. Registration is a handshake over the daemon's Unix socket:

### 1. Server announces itself

```json
{
  "type": "mcp_register",
  "server": {
    "name": "display-mcp",
    "transport": "stdio",
    "pid": 1234,
    "tools": [
      "cognitiveos.display.render_image",
      "cognitiveos.display.render_video"
    ]
  }
}
```

### 2. Daemon acknowledges

```json
{
  "type": "mcp_registered",
  "status": "ok",
  "server_id": "display-mcp"
}
```

### 3. Periodic healthcheck

Daemon sends `{"type": "healthcheck"}` to the server every 30 seconds. Server responds with `{"type": "healthcheck_ok", "uptime_seconds": 3600, "tools_healthy": true}`.

### 4. Graceful shutdown

Server sends `{"type": "mcp_shutdown", "reason": "idle_timeout"}`. Daemon acknowledges, then terminates the process.

## Logging

MCP servers log to `/cognitiveos/logs/bridges/<server-name>.log`.

Log format (one line per event):

```
<ISO-8601> [<LEVEL>] <message>
```

Levels: `DEBUG`, `INFO`, `WARN`, `ERROR`

Log rotation is handled by cognitiveosd (size-based, 5 × 10 MB max).

## Healthcheck Endpoint

HTTP-transport servers must expose a healthcheck endpoint:

```
GET /health
→ 200 OK
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "tools": ["cognitiveos.display.render_image", "cognitiveos.display.render_video"],
  "version": "1.0.0"
}
```

Stdio-transport servers respond to `{"type": "healthcheck"}` as described above.

## Versioning

MCP servers SHALL expose their version in:

1. The `--version` flag (e.g., `display-mcp --version` → `display-mcp 1.0.0`)
2. The `cognitive.json` manifest of their parent .cgp patch
3. The healthcheck response (HTTP) or healthcheck message (stdio)
