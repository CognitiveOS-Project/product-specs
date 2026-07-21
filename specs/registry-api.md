# Registry Server API Specification

Version: 2.1.0-draft

## Overview

The CognitiveOS registry server is a **notary proxy** REST API for registering, searching, and redirecting to `.cgp` packages. It does **not** host files — it stores metadata and checksums in S3-compatible storage, and redirects clients to canonical download URLs.

The protocol is open: anyone can implement a compatible server, host a private registry, or mirror the public one.

See [ADR-007](../adr/ADR-007-registry-server-architecture.md) for the full architectural rationale.

## Base URL

```
https://registry-{country}-all-distros-official.cognitive-os.org/v1
```

The primary official instance resolves at `https://registry-us-all-distros-official.cognitive-os.org/v1`.

All endpoints are prefixed with `/v1/`.

## Authentication

| Endpoint group | Auth required | Method |
|----------------|---------------|--------|
| Read (search, metadata) | No | Public |
| Signup | No (creates identity) | SSH key signature (machine + owner profile) |
| Register key | Yes (approved signup required) | SSH key signature |
| Publish (POST, PUT) | Yes (registered key) | SSH key signature |
| Unlock code verification | No | Public (code is the auth) |
| Status change | Yes | SSH key signature (admin scope) |
| Admin approvals | Yes | Admin token |

### SSH Key Authentication

Publishers authenticate using SSH public key signatures. The server stores only public keys — no secrets are ever transmitted or stored.

**Headers for authenticated requests:**

```
X-SSH-Fingerprint: SHA256:<base64-encoded-fingerprint>
X-SSH-Signature: <base64-encoded SSHSIG signature>
```

**Signature protocol:** The client signs the SHA-256 hash of the request body using the SSHSIG protocol (`golang.org/x/crypto/ssh` + `hiddeco/sshsig`). The server verifies the signature against the registered public key.

### Signup Flow (Gated Publisher Model)

Before a machine can register keys and publish, it must sign up with the registry. The server evaluates the machine's hardware/software profile and the owner's identity against configurable rules.

```
Machine identity = hardware + software + owner

cpm auth signup
  → gathers machine profile (CPU, RAM, storage, GPU, TPM, OS, kernel, cpm version)
  → gathers owner identity (SSH public key)
  → signs profile with machine's SSH key
  → POST /v1/auth/signup
  → Server evaluates profile against rules
  → Returns: { status: "approved"|"pending"|"rejected", ... }

cpm auth register
  → POST /v1/auth/register
  → Server verifies signup status = approved
  → Stores key at auth/keys/{fingerprint}.pub in S3

cpm auth login
  → stores key path in ~/.cpm/auth.json
  → PUT /v1/auth/status { "fingerprint": "SHA256:..." }
  → Server checks if key is registered
  → Returns: { registered: true/false, registered_at: "..." }

cpm publish
  → SSH signed publish request (uses stored key from auth.json)
```

See [ADR-009](../adr/ADR-009-machine-identity-profile.md) for the full architectural rationale.

### Registration Flow

```
cpm auth register --key ~/.ssh/id_ed25519.pub
  → POST /v1/auth/register
  → Body: { "public_key": "<contents of .pub file>" }
  → Server verifies signup status = approved
  → Server stores key at auth/keys/{fingerprint}.pub in S3
  → Returns: { "fingerprint": "SHA256:abc123...", "registered_at": "..." }
```

### Status Check Flow

```
cpm auth login --key ~/.ssh/id_ed25519
  → PUT /v1/auth/status
  → Body: { "fingerprint": "SHA256:..." }
  → Server looks up key by fingerprint
  → Returns 200: { "fingerprint": "...", "registered": true, "registered_at": "..." }
  → Returns 200: { "fingerprint": "...", "registered": false }
```

### Owner Identity Flow (Web UI)

Owners manage their machines through a web UI. The flow:

