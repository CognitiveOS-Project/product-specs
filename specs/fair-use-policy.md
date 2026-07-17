# CognitiveOS Registry — Fair Use Policy

Version: 1.0.0

## Overview

The CognitiveOS registry (`registry.cognitive-os.org`) is a free, community-hosted notary proxy for `.cgp` packages. To keep it running for everyone, we ask that all users follow this fair use policy.

The registry is funded by the community and operates on Google Cloud Run's free tier. Abuse threatens the availability of the service for all users.

## Acceptable Use

| Use Case | Allowed | Notes |
|----------|---------|-------|
| `cpm install` / `cpm search` | Yes | Primary use case — package management |
| `curl` / `wget` for debugging | Yes | Occasional manual requests |
| CI/CD pipelines | Yes | Building CognitiveOS images, testing |
| Automated bulk downloads | No | Use the data dump instead |
| Web scraping / crawling | No | Prohibited — see below |
| Bot farms / DDoS | No | Will result in IP ban |

## Rate Limits

Every client IP is subject to the following rate limits:

| Endpoint Group | Limit | Window |
|----------------|-------|--------|
| Read (search, metadata) | 10 req/min | Per IP |
| Download | 5 req/min | Per IP |
| Notary check | 5 req/min | Per IP |
| Publish | 2 req/min | Per fingerprint |
| Unlock | 2 req/min | Per IP |
| Auth register | 1 req/min | Per IP |
| **Global (all endpoints)** | **30 req/min** | **Per IP** |

Rate limit headers are included in every response:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1687534200
```

When rate limited, the server returns HTTP 429 with a `Retry-After` header.

### Why These Limits

A typical `cpm install` performs ~3 requests (search + metadata + download). At 10/5/5 limits, a user can install ~3 packages per minute. This is generous for interactive use while protecting against automated abuse.

## Anti-Bot Measures

The registry employs multiple layers of protection:

1. **Rate limiting** — Per-IP token bucket (see above)
2. **User-Agent validation** — Empty or known-malicious User-Agents are blocked
3. **Path probing protection** — Known attack paths (`.env`, `.git`, `wp-admin`, etc.) are blocked
4. **Request size limits** — Maximum 1 MB request body

## Prohibited Activities

| Activity | Consequence |
|----------|-------------|
| Bulk scraping of package metadata | Rate limit, then IP ban |
| Automated crawling without robots.txt compliance | IP ban |
| Attempting to exploit unlock codes | Immediate IP ban |
| DDoS or volumetric attacks | IP ban, reported to ISP |
| Circumventing rate limits via IP rotation | Subnet-level blocking |

## Data Dump (Future)

For legitimate bulk data needs ( mirrors, analytics, research), we plan to provide a daily database dump of all package manifests. This is the recommended way to access registry data in bulk.

See the crates.io model: `https://static.crates.io/db-dump.tar.gz`

## Enforcement

1. **Soft enforcement:** Rate limit headers and 429 responses
2. **Hard enforcement:** 403 Forbidden for blocked User-Agents and paths
3. **Escalation:** Repeated violations from an IP/subnet result in temporary ban
4. **Permanent ban:** DDoS attempts, exploit attempts, or sustained abuse

## Contact

If you need higher rate limits for legitimate use (e.g., CI/CD pipeline with high throughput), open an issue on the [registry-server repo](https://github.com/CognitiveOS-Project/registry-server).

## Precedents

This policy is modeled after established open-source registries:

| Registry | Policy |
|----------|--------|
| npm | 5M requests/month, enforced since 2019 |
| PyPI | Discretionary, explicit anti-scraping prohibition |
| crates.io | 1 req/sec API, daily DB dump alternative |
| Go modules | Caching proxy, no explicit limits published |
