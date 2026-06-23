# cpm — Cognitive Package Manager Specification

Version: 1.0.0-draft

## Overview

`cpm` is the CognitiveOS package manager. It installs, removes, updates, and publishes `.cgp` (Cognitive Patch) files. It is the npm/pip/apt for the agent era — but hardware-aware, MCP-native, and designed for autonomous AI operation.

## Command Reference

### Global Flags

| Flag | Description |
|------|-------------|
| `--registry <url>` | Override default registry (default: from `/etc/cognitiveos/registries.toml`) |
| `--verbose` | Detailed output |
| `--yes` | Skip confirmation prompts (automatic mode, used by AI) |
| `--no-audit` | Skip hardware audit (force install — use with caution) |

### Commands

#### `cpm install <path|name> [--registry <url>] [--no-audit] [--yes]`

Install a cognitive patch from a local `.cgp` path or a registry name.

```bash
cpm install ./email-manager.cgp
cpm install email-manager                          # resolves from registry
cpm install email-manager --registry https://my-registry.example.com
```

**Exit codes:** 0=ok, 1=generic error, 2=hardware rejection (overridable with --no-audit), 3=dependency failure, 4=network error, 5=already installed

#### `cpm remove <name>`

Remove an installed patch.

```bash
cpm remove email-manager
```

Terminates all MCP servers for this patch, deregisters its tools, deletes `/cognitiveos/patches/<name>/`.

**Exit codes:** 0=ok, 1=not installed, 2=in-use by another patch (dependency)

#### `cpm update <name> [--registry <url>]`

Update a patch to the latest version.

```bash
cpm update email-manager
```

Atomic update: download to `/cognitiveos/patches/.staging/`, install there, verify, then swap. On failure: discard staging, keep old version.

**Exit codes:** 0=ok, 1=not installed, 2=already latest, 3=update failed (rolled back), 4=network error

#### `cpm list [--installed] [--available] [--verbose]`

List patches.

```bash
cpm list                          # installed patches
cpm list --available              # available from registry
cpm list --installed --verbose    # detailed view
```

Output (installed):

```
email-manager  1.2.0    email handling (background)
photo-viewer   0.5.0    image display (active)
```

Output (verbose):

```
email-manager  1.2.0    /cognitiveos/patches/email-manager/
  tools: 1 MCP server (imap-smtp-bridge)
  memory: 128 MB
  status: active

photo-viewer  0.5.0    /cognitiveos/patches/photo-viewer/
  tools: 1 MCP server (image-processor)
  memory: 256 MB
  status: active
```

**Exit codes:** 0=ok

#### `cpm info <name>`

Show detailed manifest information.

```bash
cpm info email-manager
```

Output:

```
Name:           com.system.email-manager
Version:        1.2.0
Author:         CognitiveOS
License:        MIT
Description:    Background email triaging, drafting, and notification routing.
Hardware:       2 GB RAM, 150 MB storage
Dependencies:   (none)
MCP servers:    imap-smtp-bridge (stdio)
Installed:      /cognitiveos/patches/email-manager/
Size:           45 MB
```

**Exit codes:** 0=ok, 1=not found

#### `cpm search <query> [--license <spdx>] [--min-ram <mb>] [--page <n>]`

Search the registry for patches.

```bash
cpm search email
cpm search "image processing" --license MIT --min-ram 512
```

Output:

```
Found 3 matches:
  email-manager     1.2.0    Background email handling
  email-crypto      0.3.0    Encrypted email support
  photo-viewer      0.5.0    Image display and editing
```

**Exit codes:** 0=ok, 1=query too short, 2=registry unreachable

#### `cpm publish <path> [--registry <url>]`

Publish a `.cgp` archive to the registry.

```bash
cpm publish ./my-skill-1.0.0.cgp
```

Requires authentication token (from `~/.cognitiveos/cpm-credentials.json` or `CPM_TOKEN` env var).

**Exit codes:** 0=ok, 1=validation failed, 2=auth failed, 3=network error, 4=version already exists

#### `cpm init [<dir>]`

Create a new `.cgp` skeleton directory.

