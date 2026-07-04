# CognitiveOS Product Specs

This repo defines the **standards, schemas, and protocols** that every other CognitiveOS repo builds against.

## What's here

- `.cgp` (Cognitive Patch) format specification
- `cognitive.json` manifest schema
- System codes definition (wake, idle, security shutdown, reset, unlock)
- MCP protocol conventions for CognitiveOS
- CognitiveOS API contracts

## Validation

JSON Schema files are in `/schemas/`. Use any JSON Schema validator or `cue eval` to verify.

## Contributing

All repos follow the git workflow defined in root `.opencode/instructions/git-workflow.md` and documented fully in the [SDLC repo](https://github.com/CognitiveOS-Project/sdlc).

- Branch from `development`, not `main`
- Use topic branches: `feature/<name>`, `fix/<name>`, `bugfix/<name>`
- Open a PR to `development` — squash merge after review
- Changes flow to `main` via a release PR (never push directly to `main` or `development`)
- No rebase — prefer `git pull` (merge)
- Commit types: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`

All changes here affect every other repo — discuss breaking changes first in an issue or GitHub Discussion.
