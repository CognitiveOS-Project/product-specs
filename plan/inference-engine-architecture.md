# Inference Engine Architecture: CGo llama.cpp Bridge

Version: 1.0.0-draft

## Decision: Vendored C Source + CGo Bridge, No Subprocess

The inference engine (`coginfer`) and Raw Model (`cograw`) previously shelled out to `llama-cli` via `exec.Command`. This violated the architecture principle of **no standalone apps** — every component is a daemon, library, or protocol handler.

**Chosen approach:** Vendor `llama.cpp` as a git submodule at `vendor/llama.cpp/`, build via cmake, and link via CGo. A single CGo bridge file forms the only C→Go boundary; the rest of the codebase stays pure Go.

**Rejected alternatives:**

| Alternative | Reason Rejected |
|-------------|----------------|
| `go-skynet/go-llama.cpp` | External Go package with its own build system; duplicates dependency surface |
| `hybridgroup/yzma` | Same concern; also less maintained than upstream llama.cpp |
| `llama-cli` subprocess (status quo) | Violates no-apps principle; fragile, hard to resource-negotiate, no in-process control |
| Pure Go GGUF runtime (e.g. `llama.go`) | No production-ready pure-Go inference engine exists for GGUF models |

## Directory Structure

```
inference/
├── cmd/
│   ├── coginfer/
│   │   └── main.go              # HTTP inference server (Wide Model)
│   └── cograw/
│       └── main.go              # JSON-RPC 2.0 Raw Model daemon
├── internal/
│   ├── llm/
│   │   ├── llm.go               # Backend interface, MockBackend, CLIBackend
│   │   ├── bridge.go            # CGo declarations (ONLY file with import "C")
│   │   ├── cgobackend.go        # CgoBackend — Backend impl calling bridge
│   │   └── loadopts.go          # LoadOptions (NumCtx, GPULayers, Threads)
│   └── server/
│       └── server.go            # HTTP handlers, passes LoadOptions from request
├── vendor/
│   └── llama.cpp/               # Git submodule, pinned to known-good commit
└── go.mod
```

### Build Tags

- `bridge.go` and `cgobackend.go` carry `//go:build cgo` tag
- CI runs with `CGO_ENABLED=0` which excludes these files via the build tag
- Production Docker builds run with `CGO_ENABLED=1` and cmake + gcc toolchain
- `MockBackend` has no build tag and is always available for development and CI

## CGo Bridge Interface

The bridge file (`internal/llm/bridge.go`) is the single file with `import "C"`. It wraps these llama.h C API functions:

| C Function | Go Wrapper | Purpose |
|------------|-----------|---------|
| `llama_model_default_params()` | `llamaModelDefaultParams()` | Default model params |
| `llama_load_model_from_file()` | `llamaLoadModelFromFile()` | Load GGUF into memory |
| `llama_new_context_with_model()` | `llamaNewContextWithModel()` | Create inference context |
| `llama_tokenize()` | `llamaTokenize()` | Tokenize input string |
| `llama_eval()` | `llamaEval()` | Run inference pass |
| `llama_sample_temperature()` | `llamaSampleTemperature()` | Sample next token |
| `llama_token_to_piece()` | `llamaTokenToPiece()` | Detokenize to string |
| `llama_free_model()` | `llamaFreeModel()` | Free model memory |
| `llama_free()` | `llamaFree()` | Free context memory |
| `llama_context_default_params()` | — | Inline in NewContextWithModel |
| `llama_n_vocab()` | `llamaNVocab()` | Vocab size for token ranges |
| `llama_n_ctx()` | `llamaNCtx()` | Context window size |

No C++ files are compiled through CGo — llama.cpp is compiled externally via cmake and linked as a static archive. The bridge file only includes `llama.h` via an `#include` prelude.

### Memory Ownership

- `llama_load_model_from_file` returns an opaque `*C.struct_llama_model` pointer owned by C
- `llama_new_context_with_model` returns `*C.struct_llama_context` owned by C
- `llama_tokenize` returns a C-allocated array of `llama_token`; the bridge copies to a Go slice and frees the C array
- `llama_token_to_piece` writes to a C stack buffer; the bridge copies to a Go `[]byte`
- `llama_free_model` / `llama_free` are called via `runtime.SetFinalizer` and explicit `Close()` / `Unload()`
- All C allocations are tracked; no C pointer escapes to Go-allocated memory (CGo rules)

### Error Handling

llama.cpp uses return codes and `LOG()` macros. The bridge translates:

