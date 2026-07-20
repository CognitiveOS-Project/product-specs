# CGP Lifecycle: Create → Package → Publish → Install → Verify

This tutorial covers the complete lifecycle of a Cognitive Patch (`.cgp`) — from initial creation through distribution and verification. It is the definitive reference for understanding how packages flow through the CognitiveOS ecosystem.

## Overview

A `.cgp` (Cognitive Patch) is the distribution format for CognitiveOS skills, tools, and model adapters. The lifecycle has five phases:

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ CREATE  │───►│ PACKAGE │───►│ PUBLISH  │───►│ INSTALL │───►│ VERIFY   │
│         │    │         │    │          │    │         │    │          │
│ cpm init│    │ cpm pack│    │cpm publish│   │cpm install│   │notary    │
│ + edit  │    │ + verify│    │ + auth    │   │ + resolve│   │check     │
└─────────┘    └─────────┘    └──────────┘    └─────────┘    └──────────┘
```

## Phase 1: Create

### Scaffold the Package

Use `cpm init` to create a skeleton directory with the correct structure:

```bash
cpm init my-skill --template default
cd my-skill
```

Available templates:

| Template | Use Case | Creates |
|----------|----------|---------|
| `default` | Basic skill with prompts and tools | `cognitive.json`, `prompts/`, `tools/`, `.github/` |
| `prompt-only` | Pure prompt/persona skill | `cognitive.json`, `prompts/`, `.github/` |
| `mcp-bridge` | MCP server integration | `cognitive.json`, `prompts/`, `tools/`, `.github/` |
| `gguf-model` | GGUF model distribution | `cognitive.json`, `.github/` |
| `firmware` | MCU/ESP32 firmware | `cognitive.json`, `.github/` |
| `full` | Reference manifest | All fields with placeholders |

All templates include `.github/docker/Dockerfile.ci` and `.github/workflows/{ci,publish}.yml` for Alpine-based CI/CD.

### Define the Manifest

Edit `cognitive.json` — the package's identity card:

```json
{
  "name": "my-skill",
  "version": "0.1.0",
  "description": "What this skill does",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 512,
    "min_storage_mb": 50
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "tools_root": "tools"
  }
}
```

Key fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique package identifier |
| `version` | Yes | SemVer version string |
| `description` | Yes | One-line description |
| `author` | No | Package author |
| `license` | No | SPDX license identifier |
| `hardware_requirements` | No | Min RAM, storage, NPU |
| `runtime.system_prompt` | No | Path to system prompt file |
| `runtime.tools_root` | No | Path to tools directory |

### Add Content

Populate the directories created by the template:

```
my-skill/
├── cognitive.json          # Your manifest (already created)
├── prompts/
│   └── system.md          # AI persona and instructions
├── tools/
│   └── mcp-server         # MCP server binary (optional)
└── weights/
    └── model.gguf         # Model weights (optional)
```

## Phase 2: Package

### Pack the Archive

`cpm pack` reads the manifest, validates it, and creates a `.cgp` archive:

```bash
cpm pack
```

Output:
```
✓ my-skill-0.1.0.cgp is valid (my-skill v0.1.0)
✓ Packaged manifest as my-skill-0.1.0.cgp
```

The output filename follows the convention:
- With OS/arch: `<name>-<version>-<os>-<arch>.cgp`
- Universal: `<name>-<version>.cgp`
- With hardware requirements: `<name>-<version>.cgp`

### Verify the Archive

Use `cpm verify` to validate the archive integrity:

```bash
cpm verify my-skill-0.1.0.cgp
```

Output:
```
✓ my-skill-0.1.0.cgp is valid (my-skill v0.1.0)
```

The verify check ensures:
- Valid tar.gz format
- `cognitive.json` exists and validates against the schema
- All referenced files exist in the archive
- Hardware requirements are within sane bounds

### Inspect Package Info

For CI/CD pipelines, use `cpm info --json` to extract manifest data:

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

## Phase 3: Publish

### Register SSH Key

Before publishing, register your SSH public key with the registry:

```bash
cpm auth register --key ~/.ssh/id_ed25519.pub
```

Output:
```
Registered SSH key
  Fingerprint: SHA256:yljNAb+oO3LQEHBY0g5KZCl9vLnZNHkerroT/eOcJaA
  Key type:    ssh-ed25519
  Comment:     your-key
  Registered:  2026-07-20T00:42:38Z
```

This is a one-time operation per key. The server stores only your public key.

### Choose a Publish Path

#### Path A: Official Publish (Registry Hosts)

For packages under 32 MB, the registry server handles hosting:

```bash
cpm publish my-skill-0.1.0.cgp --key ~/.ssh/id_ed25519
```

What happens:
1. CPM reads the manifest from the .cgp archive
2. CPM computes SHA-256 of the manifest JSON bytes
3. CPM signs the hash with your SSH private key
4. CPM sends the .cgp binary + metadata to the registry
5. Registry verifies your SSH signature
6. Registry creates a GitHub Release on the official org
7. Registry uploads the .cgp as a release asset
8. Registry stores manifest + checksum in S3-compatible storage
9. Registry returns 201 with the download URL

#### Path B: Notary Proxy Publish (You Host)

For larger packages or self-hosted distribution:

```bash
cpm publish my-skill-0.1.0.cgp \
  --key ~/.ssh/id_ed25519 \
  --download-url https://github.com/your-org/releases/download/v1.0.0/my-skill-0.1.0.cgp
