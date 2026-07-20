# cpm — Cognitive Package Manager Specification

Version: 1.0.0-draft

## Overview

`cpm` is the CognitiveOS package manager. It installs, removes, updates, and publishes `.cgp` (Cognitive Patch) files. It is the npm/pip/apt for the agent era — but hardware-aware, MCP-native, and designed for autonomous AI operation.

## Universal Protocol Router

cpm is designed as a **universal protocol router** for agentic capabilities. It is not limited to its native `.cgp` schema — it can ingest packages from any ecosystem through a **Registry Dispatcher Pattern**.

When a user runs an install command, cpm parses the target string and dispatches to the appropriate protocol handler. All handlers converge to a single **Normalization Engine** that produces a system-validated `.cgp` manifest.

### 1. Supported Input Formats

| Syntax | Handler | Example |
|--------|---------|---------|
| File path | Local file | `cpm install ./email-manager.cgp` |
| Plain name | Registry (from `registries.toml`) | `cpm install email-manager` |
| `github.com/{owner}/{repo}@{tag}` | Git provider (source tarball) | `cpm install github.com/user/skill@v1.2.0` |
| `gitlab:{owner}/{repo}#{ref}` | Git provider shorthand | `cpm install gitlab:user/skill#dev` |
| `bitbucket:{owner}/{repo}@{tag}` | Git provider shorthand | `cpm install bitbucket:user/skill@v1.0.0` |
| `ghr:{owner}/{repo}@{tag}` | GitHub Releases (pre-built asset) | `cpm install ghr:user/skill@v1.0.0` |
| `npm:@{scope}/{name}` | NPM registry | `cpm install npm:@user/ambient-lighting` |
| `bun:@{scope}/{name}` | Bun registry | `cpm install bun:@user/package` |
| `deno:jsr/@{scope}/{name}` | JSR (Deno) registry | `cpm install deno:jsr/@sys/automation` |
| Raw URL | Direct HTTP fetch | `cpm install https://example.com/skill.cgp` |

### 2. Protocol Handlers

#### Native & Direct Git Providers

Resolves `github.com/{owner}/{repo}@{tag}` by querying the provider's source tarball API:

```
cpm install github.com/user/skill@v1.2.0
→ GET api.github.com/repos/user/skill/tarball/v1.2.0
→ stream archive → Normalization Engine
```

The handler detects the provider from the hostname, maps to the correct API (GitHub tarball API, GitLab repository archive, Bitbucket downloads), and streams the source archive directly — no local `git clone` required.

#### GitHub Releases (ghr)

Resolves `ghr:{owner}/{repo}@{tag}` by querying the repository's release assets.

```
cpm install ghr:user/skill@v1.0.0
→ GET api.github.com/repos/user/skill/releases/tags/v1.0.0
→ find .cgp asset in release assets
→ stream asset → Normalization Engine
```

Prefer `.cgp` assets over source tarballs. If no `.cgp` asset exists, fall back to the source tarball. This handler is ideal for pre-compiled patches containing Go or C extensions that should not be compiled on low-power edge hardware.

#### NPM & Bun Registries

Resolves `npm:@{scope}/{name}` by querying the standard NPM registry protocol.

```
cpm install npm:@user/ambient-lighting
→ GET registry.npmjs.org/@user/ambient-lighting
→ extract dist.tarball URL from metadata
→ download .tgz archive → Normalization Engine
```

Supports any npm-compatible registry (public npm, GitHub Packages, Verdaccio, custom). The handler reads the `cognitive_os` key inside `package.json` after extraction to recover full CognitiveOS metadata.

#### Deno & JSR Registries

Resolves `deno:jsr/@{scope}/{name}` by querying the JSR registry API.

```
cpm install deno:jsr/@sys/automation
→ GET api.jsr.io/scopes/@sys/packages/automation
→ download source archive → Normalization Engine
```

For direct Deno URL installs, downloads the modular entry point and walks imports to assemble a complete archive.

### 3. Normalization Engine

Every downloaded archive — regardless of source — passes through the same normalization pipeline:

