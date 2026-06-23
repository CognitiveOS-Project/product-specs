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

Propose changes via PR to `development`. All changes here affect every other repo — discuss breaking changes first.
