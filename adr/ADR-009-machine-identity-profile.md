# ADR-009: Machine Identity Profile and Gated Publisher Model

**Status:** Proposed
**Date:** 2026-07-20
**Author:** CognitiveOS SDLC

## Context

### The Problem

Today, any machine that generates an SSH key can `cpm auth register` and immediately `cpm publish` to the registry. There is no gating, no approval, and no identity beyond the key itself. This creates a supply chain risk — unvetted machines can publish packages to the official registry.

The current auth flow:

```
Machine generates SSH key → cpm auth register → cpm publish
                                                   ↑
                                              No gate here
```

We need a **signup layer** that evaluates both the machine and its owner before granting publish access.

### Why cpm Needs Machine Identity

`cpm` is the package manager that runs on CognitiveOS machines. It is the tool that publishes, installs, and manages `.cgp` packages. Without machine identity, cpm has no way to:

1. **Prove it runs on a legitimate machine** — anyone can run `cpm publish` from any device. There is no proof that the machine exists, has real hardware, or is operated by a known owner.
2. **Establish accountability** — when a package is published, the registry knows only a SSH fingerprint. If that package contains malware, there is no way to trace it back to a responsible human.
3. **Enforce hardware requirements** — some packages require specific hardware (GPU, NPU, minimum RAM). The registry cannot verify that the publishing machine meets these requirements.
4. **Build trust over time** — a machine that has published 50 verified packages should be trusted more than a brand-new machine. Without identity, every machine starts from zero.

`cpm signup` gives cpm a machine-native identity mechanism. The machine proves what it IS (hardware + software) and who OWNS it (the human responsible). This is not a credential — it is an inherent property of the machine itself.

### Why the Registry Server Needs Machine Identity

The registry server is the central notary for `.cgp` packages. It stores metadata, checksums, and public keys. Without machine identity, the registry has no way to:

1. **Gate who can publish** — today, the only gate is "can you generate an SSH key." That is trivially easy. The registry needs a stronger signal of legitimacy.
2. **Apply rules before granting access** — the registry operator needs to say "only machines with TPM can publish" or "only owners in the CognitiveOS org can publish." Without a machine profile, there is nothing to apply rules against.
3. **Detect compromised publishers** — if a registered key is compromised, the attacker can publish from any machine. With machine identity, the registry can detect that a key is being used from an unexpected machine profile.
4. **Audit the supply chain** — when a security incident occurs, the registry needs to answer: "which machine published this, who owns it, what hardware/software was it running?" Without machine identity, the answer is just "a machine with this SSH fingerprint."
5. **Support different trust levels** — not all publishers are equal. A machine with TPM, known hardware, and a verified owner should have higher trust than an anonymous machine. Machine identity enables tiered trust.

The registry server evaluates the machine identity profile against configurable rules. Rules are the policy layer — they determine which machines are trusted to publish, based on their inherent properties.

### The Gap

| What exists today | What is missing |
|-------------------|-----------------|
| SSH key authentication | Machine identity (hardware + software profile) |
| Publisher fingerprint | Owner identity (who controls the machine) |
| Instant publish access | Gated approval (signup → rules → approve/reject) |
| No accountability | Traceable: machine + owner for every published package |

## Decision

Introduce a machine identity profile and gated publisher model. Before a machine can register keys and publish, it must sign up with the registry server. The server evaluates the machine's hardware/software profile and the owner's identity against configurable rules.

### Core Insight: What a Machine Has

A machine has three inherent properties:

| Property | What it is | Why it matters |
|----------|-----------|----------------|
| **Hardware** | CPU, RAM, storage, GPU, TPM, network interfaces | Proves physical capability and origin |
| **Software** | OS, kernel, packages, cpm version, running services | Proves operational environment |
| **Owner** | The person who controls the machine | Accountability — who is responsible for this machine's actions |

The machine's identity IS its profile. Not a stored credential. Not an email. The machine itself, plus the person who owns it.

### Owner Identity

The owner identifies themselves via their SSH public key. This is consistent with the existing auth model — both machine and owner have cryptographic identities. No email, no password, no OAuth.

The owner's key serves two purposes:
1. **Identity** — "who owns this machine"
2. **Accountability** — "who is responsible if this machine publishes something malicious"

### New Flow

