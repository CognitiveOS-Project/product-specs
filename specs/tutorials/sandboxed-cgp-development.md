# Sandboxed CGP Development: Build, Test, and Verify Locally

This tutorial covers developing Cognitive Patch (`.cgp`) packages in a sandboxed local environment — no registry, no internet, no publishing required. You will learn to scaffold, build, verify, and test packages entirely on your development machine.

## Overview

Sandboxed development means the full CGP lifecycle works offline:

```
┌───────────┐    ┌───────────┐    ┌────────────┐    ┌───────────────┐
│ SCAFFOLD  │───►│  DEVELOP  │───►│   VERIFY   │───►│  LOCAL TEST   │
│           │    │           │    │            │    │               │
│ cpm init  │    │ edit code │    │ cpm verify │    │ cpm install   │
│ + edit    │    │ + pack    │    │ cpm info   │    │ (local file)  │
└───────────┘    └───────────┘    └────────────┘    └───────────────┘
```

**Prerequisites:**
- Go 1.25+ installed
- `cpm` built: `cd cpm && make build`
- An SSH key pair (for future publishing): `ssh-keygen -t ed25519`

## Quick Start

```bash
# 1. Scaffold a new package
cpm init my-skill --template mcp-bridge
cd my-skill

# 2. Write your MCP server (see below)
# ... edit tools/mcp-server ...

# 3. Pack and verify
cpm pack

# 4. Install locally for testing
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./my-skill-0.1.0.cgp
```

## Step 1: Scaffold the Package

`cpm init` creates a skeleton directory with the correct structure for your use case:

| Template | Creates | Best for |
|----------|---------|----------|
| `mcp-bridge` | `cognitive.json`, `tools/`, `.github/` | Wrapping an external tool as an MCP server |
| `prompt-only` | `cognitive.json`, `prompts/`, `.github/` | Pure prompt/persona skill (no binary) |
| `gguf-model` | `cognitive.json`, `.github/` | Distributing a GGUF model with HuggingFace weights |
| `firmware` | `cognitive.json`, `.github/` | MCU/ESP32 firmware for the Raw Model |
| `default` | `cognitive.json`, `prompts/`, `tools/`, `.github/` | Basic skill with prompts and tools |
| `full` | All files with placeholders | Reference manifest with every field |

```bash
cpm init my-skill --template mcp-bridge
```

This creates:

```
my-skill/
├── cognitive.json          # Manifest (required)
├── tools/
│   └── mcp-server          # Placeholder MCP server
└── .github/
    ├── docker/Dockerfile.ci
    └── workflows/
        ├── ci.yml
        └── publish.yml
```

Every template also generates CI/CD files (Alpine-based Docker build, GitHub Actions) — these are ignored during local development.

## Step 2: Understand the Archive Structure

A `.cgp` file is a **tar.gz** archive. When you `cpm pack`, this is what gets created:

```
my-skill-0.1.0.cgp (tar.gz)
├── cognitive.json              # Manifest
├── prompts/
│   └── system.md              # System prompt (if present)
├── tools/
│   └── mcp-server             # MCP server binary or script
└── weights/
    └── model.gguf             # Weight file (if method: local)
```

**What IS in the archive:**
- `cognitive.json` (with `${VAR}` placeholders intact — never resolved at pack time)
- Prompt files
- MCP server binaries
- Local weight files (`method: local`)

**What is NOT in the archive:**
- Resolved secret values
- CI/CD workflow files (`.github/`)
- Weight files downloaded at install time (`method: remote`)
- Registry metadata

## Step 3: Write the Manifest

Edit `cognitive.json` — your package's identity card. At minimum, three fields are required:

```json
{
  "name": "my-skill",
  "version": "0.1.0",
  "description": "What this skill does"
}
```

### Common Manifest Patterns

#### MCP Bridge with Tool

```json
{
  "name": "my-bridge",
  "version": "0.1.0",
  "description": "Wraps an external tool as an MCP server",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "os": ["linux"],
    "arch": ["amd64", "arm64"],
    "min_ram_mb": 256,
    "min_storage_mb": 10
  },
  "runtime": {
    "tools_root": "tools",
    "mcp_servers": [
      {
        "name": "my-tool",
        "command": "tools/mcp-server",
        "transport": "stdio"
      }
    ],
    "background": true,
    "capabilities": [
      "com.example.my-tool.execute",
      "com.example.my-tool.status"
    ]
  }
}
```

