# ADR-005: Local Fine-Tuning for Cognitive Patches

## Status
Proposed

## Context
CognitiveOS patches (`.cgp`) provide capabilities via prompts, tools, and base models. However, to achieve true personalization and specialized performance (e.g., a tutor adapting to a student's specific weaknesses), the system needs a way to refine model weights based on local interaction data without compromising the base model's stability or requiring cloud-based training.

## Decision
We will implement a local fine-tuning mechanism called `cpm tune`. This feature will use Parameter-Efficient Fine-Tuning (PEFT), specifically Low-Rank Adaptation (LoRA), to create lightweight adapters that sit on top of the base Wide Model.

### Key Principles
1. **Non-Destructive:** The base model weights remain immutable. Tuning generates a separate adapter file (e.g., `.bin` or `.gguf`).
2. **Decentralized Execution:** `cpm` does not implement a trainer. Instead, it acts as a controller that invokes a specialized MCP tool (defined in the patch manifest) to perform the training.
3. **Local Privacy:** Training data (interaction logs) never leaves the device.
4. **Hot-Swapping:** The inference engine must be able to bind/unbind adapters at runtime without requiring a system reboot.
5. **Fail-Safe:** Rollback is achieved by simply deleting the adapter file.

## Consequences
### Pros
- Personalized AI experiences without retraining large models.
- High efficiency: LoRA adapters are tiny (MBs instead of GBs).
- Security: Base model remains a "known good" state.
- Flexibility: Different adapters can be swapped for different personas/tasks.

### Cons
- Increased complexity in the inference engine (adapter management).
- Resource consumption (CPU/NPU/RAM) during the training phase.
- Dependence on a compatible training tool being provided by the patch author.

## Implementation Strategy
- Update `cognitive.schema.json` to include `training` configurations.
- Add `cpm tune` command for manual and automated triggers.
- Update `cognitiveosd` to orchestrate training based on data milestones.
- Implement adapter binding in the inference engine.
