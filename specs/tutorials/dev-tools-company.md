# Dev Tools Company: Proprietary Static Analyzer as an MCP Server

**Company profile:** Developer tools company that builds a proprietary static analysis engine (e.g., SonarQube, Coverity, Semgrep, Snyk). They want to distribute it as an MCP server that the Wide Model can invoke during coding sessions.

This tutorial shows a multi-server package with license-key gating, hardware requirements for CI-scale analysis, and integration with the Coder Tool.

## Why .cgp Instead of a CLI Tool

| Concern | Standalone CLI | .cgp Package |
|---------|---------------|--------------|
| Discovery | Docs, blog posts | `cpm search analyzer` |
| License mgmt | Manual download, env vars | Unlock code flow, hardware-bound licensing |
| Integration | User pipes output manually | Wide Model calls it autonomously during coding |
| Updates | Manual reinstall | `cpm update` |
| Usage analytics | None | Registry tracks install counts |
| Multi-arch | Per-arch binaries | `cpm` selects correct binary from the archive |

## cognitive.json

```json
{
  "name": "mycompany-code-analyzer",
  "version": "4.2.0",
  "description": "Proprietary static analysis engine for C/C++, Go, Rust, Python, Java",
  "author": "MyCompany DevTools",
  "license": "proprietary",
  "source": {
    "repository": "https://github.com/mycompany/code-analyzer",
    "issues": "https://github.com/mycompany/code-analyzer/issues"
  },
  "dependencies": {
    "coder-tool": "^1.0.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 2048,
    "min_storage_mb": 1000,
    "min_cpu_cores": 4
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "analyzer-engine",
        "command": "./tools/mcp-analyzer",
        "args": ["--threads", "4", "--temp-dir", "/cognitiveos/tmp/analyzer"]
      },
      {
        "name": "license-daemon",
        "command": "./tools/mcp-license",
        "args": ["--port", "50999"],
        "background": true
      }
    ],
    "capabilities": [
      "code.analyze.security",
      "code.analyze.quality",
      "code.analyze.sast",
      "code.analyze.suppressions",
      "code.analyze.report"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`:**
```
You are a code analysis assistant powered by MyCompany Code Analyzer v4.

Available analysis types:
- Security (SAST): cognitiveos.code.analyze.security(path, language)
- Code quality: cognitiveos.code.analyze.quality(path, ruleset="recommended")
- Full report: cognitiveos.code.analyze.report(path, format="sarif")

Workflow:
1. When the user writes code, analyze it automatically
2. Report findings with severity, location, and remediation advice
3. Fix critical and high-severity issues before presenting code to the user
4. For medium/low, ask if they want to fix or suppress
5. Suppressions are tracked in .analyzer-suppressions at project root

License status is checked by the license-daemon. If the license is expired,
you can still run analysis but findings are limited to critical severity only.
```

## License Server

The `license-daemon` runs as a background service:

```go
// mcp-license registers: cognitiveos.code.analyze.license.status
//                      cognitiveos.code.analyze.license.activate

func (s *LicenseServer) HandleCheckout(ctx context.Context) {
    // Hardware-bound: MAC address + TPM binding
    // Floating licenses: checks out from company license server
    // Offline grace: 7 days without phone-home
    // Returns: { status: "valid"|"expired"|"grace", seats_used: 3, seats_total: 10 }
}
```

## Build & Install

```bash
cpm init mycompany-code-analyzer --template mcp-bridge
cd mycompany-code-analyzer

# Build the analyzer engine MCP server
go build -o tools/mcp-analyzer ./cmd/analyzer

# Build the license daemon
go build -o tools/mcp-license ./cmd/license

# Package
tar czf mycompany-code-analyzer-4.2.0.cgp .
cpm publish ./mycompany-code-analyzer-4.2.0.cgp
```

```bash
# User installs
cpm install mycompany-code-analyzer

# First run: license activation
# Raw Model: "MyCompany Code Analyzer requires a license.
#             Enter your activation code or visit https://mycompany.com/license"
User: "ACTIVATE-ABC123-DEF456"
  → license-daemon validates against mycompany.com
  → License: 10 seats, 12 months, hardware-bound
  → "License activated. 10 seats available."
```

## What Happens

1. **Dependency check** — `coder-tool` must be installed (provides compile flow for the analysis output)
2. **License init** — If no cached license, activation flow blocks further install
3. **Two servers spawn** — `analyzer-engine` handles analysis requests, `license-daemon` validates and tracks usage
4. **Hardware audit** — 2 GB RAM, 4 CPU cores minimum enforced
5. **Background license check** — `license-daemon` runs continuously, re-validates every 24h

## Usage

```
User writes code and asks: "Is this secure?"
  → Wide Model calls cognitiveos.code.analyze.security(path)
  → Engine runs SAST scan (5.3s)
  → Results:
     CRITICAL: SQL injection at line 42 — unsanitized user input in query string
       Fix: use parameterized queries
     HIGH: Hardcoded API key at line 15
       Fix: move to environment variable or keystore
     LOW: Unused variable 'count' at line 88
  → Wide Model auto-fixes critical and high issues:
     "I found 3 issues. I've fixed the critical SQL injection and the hardcoded key.
      The unused variable on line 88 — should I remove it?"
```

```
CI/CD integration (batch mode):

User: "Analyze all PRs in the repo and block merge if critical findings exist"
  → Wide Model calls cognitiveos.code.analyze.report(path, "sarif") for each PR
  → Results stored as SARIF artifacts
  → GitHub check created with findings
  → Wide Model summarizes in PR comment: "3 critical, 5 high — merge blocked"
```

## Usage-Based Licensing

```bash
# Check license status
User: "How many analyzer seats are we using?"
  → Wide Model calls cognitiveos.code.analyze.license.status()
  → license-daemon: { seats_used: 3, seats_total: 10, expires: "2027-07-04" }
  → "3 of 10 seats used. License expires July 4, 2027."

# The enterprise admin gets proactive notifications:
# "You've used 8 of 10 analyzer seats. Consider upgrading before the next sprint."
```