#### Prompt-Only Skill

```json
{
  "name": "voice-assistant",
  "version": "0.1.0",
  "description": "Voice-controlled personal assistant",
  "runtime": {
    "system_prompt": "prompts/system.md",
    "capabilities": ["voice.control", "voice.transcribe"]
  }
}
```

#### Model with Remote Weights

```json
{
  "name": "my-model",
  "version": "0.1.0",
  "description": "A GGUF model for code analysis",
  "brain": {
    "wide_model": {
      "base_model": "qwen2.5-coder:7b",
      "weights": {
        "method": "remote",
        "remote": {
          "source": "huggingface",
          "model_id": "Qwen/Qwen2.5-Coder-7B-GGUF",
          "filename": "qwen2.5-coder-7b-q4_k_m.gguf",
          "format": "gguf",
          "quant": "Q4_K_M",
          "size_bytes": 4567890,
          "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
        }
      }
    }
  },
  "runtime": {
    "capabilities": ["code.analysis", "code.review"]
  }
}
```

#### Package with Secrets and Unlock Codes

```json
{
  "name": "premium-analytics",
  "version": "1.0.0",
  "description": "Advanced analytics with paid tier",
  "unlock_codes": [
    "ANALYTICS-PRO-2026",
    "ANALYTICS-ENTERPRISE"
  ],
  "runtime": {
    "mcp_servers": [
      {
        "name": "analytics",
        "command": "tools/analytics-server",
        "env": {
          "API_KEY": "${ANALYTICS_API_KEY}"
        },
        "transport": "stdio"
      }
    ],
    "capabilities": ["analytics.dashboard", "analytics.export"]
  }
}
```

The `${ANALYTICS_API_KEY}` placeholder is resolved at install time from the secrets store — never stored in the archive.

### Key Manifest Fields Reference

| Field | Purpose |
|-------|---------|
| `name` | Unique package identifier (reverse-domain recommended) |
| `version` | SemVer version string |
| `description` | Human-readable description |
| `hardware_requirements` | RAM, storage, arch, NPU requirements |
| `hardware_dependencies` | System packages needed (apk, npm, pip, etc.) |
| `dependencies` | Other CGP packages required (SemVer ranges) |
| `brain.wide_model` | Large model config (remote/local/cloud weights) |
| `brain.raw_model` | Self-contained firmware model |
| `runtime.mcp_servers` | MCP servers to spawn |
| `runtime.system_prompt` | Path to system prompt file |
| `runtime.capabilities` | Declared functions for package discovery |
| `runtime.background` | Run as always-listening service |
| `unlock_codes` | Gated content requiring `--unlock` flag |
| `training` | LoRA fine-tuning configuration |

See [Manifest Fields](../manifest-fields.md) for the complete field reference.

## Step 4: Write an MCP Server

MCP servers communicate with cognitiveosd over **stdio JSON-RPC**. The daemon sends tool invocation requests; your server responds with results.

### Minimal MCP Server (Python)

```python
#!/usr/bin/env python3
"""Minimal MCP server — responds to tool calls over stdio."""
import sys
import json

def handle_request(request):
    method = request.get("method", "")

    if method == "mcp_list_tools":
        return {
            "tools": [
                {
                    "name": "my-tool.execute",
                    "description": "Execute my custom tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string", "description": "Input text"}
                        },
                        "required": ["input"]
                    }
                }
            ]
        }

    if method == "my-tool.execute":
        args = request.get("params", {}).get("arguments", {})
        return {"content": [{"type": "text", "text": f"Result: {args.get('input', '')}"}]}

    return {"error": {"code": -32601, "message": f"Unknown method: {method}"}}

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    request = json.loads(line)
    response = handle_request(request)
    response["id"] = request.get("id")
    print(json.dumps(response), flush=True)
```

### Minimal MCP Server (Go)