1. **Owner visits `/ui/login`** → redirected to GitHub OAuth
2. **Owner authenticates with GitHub** → proves real identity
3. **Callback receives GitHub user info** → owner stored in registry
4. **Owner links machine's SSH public key** → sets display name, key becomes `active`
5. **Machine can now login and publish** → server checks key status = `active`
6. **Owner can revoke key** → publish blocked, downloads still work
7. **Owner can reactivate key** → publish works again

**Web UI routes:**

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/ui/login` | GET | No | Redirect to GitHub OAuth |
| `/ui/callback` | GET | No | OAuth callback, create session |
| `/ui/logout` | GET | Session | Clear session |
| `/ui/dashboard` | GET | Session | Show machine list |
| `/ui/keys/add` | POST | Session | Link a new SSH key |
| `/ui/keys/{fp}/revoke` | GET | Session | Revoke a key |
| `/ui/keys/{fp}/activate` | GET | Session | Activate a revoked key |
| `/ui/keys/{fp}/remove` | GET | Session | Remove a key |

**Data model:**

```go
type Owner struct {
    GitHubID   int64      `json:"github_id"`
    GitHubUser string     `json:"github_user"`
    AvatarURL  string     `json:"avatar_url"`
    Keys       []OwnerKey `json:"keys"`
}

type OwnerKey struct {
    Fingerprint string    `json:"fingerprint"`
    PublicKey   string    `json:"public_key"`
    DisplayName string    `json:"display_name"` // owner-set, machine-suggested
    AddedAt     time.Time `json:"added_at"`
    Status      string    `json:"status"` // active, revoked
}
```

**S3 layout:** `auth/owners/{github_id}/owner.json`

**New env vars:** `CRS_GITHUB_CLIENT_ID`, `CRS_GITHUB_CLIENT_SECRET`, `CRS_SESSION_SECRET`, `CRS_GITHUB_REDIRECT_URL`

### Publish Flow

```
cpm publish ./patch.cgp --download-url https://...
  → Reads manifest.json from .cgp archive
  → Computes SHA-256 of manifest JSON bytes
  → Signs hash with private key (SSHSIG protocol)
  → Sends: POST /v1/patches
    Headers:
      X-SSH-Fingerprint: SHA256:abc123...
      X-SSH-Signature: <base64-encoded signature>
    Body: { manifest, sha256, download_urls, ... }

Server:
  1. Extract fingerprint from X-SSH-Fingerprint header
  2. Load public key from S3: auth/keys/{fingerprint}.pub
  3. Verify SSHSIG signature against manifest SHA-256 hash
  4. If valid → store manifest in S3, return 201
  5. If invalid → return 401 Unauthorized
