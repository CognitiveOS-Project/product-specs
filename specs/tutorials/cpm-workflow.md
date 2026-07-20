# CPM Workflow: Init → Pack → Publish

This guide demonstrates the end-to-end lifecycle of creating, packaging, and distributing a CognitiveOS patch (.cgp).

## Prerequisites

- `cpm` installed (`go install github.com/CognitiveOS-Project/cpm/cmd/cpm@latest`)
- SSH key pair for registry authentication (`ssh-keygen -t ed25519`)

## 1. Initialize a New Skill

Use `cpm init` to create a structured skeleton directory.

```bash
# Create a basic skill with prompts and tools directories
cpm init my-awesome-skill

# Create a minimal prompt-only skill
cpm init my-prompt-skill --template prompt-only

# Create an MCP server bridge
cpm init my-mcp-bridge --template mcp-bridge

# Create a GGUF model package
cpm init my-model --template gguf-model

# Create a firmware package
cpm init my-firmware --template firmware

# Create a full reference package
cpm init my-everything --template full
```

Each template creates a `.github/` directory with Alpine CI/CD workflows (Dockerfile.ci, ci.yml, publish.yml).

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
- **Weights**: If distributing a model, place `.gguf` files in `weights/` and update the manifest.

## 4. Verify the Manifest

Use `cpm verify` to validate your package before publishing:

```bash
cpm pack
cpm verify my-awesome-skill-0.1.0.cgp
```

Output:
```
✓ my-awesome-skill-0.1.0.cgp is valid (my-awesome-skill v0.1.0)
```

## 5. Inspect Package Info

Use `cpm info` to view manifest details:

```bash
# View installed package info
cpm info my-awesome-skill

# View local manifest as JSON (for CI/CD pipelines)
cpm info --json --manifest cognitive.json
```

JSON output:
```json
{
  "name": "my-awesome-skill",
  "version": "0.1.0",
  "description": "A skill that provides advanced analysis of system logs",
  "author": "Jane Doe",
  "license": "MIT",
  "filename": "my-awesome-skill-0.1.0.cgp"
}
```

## 6. Register SSH Key

Register your SSH public key with the registry (one-time per key):

```bash
cpm auth register --key ~/.ssh/id_ed25519.pub
```

Output:
```
Registered SSH key
  Fingerprint: SHA256:abc123...
  Key type:    ssh-ed25519
  Comment:     your-key
  Registered:  2026-07-20T00:42:38Z
```

## 7. Publish to Registry

Two publish modes are available:

### Official Publish (registry hosts the file)

For packages under 32 MB, the registry server handles hosting:

```bash
cpm publish my-awesome-skill-0.1.0.cgp --key ~/.ssh/id_ed25519
```

The registry:
1. Verifies your SSH signature
2. Creates a GitHub Release on the official org
3. Uploads the .cgp as a release asset
4. Stores manifest + checksum in S3-compatible storage

### Notary Proxy Publish (you host the file)

For larger packages or self-hosted distribution:

```bash
cpm publish my-awesome-skill-0.1.0.cgp \
  --key ~/.ssh/id_ed25519 \
  --download-url https://github.com/your-org/releases/download/v1.0.0/my-awesome-skill-0.1.0.cgp
```

The registry stores metadata and checksum only. Consumers install via:
```bash
cpm install ghr:your-org/my-awesome-skill@v1.0.0
```

## 8. Search and Install

Once published, others can find and install your package:

```bash
# Search the registry
cpm search my-awesome-skill

# Install from registry
cpm install my-awesome-skill@0.1.0

# Install from GitHub Release (UPR)
cpm install ghr:your-org/my-awesome-skill@v1.0.0

# Install from local file
cpm install ./my-awesome-skill-0.1.0.cgp

# List installed packages
cpm list
```

## 9. Verify Checksums

The notary system stores checksums for all published packages:

```bash
# Verify via registry API
curl "https://registry-us-all-distros-official.cognitive-os.org/v1/notary/check?source=cpm&path=my-awesome-skill&version=0.1.0"
```

Response:
```json
{
  "name": "my-awesome-skill",
  "version": "0.1.0",
  "stored_hash": "00713d22377d8237afdfce310a9cf438151944189d6fccfe6867bb64526259aa",
  "verified": true
}
```

## Summary of Workflow

| Step | Command | Purpose |
|------|---------|---------|
| **Init** | `cpm init <dir> --template <type>` | Create skeleton and manifest |
| **Develop**| Edit `cognitive.json`, `prompts/`, `tools/` | Define identity & requirements |
| **Build** | `go build ...` (if MCP server) | Create tools/binaries |
| **Pack** | `cpm pack` | Bundle and verify as `.cgp` |
| **Verify** | `cpm verify *.cgp` | Validate archive integrity |
| **Auth** | `cpm auth register --key *.pub` | Register SSH key (one-time) |
| **Publish** | `cpm publish *.cgp --key` | Distribute to registry |
| **Search** | `cpm search <query>` | Find packages |
| **Install** | `cpm install <name>` | Install from registry |
| **Info** | `cpm info --json` | Inspect manifest (CI/CD) |
