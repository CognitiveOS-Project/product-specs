# Release and Tag Strategy

Version: 1.0.0

## Overview

CognitiveOS spans 13 repos under the `CognitiveOS-Project` GitHub org. Releases are **coordinated** — all repos are tagged at the same SemVer version to form a coherent release.

## Version Numbering

```
vMAJOR.MINOR.PATCH[-SUFFIX]
```

| Bump | When | Example |
|------|------|---------|
| **MAJOR** | Change in foundations (core architecture, protocol, API contract) | `v1.0.0` → `v2.0.0` |
| **MINOR** | Change in feature status (in-development → done, done → deprecated, in-development → dismissed) | `v1.0.0` → `v1.2.0` |
| **PATCH** | Correction to an existing feature (including deleting files) | `v1.0.0` → `v1.0.1` |
| **PATCH + -patch** | Urgent bug fix | `v0.1.1-patch` |

Pre-1.0 convention: `v0.MINOR.PATCH` — MINOR for features, PATCH for fixes.

## Release Suffixes

| Suffix | Meaning | Requirements |
|--------|---------|-------------|
| `-alpha` | Low-tested release | Feature-complete, minimal smoke testing |
| `-beta` | Tested release, no functional warranty | All planned tests pass, known issues documented |
| `-lts` | Stable release, functionality warranted | All tests passing, changelog complete, no known critical issues |

A version without a suffix (e.g. `v1.0.0`) is a **bare release** — use when the stability level is self-evident from context. Prefer explicit suffixes for public releases.

Examples:

| Tag | Meaning |
|-----|---------|
| `v0.1.0-alpha` | First alpha, foundations in development |
| `v0.4.0-beta` | Feature-complete beta, ready for testing |
| `v1.0.0-lts` | First stable release with warranty |
| `v1.2.3-patch` | Urgent bug fix on any track |

## When to Tag

Tag at the end of a **release cycle** — after all PRs for that cycle have been promoted from `development` → `main` across all affected repos. A cycle may include:

- New feature work (new specs, binaries, integrations)
- Bug fixes
- CI / documentation improvements
- Cross-repo coordination changes

## Tag Requirements

- **Annotated tags only** — lightweight tags (`git tag vX.Y.Z`) must not be used. Annotated tags carry a message and creator metadata:
  ```bash
  git tag -a v0.1.0-alpha -m "v0.1.0-alpha — foundations in development"
  ```
- **Tag message** should briefly describe the contents of the release for that repo.
- **Tags must be pushed** to the remote:
  ```bash
  git push origin v0.1.0-alpha
  ```

## Tagging Process

### Single Repo

```bash
git fetch origin main
git tag -a vMAJOR.MINOR.PATCH-SUFFIX -m "vMAJOR.MINOR.PATCH-SUFFIX — description" origin/main
git push origin vMAJOR.MINOR.PATCH-SUFFIX
```

### All Repos (Bulk)

Use the API for bulk tagging to avoid cloning every repo:

```bash
version="vMAJOR.MINOR.PATCH-SUFFIX"
for repo in cognitiveos product-specs sdlc cpm core-mcp-bridges inference cognitiveosd cli registry-server cgp-template cognitiveos-distro cognitive-os.org .github; do
  gh -R CognitiveOS-Project/$repo api repos/CognitiveOS-Project/$repo/git/refs -X POST \
    -f ref="refs/tags/$version" \
    -f sha="$(gh -R CognitiveOS-Project/$repo api repos/CognitiveOS-Project/$repo/branches/main --jq '.commit.sha')"
done
```

Note: The API-based method creates **lightweight** tags. For **annotated** tags across all repos, tag locally on repos you have cloned and push, or use the API to create a tag object first, then a ref.

### For Repos Without Changes

Even if a repo had no changes in a release cycle, it should still be tagged at the same version to maintain alignment. The tag points at the existing `main` HEAD.

## Integration Tags (Development)

Optionally, tag `development` branch HEADs with a `-dev.N` suffix after each feature/fix merge. The suffix appends to the full version including release suffix:

```bash
git tag -a v0.1.0-alpha-dev.1 -m "v0.1.0-alpha-dev.1 — post-merge integration checkpoint"
git push origin v0.1.0-alpha-dev.1
```

These are **not required** — they are useful for tracking intermediate states during long release cycles.

## Relationship to Branch Protection

Branch protection on `main` and `development` requires 1 approving review. During release promotion:

1. Temporarily disable protection on `main` (or `development` if needed)
2. Merge via PR (cherry-pick topic branch from `main`)
3. Re-enable protection immediately after
4. Tag after all merges are complete and protection is restored

## Release Pipeline

See [git-workflow.md](../../../.opencode/instructions/git-workflow.md) for the full multi-repo release pipeline:

1. Merge topic branches to `development` via PR
2. Cherry-pick changes to `main` via topic branches from `main` (due to squash-merge history divergence)
3. Tag all repos at the same version
4. Verify deployment (website, docs, etc.)

## See Also

- [git-workflow.md](../../../.opencode/instructions/git-workflow.md) — branching, PR flow, cherry-pick promotion
- [CI/CD](../../../sdlc/specs/ci-cd.md) — CI pipeline and deployment
