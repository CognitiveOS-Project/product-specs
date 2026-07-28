# Secret Management with `cpm secret`

This tutorial covers CPM's secret management system for storing API keys, tokens, and credentials that packages need at runtime. Secrets use `${VAR}` placeholders in manifests and are resolved at install time — archives never contain real values.

## Overview

CognitiveOS packages often need secrets — API keys for cloud models, tokens for third-party services, or credentials for authenticated endpoints. The `cpm secret` commands manage these values across two scopes:

| Scope | Location | Survives |
|-------|----------|----------|
| **Patch** | `/cognitiveos/lib/cpm/secrets/<patch-name>/secrets.json` | `cpm remove`, reset |
| **Global** | `~/.cpm/secrets.json` | Everything |

Patch scope overrides global scope when both define the same key.

## Prerequisites

- `cpm` installed (`go install github.com/CognitiveOS-Project/cpm/cmd/cpm@latest`)

## Adding Secrets

Store a secret value with `cpm secret add`:

```bash
# Add to patch scope (default)
cpm secret add API_KEY sk-abc123

# Add to global scope
cpm secret add HF_TOKEN hf_abc123 --scope global

# Overwrite an existing secret
cpm secret add API_KEY sk-newkey --force
```

Output:
```
✓ Added secret "API_KEY" to patch scope
```

Without `--force`, adding a duplicate key fails with an error suggesting the flag.

## Listing Secrets

View stored secrets with `cpm secret list`:

```bash
# List with masked values (default)
cpm secret list

# List with revealed values
cpm secret list --reveal

# List global secrets only
cpm secret list --scope global
```

Output (masked):
```
Patch:
  API_KEY    ****c123
  HF_TOKEN   ****abc3
```

Output (revealed):
```
Patch:
  API_KEY    sk-abc123
  HF_TOKEN   hf_abc123
```

## Getting a Secret

Print a single secret value to stdout:

```bash
cpm secret get API_KEY
```

Output:
```
sk-abc123
```

The value is printed to stdout — useful for piping into other commands.

## Removing Secrets

Remove a secret from a scope:

```bash
# Remove from patch scope
cpm secret remove API_KEY

# Remove from global scope
cpm secret remove HF_TOKEN --scope global
```

Output:
```
✓ Removed secret "API_KEY" from patch scope
```

If the secret doesn't exist in the specified scope, an error is returned.

## Using Secrets in Manifests

Reference secrets in `cognitive.json` using `${VAR}` syntax:

```json
{
  "name": "cloud-assistant",
  "version": "1.0.0",
  "brain": {
    "wide_model": {
      "weights": {
        "method": "cloud",
        "cloud": {
          "api_base": "https://api.openai.com",
          "model_id": "gpt-4o-mini",
          "api_key": "${OPENAI_API_KEY}"
        }
      }
    }
  }
}
```

The `${OPENAI_API_KEY}` placeholder is resolved at install time. The archive (`.cgp`) always contains the literal `${OPENAI_API_KEY}` string — real values never leak into archives or the registry.

## Resolution at Install Time

When `cpm install` processes a package:

1. Extract the `.cgp` archive
2. Validate the manifest against the JSON schema
3. **Resolve secrets** — replace `${VAR}` placeholders with real values from the merged secrets store
4. Move the resolved manifest to the install path

```bash
# Install resolves secrets automatically
cpm install cloud-assistant@1.0.0

# Secrets must exist before install
cpm secret add OPENAI_API_KEY sk-abc123
cpm install cloud-assistant@1.0.0
```

If a placeholder references an undefined secret, installation fails:

```
ERROR: secret "OPENAI_API_KEY" not found — add it with: cpm secret add OPENAI_API_KEY <value>
```

## Scope Hierarchy

When both patch and global scopes define the same key, patch wins:

```bash
# Global scope
cpm secret add API_KEY global-value --scope global

# Patch scope (same key)
cpm secret add API_KEY patch-value

# Patch value is used during install
cpm secret get API_KEY
# Output: patch-value
```

This lets you set organization-wide defaults in global scope and override per-package in patch scope.

## File Locations

| Scope | Path | Permissions |
|-------|------|-------------|
| Patch | `/cognitiveos/lib/cpm/secrets/<patch-name>/secrets.json` | File: 0600, Dir: 0700 |
| Global | `~/.cpm/secrets.json` | File: 0600, Dir: 0700 |

Patch secrets survive `cpm remove` but are wiped on system reset. Use `cpm remove --purge` to explicitly delete patch secrets.

## Security Model

- Secrets are stored as plaintext JSON on disk (protected by file permissions)
- Archives always contain `${VAR}` placeholders — real values never leave the machine
- The registry never sees or stores secret values
- `cpm secret list` masks values by default — use `--reveal` to see them
- `cpm remove` preserves secrets; `cpm remove --purge` deletes them
- System reset wipes all patch secrets

## See Also

- [Cloud Models](cgp-lifecycle.md) — using `${SECRET}` in cloud model configuration
- [CPM Spec](../cpm-spec.md) — full `cpm secret` command reference
- [Manifest Fields](../manifest-fields.md) — fields that support `${VAR}` placeholders