```

What happens:
1. CPM reads the manifest and computes SHA-256
2. CPM signs the manifest with your SSH private key
3. CPM sends metadata + checksum to the registry (no binary)
4. Registry verifies your SSH signature
5. Registry stores metadata + checksum in S3-compatible storage
6. You host the .cgp file yourself (GitHub Releases, CDN, etc.)

Consumers install via UPR:
```bash
cpm install ghr:your-org/my-skill@v1.0.0
```

### Large Packages (>32 MB)

The registry server has a 32 MB request limit. For packages with model weights:

1. **Split weights** — keep the core .cgp under 32 MB, download weights separately via `cpm download-weights`
2. **Use notary proxy** — host the .cgp on GitHub Releases, publish metadata only
3. **Direct UPR** — consumers install directly from GitHub Releases: `cpm install ghr:owner/repo@tag`

## Phase 4: Install

### From Registry

```bash
# Search for packages
cpm search my-skill

# Install specific version
cpm install my-skill@0.1.0

# Install latest
cpm install my-skill
```

### From GitHub Release (UPR)

```bash
cpm install ghr:your-org/my-skill@v1.0.0
```

### From Local File

```bash
cpm install ./my-skill-0.1.0.cgp
```

### From Git Source

```bash
cpm install github.com/your-org/my-skill@v1.0.0
```

### What Happens During Install

1. **Resolve** — find the package (registry, GitHub, local file)
2. **Download** — fetch the .cgp archive
3. **Parse** — extract and validate `cognitive.json`
4. **Audit** — check hardware requirements (RAM, storage, NPU)
5. **Resolve Dependencies** — install any required packages
6. **Extract** — unpack to `/cognitiveos/patches/<name>/`
7. **Spawn** — start MCP servers declared in the manifest
8. **Register** — make tools available to the Wide Model
9. **Inject** — prepend system prompt to the AI's prompt chain

### Verify Installation

```bash
# List installed packages
cpm list

# Show package details
cpm info my-skill
```

## Phase 5: Verify

### Notary Check

The registry stores checksums for all published packages. Verify a package's integrity:

```bash
curl "https://registry-us-all-distros-official.cognitive-os.org/v1/notary/check?source=cpm&path=my-skill&version=0.1.0"
```

Response:
```json
{
  "name": "my-skill",
  "version": "0.1.0",
  "stored_hash": "00713d22377d8237afdfce310a9cf438151944189d6fccfe6867bb64526259aa",
  "verified": true,
  "checked_at": "2026-07-20T00:56:16Z"
}
```

### Checksum Verification

When installing from any source, cpm automatically verifies the checksum against the notary:

- **First-seen**: Registry fetches the package, records SHA-256, returns it to cpm
- **Subsequent**: Registry returns recorded SHA-256. cpm computes local hash and compares
- **Mismatch**: Installation rejected, security alert logged

### Update and Remove

```bash
# Update to latest version
cpm update my-skill

# Remove installed package
cpm remove my-skill
```

## CI/CD Integration

Every `cpm init` template includes GitHub Actions workflows:

### Dockerfile.ci (Alpine via QEMU)

```dockerfile
ARG GO_VERSION=1.25
FROM golang:${GO_VERSION}-alpine

ARG WORKDIR=.
WORKDIR /src
COPY ${WORKDIR} .

RUN apk add --no-cache jq
RUN go install github.com/CognitiveOS-Project/cpm/cmd/cpm@latest

RUN cpm pack
RUN cpm info --json > /out/pkg.json
RUN cp *.cgp /out/

FROM scratch
COPY --from=0 /out /out
```

### CI Workflow (`.github/workflows/ci.yml`)

Triggers on push/PR to main/development:
1. Sets up QEMU + Docker Buildx
2. Builds the Alpine container
3. Runs `cpm pack` and `cpm info --json`
4. Extracts artifacts for verification

### Publish Workflow (`.github/workflows/publish.yml`)

Triggers on version tags (`v*`):
1. Builds the same Alpine container
2. Extracts .cgp and pkg.json
3. Creates a GitHub Release with the artifacts

## Complete Example

```bash
# 1. Create
cpm init hello-world
cd hello-world

# 2. Edit cognitive.json and prompts/system.md
vim cognitive.json
vim prompts/system.md

# 3. Package
cpm pack
cpm verify hello-world-0.1.0.cgp

# 4. Register
cpm auth register --key ~/.ssh/id_ed25519.pub

# 5. Publish
cpm publish hello-world-0.1.0.cgp --key ~/.ssh/id_ed25519

# 6. Verify publication
cpm search hello-world
curl "https://registry-us-all-distros-official.cognitive-os.org/v1/notary/check?source=cpm&path=hello-world&version=0.1.0"

# 7. Install (on another machine)
cpm install hello-world@0.1.0

# 8. Verify installation
cpm list
cpm info hello-world
```

## Related Specs

- [CPM Spec](../cpm-spec.md) — Full command reference
- [CGP Format](../cgp-format.md) — Archive format specification
- [Registry API](../registry-api.md) — REST API contract
- [Publish Flow](../cpm-publish-flow.md) — Architecture and constraints
- [Security Model](../security-model.md) — Authentication and integrity
- [Fair Use Policy](../fair-use-policy.md) — Rate limits and acceptable use
