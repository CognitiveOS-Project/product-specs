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

## Update Priority

When updating CognitiveOS (system update, package manager upgrade, distro reflash), always use the **latest available version** across all repos, selected by the following priority order:

| Priority | Suffix | Description |
|----------|--------|-------------|
| 1 (highest) | `-lts` | Stable release, fully tested, functionally warranted |
| 2 | `-beta` | Tested release, no warranty |
| 3 (lowest) | `-alpha` | Low-tested release |

**Rule:** Select the highest-priority suffix that exists for the target version number. If `v1.0.0-lts` exists, it is preferred over `v1.2.0-beta`. If no `-lts` is available, prefer `-beta` over `-alpha`.

Bare versions (no suffix) are treated as equal to `-lts` for update priority — they represent a stable, warranted release. When both a bare version and an `-lts` exist at the same MAJOR.MINOR.PATCH, prefer the `-lts` (it carries an explicit stability commitment).

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

Use the `release-tag.sh` script from the [sdlc](https://github.com/CognitiveOS-Project/sdlc) repo. It implements this exact process with proper error handling:

```bash
sdlc/scripts/release-tag.sh vMAJOR.MINOR.PATCH-SUFFIX "vMAJOR.MINOR.PATCH-SUFFIX — description"
```

The script:
- **Always creates annotated tags** — compliant with the tag requirements
- **Isolates each repo** in a subshell — a failure in one does not poison the next
- **Only clones once** — persistent cache at `~/.cache/cognitiveos/releases`
- **Fetches remote tags** first — prevents accidental overwrite of existing releases
- **Idempotent** — skips repos where the tag already exists
- **Reports per-repo status** — summary table with pass/fail/skip

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