```
Machine                          Registry Server
  │                                     │
  │  1. cpm signup                      │
  │  → gathers machine profile          │
  │     (hardware + software)           │
  │  → gathers owner identity           │
  │     (owner's SSH public key)        │
  │  → signs profile with machine key   │
  │  → POST /v1/auth/signup             │
  │  ─────────────────────────────────► │
  │                                     │
  │                                     │  2. Evaluate:
  │                                     │     - machine profile
  │                                     │     - owner identity
  │                                     │     against rules
  │                                     │
  │  ◄── 200 Approved ─────────────────│  (or 403 Rejected)
  │                                     │
  │  3. cpm auth register               │
  │  → POST /v1/auth/register           │
  │  ─────────────────────────────────► │
  │                                     │  4. Verify signup
  │                                     │     status = approved
  │                                     │     Store key
  │  ◄── 201 Key registered ───────────│
  │                                     │
  │  5. cpm publish                     │
  │  → SSH signed request               │
  │  ─────────────────────────────────► │
  │                                     │  6. Verify key is
  │                                     │     registered + approved
  │  ◄── 201 Published ────────────────│
```

### Machine Identity Profile

The machine gathers its inherent properties during `cpm signup`:

```json
{
  "machine": {
    "hardware": {
      "cpu": "AMD Ryzen 9 5900X 12-Core",
      "cores": 24,
      "arch": "amd64",
      "ram_mb": 65536,
      "storage_mb": 1000000,
      "gpu": "NVIDIA RTX 3090",
      "tpm": true,
      "machine_id": "a1b2c3d4-..."
    },
    "software": {
      "os": "linux",
      "kernel": "6.12.0",
      "distro": "alpine",
      "cpm_version": "0.1.0",
      "packages": ["docker", "go", "python3"],
      "services": ["sshd", "docker"]
    },
    "network": {
      "ip": "192.168.1.100"
    }
  },
  "owner": {
    "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG8...",
    "fingerprint": "SHA256:abc123...",
    "comment": "jean@cognitive-os.org"
  }
}
```

### Data Collection

`cpm signup` collects from the machine:

| Source | Data | Mechanism |
|--------|------|-----------|
| CPU | Model, cores | `/proc/cpuinfo`, `lscpu` |
| RAM | Total MB | `/proc/meminfo` |
| Storage | Total/free MB | `statfs()` |
| GPU | Model, VRAM | `lspci`, `nvidia-smi` |
| TPM | Present | `/sys/class/tpm/` |
| Machine ID | Unique identifier | `/etc/machine-id` |
| OS | Name, version | `runtime.GOOS`, `/etc/os-release` |
| Kernel | Version | `uname -r` |
| cpm | Version | embedded at build time |
| Network | IP address | Socket bound during connection |
| Owner key | Public key, fingerprint | `--key` flag or default `~/.ssh/id_ed25519.pub` |

### Server-Side Rules

Rules evaluate the signup profile and decide approval. Rules are stored in S3 and configurable by registry operators.

```yaml
# rules/signup-rules.yaml
rules:
  # Hardware minimums
  - field: machine.hardware.ram_mb
    operator: gte
    value: 1024
    action: approve
    reason: "Minimum 1 GB RAM required"

  # OS allowlist
  - field: machine.software.os
    operator: in
    value: ["linux", "darwin"]
    action: approve
    reason: "Supported operating systems"

  # Key type restriction
  - field: owner.key_type
    operator: in
    value: ["ssh-ed25519"]
    action: approve
    reason: "Only ed25519 keys accepted"

  # Known owner allowlist
  - field: owner.fingerprint
    operator: in
    value: ["SHA256:known_trusted_key..."]
    action: approve
    reason: "Trusted publisher"

  # TPM required for high-trust publishing
  - field: machine.hardware.tpm
    operator: equals
    value: true
    action: approve
    reason: "TPM present — hardware-rooted trust"

  # Default: queue for review
  - default: true
    action: review
    reason: "No matching rules — queued for review"
```

**Rule operators:**

| Operator | Description |
|----------|-------------|
| `equals` | Exact match |
| `not_equals` | Inverse match |
| `in` | Value in list |
| `not_in` | Value not in list |
| `gte` | Greater than or equal (numeric) |
| `lte` | Less than or equal (numeric) |
| `contains` | String contains substring |
| `regex` | Regular expression match |

**Approval states:**

