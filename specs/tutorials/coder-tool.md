# Coder Tool

A skill that compiles, lints, and analyzes source code through MCP server binaries. Demonstrates a multi-server skill with multiple coordinated MCP servers and capability-based routing.

## cognitive.json

```json
{
  "name": "coder-tool",
  "version": "1.0.0",
  "description": "Code compilation, linting, and static analysis",
  "author": "Your Name",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/your-org/coder-tool",
    "issues": "https://github.com/your-org/coder-tool/issues"
  },
  "hardware_requirements": {
    "min_ram_mb": 1024,
    "min_storage_mb": 500
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "compiler",
        "command": "./tools/mcp-compiler",
        "args": ["--temp-dir", "/cognitiveos/tmp/coder"]
      },
      {
        "name": "linter",
        "command": "./tools/mcp-linter"
      },
      {
        "name": "git-mcp",
        "command": "./tools/mcp-git"
      }
    ],
    "capabilities": ["code.compile", "code.lint", "code.analyze", "code.git"]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are a programming assistant. You can compile, lint, and manage Git repositories.

Code workflow:
1. Write or receive code from the user
2. Lint it with cognitiveos.code.lint to catch errors
3. Fix any lint issues
4. Compile with cognitiveos.code.compile
5. If the user asks, commit with cognitiveos.code.git

Always lint before compiling. Always report the full compiler/linter output.
```

## Build & Install

```bash
cpm init coder-tool --template mcp-bridge
cd coder-tool

# Build MCP servers
go build -o tools/mcp-compiler ./cmd/compiler
go build -o tools/mcp-linter   ./cmd/linter
go build -o tools/mcp-git      ./cmd/git-mcp

# Package and install
tar czf coder-tool-1.0.0.cgp .
cpm install ./coder-tool-1.0.0.cgp
```

## What Happens

1. Three separate MCP servers spawn, each connecting to the daemon independently
2. Each registers its own set of tools:
   - compiler: `cognitiveos.code.compile.c`, `cognitiveos.code.compile.go`, `cognitiveos.code.compile.rust`
   - linter: `cognitiveos.code.lint`, `cognitiveos.code.lint.fix`
   - git-mcp: `cognitiveos.code.git.status`, `cognitiveos.code.git.commit`, `cognitiveos.code.git.push`
3. The Wide Model autonomously chains tools — lint first, then compile, then commit
4. The daemon transparently routes each tool call to the correct server

## Usage

```
User: "Here's my Go program, check it and compile it:
       package main
       import \"fmt\"
       func main() { fmt.Println(\"Hello\") }"
  → Wide Model calls cognitiveos.code.lint with the code
  → Linter returns: "No issues found"
  → Wide Model calls cognitiveos.code.compile.go with the code
  → Compiler returns: "Build successful (2.3s)"
  → Wide Model: "Your Go program compiles cleanly."
```

```
User: "Create a new Git repo, add a main.go, commit it"
  → Wide Model calls cognitiveos.code.git.init
  → Writes main.go
  → Calls cognitiveos.code.git.add("main.go")
  → Calls cognitiveos.code.git.commit("Initial commit")
  → Wide Model: "Repo created and committed."
```
