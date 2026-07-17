# ADR-007: Registry Server Architecture — S3 Store, SSH Auth, Notary Model

**Status:** Accepted
**Date:** 2026-07-17
**Author:** CognitiveOS SDLC

## Context

The registry-server is the centralized notary proxy for `.cgp` packages. The current implementation has several architectural weaknesses:

| Issue | Current State | Impact |
|-------|--------------|--------|
| Storage | Filesystem-backed JSON files (`MemoryStore` or `FileStore`) | Data loss on restart (memory), no scalability, no redundancy |
| Auth | Hardcoded Bearer token (`test-token`) | No real security, no publisher identity, no audit trail |
| Checksum verification | Stores publisher-submitted SHA-256 but never re-verifies | Tamper detection is trust-based, not cryptographic |
| Download variants | Single `download_url` per version | No `os`/`arch` variant resolution despite spec support |
| Notary check | `cpm-spec.md` describes `GET /v1/notary/check` but endpoint does not exist | Core vision concept unimplemented |

The Gemini vision conversations established that the registry should act as a **Decentralized Router and Security Notary** — storing only metadata and checksums in S3-compatible storage, authenticating publishers via SSH keys, and re-verifying package integrity on demand.

## Decision

Replace the filesystem store and Bearer token auth with an S3-compatible store and SSH public key authentication.

### Store: S3-Compatible Interface

Define a `Store` interface with S3 as the primary implementation. Works with Cloudflare R2 (default), MinIO, AWS S3, Backblaze B2, or any S3-compatible backend.

```
Store interface
├── S3Store          — S3/R2 implementation (production)
├── MemoryStore      — in-memory (tests only)
└── FileStore        — local filesystem (development, backward compat)
```

**Configuration via environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_ENDPOINT` | — | S3-compatible endpoint URL |
| `S3_BUCKET` | `cognitiveos-registry` | Bucket name |
| `S3_ACCESS_KEY` | — | Access key ID |
| `S3_SECRET_KEY` | — | Secret access key |
| `S3_REGION` | `auto` | Region (R2 uses `auto`) |

**S3 Object Layout:**

```
cognitiveos-registry/
├── notary/
│   └── {source}/
│       └── {path}/
│           └── {version}/
│               └── manifest.json
├── auth/
│   └── keys/
│       └── {fingerprint}.pub
└── unlock/
    └── {source}/{path}/{version}/
        └── {code_hash}.json
```

Each `manifest.json` stores:

```json
{
  "manifest": { "name": "...", "version": "...", ... },
  "sha256": "abc123...",
  "download_urls": {
    "linux/amd64": "https://github.com/.../patch-linux-amd64.cgp",
    "linux/arm64": "https://github.com/.../patch-linux-arm64.cgp"
  },
  "publisher_fingerprint": "SHA256:abc123...",
  "published_at": "2026-07-17T00:00:00Z",
  "status": "active",
  "tags": ["vision", "display"],
  "capabilities": ["display.render_image"]
}
```

### Auth: SSH Public Key Verification

Replace Bearer tokens with SSH key-based authentication. Publishers register their SSH public key once; cpm signs requests with their private key.

**Registration flow:**

```
Publisher runs:
  cpm auth register --key ~/.ssh/id_ed25519.pub
    → POST /v1/auth/register
    → Body: { "public_key": "<contents of .pub file>" }
    → Server stores key at auth/keys/{fingerprint}.pub in S3
    → Server returns: { "fingerprint": "SHA256:abc123...", "registered_at": "..." }
```

**Publish flow:**

```
Publisher runs:
  cpm publish ./patch.cgp --download-url https://...
    → Reads manifest.json from .cgp archive
    → Computes SHA-256 of manifest JSON bytes
    → Signs hash with private key (SSHSIG protocol via golang.org/x/crypto/ssh)
    → Sends: POST /v1/patches
      Headers:
        X-SSH-Fingerprint: SHA256:abc123...
        X-SSH-Signature: <base64-encoded signature>
      Body: { manifest, sha256, download_urls, ... }

Server:
  1. Extract fingerprint from header
  2. Load public key from S3: auth/keys/{fingerprint}.pub
  3. Verify signature against manifest hash
  4. If valid → store manifest in S3, return 201
  5. If invalid → return 401 Unauthorized
