# Ephemeral Identity — Long-Term Vision

Version: 0.1.0-draft

## Overview

Ephemeral Identity is the long-term vision for identity in CognitiveOS. It replaces persistent, platform-bound identity with **transaction-based attestation** — each interaction generates a short-lived, signed proof of who you are, used once and discarded.

This is the **future direction**. Near-term identity remains [code-based](raw-model.md#2-code-based-authentication): the human speaks or types an unlock code, and the Raw Model validates it.

## The Problem

Traditional identity models are:
- **Persistent**: accounts live forever, can be stolen, replayed, sold
- **Platform-bound**: your identity belongs to Google/Apple/Microsoft
- **Non-portable**: switching platforms means losing your data and relationships
- **Password-based**: passwords are phishable, guessable, replayable

## The Solution: Pharmacist / Pharmacy Analogy

```
Physical world:                     CognitiveOS:

You show up at the pharmacy          You present attestation to a service
You present ID + prescription        Raw Model generates ephemeral token
Pharmacist verifies:                 Service verifies:
  - ID is valid (government-issued)   - Token is signed by trusted Raw Model
  - Prescription is signed by doctor  - Token is fresh (< 60 seconds old)
  - You match the photo               - Token matches this transaction

Pharmacist doesn't keep your ID.     Service doesn't store your token.
Pharmacist keeps a log:              Service keeps a log:
  "Person X presented valid ID        "Raw Model Y attested for human Z
   for prescription Y at time T"       for transaction W at time T"
```

## Architecture

### Components

| Component | Role | Location |
|-----------|------|----------|
| **Raw Model** | Attestation authority | Firmware, root-level |
| **Biometric sensor** | Identity capture | Camera / mic / touch sensor |
| **Attestation token** | Short-lived proof | Generated per transaction |
| **Registry server** | Verifier | Remote |

### Flow

```
1. Human wants to: purchase a premium cognitive patch
2. CognitiveOS prompts: "Please look at the camera for identity verification"
3. Raw Model captures face image via camera MCP bridge (direct, no OS buffer)
4. Raw Model runs face embedding through the always-loaded raw model GGUF:
   - Captured embedding vs. stored enrollment (in read-only firmware partition)
   - Match score must exceed threshold (decided by human at enrollment time)
5. On match:
   - Raw Model generates a signed JWT containing:
     - Raw Model public key fingerprint
     - Transaction ID (one-time use)
     - Timestamp (issued at, expires at)
     - Attested claims (e.g. "age > 18", "is_owner", "payment_authorized")
   - Token TTL: 60 seconds
6. Token is forwarded to the registry server
7. Registry server:
   - Verifies signature against Raw Model's public key (registered at first boot)
   - Checks timestamp (must be < 60 seconds old)
   - Checks transaction ID (never seen before)
   - If all pass: authorizes the transaction
8. Token is discarded by all parties
```

## Enrollment

On first boot (or factory reset), the system has no biometric data:

1. Raw Model boots in **unlocked mode** (no authentication required for first 24 hours)
2. Human sets up the device, connects to network
3. Human is prompted: "Would you like to enroll biometric identity?"
4. If yes: Raw Model captures 3 samples (face from different angles, or voice passphrase repeated)
5. Samples are processed into a template stored in the **read-only firmware partition**
6. Enrollment is complete — unlock mode expires

### Re-enrollment

If the human wants to re-enroll (e.g. appearance changed):
1. Requires physical presence (button combo + code)
2. Old template is purged, new enrollment begins

## Security Properties

| Threat | Mitigation |
|--------|-----------|
| Replay attack | Token TTL 60s, single-use transaction ID |
| Stolen token | Useless after 60s, bound to specific transaction |
| Impersonation | Biometric match required for token generation |
| Raw Model compromise | Attestation key is hardware-backed (read-only partition) |
| Server compromise | No stored tokens to steal; log only has transaction hash |
| Offline attacks | No identity data leaves the device |

## Limitations and Trade-offs

| Trade-off | Explanation |
|-----------|-------------|
| Hardware dependency | Requires camera/mic; not available on all distro variants |
| Enrollment friction | Human must enroll before using paid services |
| No recovery | Lost device = lost identity; no cloud backup |
| Single-user | One enrollment per device; no multi-account |
| Privacy vs convenience | Stronger privacy (no persistent identity), less convenience (must present biometric each time) |

## Non-Goals

- **Not an SSO provider** — tokens are not reusable across services
- **Not a recovery mechanism** — lost enrollment cannot be restored
- **Not multi-user** — one human per device
- **Not FIDO2/WebAuthn** — different threat model and architecture
- **Not a replacement for code-based auth** — codes remain the primary unlock mechanism; biometrics are an additional option for high-value transactions

## Relationship to Code-Based Auth

| Aspect | Code-Based Auth (near-term) | Biometric Auth (long-term) |
|--------|---------------------------|---------------------------|
| **Method** | Human speaks/types a numeric code | Raw Model captures face/voice/touch |
| **Strength** | 6-8 digit code, standard entropy | Biometric match, high entropy |
| **Phishing resistance** | Low (code can be observed) | High (cannot observe biometric) |
| **Hardware requirement** | None (mic or keyboard) | Camera/mic/touch sensor |
| **Use case** | Daily unlock, free patches | Premium patches, payment, sensitive actions |
| **Implementation** | Now (v1.0) | Future (v2.0+) |

## See Also

- [Raw Model](raw-model.md) — attestation authority; code-based auth for v1.0
- [Security Model](security-model.md) — trust boundaries
- [System Codes](system-codes.md) — unlock code flow
