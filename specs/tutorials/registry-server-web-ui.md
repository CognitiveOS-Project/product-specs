# Registry Server Web UI — Managing Keys and Publish Permissions

This tutorial covers the owner dashboard for managing SSH keys, publish permissions, and machine identity through the registry server's web interface.

## Overview

The registry server provides a web UI at `/ui/` where package publishers manage their SSH keys and control which machines can publish under their identity. The flow:

1. **Register** your machine identity with the registry (`cpm auth signup`)
2. **Register** your SSH public key (`cpm auth register`)
3. **Claim** the key in the Web UI (proves you own it via GitHub OAuth)
4. **Grant** publish permission to specific machines
5. **Publish** from those machines (`cpm publish`)

Without step 4, `cpm publish` is blocked with `PUBLISH_NOT_AUTHORIZED`.

## Prerequisites

- `cpm` installed
- SSH key pair (`ssh-keygen -t ed25519`)
- GitHub account (for OAuth login)

## First-Time Setup

### 1. Sign Up (Machine Identity)

Register your machine's identity profile with the registry:

```bash
cpm auth signup --key ~/.ssh/id_ed25519.pub
```

Output:
```
Machine registered
  Machine ID:   a1b2c3d4e5f6
  Status:       pending (claim your key in the Web UI)
```

Status is `pending` — the machine is registered but the registry doesn't know who owns it yet.

### 2. Register Your SSH Key

Register the public key with the registry (one-time per key):

```bash
cpm auth register --key ~/.ssh/id_ed25519.pub
```

Output:
```
Registered SSH key
  Fingerprint: SHA256:yljNAb+oO3LQEHBY0g5KZCl9vLnZNHkerroT/eOcJaA
  Key type:    ssh-ed25519
  Comment:     your-key
```

### 3. Login (Store Key Locally)

Store the key path locally so `cpm publish` can find it automatically:

```bash
cpm auth login --key ~/.ssh/id_ed25519
```

Output:
```
Logged in
  Key path:     /home/user/.ssh/id_ed25519
  Fingerprint:  SHA256:yljNAb+oO3LQEHBY0g5KZCl9vLnZNHkerroT/eOcJaA
  Status:       pending (claim your key in the Web UI)
```

After login, `cpm publish` no longer requires `--key`.

## Claiming Your Key

1. Open the Web UI: `https://registry-us-all-distros-official.cognitive-os.org/ui/`
2. Click **Login with GitHub**
3. Authorize the CognitiveOS Registry app
4. Your registered key appears in the dashboard as **Pending**

Click **Claim** to link the key to your GitHub identity. Status changes to **Active**.

## Granting Publish Permission

After claiming, the key shows a **Grant Publish** button. Click it to allow `cpm publish` from this machine.

Without this step, publishing is blocked:

```
ERROR: PUBLISH_NOT_AUTHORIZED — owner has not granted publish permission for this key
```

You can revoke publish permission at any time using the **Revoke** button. The key remains claimed but publishing is disabled until you grant again.

## Dashboard Features

### Key List

The dashboard shows all your claimed keys:

| Column | Description |
|--------|-------------|
| **Display Name** | Human-readable name (e.g., "Work Laptop") |
| **Status** | `active` or `revoked` |
| **Publish** | Permission status with Grant/Revoke toggle |
| **Added** | Date the key was claimed |

### Add New Key

The **Add Key** form is always visible at the bottom of the dashboard. Enter the SSH public key text and a display name to link a new machine.

### Key Actions

Each key has action buttons:

| Action | Effect |
|--------|--------|
| **Grant Publish** | Allows `cpm publish` from this machine |
| **Revoke Publish** | Blocks `cpm publish` (key stays claimed) |
| **Remove** | Unlinks the key from your identity |

## Key Lifecycle

```
registered (pending)  →  claimed (pending)  →  active
                                    ↓
                              revoked (publish blocked)
```

| State | Meaning |
|-------|---------|
| **Registered (pending)** | Machine registered via `cpm auth signup`, key not yet claimed |
| **Claimed (pending)** | Key linked to owner via Web UI, publish not yet granted |
| **Active** | Owner granted publish permission — `cpm publish` allowed |
| **Revoked** | Owner revoked publish permission — `cpm publish` blocked |

## Logout

Clear the local auth state (does not affect the server):

```bash
cpm auth logout
```

After logout, `cpm publish` requires `--key` again, or re-run `cpm auth login`.

## URL Structure

| URL | Page |
|-----|------|
| `/ui/` | Landing page with project overview |
| `/ui/login` | Redirects to GitHub OAuth |
| `/ui/callback` | OAuth callback handler |
| `/ui/dashboard` | Key management dashboard (requires login) |
| `/ui/keys/{index}/grant` | Grant publish permission to key at index |
| `/ui/keys/{index}/revoke` | Revoke publish permission from key at index |
| `/ui/keys/{index}/remove` | Remove key from owner identity |
| `/ui/logout` | Clear session |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `KEY_NOT_CLAIMED` | Key registered but not claimed in Web UI | Log in at `/ui/`, claim the key |
| `PUBLISH_NOT_AUTHORIZED` | Key claimed but publish not granted | Click "Grant Publish" in dashboard |
| `KEY_REVOKED` | Owner revoked publish permission | Ask owner to re-grant, or use different key |

## See Also

- [CPM Spec](../cpm-spec.md) — `cpm auth` command reference
- [Registry API](../registry-api.md) — Web UI routes and owner identity model
- [Publishing Tutorial](cgp-publishing.md) — end-to-end publish walkthrough
