# ADR-010: Cloud Models & Secret Management

**Status:** Accepted
**Date:** 2026-07-28
**Author:** CognitiveOS SDLC

## Context

CognitiveOS needs to support three ways of consuming LLM models:

1. **Remote** (existing): Download GGUF weights from HuggingFace at install time
2. **New — Local**: Bundle weight files directly in the `.cgp` archive
3. **New — Cloud**: Consume models from OpenAI-compatible API providers (no local weights)

Additionally, CPM needs a secret management system for storing API keys and credentials used by cloud models and other integrations.

## Decision

### Cloud Model Support

Add `method` field to `WeightsConfig` alongside `remote`/`local`/`cloud` sub-objects. The `method` field is a discriminator — only the sub-object matching `method` is active.

**Manifest shape:**
```json
{
  "brain": {
    "wide_model": {
      "weights": {
        "method": "cloud",
        "cloud": {
          "api_base": "https://api.openai.com/v1",
          "model_id": "gpt-4o-mini",
          "api_key": "${OPENAI_API_KEY}"
        }
      }
    }
  }
}
```

**Separation of concerns:**
- **coginfer** manages all wide model inference (local GGUF + cloud API)
- **cognitiveosd** always calls `WideModelClient` — no knowledge of where model lives
- **CPM** resolves secrets at install time; daemon/coginfer never know about secrets

**Cloud validation:** `cpm install` tests API reachability (HTTP HEAD with 5s timeout) — not a full inference request, just connectivity.

### Secret Management

CPM-native secret storage with two scopes:

| Scope | Location | Survives `cpm remove`? | Survives reset? |
|-------|----------|----------------------|-----------------|
| Patch | `/cognitiveos/lib/cpm/secrets/<patch-name>/secrets.json` | Yes | No |
| Global | `~/.cpm/secrets.json` | N/A | Yes |

**Resolution:** Centralized `ResolveSecrets()` function replaces `${VAR}` placeholders with values from the merged secrets store (patch overrides global). Resolution happens at install time only — archives always contain `${VAR}` placeholders.

**Commands:**
```
cpm secret add <name> <value> [--scope patch|global] [--force]
cpm secret list [--scope patch|global] [--reveal]
cpm secret remove <name> [--scope patch|global]
cpm secret get <name> [--scope patch|global]
```

**Security:**
- Secrets file: 0600 permissions, directory: 0700
- Archives never contain resolved secret values
- Registry never sees secrets (resolves at install, not publish)
- `cpm remove` preserves patch secrets; `--purge` deletes them

## Consequences

**Positive:**
- Single manifest covers all model consumption patterns
- Secrets never leak into archives or registries
- Cloud inference decoupled from daemon (coginfer handles it)
- Patch secrets survive package updates/removals
- Works outside CognitiveOS (CPM is independent)

**Negative:**
- Three weight methods increase manifest complexity
- Cloud models require network connectivity
- Secret resolution at install means secrets must be present on the target machine

**Risks:**
- Cloud API rate limiting (mitigated by reachability check, not full request)
- Secret file permissions on shared systems (mitigated by 0600/0700 defaults)

## Alternatives Considered

1. **Secrets in environment variables only** — rejected: no persistence, no scope isolation
2. **Cloud inference in cognitiveosd** — rejected: violates separation of concerns (coginfer manages inference)
3. **Secrets resolved at pack time** — rejected: leaks secrets into archives
4. **Single scope (global only)** — rejected: patch-specific secrets need isolation

## References

- `manifest-fields.md` — `weights.method`, `weights.local`, `weights.cloud` field specs
- `cognitive.schema.json` — JSON Schema with new weight methods
- `filesystem-hierarchy.md` — `/cognitiveos/lib/cpm/secrets/` directory
- `cpm-spec.md` — `cpm secret` command documentation