| State | Meaning |
|-------|---------|
| `approved` | Machine + owner passed all rules. Can register keys and publish. |
| `pending` | No matching rules, or default action is `review`. Queued for admin review. |
| `rejected` | Machine or owner failed a rule. Cannot register or publish. |

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /v1/auth/signup` | POST | SSH signature | Machine registers identity profile |
| `GET /v1/auth/status` | GET | SSH signature | Check signup approval status |
| `POST /v1/auth/register` | POST | SSH signature | Register SSH key (requires approved signup) |
| `GET /v1/admin/approvals` | GET | Admin token | List pending signups |
| `POST /v1/admin/approve/{id}` | POST | Admin token | Approve/reject signup |

#### `POST /v1/auth/signup`

Request:
```json
{
  "machine": {
    "hardware": { ... },
    "software": { ... },
    "network": { ... }
  },
  "owner": {
    "public_key": "ssh-ed25519 AAAAC3...",
    "comment": "jean@cognitive-os.org"
  }
}
```

Headers:
```
X-SSH-Fingerprint: SHA256:<machine-key-fingerprint>
X-SSH-Signature: <base64-encoded signature of profile>
```

Response (approved):
```json
{
  "status": "approved",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "approved_at": "2026-07-20T00:42:38Z",
  "reason": "Hardware + owner meet all rules"
}
```

Response (pending):
```json
{
  "status": "pending",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "queued_at": "2026-07-20T00:42:38Z",
  "reason": "No matching rules — queued for review"
}
```

Response (rejected):
```json
{
  "status": "rejected",
  "machine_id": "a1b2c3d4-...",
  "owner_fingerprint": "SHA256:abc123...",
  "rejected_at": "2026-07-20T00:42:38Z",
  "reason": "Only ed25519 keys accepted"
}
```

#### `GET /v1/auth/status`

Headers:
```
X-SSH-Fingerprint: SHA256:<machine-key-fingerprint>
X-SSH-Signature: <signature>
```

Response:
```json
{
  "machine_id": "a1b2c3d4-...",
  "status": "approved",
  "owner_fingerprint": "SHA256:abc123...",
  "registered_keys": 2,
  "approved_at": "2026-07-20T00:42:38Z"
}
```

### S3 Object Layout

```
cognitiveos-registry/
├── auth/
│   ├── keys/
│   │   └── {fingerprint}.pub
│   └── machines/
│       └── {machine_id}/
│           ├── profile.json       # machine identity profile
│           ├── status.json        # approved/pending/rejected
│           └── owner/
│               └── {fingerprint}.pub  # owner's public key
├── rules/
│   └── signup-rules.yaml          # configurable approval rules
├── notary/
│   └── ...
└── unlock/
    └── ...
```

### CPM Client Changes

| Command | Status | Change |
|---------|--------|--------|
| `cpm signup` | **New** | Gathers machine profile + owner key, signs, sends to server |
| `cpm auth status` | **New** | Checks signup approval status |
| `cpm auth register` | **Modified** | Now checks signup status before registering key |
| `cpm publish` | **Unchanged** | Still uses SSH key signing |

### Ephemeral Design

Per the principle of no credential storage:

- `cpm signup` is a **one-shot command** — gathers profile, sends, gets response
- No tokens stored locally on the machine
- `cpm auth register` and `cpm publish` continue using SSH keys (ephemeral signing)
- The server stores the profile and approval status in S3
- The machine re-signs every request (no session tokens)
- Profile is re-gathered on each `cpm signup` call (not cached)

### What Changes vs. Today

| Aspect | Today | After ADR-009 |
|--------|-------|---------------|
| Who can register keys | Any machine | Only approved machines |
| Identity | SSH key only | Machine profile (hardware + software) + owner key |
| Approval | None (instant) | Rule-based auto-approval or manual review |
| Accountability | Key fingerprint only | Machine profile + owner identity |
| Gate between register and publish | None | Signup → approval → register → publish |
| Supply chain audit | SSH fingerprint | Full machine + owner trail for every publish |
| Trust levels | Binary (registered or not) | Tiered (rules evaluate profile for trust level) |
| Compromise detection | None | Profile mismatch → anomaly detected |

### Rejected Alternatives

| Alternative | Why rejected |
|-------------|-------------|
| Email + password accounts | Obsolete human-centric identity. Not suitable for machine-first systems. |
| GitHub OAuth | Same as email/password — derives identity from a third-party human account. |
| Hardware TPM-only identity | Platform-dependent, not all machines have TPM. Too restrictive. |
| IP-based trust only | IPs change, NAT makes them unreliable as identity. |
| No owner, machine-only | No accountability — who is responsible if the machine misbehaves? |

## Consequences

### Positive
- Supply chain security: only vetted machines can publish
- Accountability: owner identity ties machines to responsible humans
- Machine-native: identity is what the machine IS, not what it stores
- Ephemeral: no credentials to leak, no sessions to manage
- Configurable: rules can be tuned per deployment

### Negative
- Friction: new publishers must wait for approval (mitigated by good default rules)
- Complexity: server needs rule engine and machine profile storage
- Privacy: machine hardware profile is sent to registry (mitigated by: this is a publishing flow, not a browsing flow)

### Risks
- Rule misconfiguration could block legitimate publishers (mitigated by: manual review fallback)
- Machine profile can be spoofed (mitigated by: TPM attestation, network origin checks)
- Owner key compromise (mitigated by: key rotation, re-signup flow)