```go
package main

import (
    "bufio"
    "encoding/json"
    "fmt"
    "os"
)

type Request struct {
    Method string                 `json:"method"`
    Params map[string]interface{} `json:"params"`
    ID     interface{}            `json:"id"`
}

type Response struct {
    ID      interface{} `json:"id"`
    Content []struct {
        Type string `json:"type"`
        Text string `json:"text"`
    } `json:"content,omitempty"`
    Tools []struct {
        Name        string      `json:"name"`
        Description string      `json:"description"`
        InputSchema interface{} `json:"inputSchema"`
    } `json:"tools,omitempty"`
}

func main() {
    scanner := bufio.NewScanner(os.Stdin)
    for scanner.Scan() {
        var req Request
        json.Unmarshal(scanner.Bytes(), &req)

        resp := Response{ID: req.ID}
        switch req.Method {
        case "mcp_list_tools":
            resp.Tools = []struct {
                Name        string      `json:"name"`
                Description string      `json:"description"`
                InputSchema interface{} `json:"inputSchema"`
            }{{
                Name:        "my-tool.execute",
                Description: "Execute my custom tool",
                InputSchema: map[string]interface{}{
                    "type": "object",
                    "properties": map[string]interface{}{
                        "input": map[string]string{"type": "string"},
                    },
                    "required": []string{"input"},
                },
            }}
        case "my-tool.execute":
            args, _ := req.Params["arguments"].(map[string]interface{})
            input, _ := args["input"].(string)
            resp.Content = []struct {
                Type string `json:"type"`
                Text string `json:"text"`
            }{{Type: "text", Text: fmt.Sprintf("Result: %s", input)}}
        }

        out, _ := json.Marshal(resp)
        fmt.Println(string(out))
    }
}
```

### MCP Protocol Summary

| Message | Direction | Purpose |
|---------|-----------|---------|
| `mcp_list_tools` | daemon → server | Discover available tools |
| `mcp_register` | server → daemon | Announce capabilities |
| `mcp_registered` | daemon → server | Acknowledge registration |
| `<tool_name>` | daemon → server | Invoke a tool |
| `mcp_shutdown` | daemon → server | Graceful shutdown |

Tool naming convention: `cognitiveos.<domain>.<action>` (e.g., `cognitiveos.email.send`, `cognitiveos.filesystem.read`).

See [MCP Conventions](../mcp-conventions.md) for the full protocol specification.

### Make the Server Executable

```bash
chmod +x tools/mcp-server
```

`cpm verify` checks that all files in `tools/` are valid executables (ELF binary or shebang `#!` script). Non-executable files in `tools/` cause verification failure (error V012).

## Step 5: Write a System Prompt

If your package includes a system prompt, create it at the path specified in `runtime.system_prompt`:

```bash
mkdir -p prompts
cat > prompts/system.md << 'EOF'
You are a helpful assistant with access to custom tools.

When the user asks you to execute a task, use the my-tool.execute tool
with their input as the argument.

Always confirm the result before moving to the next task.
EOF
```

The daemon merges system prompts from all installed packages into a single prompt chain. Each prompt is prepended to the Wide Model's context.

## Step 6: Pack and Verify

### Pack the Archive

```bash
cpm pack
```

Output:
```
✓ my-skill-0.1.0.cgp is valid (my-skill v0.1.0)
✓ Packaged manifest as my-skill-0.1.0.cgp
```

`cpm pack` automatically runs `cpm verify` on the generated archive. If verification fails, the `.cgp` is deleted.

The output filename follows convention:
- With hardware requirements but no OS/arch: `<name>-<version>.cgp`
- With OS/arch in manifest: `<name>-<version>-<os>-<arch>.cgp`
- No hardware requirements: `<name>-<version>-universal.cgp`

### Verify Manually

```bash
cpm verify my-skill-0.1.0.cgp
```

Output:
```
✓ my-skill-0.1.0.cgp is valid (my-skill v0.1.0)
```

### What `cpm verify` Checks

The verification runs 12 checks in order:

| Code | Check | Failure |
|------|-------|---------|
| V001 | File is openable | File not found or permission denied |
| V002 | Valid gzip format | Not a gzip file |
| V003 | Valid tar format | Not a tar archive |
| V005 | `cognitive.json` exists in archive root | Missing manifest |
| V004 | Manifest is parseable JSON | Malformed JSON |
| V006 | Validates against JSON Schema | Missing required fields, invalid types |
| V010 | Hardware bounds sane | `min_ram_mb` > 1TB or `min_storage_mb` > 1TB |
| V011 | Hardware dependencies valid | Invalid package manager or stage |
| V007 | System prompt file exists | `runtime.system_prompt` points to missing file |
| V008 | MCP server binaries exist | `runtime.mcp_servers[].command` points to missing binary |
| V009 | Adapter file exists | `brain.adapter` points to missing file |
| V012 | Executables are valid | Non-executable files in `tools/` |

