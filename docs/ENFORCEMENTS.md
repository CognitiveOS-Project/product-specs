# CognitiveOS Process Enforcements

This document records the mandatory working agreements adopted across all CognitiveOS-Project repos. Every contributor, agent, and automation MUST follow these enforcements. They are the RFC 2119 **MUST**-level rules of engagement for the CognitiveOS ecosystem.

## 1. SPECv1 — Specification Vocabulary (MUST)

**SPECv1** is the normative vocabulary for all product specifications in CognitiveOS.

- All software product specifications MUST be authored using SPECv1 folder structure (`01-product-vision/` through `11-implementation-plan/`).
- Every normative statement MUST use capitalized RFC 2119 key words (`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, `MAY`).
- Lowercase variants (`must`, `should`, `may`) are NOT normative and MUST NOT be used for requirement statements.
- All specifications live in `product-specs` as the single source of truth for what the system MUST do.
- `sdlc` references `product-specs/specs/` as the canonical spec location; it does not duplicate spec content.

## 2. GHW — Git Workflow (MUST)

**GHW** is the mandatory git workflow for all CognitiveOS repos.

- No work MUST be committed directly on `main` or `development`.
- Work MUST use a topic branch from `development`: `git fetch origin` then `git checkout -b feature/<topic> development` (or `fix/<topic>` / `bugfix/<topic>`).
- Work MUST be pushed and a PR opened into `development` via `gh pr create` or GitHub UI.
- Merge to `development` MUST be via PR (squash after review).
- Promotion `development` → `main` MUST use a release PR (topic branch from `main` + cherry-pick or direct PR if history permits).
- No rebase MUST be used. Prefer plain `git pull` (merge) when updating from remote.
- Commit types MUST be: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.

**Exception:** Direct push to `main` or `development` is permitted only on explicit user instruction (maintainer emergency), and MUST be acknowledged as bypassing the topic-branch flow.

## 3. VibeLeading — Working Methodology (MUST)

**VibeLeading** is the mandatory working methodology for all CognitiveOS work.

- Every mission MUST start with a Mission Script containing: Mission Name, Frequency, Outcome, Constraints, Acceptance, Verification.
- Frequency MUST be declared as either **Stealth/Precision** (correctness, validation, security) or **High-Velocity/Market-Capture** (speed to insight).
- IRA (Intent-Result Alignment) MUST be scored per phase; target 8-10 per phase, ship at 95%+, investigate the Vibe below 70%.
- The three HUD signals MUST be tracked: Traction (IRA), Circuit Delta, Hallucination Debt.
- Every Lap MUST end in a Pit Stop (Review, Refuel, Restart); every month MUST include a Vibe Audit.
- The Pilot's Final Checklist MUST be run at kickoffs, quarter starts, and after significant drift.

## 4. ABSEv1 — Synthesis Engine (MUST)

**ABSEv1** is the mandatory synthesis engine for agentic autonomous intelligence in the CognitiveOS creative process.

- All creative architecture blueprints MUST use the ABSEv1 AESE methodology (5W2H, Design Thinking, Vision/Mission Cascade, Lean Validation, Stage-Gated Pipeline).
- ABSEv1 operates in two strict modes: Phase 1 Interactive Specification (`WHAT <sentence>` → `INIT`) and Phase 2 Autonomous Execution (STAGE-100 → STAGE-999).
- Once `INIT` is received, zero interactivity is permitted; all stages execute autonomously to terminal code (`STAGE-999: SUCCESS_DELIVERY` or `BURNOUT-000: TIER_CONSTRAINT_VIOLATION`).
- Infrastructure and tier constraints MUST be declared in `WHAT`; no infrastructure assumptions are permitted.

## 5. Release Tooling (MUST)

**`sdlc/scripts/release-tag.sh`** — Coordinated SemVer tagging across all CognitiveOS repos.

- All coordinated version tags MUST be created using `sdlc/scripts/release-tag.sh`.
- Tags MUST follow annotated SemVer format: `vMAJOR.MINOR.PATCH` (or `vMAJOR.MINOR.PATCH-dev.N` for integration tags on `development`).
- Tags MUST be created on `main` after a release PR merge, never on feature branches.
- The tag message MUST document the release contents.
- Tags MUST be pushed to all 15 CognitiveOS repos in a coordinated batch.

**`sdlc/scripts/healthcheck.sh`** — Periodic CI health check across all CognitiveOS repos.

- Health checks MUST be run against `--tag <version>` on `main` for every coordinated release.
- All repos MUST pass all checks (`sh -n`, `shellcheck`, `go vet`, tag presence, branch match, repository visibility) before a release is considered complete.
- Any FAIL result MUST be remediated before the release is tagged.

## 6. Repo Responsibilities

| Repo | Role | Source of Truth For |
|------|------|---------------------|
| `product-specs` | Architecture | Standards, schemas, protocol definitions, .cgp format, cognitive.json manifest |
| `sdlc` | Development | Implementation plan, milestones, workflow, CI/CD, mission scripts, process enforcements, release tooling (`release-tag.sh`, `healthcheck.sh`) |

## 7. Change Control

- Breaking changes to these enforcements MUST be discussed first in an issue or GitHub Discussion.
- All changes to this document MUST follow the GHW flow: topic branch → PR → `development` → release PR → `main`.

---
**Adopted:** CognitiveOS Project-wide  
**Authority:** Pilot (VibeLeading)  
**Vocabulary:** SPECv1 (RFC 2119)