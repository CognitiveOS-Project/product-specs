# ADR-004: Package Manager MCP Bridge — AI-Initiated Package Management

**Status:** Accepted  
**Date:** 2026-07-05  
**Author:** CognitiveOS SDLC

## Context

CognitiveOS's package manager (`cpm`) is a CLI tool — it must be invoked from a shell. The Wide Model (AI) communicates only through text generation and MCP tool calls. There is currently no mechanism for the AI to autonomously discover, install, or remove packages in response to human requests.

For example, if the user says "Show me my photos from last weekend," the Wide Model needs to determine it lacks an image-rendering capability, find a suitable package, install it, and then use it — all without human intervention.

This requires three things:
1. **MCP tools** that package operations (search, install, remove, list, info, update)
2. **Security validation** — every package operation must be checked by the Raw Model against OS rules and security conditions before execution
3. **System prompt** — the Wide Model must know it can autonomously discover and install capabilities

### Architectural Constraints

From the existing security model:

| Constraint | Rationale |
|------------|-----------|
| Wide Model cannot execute shell commands | Runs as `widemodel` user, seccomp-blocked |
| Wide Model cannot invoke `cpm` directly | No shell access, no filesystem write to `/cognitiveos/patches/` |
| Package installs must be validated by the Raw Model | Raw Model is the trusted supervisor; it checks OS rules, security conditions, and denies packages containing `raw_model` descriptors |
| Raw Model cannot be hot-reloaded | A `.cgp` package containing a `raw_model` field must never be auto-downloaded |
| Raw Model has no knowledge of MCP | It is a pure guardrail GGUF communicating via JSON-RPC 2.0 |

## Decision

Add a **6th core MCP bridge** — `package-mcp` — to the `core-mcp-bridges` repo, and introduce a **validation hook** in the daemon's MCP routing layer. All `cognitiveos.package.*` tool calls are intercepted by the daemon and validated against the Raw Model before forwarding.

### Architecture

```
Wide Model: calls cognitiveos.package.install("photo-viewer")
  → daemon intercepts (validated tool namespace)
  → daemon sends validate_package_request RPC to Raw Model
       { operation, package_name, version, manifest_metadata }
  → Raw Model checks compiled-in rules:
       - has_raw_model? → deny
       - critical package? → deny
       - rate limit exceeded? → deny
       - sufficient disk space? → deny
       - registry allowlist? → deny
  → if approved: daemon forwards to package-mcp bridge
  → package-mcp execs `cpm install photo-viewer`
  → result flows back: package-mcp → daemon → Wide Model
```

### 1. Package MCP Bridge (`package-mcp`)

A new binary in `core-mcp-bridges/package/` that wraps the `cpm` CLI, exposing package operations as MCP tools:

| Tool | Description | Maps to |
|------|-------------|---------|
| `cognitiveos.package.search` | Search registry for packages | `cpm search <query>` |
| `cognitiveos.package.list` | List installed packages | `cpm list` |
| `cognitiveos.package.install` | Install a package from registry | `cpm install <name> [--version]` |
| `cognitiveos.package.remove` | Uninstall a package | `cpm remove <name>` |
| `cognitiveos.package.info` | Show package manifest details | `cpm info <name>` |
| `cognitiveos.package.update` | Update a package to latest | `cpm update <name>` |

The bridge follows the same pattern as the 5 existing bridges (display-mcp, audio-mcp, etc.): MCP JSON-RPC 2.0 over stdio, registered via tool discovery, spawned by the daemon at startup.

### 2. Raw Model Validation (`validate_package_request` RPC)

A new JSON-RPC method on `cograw` that validates every package operation before execution. The Raw Model uses compiled-in rules (not NN inference) for deterministic, fast decisions:

| Rule | Operation | Action |
|------|-----------|--------|
| Manifest has `raw_model` field | install | Deny |
| Package is critical system component (`cognitiveosd`, `raw-model`, `base-os`) | install, remove, update | Deny |
| Rate limit exceeded (>5 operations / 5 min) | all | Deny |
| Disk space insufficient for install | install, update | Deny |
| Registry not in allowlist | install, update | Deny |
| Search, list, info with no violations | read-only | Allow |