```
[ Downloaded Archive ] (from any resolver)
          │
          ▼
┌─────────────────────────────────────────────────┐
│              Normalization Engine                │
├─────────────────────────────────────────────────┤
│ 1. Unpack archive to isolated temp sandbox       │
│ 2. Scan for manifest:                            │
│    ┌──────────────────────────────────────┐      │
│    │ IF cognitive.json exists:            │      │
│    │   Parse natively (full schema)       │      │
│    │ IF package.json exists:              │      │
│    │   Extract cognitive_os key            │      │
│    │   Merge with package.json metadata   │      │
│    │ IF neither: reject archive           │      │
│    └──────────────────────────────────────┘      │
│ 3. Validate merged manifest against schema       │
│ 4. Return Manifest + extracted path              │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
          [ Standard install pipeline ]
          (hardware audit → deps → source
           validation → extract → spawn)
```

For JavaScript/TypeScript ecosystems (NPM, Bun, Deno), a standard `package.json` is augmented with a `cognitive_os` key to carry CognitiveOS-specific metadata without requiring a separate `cognitive.json`:

```json
{
  "name": "@user/ambient-lighting",
  "version": "1.0.4",
  "main": "dist/index.js",
  "cognitive_os": {
    "runtime": {
      "command": "bun",
      "args": ["run", "dist/index.js"],
      "memory_mb": 64,
      "capabilities": ["audio"]
    },
    "prompts": ["prompts/main.md"],
    "tools": ["tools/schema.json"],
    "hardware_requirements": {
      "min_ram_mb": 512,
      "npu_required": false
    }
  }
}
```

The Normalization Engine:
- Extracts `name`, `version`, `description` from `package.json` top-level fields
- Merges `cognitive_os.*` fields into the manifest
- Validates the combined result against the standard `cognitive.schema.json`
- Produces a pruned `.cgp`-format directory ready for the standard install pipeline

### 4. Updated Install Lifecycle

