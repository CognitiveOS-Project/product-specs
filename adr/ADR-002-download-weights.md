# ADR-002: `cpm download-weights` — Standalone Weight Download Command

**Status:** Accepted  
**Date:** 2026-07-05  
**Author:** CognitiveOS SDLC  
**Supersedes:** Manual `curl` scripts in `download_qwen.sh`

## Context

CognitiveOS needs to download LLM weight files (GGUF, safetensors) from remote providers like Hugging Face Hub. Previously this was done via ad-hoc shell scripts (`download_qwen.sh`). The system needs a unified, reusable download mechanism that:

- Works as a standalone CLI command for end-users
- Integrates into `cpm install` when a `.cgp` manifest declares `weights.remote`
- Supports multiple weight providers (HF Hub now, `models.dev` in future)
- Handles multi-GB files with progress reporting
- Places weights at the correct filesystem locations for the daemon/inference engine
- Works without authentication for public models

## Decision

Add a `cpm download-weights` subcommand with a `Provider` interface abstraction.

### Provider Pattern

Each weight provider implements a `Provider` interface with `Search()` and `Resolve()` methods. The first provider is Hugging Face Hub (`hf`), using the public API with `library=gguf` filter — no auth required.

```
Provider interface
├── hf.go          — Hugging Face Hub (public API, no token)
└── modelsdev.go   — future: models.dev integration
```

### HF Provider Implementation

Uses `GET https://huggingface.co/api/models?library=gguf&search=<query>&sort=downloads&direction=-1&limit=<n>&full=true` to search. Filters siblings by file extension (`.gguf` or `.safetensors`). Returns download URLs as `https://huggingface.co/<modelID>/resolve/main/<filename>`. No authentication — public models only.

### File Placement

| `--kind` | Destination | Overwrite |
|----------|-------------|-----------|
| `raw` | `/cognitiveos/models/raw/raw-model-<name>.gguf` | Never (skip if exists) |
| `wide` | `/cognitiveos/patches/<pkg>/weights/<filename>.gguf` | Always (re-download) |

The raw model uses a named pattern (`raw-model-<name>.gguf`) since raw models are single-file and cannot be hot-reloaded — skip prevents accidental overwrite. Wide models use the filename from the download candidate and can be overwritten (the daemon picks the first `.gguf` in the directory at startup).

### Progress Reporting

A `ProgressFn` callback (`func(current, total int64)`) decouples download logic from display:
- **Default:** Text progress line to stderr (`\r42% 621MB/1.4GB`)
- **Scripting:** Pass `nil` for silent operation
- **TUI:** Future TUI passes its own render function — download logic unchanged

### Integration with `cpm install`

When `cpm install` encounters a `.cgp` manifest with `brain.<kind>_model.weights.remote.source = "huggingface"`, it:
1. Resolves the remote weight via the HF provider using `model_id`
2. Downloads to the standard location per the placement rules above
3. Verifies SHA-256 if `checksum.sha256` is present in the manifest

The download happens before the hardware audit and MCP server spawn — the weight file must be on disk before the model is loaded.

### Template Support

The `gguf-model` template for `cpm init` scaffolds a `cognitive.json` with a pre-filled `brain.wide_model.weights.remote` block, making it easy for model publishers to create distributable `.cgp` packages.

## Consequences

**Positive:**
- Single download entry point for both CLI users and programmatic install
- Decoupled progress display enables both CLI and future TUI
- No third-party auth dependencies for public models
- Filesystem layout is predictable for daemon and inference engine
- Provider abstraction allows future providers without changing core logic

**Negative:**
- Initial implementation only supports public HF models — gated models require future work (HF_TOKEN passthrough)
- Raw models cannot be hot-reloaded, requiring a reboot after change
- No download resume — failed multi-GB downloads restart from zero

**Risks:**
- HF API rate limiting on `library=gguf` queries (mitigated by caching search results)

## Alternatives Considered

1. **Shell scripts only** — rejected: no progress, no error handling, no integration
2. **Embed HF download in `cpm install` only** — rejected: users need standalone weight download without a `.cgp` package
3. **Use `huggingface_hub` Python library via subprocess** — rejected: adds Python dependency, breaks standalone Go binary
4. **Integrate with registry-server as download proxy** — rejected: registry is a notary, not a file host; direct HF download is simpler and faster

## References

- `manifest-fields.md` — `weights.remote` field specification
- `cognitive.schema.json` — JSON Schema with `source: "huggingface"` enum
- `cpm-spec.md` — cpm CLI specification (to be updated)
- `filesystem-hierarchy.md` — standard model directory layout
