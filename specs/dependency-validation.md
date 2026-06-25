# Dependency and Third-Party Content Validation

Version: 1.0.0-draft

## Overview

CognitiveOS downloads and runs third-party content — `.cgp` packages, MCP server binaries, GGUF models, and tools. Because the OS operates without human supervision, every validation must be **automated, deterministic, and fail-closed** by default. No prompts, no warnings that can be ignored, no partial states.

This spec defines the validation rules, the action for each rule, and the quarantine flow for content that fails validation.

## Design Principles

| Principle | Meaning |
|-----------|---------|
| **Automated pipeline** | All validations run inline during publish/install/spawn/load — no human prompts |
| **Fail closed** | Any check that fails = operation aborted, state rolled back |
| **Quarantine, don't ignore** | Failed content preserves evidence in `/cognitiveos/quarantine/` for automated sweep or later inspection |
| **Deterministic** | Same input always produces the same outcome — no random ordering, no race conditions |
| **No side effects during install** | Install writes files only; starting services (spawning MCPs, loading models) is a separate explicit action |

## Content Types

| Type | Format | Delivered Via | Validation Points |
|------|--------|---------------|-------------------|
| `.cgp` package | tar.gz with `cognitive.json` manifest | Registry-server download | Publish (registry), Install (cpm) |
| MCP server binary | ELF executable | Bundled in `.cgp` (`tools/`) | Publish (registry), Spawn (cognitiveosd) |
| GGUF model | GGUF format file | Registry download or distro-baked | Load (inference engine) |
| Tool binary | ELF executable | Bundled in `.cgp` (`tools/`) | Same as MCP server |

## Validation Rules

### A. Publish-time Rules (Registry-Server)

These run when a publisher uploads a `.cgp` to the registry. Failures reject the publish — they never reach any client.

| # | Validation | Pass | Fail Action |
|---|-----------|------|-------------|
| A1 | `cognitive.json` exists inside the `.cgp` and is valid JSON | Proceed | **Reject publish** (HTTP 422), return parse error |
| A2 | Manifest matches `cognitive.schema.json` — all required fields present, no unknown fields, types match schema | Proceed | **Reject publish** (HTTP 422), return schema violations |
| A3 | SHA-256 checksum computed from the full `.cgp` blob | Store checksum as `sha256` field in registry metadata | **Reject publish** if blob is unreadable (HTTP 422) |
| A4 | Dependency graph: no cycles | Proceed | **Reject publish** (HTTP 422), list cycle path |
| A5 | All transitive dependencies exist in registry at declared versions | Proceed | **Reject publish** (HTTP 422), list unresolvable deps |
| A6 | No transitive dependency has status `buggy` | Proceed | **Reject publish** (HTTP 422), list buggy deps |
| A7 | All files referenced in `runtime.mcp_servers[].command` and `contents` exist inside the `.cgp` archive | Proceed | **Reject publish** (HTTP 422), list missing files |
| A8 | Declared `hardware_requirements` values are within sane bounds (`min_ram_mb` ≤ 1048576, `min_storage_mb` ≤ 1073741824, etc.) | Proceed | **Reject publish** (HTTP 422), return field that exceeds bounds |
| A9 | `source.repository` is a valid URL with a known git provider host (github.com, gitlab.com, bitbucket.org) or a self-hosted domain that serves a git page | Proceed | **Reject publish** (HTTP 422), "invalid or unreachable repository URL" |
| A10 | `source.issues` is a valid URL that responds with HTTP 200 within 10 seconds | Proceed | **Reject publish** (HTTP 422), "invalid or unreachable issues URL" |

**Result of full pass:** Package stored in registry, metadata includes `sha256`, parsed `cognitive.json`, `source` URLs, and computed dependency tree. Clients can now discover and install it.

### B. Install-time Rules (cpm)

These run when cpm downloads and installs a `.cgp`. All deps in the tree are resolved and validated **before any files are written**. If any rule fails, the entire transaction is rolled back — no partial state.

| # | Validation | Pass | Fail Action |
|---|-----------|------|-------------|
| B1 | SHA-256 of downloaded blob matches `sha256` from registry metadata | Proceed | **Delete download**, log audit event (type: `checksum_mismatch`, expected hash, actual hash) |
| B2 | Re-validate manifest against schema (defense in depth — registry should have caught it, but local validation is cheap) | Proceed | **Delete download**, log audit event |
| B3 | Hardware audit: system RAM ≥ `min_ram_mb`, free storage ≥ `min_storage_mb`, NPU available if `npu_required` | Proceed | **Delete download**, log audit event (type: `insufficient_resources`, field that failed) |
| B4 | All transitive dependencies already installed OR resolvable from registry — no version conflicts | Resolve full tree | **Delete download**, log audit event (type: `dependency_conflict`, details) |
| B5 | No transitive dependency has status `buggy` | Proceed | **Delete download**, log audit event (type: `buggy_dependency`, list buggy versions) |
| B6 | Free disk space ≥ total size of all archives in the dependency tree (pre-flight check) | Proceed | **Delete download**, log audit event (type: `disk_space`, required bytes, available bytes) |
| B7 | `source.issues` URL is reachable (HTTP 200 within 10 seconds) | Proceed | **Log warning**, continue install |
| B8 | Query `source.issues` provider API for open bugs labelled "bug" — if known provider (GitHub/GitLab/Bitbucket), derive API URL automatically; otherwise use `source.issues_api` | Proceed | **Delete download**, log audit event (type: `unreachable_issues_api`, URL) |
| B9 | No open bugs found in provider API response | Proceed | **Delete download**, log audit event (type: `known_bugs`, count, list of bug URLs) |