**Input:**
```json
{
  "operation": "install" | "remove" | "update" | "search" | "list" | "info",
  "package_name": "photo-viewer",
  "version": "1.0.0",
  "manifest_metadata": {
    "has_raw_model": false,
    "disk_space_mb": 128,
    "registry": "registry.cognitiveos.org",
    "is_critical": false
  }
}
```

**Output:**
```json
{
  "status": "approved" | "denied",
  "reason": "",
  "command": "cpm install photo-viewer"
}
```

### 3. Daemon Validation Hook

The daemon's MCP routing layer (`mcp_lifecycle.go`) is extended with a validation hook. When an `Invoke()` call targets a tool in the `cognitiveos.package.*` namespace, the daemon:

1. Fetches the manifest metadata from the registry (for `install`/`update`)
2. Sends `validate_package_request` to the Raw Model
3. If denied: returns error to the Wide Model
4. If approved: forwards the call to `package-mcp`

Read-only operations (`search`, `list`, `info`) skip the manifest fetch but still require Raw Model validation (to enforce rate limits).

### 4. Base System Prompt

A new daemon-level system prompt tells the Wide Model it can autonomously discover and install capabilities:

> You can autonomously discover and install capabilities from the CognitiveOS package registry. If a user asks for something you cannot do, search for a package that provides that capability and install it.

### Startup Order

The current startup sequence already has the correct order:
1. Daemon starts
2. Opens socket
3. Hardware audit
4. **Loads Raw Model** (validation available after this point)
5. Scans patches
6. **Spawns MCP bridges** (package-mcp spawned here)
7. Loads Wide Model

No change needed — Raw Model is always loaded before bridges are spawned.

## Consequences

**Positive:**
- AI can autonomously discover and install capabilities without human intervention
- All package operations are validated by the Raw Model — no bypass possible
- Consistent with existing MCP bridge pattern (6th bridge, same lifecycle)
- `package-mcp` is a core bridge on the read-only root partition — cannot be tampered with
- Raw Model validation uses compiled-in rules — deterministic, no NN hallucination
- Read-only ops (search/list/info) also rate-limited by Raw Model
- No new repos or deployment mechanisms needed

**Negative:**
- Daemon MCP routing gains complexity (validation hook per namespace)
- `package-mcp` requires `cpm` binary on `PATH` at runtime — dependency on cpm installation
- Network required for registry operations — offline mode unavailable
- Adding new validation rules requires a firmware reflash (Raw Model recompile)

**Risks:**
- Wide Model could spam package operations (mitigated by Raw Model rate limiting: 5 ops / 5 min)
- Network failure during `cpm install` could leave system in partial state (mitigated by cpm's atomic install: all-or-nothing via temp dir + rename)
- Registry metadata must be fetched before validation — adds latency to install flow (mitigated by fetching concurrent with Raw Model validation preparation)

## Alternatives Considered

1. **`cpm serve-mcp` subcommand** — rejected: package management is a core OS capability like display/audio/network; belongs in core-mcp-bridges alongside the other hardware abstraction layer bridges
2. **Daemon-internal handler (no MCP bridge)** — rejected: inconsistent with all other tool namespaces; would require duplicating MCP server lifecycle logic
3. **Third-party `.cgp` patch MCP server** — rejected: package management must be available before any patches are installed; core bridge is boot-time available
4. **Wide Model calls `cpm` via shell** — rejected: security model forbids shell access for the Wide Model
5. **No Raw Model validation (daemon validates alone)** — rejected: Raw Model is the trusted supervisor by design; bypassing it for package operations would be a gap in the security model

## References

- `mcp-conventions.md` — MCP tool naming, domains, registration protocol
- `cognitiveosd-api.md` — daemon message protocol, MCP routing
- `raw-model.md` — Raw Model RPC methods, startup sequence
- `cpm-spec.md` — cpm CLI subcommands (search, list, install, remove, info, update)
- `security-model.md` — trust boundaries, process isolation
- `architecture.md` — system architecture, core-mcp-bridges layer
- `filesystem-hierarchy.md` — standard bridge binary and log paths
- `manifest-fields.md` — `raw_model` field in cognitive.json manifest
- ADR-002 — weight download architecture (precedent for provider pattern)