```bash
cpm init my-skill
cd my-skill
# Edit cognitive.json, add prompts/tools/weights
```

Creates the standard `.cgp` directory structure with a default `cognitive.json`:

```
my-skill/
├── cognitive.json
├── prompts/
│   ├── system.md
│   └── templates/
└── tools/
```

**Exit codes:** 0=ok, 1=directory already exists

#### `cpm verify <path>`

Verify a `.cgp` archive integrity.

```bash
cpm verify ./my-skill.cgp
```

Checks:
- Valid tar.gz format
- `cognitive.json` exists and validates against schema
- All referenced files in manifest exist in archive
- No missing dependencies
- Executables in `tools/` have valid shebangs or are ELF binaries

**Exit codes:** 0=valid, 1=invalid format, 2=schema violation, 3=missing file, 4=dependency not met

## Install Lifecycle (Detailed)

### Step 1: Resolve Source

```
Input: "cpm install email-manager"
  1.1 Check if installed already (exit 5 if yes)
  1.2 Check if path is a local file/dir (.cgp file or directory with cognitive.json)
  1.3 If not local, resolve name from registry:
      GET /v1/search?q=email-manager&exact=true
  1.4 Get latest version metadata
  1.5 Download .cgp to /cognitiveos/data/cache/downloads/<name>-<version>.cgp
```

### Step 2: Parse and Validate

```
  2.1 Extract cognitive.json from archive
  2.2 Validate against cognitive.schema.json
  2.3 Fail if invalid (exit 2)
```

### Step 3: Resolve Dependencies

```
  3.1 Read cognitive.json → dependencies field
  3.2 For each dependency:
      3.2.1 Check if already installed and version matches range
      3.2.2 If not, resolve from registry (recursive)
      3.2.3 Check for circular dependencies (fail if circular, exit 3)
  3.3 Install dependencies first (recursive call to install)
```

### Step 4: Hardware Audit

```
  4.1 Read cognitive.json → hardware_requirements
  4.2 Run audit (or read latest /cognitiveos/audit/current.json):
      4.2.1 Check min_ram_mb against available RAM
      4.2.2 Check min_storage_mb against available storage
      4.2.3 Check npu_required against available hardware
  4.3 If hardware requirements not met:
      4.3.1 If --no-audit: proceed with warning
      4.3.2 If --yes or AI mode: report to daemon, daemon decides
      4.3.3 If interactive: print warning, ask "Install anyway? [y/N]"
      4.3.4 If forced no: exit 2
```

### Step 5: Extract

```
  5.1 Create directory: /cognitiveos/patches/<name>/
  5.2 Extract all files from archive
  5.3 Set permissions: tools/mcp-server-* → executable (0755)
  5.4 Write cognitive.json to patch root
```

### Step 6: Spawn MCP Servers

```
  6.1 Read cognitive.json → runtime.mcp_servers
  6.2 For each server:
      6.2.1 Set environment variables from manifest
      6.2.2 Spawn process: <command> <args>
      6.2.3 Wait for mcp_register message on daemon socket
      6.2.4 Timeout: 10 seconds. If no registration, log warning but continue.
```

### Step 7: Register Tools

```
  7.1 Daemon receives mcp_register from each MCP server
  7.2 Tools are indexed in daemon's tool registry
  7.3 Tools become available to the Wide Model
```

### Step 8: Inject System Prompt

```
  8.1 If cognitive.json → runtime.system_prompt exists:
      8.1.1 Prepend contents to Wide Model's system prompt chain
  8.2 If background: true:
      8.2.1 Mark server as always-running
```

## Remove Lifecycle

### Step 1: Check Dependents

```
  1.1 Check if any other installed patch depends on this one
  1.2 If yes: print error "Cannot remove: patch X depends on this" → exit 2
```

### Step 2: Terminate MCP Servers

```
  2.1 Send mcp_unregister to each MCP server
  2.2 Send SIGTERM to each process
  2.3 Wait 3 seconds for graceful shutdown
  2.4 Send SIGKILL to any remaining processes
```

### Step 3: Deregister

