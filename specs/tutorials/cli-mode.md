# CLI Mode: Non-Interactive Automation

The `cognitiveos-cli --cmd` flag runs CognitiveOS in non-interactive mode: send a command, get a response, exit. This tutorial covers practical use cases where non-interactive access to the AI is more powerful than the interactive TUI.

## When to Use CLI Mode

| Use Case | Why CLI Mode |
|----------|-------------|
| Shell scripts | Pipe AI responses into other commands |
| Cron jobs | Schedule recurring AI tasks without a human at the terminal |
| CI/CD pipelines | Automate code review, documentation, or testing |
| SSH sessions | Query the system remotely without a TTY |
| Monitoring | Health checks, status reports, alerting |
| Data extraction | Parse structured JSON output with `jq` |

## Basic Usage

```bash
# Simple query — prints plain text response
cognitiveos-cli --cmd "what time is it"

# JSON output — full envelope for parsing
cognitiveos-cli --cmd "system status" --json

# Custom socket path
cognitiveos-cli --socket /tmp/daemon.sock --cmd "list installed patches"
```

## Examples

### 1. Shell Script: Daily System Report

```bash
#!/bin/sh
# daily-report.sh — Generate a daily system status report

echo "=== CognitiveOS Daily Report ==="
echo "Date: $(date)"
echo ""

# Get system status as plain text
status=$(cognitiveos-cli --cmd "give me a brief system status" 2>/dev/null)
echo "System: $status"

# Get installed patches
patches=$(cognitiveos-cli --cmd "list all installed patches with versions" 2>/dev/null)
echo "Patches: $patches"

# Check disk usage
disk=$(cognitiveos-cli --cmd "check disk usage and warn if above 80%" 2>/dev/null)
echo "Disk: $disk"
```

### 2. Cron Job: Scheduled Monitoring

```bash
# Check every 5 minutes, alert if something is wrong
*/5 * * * * cognitiveos-cli --cmd "run a quick health check and report any issues" 2>/dev/null | mail -s "CognitiveOS Alert" admin@example.com
```

### 3. CI/CD Pipeline: Automated Code Review

```yaml
# .github/workflows/review.yml
steps:
  - name: AI Code Review
    run: |
      diff=$(git diff HEAD~1)
      review=$(echo "$diff" | cognitiveos-cli --cmd "review this code diff for bugs and security issues" --json)
      echo "$review" | jq -r '.payload.content'
```

### 4. Monitoring Script: Health Check

```bash
#!/bin/sh
# healthcheck.sh — Verify CognitiveOS services are running

check_service() {
  local service=$1
  local result
  result=$(cognitiveos-cli --cmd "check if $service is running and healthy" --json 2>/dev/null)
  
  if [ $? -ne 0 ]; then
    echo "FAIL: $service — no response"
    return 1
  fi
  
  local status
  status=$(echo "$result" | jq -r '.payload.content')
  echo "OK: $service — $status"
  return 0
}

check_service "cognitiveosd"
check_service "cograw"
check_service "coginfer"
```

### 5. Data Extraction: JSON Pipeline

```bash
# Get structured data and process with jq
cognitiveos-cli --cmd "list all installed patches with name, version, and size" --json \
  | jq -r '.payload.content' \
  | grep -E "^[a-z]" \
  | sort
```

### 6. Remote Query via SSH

```bash
# Query a remote CognitiveOS device
ssh pi@cognitiveos-device \
  "cognitiveos-cli --cmd 'what is the current temperature and network status'"
```

### 7. Conditional Logic in Scripts

```bash
#!/bin/sh
# install-patch.sh — Install a patch only if not already installed

PATCH_NAME="photo-viewer"

installed=$(cognitiveos-cli --cmd "is $PATCH_NAME installed?" 2>/dev/null)

case "$installed" in
  *already installed*|*yes*)
    echo "$PATCH_NAME is already installed"
    ;;
  *)
    echo "Installing $PATCH_NAME..."
    cognitiveos-cli --cmd "install $PATCH_NAME" 2>/dev/null
    echo "Done"
    ;;
esac
```

### 8. Pipeline: AI-Powered Log Analysis

```bash
# Analyze system logs with AI
tail -100 /var/log/cognitiveos/daemon.log \
  | cognitiveos-cli --cmd "analyze these logs and report any errors or warnings" \
  | head -20
```

## JSON Output Format

When using `--json`, the full envelope is printed:

```json
{
  "type": "output_deliver",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "from": "cognitiveosd",
  "timestamp": "2026-07-16T15:42:00Z",
  "payload": {
    "content": "The system is running normally. 3 patches installed, 2.1 GB free disk space."
  }
}
```

Parse with `jq`:

```bash
# Extract just the response text
cognitiveos-cli --cmd "status" --json | jq -r '.payload.content'

# Extract the message ID for logging
cognitiveos-cli --cmd "status" --json | jq -r '.id'

# Check if response exists
response=$(cognitiveos-cli --cmd "status" --json)
if [ $? -eq 0 ]; then
  echo "AI responded: $(echo "$response" | jq -r '.payload.content')"
fi
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — response received |
| 1 | Error — connection failed, timeout, or invalid flags |

Use in conditional logic:

```bash
if cognitiveos-cli --cmd "verify package integrity" 2>/dev/null; then
  echo "Verification passed"
else
  echo "Verification failed or timed out"
  exit 1
fi
```

## Timeouts

- **Connection**: Retries for 30 seconds, then fails
- **Response**: Waits 30 seconds for `output_deliver`, then times out

For long-running queries, the Wide Model may take time to process. If timeout is an issue, the query may need to be simplified or the model resources increased.

## Advantages Over TUI

| Feature | TUI Mode | CLI Mode |
|---------|----------|----------|
| Interactive editing | Yes | No |
| Voice input | Yes | No |
| Media rendering | Yes | No |
| Scriptable | No | Yes |
| Pipeable | No | Yes |
| Cron-compatible | No | Yes |
| SSH-friendly (no TTY) | No | Yes |
| JSON output | No | Yes |
| Batch operations | No | Yes |
| Remote automation | No | Yes |

## Limitations

- **No session state**: Each `--cmd` call is independent. There is no conversation history between calls.
- **No voice**: Text input only. Voice capture requires the interactive TUI.
- **No media**: Output is text only. Image/video rendering requires the TUI's framebuffer integration.
- **No editing**: You cannot edit or refine your command after sending it. The response is final.
- **Single response**: Only the first `output_deliver` is captured. If the Wide Model sends multiple responses, only the first is printed.

## See Also

- [CLI Specification](../cli-spec.md) — Full flag reference and behavior details
- [Daemon API](../cognitiveosd-api.md) — Wire protocol and message types
- [CPM Workflow](cpm-workflow.md) — Packaging and distributing skills