```

**Why SSH keys over Bearer tokens:**

| Property | Bearer Tokens | SSH Keys |
|----------|--------------|----------|
| Secret storage | Server stores secret | Server stores only public key |
| Identity binding | Token = access, no identity | Fingerprint = unique publisher identity |
| Revocation | Delete token | Delete public key |
| Audit trail | Token prefix only | Full fingerprint, key type, comment |
| Industry trend | Legacy | Modern (Sigstore, GitHub, GitLab) |
| Developer UX | Generate + manage token | Use existing SSH keypair |

### Notary Check: Remote Verification

Add `GET /v1/notary/check` as specified in `cpm-spec.md`:

```
GET /v1/notary/check?source=github.com&path=user/skill&version=v1.2.0

Server:
  1. Load manifest from S3: notary/github.com/user/skill/v1.2.0/manifest.json
  2. Extract download_url for the requested variant
  3. HEAD request to download_url → get Content-Length and ETag
  4. If ETag matches stored sha256 → verified
  5. If no ETag: GET full file, compute SHA-256, compare
  6. Return { verified: bool, stored_hash, remote_hash, checked_at }
```

### Multi-Variant Downloads

The `download_urls` field is a `map[string]string` keyed by `{os}/{arch}` (e.g., `"linux/amd64"`, `"linux/arm64"`, `"linux/arm/v7"`).

The download endpoint resolves variants:

```
GET /v1/patches/{name}/{version}/download?os=linux&arch=arm64

Resolution:
  1. Look up download_urls["linux/arm64"]
  2. If found → 302 redirect to that URL
  3. If not found → look up download_urls[""] (universal)
  4. If neither → 404
```

### Breaking Changes

| Change | Before | After |
|--------|--------|-------|
| Auth method | `Authorization: Bearer <token>` | `X-SSH-Fingerprint` + `X-SSH-Signature` headers |
| Token format | `cpg_reg_...` | SSH public key fingerprint |
| Store backend | Filesystem/JSON | S3-compatible (R2 default) |
| Download field | `download_url` (string) | `download_urls` (map[string]string) |
| Notary check | Not implemented | `GET /v1/notary/check` |
| Rate limit scope | Per token | Per publisher fingerprint |

## Consequences

**Positive:**
- No secrets stored on the server (only public keys)
- Publisher identity is cryptographic, not opaque token
- S3-compatible store scales to any volume, free tier on R2
- Notary check provides real tamper detection, not trust-based
- Multi-variant downloads enable proper cross-platform distribution
- S3 interface allows switching backends without code changes

**Negative:**
- Breaking change to publish API — requires coordinated cpm + registry release
- SSH key management adds UX step (publisher must register key once)
- S3 adds operational dependency (mitigated by R2 free tier and S3-compatible alternatives)
- Notary check adds latency to pre-install verification (mitigated by caching)

**Risks:**
- R2 free tier limits (10GB, 1M writes, 10M reads) may be exceeded at scale — monitor and upgrade plan needed
- SSH key compromise — publisher must revoke and re-register (mitigated by key rotation in cpm)

## Alternatives Considered

1. **SQLite metadata store** — rejected: too expensive at scale, no built-in replication, operational overhead for edge deployments
2. **PostgreSQL** — rejected: operational complexity overkill for a metadata-only store
3. **Bearer tokens (keep current)** — rejected: persistent secrets, no publisher identity, industry is moving to key-based auth
4. **x509 client certificates** — rejected: more complex than SSH keys, PKI infrastructure overhead, deferred to future consideration
5. **Cloudflare Workers + D1 (serverless)** — rejected: requires Go-to-WASM compilation, not worth the rewrite when Go binary + R2 works
6. **npm-compatible proxy** — rejected: replaced by cpm Universal Protocol Router (npm, Bun, Deno, GitHub support in cpm client)
7. **Filesystem store with S3 fallback** — rejected: adds unnecessary abstraction layer; S3 as primary is simpler

## References

- `specs/registry-api.md` — REST API contract (updated to v2.0.0-draft)
- `specs/cpm-spec.md` — cpm Universal Protocol Router, `notary/check` endpoint
- `specs/security-model.md` — trust boundary, supply chain verification
- `specs/ephemeral-identity.md` — future biometric attestation (complements SSH key auth)
- `gemini-conversation-about-registry-server.md` — vision: decentralized notary, Cloudflare hosting
- `gemini-conversation-cpm-multiple-registry-servers.md` — vision: S3/D1 schema, notary ledger
- `adr/ADR-002-download-weights.md` — precedent: provider pattern for registry interactions