```
  3.1 Daemon removes tools from its tool registry
  3.2 Daemon removes system prompt from Wide Model's prompt chain
```

### Step 4: Delete

```
  4.1 Remove /cognitiveos/patches/<name>/
  4.2 Log removal to /cognitiveos/logs/cpm.log
```

## Update Lifecycle

### Step 1: Resolve

```
  1.1 Check patch is installed (exit 1 if not)
  1.2 Resolve latest version from registry
  1.3 If version matches current → exit 2 (already latest)
```

### Step 2: Atomic Install

```
  2.1 Download new version to /cognitiveos/data/cache/downloads/
  2.2 Extract to staging: /cognitiveos/patches/.staging/<name>/
  2.3 Run install steps 2-6 (parse, deps, audit, spawn, register)
  2.4 If any step fails → discard staging → exit 3 (rolled back)
```

### Step 3: Swap

```
  3.1 Notify old MCP servers: prepare for shutdown
  3.2 Stop old daemon MCP servers
  3.3 Move /cognitiveos/patches/<name>/ → /cognitiveos/patches/.trash/<name>/
  3.4 Move /cognitiveos/patches/.staging/<name>/ → /cognitiveos/patches/<name>/
  3.5 Remove trash directory
  3.6 Log update to cpm.log
```

## Hardware Audit

The hardware audit checks these resources:

| Resource | Source | Field in manifest | Unit |
|----------|--------|-------------------|------|
| RAM | `/proc/meminfo` | `min_ram_mb` | MB |
| Storage (free) | `statfs()` on `/cognitiveos/` | `min_storage_mb` | MB |
| NPU availability | `/sys/class/npu/` or `lspci` | `npu_required` | boolean |
| CPU cores | `/proc/cpuinfo` | `min_cpu_cores` | integer |
| Network required | Ping test or connectivity check | Implicit from manifest | boolean |

Audit results are cached at `/cognitiveos/audit/current.json` and refreshed every 60 seconds by cognitiveosd.

## Registry Protocol

### Default Registry

The default registry URL is configured in `/etc/cognitiveos/registries.toml`:

```toml
[default]
url = "https://registry.cognitive-os.org/v1"

[alternative]
url = "https://my-private-registry.example.com/v1"
```

### API Contract

cpm implements the client side of the [registry API](registry-api.md). Key interactions:

**Search:**
```
GET /v1/search?q=<query>&page=1&per_page=20
→ 200
{
  "results": [
    {
      "name": "email-manager",
      "version": "1.2.0",
      "description": "...",
      "license": "MIT",
      "hardware_requirements": { "min_ram_mb": 2048 }
    }
  ],
  "total": 1,
  "page": 1
}
```

**Download:**
```
GET /v1/patches/email-manager/1.2.0/download
→ 200
Content-Type: application/octet-stream
→ binary .cgp data
```

**Metadata:**
```
GET /v1/patches/email-manager/1.2.0
→ 200
{
  "name": "email-manager",
  "version": "1.2.0",
  "description": "...",
  "checksum_sha256": "abc123def..."
}
```

## Error Messages

All errors are printed to stderr in a consistent format:

```
ERROR:<error_code>:<human-readable message>

  Possible causes:
    - Network timeout
    - Registry unreachable

  Try:
    - Check your connection
    - Specify a different registry with --registry
```

| Error Code | Message Pattern |
|------------|----------------|
| `ERR_NOT_FOUND` | `Patch "<name>" not found` |
| `ERR_ALREADY_INSTALLED` | `Patch "<name>" is already installed` |
| `ERR_NOT_INSTALLED` | `Patch "<name>" is not installed` |
| `ERR_HARDWARE` | `Hardware requirements not met: <details>` |
| `ERR_DEPENDENCY` | `Dependency "<name>" not met: <details>` |
| `ERR_CIRCULAR` | `Circular dependency detected: <chain>` |
| `ERR_NETWORK` | `Network error: <details>` |
| `ERR_AUTH` | `Authentication failed` |
| `ERR_VALIDATION` | `Validation failed: <details>` |
| `ERR_INTERNAL` | `Internal error: <details>` |