- Null return from `llama_load_model_from_file` → Go error with GGUF file path
- Negative return from `llama_eval` → Go error with eval context
- Zero-length tokenization → Go error with empty prompt
- All other C functions panic on null pointer (defensive, should not happen if load succeeded)

No CGo callbacks into Go — llama.cpp's `ggml_log_set` is not wrapped in v1. CPU-only initial release uses llama.cpp's default stderr logging, redirected to `/cognitiveos/logs/inference.log` via stdout/stderr capture.

## Backend Interface

Defined in `internal/llm/llm.go`:

```go
type Backend interface {
    // Load loads a GGUF model from path.
    // opts may be nil (use defaults).
    // Returns a ModelHandle for inference calls.
    Load(modelPath string, opts *LoadOptions) (ModelHandle, error)
}

type ModelHandle interface {
    // Generate runs a single completion synchronously.
    // Returns the full generated text.
    Generate(ctx context.Context, req GenerateReq) (GenerateResp, error)

    // Unload frees all model resources.
    Unload() error

    // Stats returns current resource usage.
    Stats() (ModelStats, error)
}

type LoadOptions struct {
    NumCtx    int // context window size (default 2048)
    GPULayers int // layers offloaded to GPU (default 0 = CPU only)
    Threads   int // CPU threads (default = runtime.NumCPU())
}

type GenerateReq struct {
    Prompt      string
    System      string
    Temperature float64
    NumPredict  int
    TopK        int
    TopP        float64
    Stream      bool
}

type GenerateResp struct {
    Text        string
    Done        bool
    TokenCount  int
    Duration    time.Duration
}

type ModelStats struct {
    RAMUsageMB   int
    VRAMUsageMB  int
    ContextSize  int
    ContextUsed  int
    TokensPerSec float64
    Uptime       time.Duration
}
```

### Implementations

| Backend | Build Tag | File | Use Case |
|---------|-----------|------|----------|
| `MockBackend` | (none) | `llm.go` | Development, CI, testing |
| `CgoBackend` | `cgo` | `cgobackend.go` | Production Alpine builds |
| `CLIBackend` | (none) | `llm.go` | **Deprecated, Phase 5 removal** |

**Registration:** Backends are registered via `--backend` flag in `cmd/coginfer/main.go`:

```
--backend mock    # MockBackend (dev/CI)
--backend cgo     # CgoBackend (production)
--backend cli     # CLIBackend (deprecated, transitional)
```

When `--backend` is not specified, the default is `"cgo"` on production builds and `"mock"` when `CGO_ENABLED=0`.

## CgoBackend: Load Flow

```
Load(modelPath, opts)
  │
  ├─ 1. Verify file exists at modelPath (Go stat)
  ├─ 2. Verify GGUF magic bytes "GGUF" at offset 0 (Go read)
  ├─ 3. Call bridge.llamaLoadModelFromFile(path, params)
  │     └─ C: llama_load_model_from_file() → *llama_model or NULL
  ├─ 4. If NULL → return error, log, quarantine
  ├─ 5. Call bridge.llamaNewContextWithModel(model, ctxParams)
  │     └─ C: llama_new_context_with_model() → *llama_context or NULL
  ├─ 6. If NULL → free model, return error
  ├─ 7. Store model/context pointers in CgoBackend struct
  └─ 8. Return CgoModelHandle{backend, modelPtr, ctxPtr, mu}
```

Step 2 satisfies dependency-validation.md rule D3 (GGUF magic bytes check) before ever calling C code, keeping format validation pure Go.

## CgoBackend: Generate Flow

```
Generate(ctx, req)
  │
  ├─ 1. Tokenize prompt via bridge.llamaTokenize() → []llama_token
  ├─ 2. Loop:
  │     ├─ bridge.llamaEval(ctx, tokens) → int (next token count)
  │     ├─ bridge.llamaSampleTemperature(ctx, temp) → llama_token
  │     ├─ bridge.llamaTokenToPiece(token) → string
  │     ├─ Append to output
  │     ├─ If streaming, flush via http flusher
  │     └─ Break on: EOS token, max tokens reached, context full
  ├─ 3. Build GenerateResp with stats
  └─ 4. Return
```

### Context Management

- The context (`llama_context`) is protected by a `sync.Mutex` — only one Generate at a time per model handle
- On context exhaustion (`llama_eval` returns negative), the model is automatically unloaded and reloaded with a larger context window (up to configured max)
- Idle timeout (configurable, default 300s) triggers `Unload()` which calls `llama_free()` + `llama_free_model()`
- On idle timeout, the model path and LoadOptions are saved for fast reload (<500ms) — the file handle remains open in Go's side

