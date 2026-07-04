# Registry Server API Specification

Version: 1.0.0-draft

## Overview

The CognitiveOS registry server is a REST API for hosting, searching, and distributing `.cgp` patches. It is the backend that `cpm` communicates with.

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
| Read (search, metadata, download) | No | Public |
| Publish (upload, version) | Yes | Bearer token |
| Unlock code verification | No | Public (code is the auth) |

### Token Format

```
Authorization: Bearer cpg_reg_xxxxxxxxxxxxxxxxxxxx
```

Tokens are issued by registry operators. They are opaque strings — the server validates them against its internal store.

### Token Scopes

| Scope | Permission |
|-------|------------|
| `publish` | Publish new patches and versions |
| `admin` | Full administrative access |

## Endpoints

### `GET /v1/search`

Search for patches.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Search query (matches name, description, author) |
| `exact` | boolean | false | If true, match name exactly |
| `license` | string | — | Filter by SPDX license identifier |
| `min_ram_mb` | integer | — | Minimum RAM requirement |
| `min_storage_mb` | integer | — | Minimum storage requirement |
| `author` | string | — | Filter by author |
| `page` | integer | 1 | Page number (1-indexed) |
| `per_page` | integer | 20 | Results per page (max 100) |

#### Response

```json
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
      "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
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

Get the latest version metadata for a patch.

#### Response

```json
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

List all versions of a patch.

#### Response

```json
{
  "name": "email-manager",
  "versions": [
    {
      "version": "1.2.0",
      "published_at": "2026-06-23T14:30:00Z",
      "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size_bytes": 47185920
    },
    {
      "version": "1.1.0",
      "published_at": "2026-06-10T10:00:00Z",
      "checksum_sha256": "a4b5c6d7e8f90123456789abcdef0123456789abcdef0123456789abcdef0123",
      "size_bytes": 46137344
    }
  ]
}
```

### `GET /v1/patches/{name}/{version}`

Get metadata for a specific version.

#### Response

```json
{
  "name": "email-manager",
  "version": "1.2.0",
  "description": "Background email triaging, drafting, and notification routing.",
  "author": "CognitiveOS",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 2048,
    "min_storage_mb": 150,
    "npu_required": false
  },
  "dependencies": {
    "contacts-bridge": "^1.0.0"
  },
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 47185920,
  "published_at": "2026-06-23T14:30:00Z",
  "downloads": 42,
  "cognitive_schema_version": "1.0.0"
}
```

### `GET /v1/patches/{name}/{version}/download`

Download the `.cgp` archive.

#### Headers

| Header | Value |
|--------|-------|
| `Content-Type` | `application/octet-stream` |
| `Content-Disposition` | `attachment; filename="<name>-<version>.cgp"` |
| `Content-Length` | `<size_bytes>` |
| `X-Checksum-SHA256` | `<hex>` |

#### Response

Binary stream of the `.cgp` archive.

#### Error

```json
// 404
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Patch 'email-manager' version '1.2.0' not found"
  }
}
```

### `POST /v1/patches`

Publish a new patch (first version).

#### Headers

```
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

#### Body

| Field | Type | Description |
|-------|------|-------------|
| `cognitive.json` | file | The manifest file (uploaded separately for indexing) |
| `archive` | file | The `.cgp` archive |

#### Response

```json
// 201 Created
{
  "name": "my-skill",
  "version": "1.0.0",
  "checksum_sha256": "abc123...",
  "size_bytes": 12345,
  "url": "/v1/patches/my-skill/1.0.0"
}
```

#### Errors

| Code | Status | Description |
|------|--------|-------------|
| `VALIDATION_FAILED` | 422 | `cognitive.json` fails schema validation |
| `ALREADY_EXISTS` | 409 | Patch version already exists |
| `UNAUTHORIZED` | 401 | Invalid or missing token |
| `FORBIDDEN` | 403 | Token lacks `publish` scope |

### `PUT /v1/patches/{name}/{version}`

Publish a specific version of an existing patch.

Same request/response format as `POST /v1/patches`. The name in the URL must match the name in `cognitive.json`.

### `POST /v1/patches/{name}/{version}/unlock`

Verify an unlock code for a paid patch.

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
  "message": "Unlock code accepted. Download authorized.",
  "download_token": "cpg_dl_xxxxxxxxxxxxxxxxxxxx"
}
```

The `download_token` is a single-use token valid for 24 hours. It is used as:

```
Authorization: Bearer cpg_dl_xxxxxxxxxxxxxxxxxxxx
GET /v1/patches/email-manager/1.2.0/download
```

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
    "message": "Patch not found or does not require unlock."
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
      "field": "cognitive.json",
      "reason": "Missing required field: 'name'"
    }
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_FAILED` | 422 | Input validation failed |
| `ALREADY_EXISTS` | 409 | Resource already exists |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Authenticated but not permitted |
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

## Healthcheck

```
GET /health
→ 200 OK
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "patches_count": 142,
  "version": "1.0.0"
}
```
