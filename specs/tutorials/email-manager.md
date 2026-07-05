# Email Manager

A full email client skill with IMAP and SMTP MCP servers. Demonstrates multi-server coordination, credential management, and complex system prompts.

## cognitive.json

```json
{
  "name": "email-manager",
  "version": "1.2.0",
  "description": "AI-powered email client with IMAP/SMTP support",
  "author": "Your Name",
  "license": "Apache-2.0",
  "source": {
    "repository": "https://github.com/your-org/email-manager",
    "issues": "https://github.com/your-org/email-manager/issues"
  },
  "dependencies": {
    "contacts-manager": "^1.0.0",
    "notifications": "^2.3.0"
  },
  "hardware_requirements": {
    "min_ram_mb": 256,
    "min_storage_mb": 100
  },
  "runtime": {
    "system_prompt": "prompts/system.md",
    "mcp_servers": [
      {
        "name": "imap-bridge",
        "command": "./tools/mcp-imap",
        "args": ["--config", "config/imap.json"]
      },
      {
        "name": "smtp-bridge",
        "command": "./tools/mcp-smtp",
        "args": ["--config", "config/smtp.json"]
      }
    ],
    "capabilities": [
      "email.list",
      "email.read",
      "email.send",
      "email.search",
      "email.draft",
      "email.folder.create",
      "email.folder.move"
    ]
  }
}
```

## System Prompt

**`prompts/system.md`**
```
You are an email management assistant. You handle all email operations.

Commands:
- "show my inbox" → cognitiveos.email.list("INBOX", limit=20)
- "read email 5" → cognitiveos.email.read(uid=5)
- "search for 'meeting'" → cognitiveos.email.search("meeting")
- "send an email" → guide through compose, then cognitiveos.email.send(...)

Workflow for sending:
1. Ask for recipient, subject, and body
2. Optionally check contacts-manager for address completion
3. Show a preview before sending
4. Call cognitiveos.email.send with the final content
5. Confirm sent

Workflow for triage:
1. List inbox
2. Ask which emails to read
3. After reading, offer actions: reply, archive, delete, mark spam
4. Call appropriate tool

Security: Never compose or send emails without user confirmation.
Always confirm the recipient address before sending.
```

## Build & Install

```bash
cpm init email-manager --template mcp-bridge
cd email-manager

# Build IMAP and SMTP MCP servers
go build -o tools/mcp-imap ./cmd/imap
go build -o tools/mcp-smtp ./cmd/smtp

# Configure credentials
mkdir config
cat > config/imap.json << 'EOF'
{
  "server": "imap.gmail.com:993",
  "auth": "oauth2"
}
EOF
cat > config/smtp.json << 'EOF'
{
  "server": "smtp.gmail.com:587",
  "auth": "oauth2"
}
EOF
# NOTE: credentials are stored in the daemon's secure keystore,
# NOT in config files. Config files reference the key name.

# Package and install
tar czf email-manager-1.2.0.cgp .
cpm install ./email-manager-1.2.0.cgp
```

## What Happens

1. Two MCP servers spawn — `imap-bridge` handles incoming mail, `smtp-bridge` handles outgoing mail
2. Both servers reference credential keys stored in the daemon's secure keystore (hardware-backed on supported platforms)
3. The Wide Model uses the system prompt to drive the full email workflow
4. Dependencies on `contacts-manager` and `notifications` are resolved at install time — if missing, cpm installs them too

## Usage

```
User: "Check my email"
  → Wide Model calls cognitiveos.email.list("INBOX", limit=20)
  → Server returns 20 recent messages
  → Wide Model: "You have 20 emails in your inbox. 3 are unread:
     1. Alice — "Meeting tomorrow" (unread)
     2. Bob — "Lunch on Friday" (unread)
     3. Spam — "You won!" (unread) ← likely spam
     Would you like me to read any of them?"

User: "Read the one from Alice"
  → Wide Model calls cognitiveos.email.read(uid=1)
  → Server returns full email: subject, from, date, body, attachments
  → Wide Model summarizes: "Alice wants to meet tomorrow at 2pm about the Q3 planning. Should I reply?"
```

```
User: "Send an email to Bob saying I'll be there for lunch"
  → Wide Model: "To Bob <bob@example.com>, subject 'Re: Lunch on Friday', body 'I'll be there!'. Send?"
User: "Yes"
  → Wide Model calls cognitiveos.email.send(to="bob@example.com", subject="Re: Lunch on Friday", body="I'll be there!")
  → Server sends via SMTP
  → Wide Model: "Sent. Should I archive your original thread?"
```

## Cross-Ecosystem Install

Because `cpm` is a universal protocol router, you can also install email-related packages from other ecosystems:

```bash
# Install an npm email template package
cpm install npm:@email-templates/welcome

# Install a GitHub-published MCP server
cpm install github.com/user/mcp-smtp@v1.0.0

# The Normalization Engine converts these to .cgp format automatically
```
