# Downloading Model Weights with `cpm download-weights`

**Use case:** Download a GGUF or safetensors model directly from Hugging Face Hub to the correct filesystem location, without creating a `.cgp` package first.

Useful for:
- Quickly swapping the Wide Model (general-purpose LLM)
- Replacing the Raw Model (firmware guardrail)
- Testing a new quantization before publishing a `.cgp` wrapper

## Quick Start

```bash
# Search for and download a GGUF model as the Wide Model
cpm download-weights --kind wide --type gguf SmolLM2-135M-Instruct
```

Output:
```
Found: https://huggingface.co/unsloth/SmolLM2-135M-Instruct-GGUF/resolve/main/SmolLM2-135M-Instruct-F16.gguf
File:  SmolLM2-135M-Instruct-F16.gguf
Dest:  /cognitiveos/patches/base/weights/SmolLM2-135M-Instruct-F16.gguf
Downloading...
100% (258258240 / 258258240 bytes)
✓ Downloaded to /cognitiveos/patches/base/weights/SmolLM2-135M-Instruct-F16.gguf
```

The daemon picks up the new model automatically on next startup — it scans `/cognitiveos/patches/base/weights/` for `.gguf` and `.safetensors` files.

## Key Concepts

### Providers

| Provider | Flag | Description |
|----------|------|-------------|
| Hugging Face Hub | `--provider hf` | Searches public GGUF models via the HF API, sorted by downloads. No authentication required. |

Additional providers (models.dev, etc.) will be added in future releases.

### Model Kinds

| `--kind` | Destination | Overwrite Policy |
|----------|-------------|------------------|
| `wide` | `/cognitiveos/patches/base/weights/<filename>.gguf` | Always overwrites |
| `raw` | `/cognitiveos/models/raw/raw-model-<name>.gguf` | Skips if file exists |

The **wide model** is the general-purpose LLM loaded by the inference engine. The **raw model** is the system's firmware guardrail — a fixed single-file model that cannot be hot-reloaded, so it is never overwritten without explicit removal first.

### File Formats

| `--type` | Extension | Description |
|----------|-----------|-------------|
| `gguf` | `.gguf` | GGML Universal Format (llama.cpp ecosystem) |
| `safetensors` | `.safetensors` | Safe tensors format (Hugging Face ecosystem) |

## Full Usage

```
cpm download-weights <model-name> [flags]

Flags:
      --provider string   Weight provider (hf)
      --kind string       Model kind (raw or wide) (default "wide")
      --type string       File format (gguf or safetensors) (default "gguf")
      --output string     Custom output path (overrides default)
      --dry-run           Show what would be downloaded without downloading
```

### Search and Preview

Use `--dry-run` to see what model will be downloaded:

```bash
cpm download-weights --dry-run --kind wide --type gguf qwen2.5-coder-3b
```

Example output:
```
Found: https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf
File:  qwen2.5-coder-3b-instruct-q4_k_m.gguf
Dest:  /cognitiveos/patches/base/weights/qwen2.5-coder-3b-instruct-q4_k_m.gguf
```

Run without `--dry-run` to download.

### Custom Output Path

Override the destination for testing or non-standard setups:

```bash
cpm download-weights --kind wide --output /tmp/models/my-test.gguf SmolLM2-135M-Instruct
```

### Replacing the Raw Model

The raw model is a fixed single file intended for the firmware guardrail. Download it once:

```bash
cpm download-weights --kind raw --type gguf CognitiveOS/raw-model-v3
```

This writes to `/cognitiveos/models/raw/raw-model-CognitiveOS-raw-model-v3.gguf`. If the file already exists, the download is skipped — delete it manually if you need to replace it.

## Integration with `cpm install`

When you have a `.cgp` package that declares remote weights (e.g. a model publisher's package), `cpm install` automatically downloads the weights:

```json
{
  "brain": {
    "wide_model": {
      "weights": {
        "remote": {
          "source": "huggingface",
          "model_id": "google/gemma-4-2b",
          "filename": "gemma-4-2b-Q4_K_M.gguf"
        }
      }
    }
  }
}
```

```bash
cpm install gemma-4-2b
```

During install, cpm will:
1. Validate the manifest schema
2. Search Hugging Face Hub for the matching model file
3. Download to `/cognitiveos/patches/base/weights/gemma-4-2b-Q4_K_M.gguf`
4. Verify SHA-256 if provided in the manifest
5. Proceed with the rest of the install (hardware audit, MCP server spawn, tool registration)

## Creating a Distributable Package

To publish a model so others can install it with `cpm install`, use the `gguf-model` template:

```bash
cpm init my-gemma-model --template gguf-model
```

This scaffolds a `cognitive.json` with a pre-filled `weights.remote` block. Edit the placeholders (`model_id`, `filename`, `quant`, `size_bytes`) and publish to the registry.

## Weight Methods

The `weights.method` field controls how weights are consumed. Three methods are available:

### Remote (default)

Downloads from HuggingFace Hub at install time:

```json
{
  "brain": {
    "wide_model": {
      "weights": {
        "method": "remote",
        "remote": {
          "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-GGUF/resolve/main/qwen2.5-1.5b-q4_k_m.gguf",
          "filename": "qwen2.5-1.5b-q4_k_m.gguf"
        }
      }
    }
  }
}
```

### Local

Includes the weight file in the `.cgp` archive at pack time. No download needed at install:

```json
{
  "brain": {
    "wide_model": {
      "weights": {
        "method": "local",
        "local": {
          "path": "weights/model.gguf"
        }
      }
    }
  }
}
```

Place the weight file in `weights/` before running `cpm pack`. The archive will be larger but fully self-contained — useful for air-gapped deployments or models not on HuggingFace.

### Cloud

Delegates inference to an OpenAI-compatible API provider. No weight file involved:

```json
{
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

The `${OPENAI_API_KEY}` placeholder is resolved at install time from the secrets store. `cpm install` tests API reachability via HTTP HEAD before completing installation.

```bash
# Store the API key first
cpm secret add OPENAI_API_KEY sk-abc123

# Then install — secrets are resolved automatically
cpm install cloud-assistant@1.0.0
```

See [Secret Management](secret-management.md) for storing API keys.

## Example: Downloading a Full Quantization Suite

```bash
# Preview all available quants for a model
cpm download-weights --dry-run --kind wide --type gguf Llama-3.2-1B

# Download the Q4_K_M quant (best size/quality tradeoff)
cpm download-weights --kind wide --type gguf Llama-3.2-1B-Instruct

# Switch to a higher quality quant
cpm download-weights --kind wide --type gguf Llama-3.2-1B-Instruct-Q8_0
```

The daemon loads the first `.gguf` found in `/cognitiveos/patches/base/weights/`. Replace a model by downloading a new one — the old file remains but won't be loaded unless it's the first alphabetically.
