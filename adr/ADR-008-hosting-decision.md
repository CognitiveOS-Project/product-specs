# ADR-008: Hosting Decision — Google Cloud Run

**Status:** Accepted
**Date:** 2026-07-17
**Author:** CognitiveOS SDLC

## Context

The registry-server needs a hosting platform. After evaluating 10+ options across serverless, VPS, and managed container platforms, we selected Google Cloud Run as the primary hosting target. The registry-server must be hosting-agnostic (no platform-specific code), but Cloud Run is the deployment target for the official instance.

## Decision

**Primary:** Google Cloud Run (free tier, `min-instances=0`)
**Future mirror:** AWS Lambda + API Gateway (mentioned, not implemented)
**Storage:** Cloudflare R2 (S3-compatible, 10GB free tier)

### Why Cloud Run

| Criterion | Cloud Run | Fly.io | Hetzner VPS | AWS t2.micro | Vercel |
|-----------|-----------|--------|-------------|-------------|--------|
| Free tier | 240K vCPU-s, 450K GiB-s/mo | 3 VMs, 160GB BW | None (3.29 EUR/mo) | 750 hrs/12mo only | Hobby (non-commercial) |
| Go support | Native (Dockerfile) | Native | Native | Native | Secondary (serverless) |
| Cold starts | 100-200ms (Go) | Configurable | None | None | Yes |
| Vendor lock-in | Moderate | Moderate | None | High | High |
| Ops burden | Low (managed) | Low | Medium | Medium | Low |

Cloud Run wins on the combination of free tier generosity, Go native support, and zero-ops deployment. Go cold starts on Cloud Run are 100-200ms (fastest of any serverless platform) due to the compiled binary and minimal container image.

### Hosting Candidates Considered

| Platform | Why Rejected |
|----------|-------------|
| Cloudflare Workers | Requires Go to WASM compilation (TinyGo). ADR-007 explicitly rejected this |
| Fly.io | Free tier VMs sleep after inhibernation. Cold starts on every first request |
| Hetzner CX22 | 3.29 EUR/mo, excellent value, but adds ops burden for a single stateless service |
| AWS t2.micro | Free only 12 months, then $8.47/mo. 2.5x more expensive than Hetzner for fewer resources |
| Railway | $5 free credit burns down, then pay-per-use. Less predictable costs |
| DigitalOcean App Platform | No free tier, more expensive than Hetzner for same specs |
| Vercel | Frontend-first platform. Go is secondary. Hobby plan is non-commercial only |
| Google Cloud Functions | Wrong abstraction for HTTP servers. Designed for single-purpose event handlers |
| AWS Lambda + API Gateway | Viable but more complex setup than Cloud Run. Considered as future mirror |

### Architecture: Hosting-Agnostic Design

The registry-server is designed to run anywhere:

- **No platform-specific imports** — pure Go stdlib + `golang.org/x/time/rate`
- **Environment variable configuration** — `PORT`, `DATA_DIR`, `S3_*` (Cloud Run injects PORT automatically)
- **Dockerfile-based deployment** — works on Cloud Run, Fly.io,任何 container orchestrator
- **S3-compatible storage** — R2 default, configurable via env vars
- **Static binary** — `CGO_ENABLED=0`, runs on scratch/distroless

### Anti-Bot and Rate Limiting

The registry employs layered defense:

1. **Rate limiting** — Per-IP token bucket via `golang.org/x/time/rate`
2. **User-Agent filtering** — Blocks empty and known-malicious User-Agents
3. **Path probing protection** — Blocks `.env`, `.git`, `wp-admin`, etc.
4. **Request size limits** — 1 MB max body

Rate limits are intentionally restrictive (tiniest viable) to protect the free tier:
- 10 req/min per IP for reads
- 5 req/min for downloads
- 30 req/min global cap

See `specs/fair-use-policy.md` for the public-facing policy.

### Future: AWS Lambda Mirror

AWS Lambda + API Gateway is mentioned as a future mirror candidate for hosting-agnostic redundancy. The same Dockerfile and S3-compatible store design makes this straightforward to add. Implementation is deferred until the primary Cloud Run deployment is stable.

## Consequences

**Positive:**
- Zero hosting cost on free tier for low-to-moderate traffic
- Zero ops burden (managed platform)
- Go cold starts are fast (100-200ms)
- Hosting-agnostic code allows future migration or mirroring
- S3-compatible store works with any provider

**Negative:**
- Cloud Run free tier may be exceeded at high traffic (monitor and set `max-instances`)
- Cold starts on `min-instances=0` (accepted trade-off for zero cost)
- Vendor lock-in to GCP for the official instance (mitigated by hosting-agnostic design)

**Risks:**
- GCP free tier limits may change — monitor quarterly
- Free tier exhaustion at scale — set billing alerts, consider `min-instances=1` if latency matters

## References

- `specs/registry-api.md` — REST API contract
- `specs/fair-use-policy.md` — Public fair use policy
- `specs/security-model.md` — Trust boundary, supply chain
- `adr/ADR-007-registry-server-architecture.md` — S3 store, SSH auth, notary model
- Cloud Run pricing: https://cloud.google.com/run/pricing