## Cograw Integration

The Raw Model (`cmd/cograw/main.go`) uses the same CGo bridge but with a stripped-down interface:

- **No model swapping** — single model at `/cognitiveos/models/raw/raw-model.gguf` loaded at startup
- **No streaming** — all inference is request-response (JSON-RPC 2.0)
- **No chat history** — stateless, each call independent
- **Context window:** 1024 tokens (fixed, small, fast)
- **Process model:** Always-on root daemon, never terminates

### RPC Methods Backed by CGo

| RPC Method | CGo Bridge Usage |
|------------|-----------------|
| `validate_system_code` | Prompt-based validation: tokenize code + context, eval, sample output |
| `check_unlock_code` | Same pattern as validate_system_code |
| `audit_resources` | No LLM call — pure Go reads `/proc/meminfo`, `statfs()` |
| `healthcheck` | Returns model_loaded: true if bridge pointers are non-nil |

The Raw Model does NOT use the HTTP server infrastructure. It binds a Unix socket directly and speaks JSON-RPC 2.0. It shares only the `bridge.go` and `loadopts.go` files from `internal/llm/`.

## Build Toolchain

### Requirements

- cmake ≥ 3.20
- gcc / g++ (C++17 capable)
- make
- Go ≥ 1.22 with `CGO_ENABLED=1`

### Build Process

```
# In Dockerfile.build:
git submodule update --init vendor/llama.cpp
cd vendor/llama.cpp && cmake -B build \
  -DLLAMA_NO_ACCELERATE=1 \
  -DLLAMA_STATIC=1 \
  -DLLAMA_NATIVE=0 \
  -DBUILD_SHARED_LIBS=0 \
  -DLLAMA_BUILD_TESTS=0 \
  -DLLAMA_BUILD_EXAMPLES=0 \
  -DLLAMA_BUILD_SERVER=0
cmake --build build --config Release -j$(nproc)

# Then:
cd inference && CGO_ENABLED=1 go build -tags=cgo ./cmd/coginfer/
```

The static library `vendor/llama.cpp/build/libllama.a` is linked automatically by CGo's `#cgo LDFLAGS:` directive in bridge.go.

### LDFLAGS in bridge.go

```go
/*
#cgo LDFLAGS: -L${SRCDIR}/../../vendor/llama.cpp/build -llama -lm -lstdc++
#cgo CFLAGS: -I${SRCDIR}/../../vendor/llama.cpp
#include "llama.h"
*/
import "C"
```

### CPU-Only Initial Release

`LLAMA_NO_ACCELERATE=1` disables all GPU acceleration (CUDA, Metal, Vulkan). This keeps the initial build simple and portable. GPU support is added later by enabling cmake flags:

- CUDA: `-DLLAMA_CUDA=1` + `-DCMAKE_CUDA_ARCHITECTURES=<arch>`
- Metal: `-DLLAMA_METAL=1` (macOS only)
- Vulkan: `-DLLAMA_VULKAN=1`

## Spec Compliance Mapping

### inference-api.md

| Spec Requirement | Implementation |
|-----------------|----------------|
| `POST /api/generate` | `server.go` handler → `backend.Generate()` → CGo bridge → `llama_eval()` loop |
| `POST /api/chat` | Same as generate, with system prompt prepended to chat history |
| `GET /api/tags` | Pure Go — reads `/cognitiveos/patches/**/weights/*.gguf` |
| `GET /cognitiveos/status` | Calls `backend.Stats()` → reports RAM/VRAM from CGo context |
| `GET /cognitiveos/capabilities` | Pure Go — probes hardware, reports backend availability |
| Resource negotiation | `server.go` checks `backend.Stats()` RAM before load; alternatives in response |
| Idle timeout | Go timer in server.go — calls `backend.Unload()` after 300s idle |
| Model lifecycle | State machine in server.go: UNLOADED → LOADING → READY → UNLOADING |
| Healthcheck | `GET /health` — checks backend is loaded and responsive |
| Transport | HTTP on :11434 (TCP) and `/cognitiveos/run/inference.sock` (Unix) |

### raw-model.md

| Spec Requirement | Implementation |
|-----------------|----------------|
| Always-on root daemon | `cmd/cograw/main.go` runs as root, started by cognitiveosd at boot |
| JSON-RPC 2.0 on Unix socket | Raw JSON-RPC handler over `net.Listen("unix", "/cognitiveos/run/raw.sock")` |
| Same llama.cpp bindings as coginfer | Shares `bridge.go` and `loadopts.go` from `internal/llm/` |
| No streaming, no chat history | Request-response only; single turn per RPC call |
| 1024-token context | Fixed `LoadOptions{NumCtx: 1024}` in cograw |
| Single model, no swap | Loaded at startup, freed only on shutdown |
| Seccomp/cgroup enforcement | Pure Go — `unix.Syscall` interface, no LLM involvement |

