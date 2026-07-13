# CPM Workflow: Init → Pack → Publish

This guide demonstrates the end-to-end lifecycle of creating, packaging, and distributing a CognitiveOS patch (.cgp).

## 1. Initialize a New Skill

Use `cpm init` to create a structured skeleton directory based on your skill type.

```bash
# Create a basic skill with prompts and tools directories
cpm init my-awesome-skill --template default

# Or create a minimal prompt-only skill
cpm init my-prompt-skill --template prompt-only

# Or create an MCP server bridge
cpm init my-mcp-bridge --template mcp-bridge
```

Navigate into your project:
```bash
cd my-awesome-skill
```

## 2. Customize Your Manifest

Edit `cognitive.json` to define your skill's identity, requirements, and runtime behavior.

**Example `cognitive.json`**
```json
{
  "name": "my-awesome-skill",
  "version": "0.1.0",
  "description": "A skill that provides advanced analysis of system logs",
  "author": "Jane Doe",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 1024,
    "min_storage_mb": 50
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "tools_root": "tools"
  }
}
```

## 3. Add Content

Depending on your template, add your assets:

- **Prompts**: Edit `prompts/system.md` to define the AI's persona and instructions.
- **Tools**: Place your MCP server binaries or scripts in the `tools/` directory.
- **Weights**: If distributing a model, place `.gguf` files in `weights/` and update the `brain` section of the manifest.

## 4. Package the Skill

Use `cpm pack` to bundle your manifest and assets into a signed, verified `.cgp` archive.

### Scenario A: Packaging from a directory (automatic manifest detection)
If you have a `cognitive.json` in your current directory:
```bash
cpm pack --bin ./build/bin/my-tool
```
*This will find `cognitive.json` automatically, include the binary in `tools/`, and create a `.cgp` file.*

### Scenario B: Packaging a minimal manifest via CLI
If you don't have a manifest file, you can define one on the fly:
```bash
cpm pack --name "my-skill" --version "0.1.0" --os linux --arch amd64
```

### Scenario C: Using a specific manifest file
```bash
cpm pack --manifest path/to/custom-cognitive.json
```

**Output**: You will get a file like `my-awesome-skill-0.1.0-universal.cgp`.

## 5. Publish to Registry

Once packaged, upload your `.cgp` to the official CognitiveOS registry for distribution.

```bash
# Replace with your actual package filename
cpm publish my-awesome-skill-0.1.0-universal.cgp --download-url "https://github.com/your-org/my-skill/releases/download/v0.1.0/my-awesome-skill-0.1.0-universal.cgp"
```

## Summary of Workflow

| Step | Command | Purpose |
|------|---------|---------|
| **Init** | `cpm init <dir>` | Create skeleton and manifest |
| **Develop**| `vim cognitive.json` | Define identity & requirements |
| **Build** | `go build ...` | Create tools/binaries |
| **Pack** | `cpm pack` | Bundle and verify as `.cgp` |
| **Publish**| `cpm publish` | Distribute to registry |
