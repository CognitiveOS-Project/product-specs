# Cognitive Patch (.cgp) Format Specification

Version: 1.0.0-draft

## Overview

A Cognitive Patch (`.cgp`) is the distribution format for CognitiveOS skills, tools, and model adapters. It is the agent-era equivalent of `.apk`, `.deb`, or `.npm` packages — a single archive containing everything needed to extend the AI's capabilities.

## Format

A `.cgp` file is a **tar.gz** (gzip-compressed tar archive). Uncompressed directories are also valid for development.

### Directory structure

```
<name>-<version>.cgp/
├── cognitive.json          # Manifest (REQUIRED)
├── prompts/                # System prompts and templates (OPTIONAL)
│   ├── system.md           # Primary behavioral persona
│   └── templates/          # Structured response formats
├── tools/                  # MCP servers and scripts (OPTIONAL)
│   └── mcp-server-*        # Executable MCP server binary or script
└── weights/                # Model weights (OPTIONAL)
    └── *.gguf              # Bundled GGUF firmware or adapter
```

### Rules

1. `cognitive.json` is the only required file — a patch can consist solely of a manifest (e.g., a prompt-only skill).
2. All paths in `cognitive.json` are relative to the archive root.
3. Executables in `tools/` must be compiled for the target architecture or be scripts with a valid shebang.
4. Archives use `.cgp` extension. Uncompressed directories are identified by the presence of `cognitive.json`.

## Lifecycle

### Install

```bash
cpm install <path-or-name>.cgp
```

The install sequence is:

1. **Parse** `cognitive.json` manifest.
2. **Audit** hardware requirements (RAM, storage, NPU).
3. **Resolve** dependencies (other required patches).
4. **Extract** to `/cognitiveos/patches/<name>/`.
5. **Spawn** MCP servers declared in `runtime.mcp_servers`.
6. **Register** tools with cognitiveosd's tool registry.

### Remove

```bash
cpm remove <name>
```

1. **Terminate** all MCP server processes for this patch.
2. **Deregister** tools from the registry.
3. **Delete** `/cognitiveos/patches/<name>/`.

### Update

```bash
cpm update <name>
```

1. Download new version from registry.
2. Run install sequence.
3. If install succeeds, remove old version. If install fails, roll back.

## Registry Integration

Patches can be published to a [registry-server](https://github.com/CognitiveOS-Project/registry-server):

```bash
cpm publish ./my-skill.cgp
cpm install my-skill  # resolves from registry
```

Search syntax:

```bash
cpm search email
cpm search "image processing" --license MIT
```

## Distribution

- Public patches: hosted on the official CognitiveOS registry
- Private patches: self-hosted registries or direct file transfers
- Paid patches: require unlock code (see [system-codes.md](system-codes.md))
