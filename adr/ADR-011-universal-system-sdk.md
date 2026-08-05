# ADR-011: Universal System SDK (cogsdk)

**Status:** Accepted
**Date:** 2026-08-04
**Author:** CognitiveOS SDLC

## Context

Cross-cutting concerns are reimplemented per-repo with subtle drift:

1. **JSON framing** — `cpm/internal/daemon/client.go` defines its own Unix-socket `Envelope{Type, From, Payload}`; `cognitiveosd/internal/daemon/` defines its own `socket.go`, `raw_client.go`, and `wide_client.go`; `core-mcp-bridges/internal/mcp/server.go` reimplements MCP JSON-RPC 2.0 framing. Each repo owns a private variant of the same wire format.
2. **Schema validation** — `cpm/internal/schema/cognitive.schema.json` and `schema.go` duplicate the JSON Schema source of truth in `product-specs/schemas/cognitive.schema.json`. Validation logic is embedded in consumers rather than shared.
3. **Logging / secrets / env** — `slog` setup, `${VAR}` secret resolution (ADR-010), and config/env resolution are copied across `cpm`, `cognitiveosd`, `cli`, and `core-mcp-bridges`.
4. **MCP tool calls** — the Wide Model → daemon → bridge tool-call path (MCP conventions) has no shared typed client; each caller hand-rolls its requests.

Because there is no universal SDK, new Go code picks the nearest repo's private copy and diverges further.

## Decision

Establish a **mandatory universal Go SDK** for all CognitiveOS Go code: repository and Go module **`github.com/CognitiveOS-Project/cogsdk`**, commonly shortened to **`cogsdk`**.

New Go code across CognitiveOS must import `cogsdk` for shared concerns; existing code migrates incrementally (targeting `cpm`, `cognitiveosd`, `product-specs`, `sdlc` first).

### Package Layout — Three Tiers

| Tier | Package | Responsibility |
|------|---------|----------------|
| `client/` | `mcp` | MCP JSON-RPC 2.0 framing, tool-call wrappers, schema validation |
| `client/` | `daemon` | cognitiveosd IPC client, system codes, envelope types |
| `client/` | `cpm` | CPM RPC client — the **only** path to nested `.cgp` tools (daemon-brokered) |
| `client/` | `env` | cgroup, systemd, config/env resolution |
| `adk/` | `agent` | Agent toolkit (future) |
| `adk/` | `intent` | Intent recognition (future) |
| `adk/` | `memory` | Memory persistence (future) |
| `adk/` | `prompt` | Prompt construction (future) |
| `cdk/` | `builder` | Image/toolchain builder (staged) |
| `cdk/` | `cloudinit` | Cloud-init orchestration (staged) |
| `cdk/` | `target` | Target provisioning (staged) |

`client/` is implemented now; `adk/` and `cdk/` are declared placeholders staged for later work.

### Single Source of Truth for Schemas

`cogsdk` becomes the **single source of truth** for shared type definitions and JSON Schema validation. Consumers validate in-process against the canonical schema ("shift-left") rather than against registry/daemon latency.

### Broker-Mediated Tool Invocation

Nested `.cgp` tool invocation is strictly mediated by the `cpm` daemon (per ADR-004's validated tool domains). `cogsdk` provides **typed clients only** — it never executes tools directly.

## Consequences

**Positive:**
- One implementation of framing, validation, logging, secrets, and env resolution
- Shift-left validation — failures surface at import/test time, not at registry round-trips
- Repos converge on a single wire format instead of private variants
- `adk/` and `cdk/` provide a stable home for future agent and build tooling

**Negative:**
- Mandatory dependency — all repos must import `cogsdk`; migration burden is nonzero
- `adk/` and `cdk/` are empty placeholders until their work is scheduled
- `client/mcp` must track the evolving MCP convention spec

**Risks:**
- Version skew — consumer repos pinned to different `cogsdk` versions (mitigated by SemVer + coordinated release tagging)
- Premature abstraction if `cdk/` is filled before its requirements are concrete (mitigated by staging — declared, not implemented)

## Alternatives Considered

1. **Status quo (per-repo duplication)** — rejected: drift already visible across the four JSON/MCP implementations
2. **A library per tier** (separate `client`, `adk`, `cdk` modules) — rejected: premature; a single module keeps `v1` iteration simple
3. **Registry-side validation only** — rejected: adds latency and keeps schema logic server-bound
4. **Vendoring shared code into each repo** — rejected: no single source of truth

## References

- `ADR-004` — package-manager MCP bridge; validated tool domains and daemon brokerage
- `ADR-010` — cloud models & secret management; `ResolveSecrets` pattern
- `mcp-conventions.md` — MCP framing and tool-call conventions
- `cognitiveosd-api.md` — daemon IPC surface and system codes
- `cpm-spec.md` — CPM RPC surface
- `cognitive.schema.json` — canonical manifest schema