The existing [install lifecycle](#install-lifecycle-detailed) gains a new resolution step at the front:

```
Step 0: Resolve Source (updated)
  0.1 Parse target string through Registry Dispatcher
  0.2 Route to appropriate protocol handler
  0.3 Download archive from source. For registry downloads, cpm includes host environment metadata (`os` and `arch`) to resolve the correct variant.
  0.4 Normalize archive (unpack → detect → validate)
  0.5 Continue to existing lifecycle (Step 2: Parse and Validate)
```

Steps 2-8 remain unchanged — the Normalization Engine guarantees the same `.cgp` format regardless of origin.

### 5. Security: Immutable Checksum Ledger

When downloading from any non-registry source (git provider, NPM, etc.), cpm queries the configured registry's checksum notary endpoint:

```
GET /v1/notary/check?source=github.com&path=user/skill&version=v1.2.0
```

- **First-seen:** Registry fetches the package, records SHA-256, returns it to cpm.
- **Subsequent:** Registry returns recorded SHA-256. cpm computes local hash and compares.
- **Mismatch:** Installation rejected, security alert logged.

If no registry is configured, cpm records checksums locally at `/cognitiveos/data/checksums.json` and warns the user.

## Command Reference

### Global Flags

| Flag | Description |
|------|-------------|
| `--registry <url\|section>` | Override registry. Accepts a URL or a section path like `official.eu` or `alternative.community` (default: from `/etc/cognitiveos/registries.toml`) |
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
cpm install email-manager --registry official.eu       # resolves to EU mirror
cpm install email-manager --registry alternative.community  # community registry
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

#### `cpm info <name> [--json] [--manifest <path>]`

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

**JSON output** (for CI/CD pipelines):

```bash
cpm info --json --manifest cognitive.json
```

Output:
```json
{
  "name": "email-manager",
  "version": "1.2.0",
  "description": "Background email triaging",
  "author": "CognitiveOS",
  "license": "MIT",
  "filename": "email-manager-1.2.0-linux-amd64.cgp"
}
```

The `filename` field follows the naming convention: `<name>-<version>-<os>-<arch>.cgp` (or `<name>-<version>.cgp` for architecture-agnostic packages).

**Exit codes:** 0=ok, 1=not found

#### `cpm search <query> [--capability <name>] [--license <spdx>] [--min-ram <mb>] [--page <n>]`

Search the registry for patches. When `--capability` is specified, only patches whose `runtime.capabilities` array includes the exact capability string are returned.

```bash
cpm search email
cpm search "image processing" --license MIT --min-ram 512
cpm search --capability display.render_image
cpm search photo --capability display.render_image
```

Output:

```
Found 3 matches:
  email-manager     1.2.0    Background email handling
  email-crypto      0.3.0    Encrypted email support
  photo-viewer      0.5.0    Image display and editing
```

**Exit codes:** 0=ok, 1=query too short, 2=registry unreachable

#### `cpm pack [--bin <path>] [--manifest <path>] [--name <name>] [--version <version>] [--os <os>] [--arch <arch>] [--description <desc>]`

Package a binary or directory of binaries into a `.cgp` archive. If `--bin` is omitted, only the manifest (and any files it references) is packaged.

**Manifest Resolution & Merging:**
If `--manifest` is not provided, cpm automatically searches for a `cognitive.json` file in the following order (shallowest to deepest):
1. `CWD/cognitive.json`
2. `parent(bin)/cognitive.json`
3. `bin/cognitive.json`
4. `--manifest <path>` (if provided, deepest priority)

Found manifests are merged sequentially; deeper definitions override shallower ones. If no manifest is found and `--name` / `--version` are missing, the command fails.

Example:
```bash
cpm pack --bin ./build/bin/bridges --manifest cognitive.json
cpm pack --bin ./build/bin/cli --name cognitiveos-cli --version 0.1.0
```

**Exit codes:** 0=ok, 1=binary not found, 2=manifest missing or invalid

#### `cpm publish <path> [--key <path>] [--download-url <url>] [--tag <tag>] [--scope <scope>] [--visibility <visibility>]`

Publish a `.cgp` archive to the registry. Authenticates using SSH key signing. Falls back to `CPM_REGISTRY_TOKEN` (deprecated) if no SSH key is found.

**Official publish** (no `--download-url`): uploads the `.cgp` to the registry, which creates a GitHub Release and stores the package. Best for packages under 32 MB.

```bash
cpm publish ./my-skill-1.0.0.cgp --key ~/.ssh/id_ed25519
```

**Notary proxy publish** (`--download-url` required): registers metadata only. The `.cgp` must be hosted externally (GitHub Releases, personal server, etc.). Consumers install via UPR:

```bash
cpm publish ./my-skill-1.0.0.cgp \
  --key ~/.ssh/id_ed25519 \
  --download-url https://github.com/owner/repo/releases/download/v1.0.0/my-skill-1.0.0.cgp
```

For packages larger than 32 MB (e.g. with model weights), host the `.cgp` on GitHub Releases and publish metadata via `--download-url`, or let consumers install directly:
```bash
cpm install ghr:owner/repo@tag
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--key <path>` | SSH private key path (default: `~/.ssh/id_ed25519`) |
| `--download-url <url>` | Canonical download URL for notary proxy mode |
| `--tag <tag>` | Tags for the package (repeatable) |
| `--scope <scope>` | Package scope (e.g. username, org) |
| `--visibility <visibility>` | Package visibility: `public` or `private` (default: `public`) |

**Exit codes:** 0=ok, 1=validation failed, 2=auth failed, 3=network error, 4=version already exists

#### `cpm auth register [--key <path>]`

Register SSH public key with the registry (one-time per key).

```bash
cpm auth register --key ~/.ssh/id_ed25519.pub
```

Output:
```
Registered SSH key
  Fingerprint: SHA256:abc123...
  Key type:    ssh-ed25519
  Comment:     your-key
  Registered:  2026-07-20T00:42:38Z
```

Server stores only the public key. No secrets are transmitted.

**Exit codes:** 0=ok, 1=network error, 2=key not found

#### `cpm register-dependencies <package> [--root <path>]`
Register system-level dependencies for an installed patch in the installation queue.
```bash
cpm register-dependencies email-manager
cpm --root=/mnt/target register-dependencies email-manager
```
**Exit codes:** 0=ok, 1=not installed, 2=registration failed

#### `cpm install-dependencies --stage <stage> [--root <path>]`
Install all pending system dependencies for the specified lifecycle stage.
```bash
cpm install-dependencies --stage boot
cpm --root=/mnt/target install-dependencies --stage build
```
**Exit codes:** 0=ok, 1=missing stage, 2=critical dependency failed, 3=manager error

Create a new `.cgp` skeleton directory.

```bash
cpm init my-skill
cd my-skill
# Edit cognitive.json, add prompts/tools/weights
```

Creates the standard `.cgp` directory structure with a default `cognitive.json`. Use `--template` to scaffold a package with the relevant fields pre-filled. These manifests are then used by `cpm pack` to generate the final `.cgp` archive.

| `--template` | Scaffolds | Use case |
|---|---|---|
| (default) | `name`, `version`, `description`, `prompts/system.md`, `tools/` | Minimal skill / prompt-only package |
| `prompt-only` | `name`, `version`, `description`, `prompts/system.md` | Skill, persona, prompt template (no tools) |
| `mcp-bridge` | `name`, `version`, `description`, `author`, `runtime.mcp_servers[]`, `runtime.system_prompt`, `prompts/`, `tools/` | Tool with MCP server binaries |
| `gguf-model` | `name`, `version`, `description`, `author`, `brain.wide_model { weights.remote }`, `checksum.sha256`, `download_url` | LLM model package (remote weights) |
| `firmware` | `name`, `version`, `description`, `author`, `brain.raw_model { type: firmware, weights }`, `checksum.sha256` | MCU/ESP32 firmware model |
| `full` | All optional fields with placeholder values | Complete package manifest for reference |

Examples:

```bash
cpm init my-email-skill --template prompt-only
cpm init my-bridge      --template mcp-bridge
cpm init gemma-4-2b     --template gguf-model
cpm init cograw-esp32   --template firmware
cpm init everything     --template full
```

**Exit codes:** 0=ok, 1=directory already exists

#### `cpm verify <path>`
Verify a `.cgp` archive integrity.

```bash
cpm verify ./my-skill.cgp
```

Checks:
- Valid tar.gz format
- `cognitive.json` exists and validates against full schema
- All referenced files in manifest exist in archive
- `hardware_requirements` values within sane bounds
- `hardware_dependencies.packages` entries have valid manager/stage enums
- Executables in `tools/` have valid shebangs or are ELF binaries

**Exit codes:** 0=valid, 1=invalid format, 2=schema violation, 3=missing file, 4=dependency not met

#### `cpm tune <name> [--background] [--epochs <n>] [--finalize] [--quantize <type>]`
Fine-tune an installed patch using local interaction data.

```bash
cpm tune study-buddy --background
cpm tune study-buddy --finalize --quantize Q4_K_M
```

Invokes the tuning tool specified in the patch manifest to generate a LoRA adapter. Use `--finalize` to compile and quantize the adapter for production use.

**Exit codes:** 0=ok, 1=not installed, 2=insufficient data, 3=training failed, 4=tool not found


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
  2.1 Extract archive to temp directory
  2.2 Read cognitive.json from extracted directory
  2.3 Validate against cognitive.schema.json
  2.4 Verify referenced files exist in extracted directory:
      - runtime.system_prompt
      - runtime.mcp_servers[].command (resolved relative to tools/)
      - brain.adapter
  2.5 Fail if invalid or missing files (exit 2), clean up temp directory
```

### Step 3: Resolve Dependencies
Cpm resolves all CGP-to-CGP dependencies before proceeding.
```
  3.1 Read cognitive.json → dependencies field
  3.2 For each dependency:
      3.2.1 Check if already installed and version matches range
      3.2.2 If not, resolve from registry (recursive)
      3.2.3 Check for circular dependencies (fail if circular, exit 3)
  3.3 Install dependencies first (recursive call to install)
```

### Step 3.5: Register and Install System Dependencies
Cpm handles OS-level dependencies declared in `hardware_dependencies.packages`.
```
  3.5.1 Register system dependencies:
       Call `cpm register-dependencies <name>` to write registration records to /cognitiveos/lib/cpm/queue/<stage>/
  3.5.2 Install immediate dependencies:
       Call `cpm install-dependencies --stage install` to process the 'install' queue.
  3.5.3 If a required dependency fails to install → abort installation and rollback queue records (exit 3)
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

## Tuning Lifecycle

### Step 1: Trigger
Tuning is triggered either manually via `cpm tune <name>` or automatically by `cognitiveosd` when data milestones (e.g., every 500 interactions) are reached.

### Step 2: Readiness Check
`cpm` reads the `training.data_requirements` block from the manifest. If the local interaction logs have fewer than `min_samples`, the process exits with `ERR_INSUFFICIENT_DATA`.

### Step 3: Execution
`cpm` invokes the MCP tool specified in `training.tool`. It passes hyperparameters (Rank, Alpha, Epochs) and the path to the interaction logs.

### Step 4: Adapter Generation
The training tool generates a LoRA adapter file (e.g., `user_adapter.bin`) and saves it to the `training.output_path` specified in the manifest.

### Step 5: Hot-Swap
`cpm` signals the daemon to bind the new adapter. The inference engine dynamically loads the adapter on top of the base Wide Model mid-session.

## Hardware Audit

The hardware audit checks these resources:

| Resource | Source | Field in manifest | Unit |
|----------|--------|-------------------|------|
| OS | `runtime.GOOS` | `os` | enum (linux, darwin, windows) |
| Architecture | `runtime.GOARCH` | `arch` | enum (amd64, arm64, arm, riscv64) |
| RAM | `/proc/meminfo` | `min_ram_mb` | MB |
| Storage (free) | `statfs()` on `/cognitiveos/` | `min_storage_mb` | MB |
| NPU availability | `/sys/class/npu/` or `lspci` | `npu_required` | boolean |
| CPU cores | `/proc/cpuinfo` | `min_cpu_cores` | integer |
| Network required | Ping test or connectivity check | Implicit from manifest | boolean |

Audit results are cached at `/cognitiveos/audit/current.json` and refreshed every 60 seconds by cognitiveosd.

## Registry Protocol

### Registry Configuration

Registry sources are configured in `/etc/cognitiveos/registries.toml`. The format distinguishes between **official** registries (maintained by the CognitiveOS Project) and **alternative** registries (self-hosted or third-party).

```toml
[official]
primary = "https://registry-us-all-distros-official.cognitive-os.org/v1"

[official.mirrors]
eu = "https://registry-eu-all-distros-official.cognitive-os.org/v1"
jp = "https://registry-jp-all-distros-official.cognitive-os.org/v1"
sg = "https://registry-sg-all-distros-official.cognitive-os.org/v1"

[alternative]
community = "https://community-registry.cognitive-os.org/v1"
my-private = "https://my-registry.example.com/v1"
```

#### URL Convention

Official registry URLs follow this naming pattern:
```
https://registry-{country}-{distro}-{role}.cognitive-os.org/v1
```

| Segment | Description | Example |
|---------|-------------|---------|
| `{country}` | ISO region tag | `us`, `eu`, `jp`, `sg`, `br` |
| `{distro}` | Distribution tag | `cognitiveos`, `all-distros` |
| `{role}` | Registry role | `official`, `mirror`, `alternative` |

#### Resolution Order

When resolving a package by name without `--registry`:

1. **Official primary** — try first
2. **Official mirrors** — try each in listed order until a match is found
3. **Alternative registries** — try each (no defined order) until a match is found
4. **Fail** — package not found

When `--registry` is specified:

- **Raw URL** (`--registry https://...`) — use that URL directly
- **Section path** (`--registry official.eu`) — resolve to the matching entry:
  - `official` → primary URL
  - `official.{mirror_name}` → named mirror
  - `alternative.{name}` → named alternative

### API Contract

cpm implements the client side of the [registry API](registry-api.md). Key interactions:
**Search:**

```
GET /v1/search?q=<query>&capability=<capability>&page=1&per_page=20
→ 200
{
  "results": [
    {
      "name": "email-manager",
      "version": "1.2.0",
      "description": "...",
      "license": "MIT",
      "hardware_requirements": { "min_ram_mb": 2048 },
      "capabilities": ["com.cognitiveos.email.send"]
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
