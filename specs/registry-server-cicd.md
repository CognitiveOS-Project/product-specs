# Registry Server CI/CD Specification

## Overview

The registry-server (`github.com/CognitiveOS-Project/registry-server`) is the centralized notary proxy for `.cgp` packages. This document specifies its CI/CD pipeline, deployment targets, and secrets management.

## Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| CI | `.github/workflows/ci.yml` | Push to `main`, PRs to `main` | Build, lint, test, vet |
| Deploy Cloud Run | `.github/workflows/deploy-cloud-run.yml` | Push to `main`, manual | Build Docker → GCR → Cloud Run |
| Publish Image | `.github/workflows/publish.yml` (root) | Push to `main`, semver tags | Docker → GHCR |

## CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.25'
      - name: Build
        run: make build
      - name: Lint
        uses: golangci/golangci-lint-action@v6
        with:
          version: latest
          args: --timeout=3m
      - name: Test
        run: make test
      - name: Vet
        run: make lint
```

## Deployment Pipeline

### Google Cloud Run (Primary)

```yaml
# .github/workflows/deploy-cloud-run.yml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - Checkout
      - Auth to GCP via service account key
      - Build Docker image
      - Push to Google Container Registry (GCR)
      - Deploy to Cloud Run with secrets as env vars
      - Set traffic to latest revision
```

### Deployment Target Configuration

| Parameter | Value |
|-----------|-------|
| Platform | Google Cloud Run |
| Region | `us-central1` |
| Min instances | 0 (free tier) |
| Max instances | 10 |
| Port | 8080 |
| CPU | 1 vCPU |
| Memory | 512 MiB |
| Concurrency | 80 |
| Timeout | 300s |

### Environment Variables (from secrets)

| Variable | Secret Name | Description |
|----------|-------------|-------------|
| `PORT` | — | Fixed: `8080` |
| `DATA_DIR` | — | Fixed: `/data` |
| `S3_ENDPOINT` | `R2_ENDPOINT` | Cloudflare R2 endpoint |
| `S3_BUCKET` | `R2_BUCKET` | R2 bucket name |
| `S3_ACCESS_KEY` | `R2_ACCESS_KEY` | R2 API token |
| `S3_SECRET_KEY` | `R2_SECRET_KEY` | R2 API token secret |
| `S3_REGION` | — | Fixed: `auto` |
| `BASE_DOMAIN` | `BASE_DOMAIN` | Domain (default: `cognitive-os.org`) |
| `REGISTRY_GH_TOKEN` | `REGISTRY_GH_TOKEN` | GitHub PAT (repo scope) — creates releases + uploads assets |
| `REGISTRY_GH_ORG` | `REGISTRY_GH_ORG` | GitHub org for official package storage |

### Domain Mapping

The registry follows the URL convention:

```
https://registry-{country}-{distro}-{role}.{BASE_DOMAIN}/v1
```

| Segment | Values | Example |
|---------|--------|---------|
| `{country}` | `us`, `eu`, `jp`, `sg`, `br` | `us` |
| `{distro}` | `all-distros`, `cognitiveos` | `all-distros` |
| `{role}` | `official`, `mirror`, `alternative` | `official` |

Primary instance: `registry-us-all-distros-official.cognitive-os.org`

Domain mapping is deferred — initial deployment uses Cloud Run's default `*.run.app` URL.

## Secrets Management

### Required GitHub Secrets

| Secret | Source | Purpose |
|--------|--------|---------|
| `GCP_PROJECT_ID` | GCP Console | Google Cloud project ID |
| `GCP_SA_KEY` | GCP IAM → Service Accounts → JSON key | Deploy authentication |
| `BASE_DOMAIN` | Configurable | Base domain (default: `cognitive-os.org`) |
| `R2_ENDPOINT` | Cloudflare R2 dashboard | S3-compatible endpoint |
| `R2_BUCKET` | Cloudflare R2 dashboard | Bucket name |
| `R2_ACCESS_KEY` | Cloudflare R2 API tokens | S3 authentication |
| `R2_SECRET_KEY` | Cloudflare R2 API tokens | S3 authentication |
| `REGISTRY_GH_TOKEN` | GitHub PAT (`repo` scope) | Official publish — creates repos, releases, uploads assets |
| `REGISTRY_GH_ORG` | GitHub org name | Official publish — target org for package storage |

### Setup Scripts

Setup scripts are in `scripts/{provider}/`:

```
scripts/
├── google-cloud/
│   ├── setup-project.sh          # Create GCP project + enable APIs
│   └── setup-service-account.sh  # Create deployer SA + roles
└── cloudflare/
    └── setup-r2.sh               # Create R2 bucket + API token
```

## Hosting Provider Matrix

The registry-server is hosting-agnostic (no platform-specific code). Deployment targets:

| Provider | Workflow File | Status |
|----------|---------------|--------|
| Google Cloud Run | `deploy-cloud-run.yml` | Primary |
| AWS Lambda + API Gateway | `deploy-aws-lambda.yml` | Future mirror (docs only) |
| Fly.io | `deploy-flyio.yml` | Future mirror (docs only) |
| Kubernetes | `deploy-k8s.yml` | Enterprise option (docs only) |

Each deployment workflow reads the same Dockerfile and env var configuration.

## Security

### CI Security

- No secrets in build logs
- Docker build uses multi-stage (builder + distroless runtime)
- `CGO_ENABLED=0` for static binary
- No shell access in runtime image (distroless)

### Deployment Security

- Service account with minimal roles (`roles/run.admin`, `roles/storage.admin`)
- Secrets injected as env vars at deploy time
- No secrets in Docker image layers
- Cloud Run HTTPS by default
- Rate limiting and anti-bot middleware active

## Monitoring

After deployment, verify:

```bash
# Health check
curl https://<service-url>/v1/health

# Rate limit headers
curl -I https://<service-url>/v1/search?q=test
# X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
```

## References

- `specs/registry-api.md` — REST API contract
- `specs/fair-use-policy.md` — Public fair use policy
- `adr/ADR-007-registry-server-architecture.md` — S3 store, SSH auth, notary model
- `adr/ADR-008-hosting-decision.md` — Google Cloud Run hosting decision
