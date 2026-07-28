# CognitiveOS Product Specs

Standards, schemas, and protocol definitions for the CognitiveOS ecosystem.

## Contents

### Specifications

| Path | Description |
|------|-------------|
| `specs/vision.md` | Product vision, design philosophy, and UX scenarios |
| `specs/architecture.md` | System architecture overview and data flow |
| `specs/filesystem-hierarchy.md` | Directory tree, partition layout, persistence rules |
| `specs/mcp-conventions.md` | MCP tool naming, transport, error codes, registration |
| `specs/cognitiveosd-api.md` | Daemon API: message types, startup/shutdown, error codes |
| `specs/cli-spec.md` | CLI/TUI: dual-mode interface — interactive TUI + non-interactive CLI |
| `specs/cpm-spec.md` | Package manager: commands, install lifecycle, error handling |
| `specs/inference-api.md` | Inference engine: Ollama-compatible API, model lifecycle |
| `specs/registry-api.md` (v2.1.0-draft) | Registry REST API: search, download, publish, unlock codes, Web UI, owner gating |
| `specs/cgp-format.md` | `.cgp` (Cognitive Patch) distribution format |
| `specs/system-codes.md` | Wake, Idle, Security, Reset, Unlock code definitions |
| `specs/security-model.md` | Trust boundary, process isolation, code integrity, incident response |
| `specs/distro-build-spec.md` | Alpine image build process, partition layout, overlay structure |
| `specs/boot-startup-analysis.md` | Complete boot/startup/process lifecycle analysis — gaps between specs and code |
| `specs/boot-flow.md` | Detailed boot flow specification for ISO and Docker deployments |
| `specs/fair-use-policy.md` | Fair use policy for the public registry |
| `specs/cpm-publish-flow.md` | CPM publish flow architecture — official and notary proxy paths |
| `specs/manifest-fields.md` | Manifest field reference (weights.method, weights.local, weights.cloud) |

### Tutorials

| Path | Description |
|------|-------------|
| `specs/tutorials/cgp-publishing.md` | End-to-end guide to publishing a .cgp package |
| `specs/tutorials/secret-management.md` | Secret management with `cpm secret` |
| `specs/tutorials/registry-server-web-ui.md` | Registry server Web UI — owner dashboard |
| `specs/tutorials/cpm-workflow.md` | CPM daily workflow tutorial |
| `specs/tutorials/cpm-tune.md` | CPM tune command tutorial |
| `specs/tutorials/download-weights.md` | Downloading model weights |
| `specs/tutorials/cli-mode.md` | CLI mode tutorial |
| `specs/tutorials/cgp-lifecycle.md` | .cgp lifecycle overview |
| `specs/tutorials/sandboxed-cgp-development.md` | Local CGP development: scaffold, build, verify, test |
| `specs/tutorials/custom-distro-images.md` | Building bootable images from source |

See the full list in `specs/tutorials/` — 25+ tutorials covering use cases from IoT vendors to AI companions.

### JSON Schemas

All schemas are in `schemas/`. See the [schemas directory](https://github.com/CognitiveOS-Project/product-specs/tree/main/schemas) for the full list.

| Schema | Description |
|--------|-------------|
| `cognitive.schema.json` | JSON Schema for cognitive.json manifest |
| `display-mcp.json` | Tool schema for display-mcp (render_image, render_video, screenshot) |
| `audio-mcp.json` | Tool schema for audio-mcp (play, capture, tts, volume, mute) |
| `network-mcp.json` | Tool schema for network-mcp (scan, connect, disconnect, status) |
| `gpio-mcp.json` | Tool schema for gpio-mcp (pin_read, pin_write, pwm, mode) |
| `serial-mcp.json` | Tool schema for serial-mcp (list, connect, send, receive) |
| `registry-health-response.json` | Health endpoint response |
| `registry-search-response.json` | Search endpoint response |
| `registry-package.json` | Full package metadata |
| `registry-package-version.json` | Single version entry |
| `registry-package-summary.json` | Package summary |
| `registry-package-search-result.json` | Search result entry |
| `registry-publish-request.json` | Publish request body |
| `registry-publish-response.json` | Publish response |
| `registry-versions-response.json` | Versions endpoint response |
| `registry-dependencies-response.json` | Dependencies endpoint response |
| `registry-notary-check-response.json` | Notary check response |
| `registry-unlock-request.json` | Unlock request body |
| `registry-unlock-response.json` | Unlock response |
| `registry-auth-status-response.json` | Auth status response |
| `registry-auth-signup-request.json` | Auth signup request |
| `registry-auth-signup-response.json` | Auth signup response |
| `registry-auth-register-request.json` | Auth register request |
| `registry-auth-register-response.json` | Auth register response |
| `registry-status-request.json` | Admin status update request |
| `registry-status-response.json` | Admin status update response |
| `registry-validate-response.json` | Admin validation response |
| `registry-error.json` | Error envelope |
| `registry-owner-key.json` | Owner key entry |

### Architecture Decision Records

| Path | Title |
|------|-------|
| `adr/ADR-003-backdoor-shell.md` | Backdoor shell access |
| `adr/ADR-004-package-manager-mcp-bridge.md` | Package manager MCP bridge |
| `adr/ADR-005-local-fine-tuning.md` | Local fine-tuning |
| `adr/ADR-006-riscv64-architecture.md` | RISC-V 64 architecture support |
| `adr/ADR-007-registry-server-architecture.md` | Registry server architecture (S3, SSH auth, notary) |
| `adr/ADR-008-hosting-decision.md` | Hosting decision (Cloud Run vs alternatives) |
| `adr/ADR-009-machine-identity-profile.md` | Machine identity profile and gated publisher model |
| `adr/ADR-010-cloud-models-and-secrets.md` | Cloud model support and secret management |

## Repos

| Repo | Layer | Description |
|------|-------|-------------|
| [product-specs](https://github.com/CognitiveOS-Project/product-specs) | Architecture | Standards and schemas (this repo) |
| [cognitiveos-alpine-distro](https://github.com/CognitiveOS-Project/cognitiveos-alpine-distro) | Base OS | Alpine Linux image builder |
| [cognitiveosd](https://github.com/CognitiveOS-Project/cognitiveosd) | Daemon | System daemon, codes, audits |
| [cli](https://github.com/CognitiveOS-Project/cli) | UI | Terminal User Interface (TUI) |
| [cpm](https://github.com/CognitiveOS-Project/cpm) | Package | Package manager |
| [inference](https://github.com/CognitiveOS-Project/inference) | Brain | LLM inference engine |
| [core-mcp-bridges](https://github.com/CognitiveOS-Project/core-mcp-bridges) | Hardware | MCP hardware servers |
| [cgp-template](https://github.com/CognitiveOS-Project/cgp-template) | Dev | .cgp boilerplate |
| [cognitiveos](https://github.com/CognitiveOS-Project/cognitiveos) | Meta | Main project repository |
| [registry-server](https://github.com/CognitiveOS-Project/registry-server) | Infra | Package registry |

See also: [cognitive-os.org](https://cognitive-os.org) — project website

## Contributing

1. Branch from `development`, not `main`
2. Use topic branches: `feature/<name>`, `fix/<name>`, `bugfix/<name>`
3. Open a PR to `development` with a clear title and description
4. Merge via squash after review
5. Changes flow to `main` via a release PR

See the [SDLC repo](https://github.com/CognitiveOS-Project/sdlc) for the full contribution guide, code review standards, and testing strategy.

## Author

**Jean Machuca** — [GitHub](https://github.com/jeanmachuca) · [Sponsor](https://github.com/sponsors/jeanmachuca)
