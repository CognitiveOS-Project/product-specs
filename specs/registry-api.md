# Registry Server API Specification

Version: 1.1.0

## Overview

The CognitiveOS registry server is a **notary proxy** REST API for registering, searching, and redirecting to `.cgp` packages. It does **not** host files — it stores metadata and checksums, and redirects clients to canonical download URLs.

The protocol is open: anyone can implement a compatible server, host a private registry, or mirror the public one.

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
| Publish (POST, PUT) | Yes | Bearer token with `publish` scope |
| Unlock code verification | No | Public (code is the auth) |
| Status change | Yes | Bearer token with `admin` scope |

### Token Format

```
Authorization: Bearer cpg_reg_xxxxxxxxxxxxxxxxxxxx
```

Tokens are issued by registry operators. They are opaque strings — the server validates them against its internal store.

### Scopes

| Scope | Permission | Required For |
|-------|------------|--------------|
| `publish` | Publish new packages and versions | `POST /v1/patches`, `PUT /v1/patches/{name}/{version}` |
| `admin` | Full administrative access | Status changes, token management |

### Token Validation

```
GET /v1/patches  → No auth required (public)
POST /v1/patches → Bearer token with publish scope
PUT /v1/patches/{name}/{version} → Bearer token with publish scope
```

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
  "version": "1.1.0"
}
```

### `GET /v1/search`

Search for packages.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (matches name, description, tags) |
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
      "download_url": "https://github.com/.../email-manager-1.2.0.cgp",
      "status": "active"
    },
    {
      "version": "1.1.0",
      "published_at": "2026-06-10T10:00:00Z",
      "sha256": "a4b5c6d7e8f90123456789abcdef0123456789abcdef0123456789abcdef0123",
      "download_url": "https://github.com/.../email-manager-1.1.0.cgp",
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
  "download_url": "https://github.com/.../email-manager-1.2.0.cgp",
  "published_at": "2026-06-23T14:30:00Z",
  "downloads": 42,
  "status": "active",
  "manifest": { }
}
```

The `manifest` field contains the full parsed `cognitive.json`.

### `GET /v1/patches/{name}/{version}/download`

Download redirect. The registry does **not** host files — it redirects to the canonical download URL.

#### Response

```
HTTP/1.1 302 Found
Location: https://github.com/.../email-manager-1.2.0.cgp
```

### `POST /v1/patches`

Publish a new package (first version). The registry acts as a **notary** — it stores metadata and checksums, not the archive itself.

#### Headers

```
Authorization: Bearer <token-with-publish-scope>
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
| `download_url` | string | Yes | Canonical download URL for the `.cgp` archive |
| `sha256` | string | Yes | SHA-256 hex digest of the full `.cgp` archive |
| `tags` | array[string] | No | Tags for discovery |
| `manifest` | object | Yes | Full parsed `cognitive.json` from the archive |

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
  "download_url": "https://github.com/.../email-manager-1.2.0.cgp",
  "url": "/v1/patches/email-manager/1.2.0"
}
```

### `PUT /v1/patches/{name}/{version}`

Publish a new version of an existing package. Same request/response format as `POST /v1/patches`. The name and version in the URL must match `manifest.name` and `manifest.version`.

#### Request

```
PUT /v1/patches/email-manager/1.3.0
Content-Type: application/json
Authorization: Bearer <token-with-publish-scope>
```

Same JSON body as `POST /v1/patches`.

#### Response

```
HTTP/1.1 201 Created
```

### `PATCH /v1/patches/{name}/{version}/status`

Update the status of a package version. Requires `admin` scope.

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

Trigger re-validation of an existing package against rules A1-A10. Requires `admin` scope.

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
  "download_url": "https://.../email-manager-1.2.0.cgp",
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
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
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
| Publish | 10 req/min | Per token |
| Unlock | 5 req/min | Per IP |

Rate limit headers are returned:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1687534200
```
