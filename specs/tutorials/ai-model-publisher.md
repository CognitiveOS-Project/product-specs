# AI Model Publisher: Distributing a Gemma-4-2B GGUF

**Company profile:** AI/ML model publisher who wants to distribute quantized models through the CognitiveOS ecosystem.

This tutorial shows how to wrap a GGUF model in a `.cgp` package so users can install it with `cpm install gemma-4-2b` — no manual download, no model path configuration, no SHA-256 checks.

## Why .cgp Instead of a Raw .gguf

| Concern | Raw .gguf | Wrapped in .cgp |
|---------|-----------|-----------------|
| Discoverability | Users must know the exact URL | `cpm search gemma` finds it |
| Integrity | Manual SHA check | Automatic checksum validation on install |
| Hardware audit | User guesses if it fits | `hardware_requirements` enforced before download |
| Versioning | Filename convention | SemVer with `cpm update` |
| Dependencies | Manual install of tokenizer, adapter | Declared in `dependencies`, auto-installed |
| Unlock codes | Not supported | Built-in unlock code flow for paid models |

## cognitive.json

```json
{
  "name": "gemma-4-2b",
  "version": "1.0.0",
  "description": "Google Gemma 4 2B parameter LLM, Q4_K_M quantization",
  "author": "Google DeepMind",
  "license": "gemma-terms-of-use",
  "download_url": "https://registry.cognitive-os.org/v1/patches/gemma-4-2b/1.0.0/download",
  "checksum": {
    "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
  },
  "source": {
    "repository": "https://huggingface.co/google/gemma-4-2b",
    "issues": "https://huggingface.co/google/gemma-4-2b/discussions"
  },
  "hardware_requirements": {
    "min_ram_mb": 4096,
    "min_storage_mb": 2048,
    "npu_required": false
  },
  "brain": {
    "wide_model": {
      "base_model": "gemma4:2b",
      "weights": {
        "remote": {
          "source": "huggingface",
          "model_id": "google/gemma-4-2b",
          "filename": "gemma-4-2b-Q4_K_M.gguf",
          "format": "gguf",
          "quant": "Q4_K_M",
          "size_bytes": 1472583690
        }
      },
      "parameters": {
        "temperature": 0.7,
        "num_ctx": 8192
      }
    }
  },
  "runtime": {
    "capabilities": ["model.llm", "model.chat"]
  }
}
```

## Publishing Multiple Quantizations

As a model publisher, you offer multiple quantization levels. Each is a separate package version or variant:

```bash
# Build packages for each quantization
cpm init gemma-4-2b --template gguf-model
# Edit cognitive.json — set quant: "Q4_K_M", size_bytes: 1472583690
tar czf gemma-4-2b-Q4_K_M.cgp .
cpm publish ./gemma-4-2b-Q4_K_M.cgp

cpm init gemma-4-2b --template gguf-model
# Edit cognitive.json — set quant: "Q8_0", size_bytes: 2945167380
tar czf gemma-4-2b-Q8_0.cgp .
cpm publish ./gemma-4-2b-Q8_0.cgp

cpm init gemma-4-2b --template gguf-model
# Edit cognitive.json — set quant: "Q2_K", size_bytes: 736291845
tar czf gemma-4-2b-Q2_K.cgp .
cpm publish ./gemma-4-2b-Q2_K.cgp
```

Users install the quantization that fits their hardware:

```bash
# Low-RAM device
cpm install gemma-4-2b --version 1.0.0  # resolves to Q4_K_M by default

# High-RAM workstation
cpm install gemma-4-2b@1.0.0-Q8_0
```

## Paid Models with Unlock Codes

For commercial models, add license enforcement:

```json
{
  "license": "proprietary",
  "hardware_requirements": {
    "min_ram_mb": 8192,
    "min_storage_mb": 4096
  }
}
```

```bash
# User installs — triggers unlock flow
cpm install gemma-4-27b-pro

# Raw Model intercepts: "Premium model requires unlock code"
# User enters code purchased from your website
# Raw Model validates against registry, authorizes download
# Model loads
```

## Build & Install

```bash
cpm init gemma-4-2b --template gguf-model
cd gemma-4-2b

# No MCP servers needed — pure model package
# Edit cognitive.json as shown above

# Package
tar czf gemma-4-2b-1.0.0.cgp .
cpm publish ./gemma-4-2b-1.0.0.cgp
```

## What Happens on Install

1. **Schema validation** — `brain.wide_model.weights.remote` is parsed
2. **Hardware audit** — 4 GB RAM, 2 GB storage — if the system doesn't have it, cpm rejects with a clear error
3. **Weight download** — 1.4 GB GGUF file streamed from Hugging Face
4. **Checksum verification** — SHA-256 compared against `checksum.sha256`
5. **Extraction** — archive goes to `/cognitiveos/patches/gemma-4-2b/`
6. **Model activation** — daemon sends `wide_model_load` to inference engine with model path and temperature/ctx params
7. **Capability registration** — `model.llm`, `model.chat` registered — other skills can declare `dependencies: ["gemma-4-2b"]`

## Usage

```
User: "Ask Gemma 4 to write a poem about AI"
  → No explicit routing needed — Gemma is the active Wide Model
  → Inference engine generates response using the loaded GGUF
  → "Here's a poem about AI:

     Silicon dreams in electric night,
     Neurons firing with digital light..."
```

```
User: "I need more memory. Switch to Q2_K version"
  → cpm install gemma-4-2b@1.0.0-Q2_K
  → cpm remove gemma-4-2b  # unloads Q4_K_M
  → New model loads — 700 MB instead of 1.4 GB, still Gemma 4
```
