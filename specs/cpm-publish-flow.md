# cpm Publish Flow — Architecture and Constraints

Version: 1.0.0-draft

## Overview

This document defines the architecture for publishing `.cgp` packages to the official CognitiveOS registry. It covers the publish flow, authentication, file hosting, infrastructure constraints, and the distinction between official and third-party packages.

See [ADR-007](../adr/ADR-007-registry-server-architecture.md) for the full architectural rationale and [registry-api.md](registry-api.md) for the REST API contract.

## Two Publish Paths

### Official Packages (cognitive-os.org)

Official CognitiveOS packages are published to the official registry at `registry-us-all-distros-official.cognitive-os.org`. The publisher authenticates with their SSH key. The registry server handles file hosting — it receives the `.cgp` archive, uploads it to GitHub Releases on the official org, and stores the manifest in R2.

```
cpm publish hello-cognitive --tag vision
```

- Publisher authenticates with SSH key (no GitHub token needed)
- Registry server is the trusted intermediary
- File hosting is automatic (GitHub Releases)
- Manifest and checksums are stored in R2 (notary)

### Third-Party Packages (UPR)

Third-party packages are published by the author to their own hosting (GitHub Releases, personal server, etc.) and registered with any compatible notary. Consumers install via the Universal Protocol Router:

```
cpm install github:author/skill@v1.0.0
cpm install https://example.com/skill.cgp
```

No registration with the official notary is required. The author controls hosting, versioning, and distribution.

## Official Publish Flow

### Sequence Diagram

```
Publisher                    Cloud Run (Registry)               GitHub Releases           R2 (Notary)
   |                                |                               |                        |
   |  cpm publish ./patch.cgp      |                               |                        |
   |  → read manifest from .cgp    |                               |                        |
   |  → marshal manifest to JSON   |                               |                        |
   |  → SHA-256(manifest bytes)    |                               |                        |
   |  → sign hash with SSH key     |                               |                        |
   |                               |                               |                        |
   |  POST /v1/patches             |                               |                        |
   |  Headers:                     |                               |                        |
   |    X-SSH-Fingerprint: SHA256  |                               |                        |
   |    X-SSH-Signature: <sig>     |                               |                        |
   |  Body: multipart              |                               |                        |
   |    - .cgp binary              |                               |                        |
   |    - manifest JSON            |                               |                        |
   |    - sha256, download_urls    |                               |                        |
   |  ──────────────────────────►  |                               |                        |
   |                               |                               |                        |
   |                               |  1. Verify SSH signature      |                        |
   |                               |     against registered key    |                        |
   |                               |                               |                        |
   |                               |  2. Store .cgp as temp file   |                        |
   |                               |                               |                        |
   |                               |  3. Create GitHub release     |                        |
   |                               |     POST /repos/.../releases ►|                        |
   |                               |                               |                        |
   |                               |  4. Upload .cgp as asset      |                        |
   |                               |     POST .../assets ─────────►|                        |
   |                               |                               |                        |
   |                               |  5. Delete temp file          |                        |
   |                               |                               |                        |
   |                               |  6. Store manifest + metadata ──────────────────────►  |
   |                               |     in R2 notary bucket       |                        |
   |                               |                               |                        |
   |  ◄──── 201 Created ──────────│                               |                        |
   |      { name, version,         |                               |                        |
   |        sha256, download_url } |                               |                        |
```

### Step-by-Step