```

### Scope Resolution

| Scope | Permission | Required For |
|-------|------------|--------------|
| `publish` | Publish new packages and versions | `POST /v1/patches`, `PUT /v1/patches/{name}/{version}` |
| `admin` | Full administrative access | Status changes, key management |

Publishers with the `admin` scope have an additional `scope: "admin"` field in their registration record. Registry operators manage admin scope out-of-band.

## Endpoints

### `GET /v1/health`

Health check.

#### Response

```json
// 200 OK
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "patches_count": 142,
  "version": "2.0.0-draft"
}
```

### `GET /v1/search`

Search for packages.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (matches name, description, tags, capabilities) |
| `capability` | string | — | Filter by exact capability string (e.g., `display.render_image`). Returns packages whose `runtime.capabilities` array includes the value |
| `exact` | boolean | false | If true, match name exactly |
| `license` | string | — | Filter by SPDX license identifier |
| `min_ram_mb` | integer | — | Minimum RAM requirement |
| `min_storage_mb` | integer | — | Minimum storage requirement |
| `author` | string | — | Filter by author |
| `page` | integer | 1 | Page number (1-indexed) |
| `per_page` | integer | 20 | Results per page (max 100) |

#### Response

```json
// 200 OK
{
  "results": [
    {
      "name": "email-manager",
      "version": "1.2.0",
      "description": "Background email triaging, drafting, and notification routing.",
      "author": "CognitiveOS",
      "license": "MIT",
      "hardware_requirements": {
        "min_ram_mb": 2048,
        "min_storage_mb": 150
      },
      "capabilities": [
        "com.cognitiveos.email.send",
        "com.cognitiveos.email.read",
        "com.cognitiveos.email.search"
      ],
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "published_at": "2026-06-23T14:30:00Z",
      "downloads": 142
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

### `GET /v1/patches/{name}`

Get the latest version metadata for a package.

#### Response

```json
// 200 OK
{
  "name": "email-manager",
  "description": "Background email triaging, drafting, and notification routing.",
  "author": "CognitiveOS",
  "license": "MIT",
  "homepage": "https://cognitive-os.org/patches/email-manager",
  "repository": "https://github.com/CognitiveOS-Project/email-manager",
  "latest_version": "1.2.0",
  "versions": ["1.0.0", "1.1.0", "1.2.0"],
  "total_downloads": 142
}
```

### `GET /v1/patches/{name}/versions`

List all versions of a package.

#### Response

```json
// 200 OK
{
  "name": "email-manager",
  "versions": [
    {
      "version": "1.2.0",
      "published_at": "2026-06-23T14:30:00Z",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "download_urls": {
        "linux/amd64": "https://github.com/.../email-manager-1.2.0-linux-amd64.cgp",
        "linux/arm64": "https://github.com/.../email-manager-1.2.0-linux-arm64.cgp"
      },
      "status": "active"
    },
    {
      "version": "1.1.0",
      "published_at": "2026-06-10T10:00:00Z",
      "sha256": "a4b5c6d7e8f90123456789abcdef0123456789abcdef0123456789abcdef0123",
      "download_urls": {
        "": "https://github.com/.../email-manager-1.1.0.cgp"
      },
      "status": "deprecated"
    }
  ]
}
```

### `GET /v1/patches/{name}/{version}`

Get metadata for a specific version.

#### Response

```json
// 200 OK
{
  "name": "email-manager",
  "version": "1.2.0",
  "description": "Background email triaging, drafting, and notification routing.",
  "author": "CognitiveOS",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/CognitiveOS-Project/email-manager",
    "issues": "https://github.com/CognitiveOS-Project/email-manager/issues"
  },
  "hardware_requirements": {
    "min_ram_mb": 2048,
    "min_storage_mb": 150,
    "npu_required": false
  },
  "dependencies": {
    "contacts-bridge": "^1.0.0"
  },
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "download_urls": {
    "linux/amd64": "https://github.com/.../email-manager-1.2.0-linux-amd64.cgp",
    "linux/arm64": "https://github.com/.../email-manager-1.2.0-linux-arm64.cgp"
  },
  "published_at": "2026-06-23T14:30:00Z",
  "downloads": 42,
  "status": "active",
  "publisher_fingerprint": "SHA256:abc123...",
  "manifest": { }
}
```

The `manifest` field contains the full parsed `cognitive.json`.

### `GET /v1/patches/{name}/{version}/download`

Download redirect. The registry does **not** host files — it redirects to the canonical download URL for the requested variant.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `os` | string | — | Target operating system (e.g., `linux`, `darwin`) |
| `arch` | string | — | Target CPU architecture (e.g., `amd64`, `arm64`) |

**Variant resolution:**

1. Construct key `{os}/{arch}` (e.g., `linux/arm64`)
2. Look up `download_urls["linux/arm64"]`
3. If found → HTTP 302 redirect to that URL
4. If not found → look up `download_urls[""]` (universal fallback)
5. If neither → HTTP 404

#### Response

```
HTTP/1.1 302 Found
Location: https://github.com/.../email-manager-1.2.0-linux-arm64.cgp
```

### `GET /v1/notary/check`

Verify the integrity of a remote package against its registered checksum. The server re-fetches the asset from the download URL and compares hashes.

This endpoint implements the notary verification flow described in `cpm-spec.md`.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | Yes | Source identifier (e.g., `github.com`) |
| `path` | string | Yes | Package path (e.g., `CognitiveOS-Project/email-manager`) |
| `version` | string | Yes | Version to check |
| `os` | string | No | Target OS variant (defaults to universal) |
| `arch` | string | No | Target arch variant (defaults to universal) |

#### Response

```json
// 200 OK
{
  "verified": true,
  "name": "email-manager",
  "version": "1.2.0",
  "variant": "linux/arm64",
  "stored_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "remote_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "remote_etag": "\"abc123\"",
  "checked_at": "2026-07-17T12:00:00Z"
}
```

If `verified` is `false`, the response includes both hashes for comparison:

```json
// 200 OK (mismatch)
{
  "verified": false,
  "name": "email-manager",
  "version": "1.2.0",
  "variant": "linux/arm64",
  "stored_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "remote_hash": "different_hash_here",
  "checked_at": "2026-07-17T12:00:00Z"
}
```

**Verification flow:**

1. Load manifest from S3: `notary/{source}/{path}/{version}/manifest.json`
2. Resolve variant via `download_urls` key
3. HEAD request to download URL → check `ETag` or `Content-Length`
4. If ETag matches stored SHA-256 → verified
5. If no ETag: GET full file, compute SHA-256, compare
6. Return verification result

### `POST /v1/auth/signup`

Register a machine identity profile. The server evaluates the machine's hardware/software profile and the owner's identity against configurable rules. Required before `auth/register`.

See [ADR-009](../adr/ADR-009-machine-identity-profile.md) for the full specification.

#### Headers

```
X-SSH-Fingerprint: SHA256:<machine-key-fingerprint>
X-SSH-Signature: <base64-encoded SSHSIG signature of profile>
Content-Type: application/json
```

#### Request Body

```json
{
  "machine": {
    "hardware": {
      "cpu": "AMD Ryzen 9 5900X 12-Core",
      "cores": 24,
      "arch": "amd64",
      "ram_mb": 65536,
      "storage_mb": 1000000,
      "gpu": "NVIDIA RTX 3090",
      "tpm": true,
      "machine_id": "a1b2c3d4-..."
    },
    "software": {
      "os": "linux",
      "kernel": "6.12.0",
      "distro": "alpine",
      "cpm_version": "0.1.0",
      "packages": ["docker", "go"],
      "services": ["sshd"]
    },
    "network": {
      "ip": "192.168.1.100"
    }
  },
  "owner": {
    "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...",
    "comment": "jean@cognitive-os.org"
  }
}
```

#### Response (approved)

```json
// 200 OK
{
  "status": "approved",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "approved_at": "2026-07-20T00:42:38Z",
  "reason": "Hardware + owner meet all rules"
}
```

#### Response (pending)

```json
// 202 Accepted
{
  "status": "pending",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "queued_at": "2026-07-20T00:42:38Z",
  "reason": "No matching rules — queued for review"
}
```

#### Response (rejected)

```json
// 403 Forbidden
{
  "status": "rejected",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "rejected_at": "2026-07-20T00:42:38Z",
  "reason": "Only ed25519 keys accepted"
}
```

### `GET /v1/auth/status`

Check signup approval status for a machine.

#### Headers

```
X-SSH-Fingerprint: SHA256:<machine-key-fingerprint>
X-SSH-Signature: <base64-encoded SSHSIG signature>
```

#### Response

```json
// 200 OK
{
  "machine_id": "a1b2c3d4-...",
  "status": "approved",
  "owner_fingerprint": "SHA256:abc123...",
  "registered_keys": 2,
  "approved_at": "2026-07-20T00:42:38Z"
}
```

### `POST /v1/auth/register`

Register an SSH public key for publishing. One-time operation per key.

#### Request

```json
{
  "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... user@example.com"
}
```

#### Response

```json
// 201 Created
{
  "fingerprint": "SHA256:abc123...",
  "public_key_type": "ssh-ed25519",
  "comment": "user@example.com",
  "registered_at": "2026-07-17T12:00:00Z"
}
```

### `POST /v1/patches`

Publish a new package (first version). The registry acts as a **notary** — it stores metadata and checksums, not the archive itself.

#### Headers

```
X-SSH-Fingerprint: SHA256:<fingerprint>
X-SSH-Signature: <base64-encoded SSHSIG signature>
Content-Type: application/json
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Package name matching `cognitive.json` |
| `version` | string | Yes | SemVer version |
| `description` | string | No | Human-readable description |
| `author` | string | No | Author or organization |
| `license` | string | No | SPDX license identifier |
| `source_repository` | string | No | Source repository URL |
| `source_issues` | string | No | Issue tracker URL |
| `download_urls` | map[string]string | Yes | Variant-keyed download URLs (e.g., `{"linux/amd64": "https://..."}`) |
| `sha256` | string | Yes | SHA-256 hex digest of the manifest JSON bytes (signed by publisher) |
| `manifest` | object | Yes | Full parsed `cognitive.json` from the archive |
| `tags` | array[string] | No | Tags for discovery |
| `capabilities` | array[string] | No | Capability strings from `runtime.capabilities` for functional discovery |

**Note:** The `download_url` (string) field from v1.x is replaced by `download_urls` (map). This is a breaking change — see [ADR-007](../adr/ADR-007-registry-server-architecture.md).

#### Validation (A1-A10)

The server performs the following validations before accepting the publish:

| # | Validation | Fail Action |
|---|-----------|-------------|
| A1 | `manifest` is valid JSON with all required fields | HTTP 422, "invalid manifest: <details>" |
| A2 | Manifest matches schema — required fields present, no unknown fields, types correct | HTTP 422, "schema violation: <details>" |
| A3 | `sha256` is a 64-char lowercase hex string | HTTP 422, "invalid sha256" |
| A4 | Dependency graph has no cycles | HTTP 422, "dependency cycle: <path>" |
| A5 | All transitive dependencies exist in registry | HTTP 422, "unresolvable dependency: <name> <version>" |
| A6 | No transitive dependency has status `buggy` | HTTP 422, "depends on buggy package: <name> <version>" |
| A7 | All referenced files exist in archive (tool binaries, adapters, system prompts) | HTTP 422, "missing file: <path>" |
| A8 | Hardware requirements within sane bounds | HTTP 422, "invalid hardware_requirements: <field>" |
| A9 | Source repository is a valid URL | HTTP 422, "invalid repository URL" |
| A10 | Source issues URL is reachable (HTTP 200 within 10s) | HTTP 422, "unreachable issues URL" |

#### Success Response

```json
// 201 Created
{
  "name": "email-manager",
  "version": "1.2.0",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "download_urls": {
    "linux/amd64": "https://github.com/.../email-manager-1.2.0-linux-amd64.cgp",
    "linux/arm64": "https://github.com/.../email-manager-1.2.0-linux-arm64.cgp"
  },
  "publisher_fingerprint": "SHA256:abc123...",
  "url": "/v1/patches/email-manager/1.2.0"
}
```

### `PUT /v1/patches/{name}/{version}`

Publish a new version of an existing package. Same request/response format as `POST /v1/patches`. The name and version in the URL must match `manifest.name` and `manifest.version`.

#### Request

```
PUT /v1/patches/email-manager/1.3.0
X-SSH-Fingerprint: SHA256:<fingerprint>
X-SSH-Signature: <base64-encoded signature>
Content-Type: application/json
```

Same JSON body as `POST /v1/patches`.

#### Response

```
HTTP/1.1 201 Created
```

### `PATCH /v1/patches/{name}/{version}/status`

Update the status of a package version. Requires admin scope (SSH key with admin privileges).

#### Request

```json
{
  "status": "deprecated"
}
```

Valid statuses: `active`, `deprecated`, `buggy`.

#### Response

```json
// 200 OK
{
  "status": "deprecated"
}
```

### `GET /v1/patches/{name}/dependencies`

Get the dependency tree for a package.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `version` | string | latest | Version to inspect |

#### Response

```json
// 200 OK
{
  "name": "email-manager",
  "version": "1.2.0",
  "dependencies": {
    "contacts-bridge": "^1.0.0"
  },
  "transitive": ["contacts-bridge@1.2.0"],
  "status": "active"
}
```

### `POST /v1/patches/{name}/{version}/validate`

Trigger re-validation of an existing package against rules A1-A10. Requires admin scope.

#### Response

```json
// 200 OK
{
  "status": "valid",
  "rules": {
    "A1": true,
    "A2": true,
    "A3": true,
    "A4": true,
    "A5": true,
    "A6": true,
    "A7": true,
    "A8": true,
    "A9": true,
    "A10": true
  }
}
```

### `POST /v1/patches/{name}/{version}/unlock`

Verify an unlock code for a paid package.

#### Request

```json
{
  "code": "CGOS-ABCD-EFGH"
}
```

#### Success Response

```json
// 200 OK
{
  "status": "valid",
  "download_urls": {
    "linux/amd64": "https://.../email-manager-1.2.0-linux-amd64.cgp",
    "linux/arm64": "https://.../email-manager-1.2.0-linux-arm64.cgp"
  },
  "download_token": "cpg_dl_xxxxxxxxxxxxxxxxxxxx"
}
```

The `download_token` is a single-use token valid for 24 hours.

#### Error Responses

```json
// 403 Forbidden
{
  "status": "invalid",
  "error": {
    "code": "INVALID_CODE",
    "message": "The unlock code provided is not valid or has expired."
  }
}

// 404 Not Found
{
  "status": "invalid",
  "error": {
    "code": "NOT_FOUND",
    "message": "Package not found or does not require unlock."
  }
}
```

## Error Response Format

All errors follow this envelope:

```json
{
  "error": {
    "code": "<ERROR_CODE>",
    "message": "<Human-readable description>",
    "details": {
      "field": "<field name>",
      "reason": "<specific reason>"
    }
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_FAILED` | 422 | Input validation failed (A1-A10) |
| `ALREADY_EXISTS` | 409 | Resource already exists |
| `UNAUTHORIZED` | 401 | Missing or invalid SSH signature |
| `FORBIDDEN` | 403 | Authenticated but lacks required scope |
| `INVALID_CODE` | 403 | Unlock code invalid or expired |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server-side error |

## Pagination

All list endpoints return paginated results.

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `per_page` | integer | 20 | Results per page (max 100) |

### Response Fields

| Field | Description |
|-------|-------------|
| `results` | Array of result objects |
| `total` | Total number of results across all pages |
| `page` | Current page number |
| `per_page` | Results per page |

## Rate Limiting

| Endpoint group | Limit | Window |
|----------------|-------|--------|
| Read (search, metadata) | 100 req/min | Per IP |
| Download | 50 req/min | Per IP |
| Publish | 10 req/min | Per publisher fingerprint |
| Notary check | 30 req/min | Per IP |
| Unlock | 5 req/min | Per IP |

Rate limit headers are returned:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1687534200
```

## S3 Storage Model

The registry stores all metadata in S3-compatible storage (Cloudflare R2 default). See [ADR-007](../adr/ADR-007-registry-server-architecture.md) for the full object layout.

**Configuration:**

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `S3_ENDPOINT` | — | S3-compatible endpoint URL |
| `S3_BUCKET` | `cognitiveos-registry` | Bucket name |
| `S3_ACCESS_KEY` | — | Access key ID |
| `S3_SECRET_KEY` | — | Secret access key |
| `S3_REGION` | `auto` | Region (R2 uses `auto`) |

**Object keys:**

```
notary/{source}/{path}/{version}/manifest.json   — package metadata + checksum
auth/keys/{fingerprint}.pub                       — registered SSH public keys
unlock/{source}/{path}/{version}/{code_hash}.json — unlock code records
```