**Provider API URL derivation:**

If the `source.issues` URL matches a known provider, cpm derives the bugs API endpoint from `source.repository` automatically:

| Provider | Repository pattern | API URL pattern (bugs) | Response parser |
|----------|-------------------|------------------------|-----------------|
| **GitHub** | `https://github.com/{owner}/{repo}` | `https://api.github.com/repos/{owner}/{repo}/issues?labels=bug&state=open&per_page=1` | JSON array — open bugs exist if array is non-empty |
| **GitLab** | `https://gitlab.com/{owner}/{repo}` | `https://gitlab.com/api/v4/projects/{owner}%2F{repo}/issues?labels=bug&state=opened&per_page=1` | JSON array — open bugs exist if array is non-empty |
| **Bitbucket** | `https://bitbucket.org/{owner}/{repo}` | `https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/issues?q=state=%22new%22+AND+kind=%22bug%22` | Paginated JSON — open bugs exist if `values` array is non-empty |
| **Self-hosted / Unknown** | — | Falls back to `source.issues_api` (must be set explicitly) | Raw JSON array — any non-empty response is treated as "bugs exist" |

If the provider is unknown and `source.issues_api` is not set, rule B8 fails (unreachable API).

**Result of full pass:**
1. All `.cgp` archives in the dependency tree are extracted to `/cognitiveos/patches/<name>/<version>/`
2. Each package's manifest is stored at `/cognitiveos/patches/<name>/<version>/cognitive.json`
3. The dependency graph is recorded at `/cognitiveos/patches/.deps.json` for use by uninstall and update operations
4. **No MCP servers are spawned, no binaries are executed** — install is write-only

**Transaction rollback on any failure:**
- All files written during this install transaction are deleted
- The `.deps.json` graph is reverted to its previous state
- The download archive is deleted
- The system is in the exact state it was in before the install began

### C. Spawn-time Rules (cognitiveosd)

These run when cognitiveosd is asked to start an MCP server binary from an installed `.cgp`. The binary was already extracted at install time, and its checksum was verified at publish time, but spawn-time re-verification catches post-install tampering.

| # | Validation | Pass | Fail Action |
|---|-----------|------|-------------|
| C1 | SHA-256 of the binary matches the checksum recorded in the package's manifest at install time | Proceed | **Refuse to spawn**, quarantine binary to `/cognitiveos/quarantine/mcp-<name>-<timestamp>/`, log security alert event |
| C2 | cgroup limits can be applied (memory, CPU, processes, disk I/O) — kernel supports the required subsystems | Apply limits and spawn | **Refuse to spawn**, log audit event (type: `isolation_unavailable`) |
| C3 | Binary is an ELF executable (file magic check) — reject non-ELF or scripts passed as binaries | Proceed | **Refuse to spawn**, quarantine binary, log alert |
| C4 | Binary has execute permission (+x) | Proceed | **Refuse to spawn**, log alert — repair would mean tampering |

**Result of full pass:** Process spawned inside cgroup at `/cognitiveos/patches/<name>/<version>/` with seccomp filter applied, chrooted to its patch directory.

### D. Load-time Rules (Inference Engine)

These run when the inference engine loads a GGUF model file.

| # | Validation | Pass | Fail Action |
|---|-----------|------|-------------|
| D1 | SHA-256 matches registry metadata (when available — not all models are registry-sourced) | Proceed | **Refuse to load**, quarantine file to `/cognitiveos/quarantine/model-<name>-<timestamp>/`, log security alert |
| D2 | Raw Model resource audit: `requested_mb ≤ available_mb` | Proceed | **Refuse to load**, log audit event (type: `insufficient_memory`) |
| D3 | File is valid GGUF format (header magic bytes `GGUF` at offset 0) | Proceed | **Refuse to load**, quarantine file, log alert (type: `invalid_format`) |

### E. Update-time Rules

These run during automated update sweeps (periodic or trigger-based).