1. **CPM reads manifest** from the `.cgp` archive (it's a tar.gz containing `cognitive.json`)
2. **CPM marshals manifest** to JSON bytes and computes SHA-256
3. **CPM signs the hash** with the publisher's SSH private key (ed25519)
4. **CPM sends** the `.cgp` binary + metadata to `POST /v1/patches` with SSH auth headers
5. **Registry verifies** the SSH signature against the registered public key
6. **Registry stores** the `.cgp` as a temp file (ephemeral filesystem on Cloud Run)
7. **Registry creates** a GitHub Release on the official org's package repo
8. **Registry uploads** the `.cgp` as a release asset
9. **Registry deletes** the temp file
10. **Registry stores** manifest + checksum in R2 notary bucket
11. **Registry returns** 201 with the `download_url` pointing to the GitHub Release asset

After this flow:
- The `.cgp` file lives permanently on GitHub Releases
- The manifest + checksum live permanently in R2
- Cloud Run is stateless — no files persist

## Authentication

### SSH Key Authentication (per ADR-007)

Publishers authenticate using SSH public key signatures. The server stores only public keys — no secrets are ever transmitted or stored.

**Headers for authenticated requests:**

```
X-SSH-Fingerprint: SHA256:<base64-encoded-fingerprint>
X-SSH-Signature: <base64-encoded SSH wire-format signature>
```

**What is signed:** The SHA-256 hash of the manifest JSON bytes (the serialized `cognitive.json`).

**Signature format:** SSH wire format (`string(format) + string(blob)`), base64-encoded with `base64.RawStdEncoding` (no padding). Verified using `golang.org/x/crypto/ssh` directly — no external SSHSIG library required.

### Registration Flow

```
cpm auth register --key ~/.ssh/id_ed25519.pub
  → POST /v1/auth/register
  → Body: { "public_key": "<contents of .pub file>" }
  → Server stores key at auth/keys/{fingerprint}.pub in S3
  → Returns: { "fingerprint": "SHA256:abc123...", "registered_at": "..." }
```

One-time operation per key. Server stores only public keys.

### Publish Auth Flow

```
cpm publish ./patch.cgp --download-url https://...
  → Reads manifest.json from .cgp archive
  → Computes SHA-256 of manifest JSON bytes
  → Signs hash with private key
  → Sends: POST /v1/patches
    Headers:
      X-SSH-Fingerprint: SHA256:abc123...
      X-SSH-Signature: <base64-encoded signature>
    Body: { manifest, sha256, download_urls, ... }

Server:
  1. Extract fingerprint from X-SSH-Fingerprint header
  2. Load public key from S3: auth/keys/{fingerprint}.pub
  3. Verify signature against manifest SHA-256 hash
  4. If valid → process upload, store metadata in R2
  5. If invalid → return 401 Unauthorized
```

### Scope Model

| Scope | Permission | Required For |
|-------|------------|--------------|
| `publish` | Publish new packages and versions | `POST /v1/patches`, `PUT /v1/patches/{name}/{version}` |
| `admin` | Full administrative access | Status changes, key management |

Publishers with `admin` scope have `scope: "admin"` in their registration record. Admin scope is managed out-of-band by registry operators.

### Backward Compatibility

The registry server accepts **either** SSH key auth **or** bearer token auth on publish routes. Bearer token auth is legacy and will be removed in a future version.

## File Hosting

### Official Packages

Official `.cgp` files are hosted on **GitHub Releases** in dedicated per-package repos under the `CognitiveOS-CGP-Packages` organization.

**Repo naming:** `CognitiveOS-CGP-Packages/{package-name}` (e.g., `CognitiveOS-CGP-Packages/hello-cognitive`)

**Release naming:** `v{version}` (e.g., `v0.1.0`)

**Asset naming:** `{package-name}-{version}-{os}-{arch}.cgp` (e.g., `hello-cognitive-0.1.0-linux-amd64.cgp`)

**Download URL pattern:**
```
https://github.com/CognitiveOS-CGP-Packages/{name}/releases/download/v{version}/{name}-{version}-{os}-{arch}.cgp
```

### Third-Party Packages

Third-party packages are hosted by the author on any accessible URL. No registration with the official notary is required. Consumers install via the Universal Protocol Router:

```
cpm install github:author/skill@v1.0.0
cpm install https://example.com/skill.cgp
```

### Why GitHub Releases

| Criterion | GitHub Releases | R2/S3 | Self-hosted |
|-----------|----------------|-------|-------------|
| **Free tier** | Unlimited (public repos) | 10 GB + 10M reads | N/A |
| **CDN** | Global (Fastly) | Cloudflare | Manual |
| **Versioning** | Native (tags + releases) | Manual | Manual |
| **Access control** | Fine-grained (teams, roles) | IAM | Manual |
| **Audit trail** | Full (who released what) | CloudTrail | Manual |
| **No vendor lock-in** | Portable (any GitHub host) | S3-compatible | Fully portable |
| **Cost at scale** | Free for public repos | $0.015/GB/mo storage + egress | Variable |

## Infrastructure Constraints

### Cloud Run (Registry Server)

| Constraint | Value | Impact |
|---|---|---|
| **Max request body** | **32 MB** | Large `.cgp` files cannot be uploaded directly |
| **Free egress** | **1 GiB/month** (Premium Tier) | Each `.cgp` upload to GitHub counts against this |
| **Free compute** | **240,000 vCPU-seconds/month** | ~66.7 hours of continuous 1 vCPU compute |
| **Free memory** | **450,000 GiB-seconds/month** | ~125 hours at 1 GiB |
| **Temp storage** | tmpfs, **consumes RAM** | Cannot buffer large files without OOM risk |
| **Max timeout** | **3,600 seconds** (1 hour) | Default is 300 seconds (5 min) |
| **Scale to zero** | Yes (`min-instances=0`) | No idle cost |
| **Current config** | 512 MiB, 1 vCPU, 300s timeout | Adequate for metadata-only operations |

**Egress alternative:** Cloud Run Standard Tier offers **200 GiB/month** free egress (vs. 1 GiB on Premium). This can be opted in via GCP Console if egress becomes a bottleneck.

### GitHub API

| Constraint | Value |
|---|---|
| **Rate limit (PAT)** | **5,000 requests/hour** |
| **Rate limit (GITHUB_TOKEN)** | **1,000 requests/hour** |
| **Max asset size** | **2 GiB** per file |
| **Max assets per release** | **1,000** |
| **Total release size** | **No limit** |
| **Concurrent requests** | **100** max |

### How Constraints Are Resolved

**32 MB request limit:** The `.cgp` binary is included in the multipart upload to Cloud Run. For files under 32 MB, this works directly. For larger files (packages with model weights), the upload will fail.

**Resolution options for large packages:**
1. Split weights from the core `.cgp` — weights are downloaded separately via `cpm download-weights` (already supported)
2. Use a presigned upload URL — Cloud Run generates a presigned GitHub upload URL, CPM uploads directly to GitHub
3. CPM uploads `.cgp` to GitHub directly, then sends only metadata to Cloud Run (requires GH token on client)

**Recommended approach:** Option 1 (split weights) is already the CPM architecture. The core `.cgp` (manifest + prompts + small binaries) stays under 32 MB. Large weights are handled by `cpm download-weights` from Hugging Face or other weight providers.

**Egress (1 GiB free):** Each `.cgp` upload to GitHub counts as egress. At 1 GiB/month, approximately:
- 33 publishes of 30 MB packages, or
- 10 publishes of 100 MB packages

For most use cases, this is sufficient. For heavy publishing, opt into Standard Tier (200 GiB free).

## Package Structure

### .cgp Archive Format

A `.cgp` file is a gzip-compressed tar archive containing:

```
hello-cognitive-0.1.0.cgp
├── cognitive.json              # REQUIRED: package manifest
├── prompts/                    # System prompts
│   └── system.md
├── tools/                      # MCP server binaries (optional)
│   └── mcp-server
└── weights/                    # Model weights (optional, may be downloaded separately)
    └── model.gguf
```

### Manifest (cognitive.json)

```json
{
  "name": "hello-cognitive",
  "version": "0.1.0",
  "description": "A test package for end-to-end registry verification",
  "author": "CognitiveOS Team",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/CognitiveOS-CGP-Packages/hello-cognitive",
    "issues": "https://github.com/CognitiveOS-CGP-Packages/hello-cognitive/issues"
  },
  "hardware_requirements": {
    "min_ram_mb": 128,
    "min_storage_mb": 50
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "tools_root": "./tools",
    "mcp_servers": []
  }
}
```

### Publish Request Body

The publish request sends the manifest fields as JSON, plus the `.cgp` binary as a multipart upload:

```json
{
  "name": "hello-cognitive",
  "version": "0.1.0",
  "description": "A test package",
  "author": "CognitiveOS Team",
  "license": "MIT",
  "download_urls": {
    "": "https://github.com/CognitiveOS-CGP-Packages/hello-cognitive/releases/download/v0.1.0/hello-cognitive-0.1.0-universal.cgp"
  },
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "tags": ["vision", "test"],
  "manifest": { ... }
}
```

## Implementation Status

### Registry Server

| Component | Status | File |
|---|---|---|
| SSH key store (memory) | Done | `internal/auth/sshauth.go` |
| SSH key store (S3) | Done | `internal/auth/sshauth.go` |
| `/v1/auth/register` endpoint | Done | `internal/server/handlers.go` |
| SSH auth middleware | **Missing** | `internal/auth/sshmiddleware.go` |
| Wire middleware to publish routes | **Missing** | `internal/server/server.go` |
| GitHub release creation | **Missing** | New handler needed |
| Temp file management | **Missing** | New handler needed |

### CPM Client

| Component | Status | File |
|---|---|---|
| Read manifest from .cgp | Done | `cmd/publish.go` |
| SHA-256 of manifest JSON bytes | **Wrong** — currently hashes entire .cgp | `cmd/publish.go` |
| SSH key signing | **Missing** | `internal/auth/signing.go` |
| `cpm auth register` command | **Missing** | `cmd/auth.go` |
| Send SSH headers | **Missing** — currently sends Bearer token | `internal/registry/registry.go` |
| Add `golang.org/x/crypto` dependency | **Missing** | `go.mod` |

### What Needs to Change

**Registry Server:**
1. Create SSH auth middleware (`internal/auth/sshmiddleware.go`)
2. Wire middleware into publish routes (`server.go`)
3. Initialize SSHKeys in main.go
4. Add GitHub release creation handler
5. Add multipart file upload handling
6. Add temp file cleanup

**CPM Client:**
1. Create SSH signing utility (`internal/auth/signing.go`)
2. Rewrite `cmd/publish.go` to use SSH signing
3. Create `cmd/auth.go` for key registration
4. Update `internal/registry/registry.go` to send SSH headers
5. Add `golang.org/x/crypto` dependency
6. Fix manifest hashing (JSON bytes, not entire .cgp)

## Testing

### Test Package: hello-cognitive

A minimal test package for verifying the end-to-end publish flow:

```
hello-cognitive/
├── cognitive.json
└── prompts/
    └── system.md
```

### Test Flow

```bash
# 1. Register SSH key
cpm auth register --key ~/.ssh/id_ed25519.pub

# 2. Pack the test package
cd /tmp/hello-cognitive
cpm pack

# 3. Publish
cpm publish ./hello-cognitive-0.1.0-universal.cgp

# 4. Search
cpm search hello-cognitive

# 5. Install
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install hello-cognitive

# 6. Verify
cpm list
cpm info hello-cognitive

# 7. Notary check
curl "https://registry-us-all-distros-official.cognitive-os.org/v1/notary/check?source=hello-cognitive&path=cognitive.json&version=0.1.0"
```

## Future Considerations

### Presigned Upload URLs

For large `.cgp` files (packages with model weights), Cloud Run can generate a presigned GitHub upload URL and return it to CPM. CPM uploads directly to GitHub, bypassing the 32 MB request limit:

```
1. CPM sends metadata + SSH signature to Cloud Run
2. Cloud Run verifies signature
3. Cloud Run generates presigned GitHub upload URL
4. Cloud Run returns 202 with presigned URL
5. CPM uploads .cgp directly to GitHub using presigned URL
6. Cloud Run polls for upload completion
7. Cloud Run stores manifest in R2
```

This requires the GitHub token to be on Cloud Run (not on the client).

### Package Signing (Future)

Beyond publisher identity, packages could be cryptographically signed to ensure integrity. This is separate from the notary checksum model and would use a package signing key managed by the registry operator.

### Package Verification (Future)

`GET /v1/notary/check` verifies a remote asset against its stored checksum. This could be extended to verify the asset's signature against the publisher's key, providing end-to-end integrity from publisher to consumer.