Common fix: if V008 fails, ensure the binary path in `mcp_servers[].command` matches the actual file location in the archive (relative to the archive root).

### Inspect Package Info

```bash
cpm info --json --manifest cognitive.json
```

Output:
```json
{
  "name": "my-skill",
  "version": "0.1.0",
  "description": "What this skill does",
  "author": "Your Name",
  "license": "MIT",
  "filename": "my-skill-0.1.0.cgp"
}
```

## Step 7: Local Testing

### Use Environment Variables for Isolation

CPM uses these environment variables to redirect file operations away from the real `/cognitiveos/` filesystem:

```bash
export CPM_PATCHES_DIR=/tmp/cpm-test/patches
export CPM_CACHE_DIR=/tmp/cpm-test/cache
```

This lets you test installs without root access or affecting the real system.

### Install from Local File

```bash
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./my-skill-0.1.0.cgp
```

Output:
```
✓ Installed my-skill v0.1.0
  Path: /tmp/cpm-test/patches/my-skill
```

### Test Secret Resolution

If your manifest uses `${VAR}` placeholders:

```bash
# Add a test secret
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm secret add API_KEY test-key-123

# Install — secrets are resolved during install
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./my-skill-0.1.0.cgp

# Verify the resolved value in the installed manifest
cat /tmp/cpm-test/patches/my-skill/cognitive.json | grep API_KEY
# Should show "API_KEY": "test-key-123" (not the placeholder)
```

### Test Unlock Codes

If your manifest includes `unlock_codes`:

```bash
# Without unlock — blocked
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./premium-analytics-1.0.0.cgp
# ERROR:E012: package requires unlock code

# With unlock — server verifies the code
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./premium-analytics-1.0.0.cgp --unlock ANALYTICS-PRO-2026
```

Note: unlock verification requires a running registry server. During local sandbox testing without a registry, you can test the flag handling but not the full verification flow.

### Test Cloud API Reachability

If your manifest uses `method: cloud`:

```bash
# Store the API key
cpm secret add OPENAI_API_KEY sk-abc123 --scope global

# Install — tests API reachability via HTTP HEAD
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install ./my-skill-0.1.0.cgp
```

CPM tests the cloud API endpoint at install time. If the endpoint is unreachable, installation fails with a clear error.

### Run the CI Pipeline Locally

Every template includes a Dockerfile that builds the package in an Alpine container:

```bash
# Build the CI container
docker build -f .github/docker/Dockerfile.ci -t my-skill-ci .

# Extract the package
docker create --name extract my-skill-ci
docker cp extract:/out/my-skill-0.1.0.cgp .
docker cp extract:/out/pkg.json .
docker rm extract

# Inspect the result
cat pkg.json
```

This verifies the package builds correctly in a clean Alpine environment — matching what CI will do.

## Step 8: Sandbox Isolation

When a `.cgp` package is installed on a running CognitiveOS system, the daemon applies three layers of isolation to every MCP server:

### Cgroup Resource Limits

Every MCP server is placed in a cgroup with strict limits:

| Resource | Default Limit | Cgroup Control |
|----------|---------------|----------------|
| RAM | 512 MB | `memory.max` |
| CPU | 25% of one core | `cpu.max` (25000/100000) |
| Processes | 16 PIDs | `pids.max` |
| Disk I/O | 10 MB/s read, 5 MB/s write | `io.max` |

Cgroup path: `/sys/fs/cgroup/cognitiveos/<server-name>/`

### Chroot Filesystem

Each MCP server is chrooted to its own patch directory:

```
/cognitiveos/patches/<name>/    ← server sees this as /
├── cognitive.json
├── tools/
│   └── mcp-server
└── weights/
```

The server cannot access files outside its patch directory.

### Seccomp System Call Filter

Blocked system calls include: `mount`, `umount2`, `reboot`, `kexec_load`, `init_module`, `bpf`, `ptrace`, `swapon`, `iopl`, `ioperm`.

### Security Zones

