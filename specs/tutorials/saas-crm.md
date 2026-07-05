# SaaS Company: CRM Integration for Salesforce

**Company profile:** SaaS company (Salesforce, HubSpot, Notion, Linear) that wants to offer an AI-native interface to their product. Users interact through natural language instead of clicking through menus.

This tutorial shows how to build an MCP bridge that gives the Wide Model full CRM access — accounts, contacts, opportunities, pipeline — all through a single `cpm install`.

## Why .cgp Instead of a Separate App

| Concern | Traditional mobile/web app | .cgp package |
|---------|---------------------------|--------------|
| Distribution | App Store approval, update friction | `cpm install`, `cpm update` |
| Auth | OAuth2 redirect, token storage | Daemon's secure keystore, ephemeral tokens |
| UI | Need to build and maintain a UI | The AI *is* the interface |
| Cross-device | Per-device install | Same package, same credentials |
| Offline | Full sync engine required | Prompt + cached data works offline |

## cognitive.json

```json
{
  "name": "salesforce-crm",
  "version": "2.3.0",
  "description": "Salesforce CRM — accounts, contacts, opportunities, pipeline, reports",
  "author": "Salesforce, Inc.",
  "license": "MIT",
  "source": {
    "repository": "https://github.com/salesforce/crm-mcp-bridge",
    "issues": "https://github.com/salesforce/crm-mcp-bridge/issues"
  },
  "dependencies": {
    "oauth2-keystore": "^1.0.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 256,
    "min_storage_mb": 100
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "sf-rest-api",
        "command": "./tools/mcp-salesforce",
        "args": ["--api-endpoint", "https://mycompany.salesforce.com"]
      }
    ],
    "capabilities": [
      "crm.account.list",
      "crm.account.get",
      "crm.contact.list",
      "crm.contact.get",
      "crm.opportunity.list",
      "crm.opportunity.get",
      "crm.pipeline.list",
      "crm.report.run"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`:**
```
You are a Salesforce CRM assistant. You can view, search, and update customer data.

Available operations:
- List accounts: cognitiveos.crm.account.list(limit=10, region="EMEA")
- Get account details: cognitiveos.crm.account.get("001XX000003GOD")
- Find contacts: cognitiveos.crm.contact.list(account="001XX000003GOD")
- Pipeline stage: cognitiveos.crm.pipeline.list()
- Opportunity details: cognitiveos.crm.opportunity.get("006XX000004ABC")

Communication style:
- Keep responses concise — executives don't have time to read paragraphs
- When asked for a list, show a table with key fields
- Before updating a record, confirm with the user
- Use CRM terminology (Account, Contact, Opportunity, Pipeline) consistently
- When running reports, summarize the key insight in one sentence

Credentials are stored in the system keystore and resolved automatically.
You never ask the user for their Salesforce password.
```

## Authentication Setup

The OAuth2 handshake happens once at install time:

```bash
cpm install salesforce-crm

# First launch: daemon detects no stored token
# Opens browser or QR code for OAuth2 authorization
# Token stored in hardware-backed keystore at /cognitiveos/secrets/
# Subsequent installs on other devices use the same flow

# Revoke access:
cpm remove salesforce-crm  # also revokes OAuth token via Salesforce API
```

## Build & Install

```bash
cpm init salesforce-crm --template mcp-bridge
cd salesforce-crm

# Build the MCP server that wraps the Salesforce REST API
go build -o tools/mcp-salesforce ./cmd/salesforce

# Package
tar czf salesforce-crm-2.3.0.cgp .
cpm publish ./salesforce-crm-2.3.0.cgp

# Users install with one command
cpm install salesforce-crm
```

## What Happens

1. **Dependency check** — `oauth2-keystore` is installed (provides the secure token storage primitives)
2. **Hardware audit** — 256 MB RAM, 100 MB storage verified
3. **Keystore init** — OAuth2 flow triggered, token stored in `secrets/` partition
4. **MCP server spawns** — `mcp-salesforce` connects to Salesforce REST API using the stored token
5. **Capabilities registered** — all `crm.*` tools indexed by the daemon
6. **System prompt injected** — teaches the Wide Model CRM terminology and workflows

## Usage

```
User: "What's in my pipeline this quarter?"
  → Wide Model calls cognitiveos.crm.pipeline.list()
  → MCP server queries Salesforce API → returns 15 opportunities
  → "You have 15 open opportunities this quarter:
     Stage      | Count | Total Value
     -----------|-------|------------
     Prospecting| 3     | $45,000
     Negotiation| 5     | $230,000
     Closed Won | 7     | $890,000
     Total pipeline: $1,165,000
     Top deal: Acme Corp — $500,000 (Negotiation stage)"

User: "Show me Acme Corp details"
  → Wide Model calls cognitiveos.crm.account.get("Acme Corp")
  → Returns full account record
  → "Acme Corp | San Francisco, CA | 150 employees | Industry: Manufacturing
     Key contacts: John Smith (CEO), Jane Doe (CTO)
     Latest activity: Demo scheduled for next Tuesday"
```

```
User: "Find John's email and send a follow-up about the demo"
  → Wide Model calls cognitiveos.crm.contact.get("John Smith")
  → "John Smith | VP Engineering | j.smith@acme.com
     Shall I draft the follow-up?"
User: "Yes, say thanks for the demo and mention we'll send pricing"
  → Wide Model drafts and presents
  → User confirms
  → Calls cognitiveos.crm.email.send or integrates with email-manager skill
```

## Enterprise SSO and Audit

For enterprise customers, SAS 70 / SOC 2 compliance is handled at the daemon level:

```
All CRM tool invocations are logged to /cognitiveos/var/audit.log:
  [2026-07-04T14:23:01Z] tool=crm.opportunity.get user=alice@company.com target="Acme Corp"
  [2026-07-04T14:23:05Z] tool=crm.pipeline.list user=alice@company.com

Audit trail is append-only, signed by the Raw Model, and exported to the enterprise SIEM.
```

## Multi-Product: Salesforce + Notion + Slack

Install all three, and the Wide Model coordinates across them:

```
User: "Get the Q3 plan from Notion, create a Salesforce opportunity for each initiative,
       and post the summary to the #planning Slack channel"
  → cognitiveos.notion.page.get("Q3 Plan")
  → cognitiveos.crm.opportunity.create() × 5
  → cognitiveos.slack.channel.post("#planning", "...")
  → "Done. 5 opportunities created from your Q3 plan. Posted to #planning."
```
