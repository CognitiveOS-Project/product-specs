# Local Fine-Tuning with `cpm tune`

This tutorial demonstrates how to implement and use local model fine-tuning in CognitiveOS. It showcases the "Controller Pattern," where `cpm` orchestrates a specialized training tool provided by the patch to create a LoRA adapter for the Wide Model.

## Concept

`cpm tune` allows a Cognitive Patch to personalize the AI's behavior based on local interaction data. Instead of retraining the entire Wide Model, it uses Parameter-Efficient Fine-Tuning (PEFT) to create a lightweight **LoRA adapter**. This adapter is hot-swapped into the inference engine at runtime, changing the model's output without needing a reboot or a full model reload.

## Patch Configuration

To support tuning, the `cognitive.json` manifest must include a `training` block. This block tells `cpm` which tool to use for training and where to store the resulting adapter.

**`cognitive.json`**
```json
{
  "name": "personalized-tutor",
  "version": "1.0.0",
  "description": "An AI tutor that adapts to your learning style",
  "brain": {
    "wide_model": {
      "base_model": "llama-3-8b-gguf"
    },
    "training": {
      "tool": "tutor-trainer",
      "output_path": "adapters/personalized.bin",
      "data_requirements": {
        "min_samples": 1000
      },
      "hyperparameters": {
        "rank": 8,
        "alpha": 16,
        "epochs": 3,
        "learning_rate": 0.0002
      }
    }
  },
  "runtime": {
    "mcp_servers": [
      {
        "name": "tutor-trainer",
        "command": "./tools/mcp-trainer",
        "args": ["--model-path", "/cognitiveos/models/wide/active/base.gguf"]
      }
    ]
  }
}
```

## Triggering Fine-Tuning

Tuning can be triggered manually via the CLI or automatically by the `cognitiveosd` daemon when certain data milestones are reached.

### Manual Trigger
```bash
# Trigger a tuning session for the personalized-tutor patch
cpm tune personalized-tutor
```

### Automated Trigger
The daemon monitors the `data_source` directory. Once enough interaction logs (e.g., 1000 samples) are collected, `cognitiveosd` sends a `tune` request to `cpm` in the background.

## What Happens During `cpm tune`

The process follows the **Controller Pattern**:

1. **Orchestration**: `cpm` reads the `training` configuration from `cognitive.json`.
2. **Tool Invocation**: `cpm` calls the `tutor-trainer` MCP tool, passing the local training data and hyperparameters.
3. **Local Training**: The `mcp-trainer` tool (implemented by the patch author) performs the LoRA training on the device (using CPU/NPU/GPU).
4. **Adapter Generation**: The trainer saves the resulting lightweight adapter file to `/cognitiveos/patches/personalized-tutor/adapters/personalized.bin`.
5. **Hot-Swap**: `cpm` signals `cognitiveosd`, which calls the inference engine's `/api/adapter` endpoint.
6. **Binding**: The inference engine calls `llama_model_load_adapter` to bind the new weights to the active base model in-memory.

## Verifying the Hot-Swap

You can verify that the adapter is active by checking the model status.

```bash
curl http://localhost:11434/cognitiveos/status
```

**Response:**
```json
{
  "status": "ready",
  "models_loaded": 1,
  "active_model": {
    "name": "/cognitiveos/models/wide/active/base.gguf + adapter(/cognitiveos/patches/personalized-tutor/adapters/personalized.bin)",
    "path": "/cognitiveos/models/wide/active/base.gguf",
    "ram_usage_mb": 4500
  }
}
```

## Rollback

Because the base model remains immutable, rolling back a tuning session is trivial:
```bash
# Remove the adapter file and reload the base model
rm /cognitiveos/patches/personalized-tutor/adapters/personalized.bin
cpm reload personalized-tutor
```