```
┌─────────────────────────────────────────────────┐
│  TRUSTED ZONE                                    │
│  Raw Model (firmware, read-only)                 │
│  System Codes (wake, idle, security, reset)      │
│  Hardware audit                                  │
│                                                  │
│  ↕ Unix socket (restricted, checksum-verified)   │
│                                                  │
│  UNTRUSTED ZONE                                  │
│  Wide Model, MCP Servers, patches/, data/        │
└─────────────────────────────────────────────────┘
```

MCP servers run in the untrusted zone. The daemon validates `cognitiveos.package.*` tool calls by sending a `validate_package_request` to the Raw Model before forwarding.

See [Security Model](../security-model.md) for the full isolation specification.

## Step 9: CI Pipeline

Every `cpm init` template generates GitHub Actions workflows:

### CI Workflow (`ci.yml`)

Triggers on push/PR to `main` or `development`:
1. Sets up QEMU + Docker Buildx
2. Builds Alpine container with `Dockerfile.ci`
3. Runs `cpm pack` + `cpm info --json` inside the container
4. Extracts `.cgp` and `pkg.json` as artifacts

### Publish Workflow (`publish.yml`)

Triggers on `v*` tags:
1. Same build as CI
2. Creates a GitHub Release with the `.cgp` as an asset

### Dockerfile.ci

The CI Dockerfile builds in a clean Alpine environment:

```dockerfile
FROM golang:1.26-alpine AS builder
RUN apk add --no-cache git jq
RUN go install github.com/CognitiveOS-Project/cpm/cmd/cpm@latest
WORKDIR /workspace
COPY . .
RUN mkdir -p /out && \
    cpm pack && \
    mv *.cgp /out/ && \
    cpm info --json > /out/pkg.json
FROM scratch
COPY --from=builder /out/ /out/
```

This ensures the package builds identically in CI and locally.

## Step 10: Prepare for Publishing (Optional)

When you're ready to publish, see the full publishing tutorial:

1. **Generate SSH key**: `ssh-keygen -t ed25519 -f ~/.ssh/cognitiveos`
2. **Sign up**: `cpm auth signup --key ~/.ssh/cognitiveos.pub`
3. **Register key**: `cpm auth register --key ~/.ssh/cognitiveos.pub`
4. **Claim key** in the [Web UI](registry-server-web-ui.md)
5. **Grant publish permission** in the Web UI
6. **Publish**: `cpm publish my-skill-0.1.0.cgp --key ~/.ssh/cognitiveos`

See [Publishing CGP Packages](cgp-publishing.md) for the complete flow.

## Troubleshooting

### V005: `cognitive.json` not found

The manifest must be at the archive root — not inside a subdirectory:

```bash
# Wrong — manifest in subdirectory
my-skill/
└── src/
    └── cognitive.json

# Correct — manifest at root
my-skill/
└── cognitive.json
```

### V008: MCP server binary not found

The path in `mcp_servers[].command` is relative to the archive root:

```json
// Wrong — points to tools/bin/mcp-server but file is at tools/mcp-server
"command": "tools/bin/mcp-server"

// Correct — matches actual file location
"command": "tools/mcp-server"
```

### V012: Non-executable files in tools/

All files in `tools/` must be valid executables:

```bash
# Fix permissions
chmod +x tools/mcp-server

# Or use a shebang for scripts
echo '#!/usr/bin/env python3' > tools/my-script.py
```

### Schema validation errors

Run `cpm verify` for detailed error messages. Common issues:
- Missing required fields (`name`, `version`, `description`)
- Invalid SemVer format in `version`
- Invalid capability pattern (must match `^[a-z][a-z0-9._-]+$`)

### Pack fails silently

Check that `cognitive.json` is valid JSON:

```bash
python3 -m json.tool cognitive.json
```

## Related Tutorials

- [CGP Lifecycle](cgp-lifecycle.md) — full lifecycle including publish and install from registry
- [CPM Workflow](cpm-workflow.md) — command reference for all CPM operations
- [Secret Management](secret-management.md) — `${VAR}` placeholders and scope hierarchy
- [Publishing CGP Packages](cgp-publishing.md) — end-to-end publish flow with SSH auth
- [Download Weights](download-weights.md) — fetching GGUF models from HuggingFace
- [Registry Server Web UI](registry-server-web-ui.md) — managing keys and publish permissions