### dependency-validation.md

| Rule | Implementation |
|------|----------------|
| D1 — SHA-256 checksum match | Pure Go in `server.go` load path (or `cpm` pre-validates before calling inference engine) |
| D2 — Raw Model resource audit | Pure Go in `cograw` — reads `/proc/meminfo`, `statfs()` |
| D3 — GGUF magic bytes | Pure Go in `cgobackend.Load()` before CGo bridge is called |

## Security Properties

| Property | Mechanism |
|----------|-----------|
| **No CGo in Wide Model business logic** | Only `bridge.go` touches `import "C"`; `cgobackend.go` and `server.go` are pure Go |
| **No external Go deps for OS ops** | No `go-skynet`, `yzma`, or any third-party CGo bindings |
| **Format validation before C code** | GGUF magic bytes checked in Go before any C function is called |
| **Single C→Go boundary** | All llama.cpp interaction goes through one file; auditing is trivial |
| **Memory safety** | C pointers never escape to Go heap; all allocations tracked via finalizers |
| **CI isolation** | `cgo` build tag means CI never compiles or links C code |

## Phase Plan

### Phase 1: Bridge + CgoBackend (Current)
- Add `vendor/llama.cpp` submodule (pinned known-good commit)
- Implement `bridge.go` with CGo declarations
- Implement `cgobackend.go` with `CgoBackend` struct
- Implement `loadopts.go` with `LoadOptions`
- Register `--backend cgo` in `cmd/coginfer/main.go`
- GCC toolchain + cmake in Dockerfile

### Phase 2: Server Wiring
- Wire `LoadOptions` from HTTP request params (`num_ctx`, `gpu_layers`, `threads`) through server handlers to `backend.Load()`
- Pass `GenerateReq.Options` (temperature, num_predict, top_k, top_p) from request to bridge
- Implement streaming response via `http.Flusher`

### Phase 3: Cograw Fix + Integration (Raw Model)
- Replace `exec.Command("llama-cli")` in `cmd/cograw/main.go` with in-process CGo bridge
- Fix: undefined `llamaBin` flag, undefined `verifyModel()` call, missing `ramMB` field
- Implement JSON-RPC 2.0 handler wrapping bridge calls
- Integrate seccomp/cgroup enforcement (Docker build, not CGo)

### Phase 4: Build Pipeline
- Update `Dockerfile.build`: add cmake+gcc, `CGO_ENABLED=1`, git submodule init
- Update variant Dockerfiles: same
- Update `scripts/build-binaries.sh`: add CGo build step
- Remove `llama-cli` from `packages.x86_64`, `packages.aarch64`, `packages.armv7`
- Add `build-essential`, `cmake`, `git` to distro packages

### Phase 5: Cleanup
- Remove `CLIBackend` and `--backend cli` flag entirely
- Remove `llama-cli` subprocess code from both `coginfer` and `cograw`
- Remove `--backend` flag (only `cgo` remains); or keep `mock` for dev

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| llama.cpp API changes between versions | Low | High | Pin submodule to known-good commit; test upgrades |
| cmake/gcc toolchain adds 5+ min to Docker build | High | Medium | Cache cmake build directory in Docker layer; separate build stage |
| CGo cross-compilation for ARM | Medium | High | Build on native ARM or QEMU user-mode; test in CI |
| GPU support adds complexity | Medium | Low | CPU-only v1; GPU via cmake flags in v2 |
| CGo cgo.Handle() / pointer passing rules | Low | Medium | Follow CGo rules strictly; no C pointers in Go-allocated memory; pre-allocate C buffers |
| llama.cpp memory leaks | Medium | Medium | Wrap in `runtime.SetFinalizer`; monitor RSS in healthcheck |

## See Also

- [Inference API](specs/inference-api.md) — HTTP API contract
- [Raw Model](specs/raw-model.md) — Raw Model spec and RPC protocol
- [Dependency Validation](specs/dependency-validation.md) — load-time model validation rules
- [Security Model](specs/security-model.md) — trust boundaries
- [SDLC Implementation Plan](https://github.com/CognitiveOS-Project/sdlc/blob/development/plan/implementation-plan.md) — Project-level phase breakdown
