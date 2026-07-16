# ADR-006: RISC-V (riscv64) Architecture Support

**Status:** Accepted  
**Date:** 2026-07-16  
**Author:** CognitiveOS SDLC

## Context

CognitiveOS currently builds for three architectures: `x86_64`, `aarch64`, and `armv7`. The CGP manifest schema (`cognitive.schema.json`) and the `cpm` hardware audit (`cpm-spec.md`) already include `riscv64` in their architecture enums, but no build target, package file, or release workflow exists for it.

RISC-V is an open-source ISA with growing adoption in AI edge hardware:
- **SBC boards:** StarFive VisionFive 2, SiFive HiFive Unmatched, OrangePi RV2, Milk-V boards
- **AI accelerators:** SiFive Intelligence P670 (AI-optimized RISC-V cores)
- **Go support:** `GOARCH=riscv64` supported since Go 1.14, `coginit` compiles cleanly
- **Alpine support:** `riscv64` is a supported Alpine architecture with official packages
- **Open ISA:** No licensing fees, no export restrictions, no vendor lock-in

The architecture naming is currently inconsistent across three layers:

| Layer | x86_64 | aarch64 | armv7 | riscv64 |
|-------|--------|---------|-------|---------|
| Alpine | `x86_64` | `aarch64` | `armv7` | `riscv64` |
| Docker | `linux/amd64` | `linux/arm64` | `linux/arm/v7` | `linux/riscv64` |
| Go | `amd64` | `arm64` | `arm` | `riscv64` |

RISC-V will be the first architecture where all three layers use the same name (`riscv64`), making it the cleanest integration point.

## Decision

1. **Add `riscv64` as a planned architecture** for CognitiveOS, starting with the `edge` class (≥2 GB RAM, embedded SBC use case).
2. **Update `distro-build-spec.md`** to document the planned architecture in the "Supported Targets" section, the platform mapping table, and the versioning convention.
3. **Naming convention:** Alpine `riscv64`, Docker `linux/riscv64`, Go `GOARCH=riscv64` — all three are identical.
4. **Initial build approach:** Cross-compile via QEMU emulation (same as current armv7 builds). Native builds when RISC-V CI runners are available.
5. **No new variant classes** — RISC-V starts as `edge-riscv64`. Future RISC-V classes (e.g., `titan-riscv64`) will be added as hardware matures.

## Consequences

- **Schema already correct:** `cognitive.schema.json` and `cpm-spec.md` already list `riscv64` — no changes needed.
- **CI pipeline:** A new `release-edge-riscv64.yml` workflow will be needed (follows existing variant workflow pattern).
- **Package file:** `packages.edge-riscv64` will be needed for Alpine package selection.
- **Kernel:** Alpine provides `linux-riscv64` (or `linux-lts-riscv64`) — package selection deferred to implementation.
- **QEMU builds:** Cross-compilation for riscv64 will use QEMU user-mode emulation (similar to armv7), with ~40-60 minute build times.
- **Docker images:** `coginit` and all Go components compile cleanly for `GOARCH=riscv64` (verified: `go build -ldflags="-s -w" -o /dev/null`).