| # | Validation | Pass | Fail Action |
|---|-----------|------|-------------|
| E1 | Update priority: non-buggy LTS > non-buggy beta > non-buggy alpha > buggy (any suffix) | Select candidate | Stay on current version if no candidate |
| E2 | Full install validation (rules B1-B6) runs on the candidate before applying the update | Apply update | Stay on current version, log why candidate failed |
| E3 | If currently installed version is declared `buggy` post-install, treat as highest-priority upgrade target | Auto-upgrade to nearest non-buggy version | If none exists, quarantine the package, log alert |
| E4 | Uninstall/removal refused if any installed package depends on the one being removed | Refuse removal | Surface dependent list |

## Version Status Lifecycle

```
active  ──────►  deprecated  ──────►  buggy
  │                                       │
  │                                       │
  └──────►  buggy (direct, skip deprecation)
```

| Status | Meaning | Can Be Declared As Dependency | Can Be Installed |
|--------|---------|-------------------------------|------------------|
| `active` | Current, maintained | Yes | Yes |
| `deprecated` | No longer maintained, no known bugs | Yes | Yes (no priority) |
| `buggy` | Has a known bug, should not be used | **No** | **No** (except for bug-fix upgrades) |

**Transition actions:**
- `active → deprecated`: Existing installs keep working; new installs get a deprecation warning logged; auto-update sweep prefers non-deprecated alternatives
- `active → buggy` or `deprecated → buggy`: Registry rejects any future publish that declares it as a dep; cpm refuses any new install that resolves to it; installed instances become highest-priority upgrade targets
- `buggy → active` (fix released): New publish allowed; cpm auto-upgrades installed instances

## Quarantine Flow

When a fail action specifies `quarantine`:

```
Validation fail at spawn/load
       ↓
Copy file(s) to /cognitiveos/quarantine/<type>-<name>-<timestamp>/
       ↓
Write structured audit event:
  {
    "type": "checksum_mismatch" | "invalid_format" | "tamper_detected",
    "component_type": "mcp" | "model" | "tool",
    "name": "<component name>",
    "version": "<version if known>",
    "expected_hash": "<sha256 from metadata>",
    "actual_hash": "<computed sha256>",
    "origin": "<registry URL or file path>",
    "timestamp": "<ISO 8601>"
  }
       ↓
Delete original from /cognitiveos/patches/ or /cognitiveos/models/
       ↓
System continues — component is simply unavailable
```

The quarantine directory is on a separate partition with limited size (1 GB). When the quarantine exceeds 80% capacity, the oldest entries are automatically purged (FIFO).

## Registry API Additions

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `PATCH` | `/v1/packages/<name>/<version>/status` | Set status: `active`, `deprecated`, `buggy` |
| `GET` | `/v1/packages/<name>/<version>` | Returns `sha256`, `status`, parsed `manifest` (dependencies, runtime, hardware_requirements) |
| `GET` | `/v1/packages/<name>/dependencies?version=<version>` | Returns the full transitive dependency tree for a package version |
| `POST` | `/v1/packages/<name>/<version>/validate` | Trigger re-validation of an existing package (re-checks rules A1-A8 against stored blob) |

## Implementation Order

| Phase | What | Rules | Risk |
|-------|------|-------|------|
| 1 | Registry-server: manifest parsing + schema validation + SHA-256 on publish | A1, A2, A3 | Low — server-side only, no client impact |
| 2 | Registry-server: dep graph check, buggy check, file reference check | A4, A5, A6, A7, A8 | Low — same layer |
| 3 | Registry-server: status endpoints, dependency endpoint | E3, dep resolution API | Low — API additions |
| 4 | Registry-server: validate endpoint, re-validation trigger | Post-publish audit | Low |
| 5 | cpm: enforce SHA-256 match, manifest re-validation, hardware audit | B1, B2, B3 | Medium — client behavior changes from warn→fail |
| 6 | cpm: transitive dep resolution, buggy check, disk pre-flight, transaction rollback | B4, B5, B6 | Medium — dependency resolver is new logic |
| 7 | cpm: update sweep with buggy upgrade priority, uninstall guard | E1, E2, E3, E4 | Medium — update resolver |
| 8 | cognitiveosd: enforce binary checksum (warn→fail), add quarantine | C1, C4 | High — changes process spawn semantics |
| 9 | cognitiveosd: ELF magic check, cgroup enforcement | C2, C3 | Medium — defense in depth |
| 10 | Inference engine: model checksum + format validation + quarantine | D1, D3 | Medium — model load hardening |
| 11 | Inference engine: Raw Model resource audit integration | D2 | Low — already exists in cograw spec |

## See Also

- [Package Manager (cpm)](https://github.com/CognitiveOS-Project/cpm) — install, verify, remove commands
- [Registry Server](https://github.com/CognitiveOS-Project/registry-server) — publish, download, status APIs
- [Registry Protocol](registry-protocol.md) — API specification
- [Security Model](security-model.md) — trust boundaries, isolation, supply chain
- [Raw Model](raw-model.md) — system codes, resource audit, unlock validation
- [Release Strategy](release-strategy.md) — version numbering, update priority, release suffixes
