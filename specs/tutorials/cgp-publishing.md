# Tutorial: Publishing CGP Packages to the Official Registry

Version: 1.0.0

## Overview

This tutorial walks through the complete end-to-end flow for publishing a `.cgp` (Cognitive Patch) package to the official CognitiveOS registry. You will:

1. Generate an SSH key pair for authentication
2. Sign up a machine identity profile with the registry
3. Log in locally (store key path)
4. Claim your key as a package owner via the Web UI
5. Create, pack, and publish a `.cgp` package
6. Verify the package appears in the registry and on GitHub
7. Install the package from the registry
8. Verify the notary checksum

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Go 1.25+** | To build CPM from source |
| **SSH keygen** | Part of OpenSSH (standard on Linux/macOS) |
| **GitHub account** | For Web UI login and package ownership |
| **Internet access** | Registry at `registry-us-all-distros-official.cognitive-os.org` |

## Architecture

```
Publisher (CPM)              Registry (Cloud Run)             GitHub Org Releases         S3 (R2)
     │                             │                              │                        │
     │  1. SSH sign profile        │                              │                        │
     │  2. signup ────────────────►│                              │                        │
     │                             │                              │                        │
     │  3. login ─────────────────►│  (verify key registered)     │                        │
     │                             │                              │                        │
     │  ... owner claims key in Web UI ...                        │                        │
     │                             │                              │                        │
     │  4. init → pack → publish   │                              │                        │
     │  5. multipart POST ────────►│                              │                        │
     │     (metadata + .cgp)       ├── create release ───────────►│                        │
     │                             ├── upload .cgp asset ────────►│                        │
     │                             ├── store metadata in S3 ─────────────────────────────►│
     │◄── { download_urls } ───────┤                              │                        │
```

## Step 1: Generate an SSH Key Pair

The registry uses SSH public key authentication. Generate a dedicated key pair:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cognitiveos -N "" -C "cognitiveos-publisher"
```

This creates:
- `~/.ssh/cognitiveos` — private key (used by CPM to sign)
- `~/.ssh/cognitiveos.pub` — public key (registered with the registry)

Verify the keys were created:

```bash
ls -la ~/.ssh/cognitiveos*
```

## Step 2: Build CPM

Clone and build CPM from source:

```bash
git clone git@github.com:CognitiveOS-Project/cpm.git
cd cpm
go build -o /usr/local/bin/cpm ./cmd/cpm.go
```

Verify:

```bash
cpm version
```

## Step 3: Sign Up (Machine Identity Profile)

`cpm auth signup` gathers your machine's hardware, software, and network profile, signs it with your SSH key, and sends it to the registry:

```bash
cpm auth signup --key ~/.ssh/cognitiveos
```

**What this does:**
1. Reads hardware info (CPU, RAM, GPU, TPM, machine ID)
2. Reads software info (OS, kernel, distro, packages)
3. Reads network info (IP address)
4. Signs the profile JSON with your SSH private key
5. Sends the signed profile + public key to `POST /v1/auth/signup`

**Expected output:**

```
Signup submitted
  Machine ID: <fingerprint-hash>
  Status:     pending
```

The `pending` status means your machine identity is registered but awaiting owner claim (Step 5). You cannot publish until an owner claims your key.

## Step 4: Login (Local Auth State)

`cpm auth login` stores your key path locally and verifies registration with the server:

```bash
cpm auth login --key ~/.ssh/cognitiveos
```

**What this does:**
1. Loads the private key and computes its fingerprint
2. Calls `PUT /v1/auth/status` to verify the key is registered
3. Saves the key path and fingerprint to `~/.cpm/auth.json`

**Expected output:**

```
Logged in
  Key:        /home/user/.ssh/cognitiveos
  Fingerprint: SHA256:...
  Status:     registered
  Registered: 2026-07-23T...
```

After login, `cpm publish` automatically uses this key without needing `--key` on every invocation.

## Step 5: Claim Key in Web UI (Owner Claim)

**This step is required.** The registry blocks publishing until an owner claims the key. This ensures every publisher is accountable to a verified human.

1. Open the registry Web UI:
   ```
   https://registry-us-all-distros-official.cognitive-os.org/ui/login
   ```

2. Click **Login with GitHub** and authorize the CognitiveOS Registry app

3. On the dashboard, you'll see your registered key (identified by fingerprint)

4. **Add a display name** for the key (e.g., "My Development Machine")

5. **Grant publish permission** — toggle the publish permission switch to enabled

6. The key status changes from `pending` to `active` with publish permission granted

**What this does on the server:**
- Links the SSH key fingerprint to your GitHub identity (owner)
- Sets `status: active` and `publish_permission: true` on the key
- From now on, `cpm publish` from this machine will pass the three publish gates:
  - `KEY_NOT_CLAIMED` → **PASS** (key is linked to owner)
  - `KEY_REVOKED` → **PASS** (key is active)
  - `PUBLISH_NOT_AUTHORIZED` → **PASS** (owner granted publish permission)

## Step 6: Create and Pack a Package

### 6a. Initialize a package skeleton

```bash
mkdir /tmp/test-publish && cd /tmp/test-publish
cpm init my-test-skill
```

This creates:

```
my-test-skill/
├── cognitive.json              # Package manifest
├── prompts/
│   ├── system.md               # System prompt
│   └── templates/
├── tools/                      # MCP server binaries (optional)
├── .github/
│   ├── docker/
│   │   └── Dockerfile.ci       # CI build (Alpine via QEMU)
│   └── workflows/
│       ├── ci.yml              # Build + verify on push
│       └── publish.yml         # Tag → GitHub Release
└── README.md
```

### 6b. Review the manifest

```bash
cat my-test-skill/cognitive.json
```

The manifest defines your package metadata:

```json
{
  "name": "my-test-skill",
  "version": "0.1.0",
  "description": "A CognitiveOS skill package",
  "author": "Your Name",
  "license": "MIT",
  "hardware_requirements": {
    "min_ram_mb": 128,
    "min_storage_mb": 50
  }
}
```

Edit `cognitive.json` to customize the description, author, and other fields.

### 6c. Pack into a .cgp archive

```bash
cd my-test-skill
cpm pack
```

**Expected output:**

```
✓ Packaged manifest as my-test-skill-0.1.0-universal.cgp
```

The `.cgp` file is a gzip-compressed tar archive containing `cognitive.json` and any referenced files.

**Naming convention:**
- No hardware requirements → `name-version-universal.cgp`
- With OS/arch → `name-version-os-arch.cgp` (e.g., `my-test-skill-0.1.0-linux-amd64.cgp`)

## Step 7: Publish to the Official Registry

### 7a. Official publish (recommended for packages under 32 MB)

```bash
cpm publish ./my-test-skill-0.1.0-universal.cgp
```

CPM automatically resolves the key from `~/.cpm/auth.json` (no `--key` flag needed after login).

**Expected output:**

```
Published my-test-skill v0.1.0 (ssh:SHA256:...)
```

**What happens internally:**

1. CPM reads the manifest from the `.cgp` archive
2. CPM marshals the manifest to JSON and computes SHA-256
3. CPM signs the hash with your SSH private key
4. CPM sends a `multipart/form-data` POST to `POST /v1/patches` with:
   - `metadata` part: JSON with name, version, manifest, etc.
   - `cgp` part: the raw `.cgp` binary
   - Headers: `X-SSH-Fingerprint`, `X-SSH-Signature`
5. Registry server verifies the SSH signature against your registered public key
6. Registry creates a GitHub Release on `CognitiveOS-CGP-Packages/my-test-skill`
7. Registry uploads the `.cgp` as a release asset
8. Registry stores manifest + checksum in S3 (notary)
9. Registry returns 201 with download URL

### 7b. Notary proxy publish (for packages over 32 MB or self-hosted)

If your `.cgp` exceeds 32 MB (e.g., includes model weights), host it externally and register only metadata:

```bash
cpm publish ./my-large-package-1.0.0.cgp \
  --download-url https://github.com/your-org/repo/releases/download/v1.0.0/my-large-package-1.0.0.cgp
```

The registry stores the metadata and redirects consumers to your hosted URL.

## Step 8: Verify

### 8a. Check registry metadata

```bash
curl -s https://registry-us-all-distros-official.cognitive-os.org/v1/patches/my-test-skill | python3 -m json.tool
```

Expected response:

```json
{
  "name": "my-test-skill",
  "version": "0.1.0",
  "description": "A CognitiveOS skill package",
  "download_urls": {
    "": "https://github.com/CognitiveOS-CGP-Packages/my-test-skill/releases/download/v0.1.0/my-test-skill-0.1.0.cgp"
  }
}
```

### 8b. Check GitHub Releases

```bash
gh release list -R CognitiveOS-CGP-Packages/my-test-skill
```

Or open in browser:
```
https://github.com/CognitiveOS-CGP-Packages/my-test-skill/releases
```

You should see a release tagged `v0.1.0` with the `.cgp` asset.

### 8c. Search the registry

```bash
cpm search my-test-skill
```

### 8d. Check notary checksum

```bash
curl -s "https://registry-us-all-distros-official.cognitive-os.org/v1/notary/check?source=cpm&path=my-test-skill&version=0.1.0" | python3 -m json.tool
```

Expected response:

```json
{
  "name": "my-test-skill",
  "version": "0.1.0",
  "verified": false,
  "stored_hash": "aaaa...",
  "remote_hash": "",
  "remote_etag": "",
  "checked_at": "2026-07-23T..."
}
```

The `stored_hash` is the SHA-256 the registry recorded. `verified: false` means the remote server (GitHub) wasn't reachable for HEAD verification — this is normal for GitHub Releases (they don't support HEAD with content hashes).

## Step 9: Install from Registry

```bash
cd /tmp
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm install my-test-skill@0.1.0
```

This:
1. Resolves `my-test-skill@0.1.0` from the registry
2. Follows the download redirect to GitHub Releases
3. Downloads the `.cgp` archive
4. Extracts to `CPM_PATCHES_DIR/my-test-skill/`

### Verify installation

```bash
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm list
CPM_PATCHES_DIR=/tmp/cpm-test/patches cpm info my-test-skill
```

## Step 10: Clean Up

Remove the test package from the registry (requires admin access):

```bash
# Or just leave it — it's a public package on GitHub
```

Remove local test files:

```bash
rm -rf /tmp/test-publish /tmp/cpm-test
```

## Troubleshooting

### "no SSH key found" error

CPM couldn't find a key. Solutions:
- Run `cpm auth login --key ~/.ssh/cognitiveos` to store the key path
- Or pass `--key ~/.ssh/cognitiveos` explicitly to `cpm publish`

### "KEY_NOT_CLAIMED" error (403)

Your SSH key is registered but no owner has claimed it in the Web UI:
1. Go to `https://registry-us-all-distros-official.cognitive-os.org/ui/login`
2. Log in with GitHub
3. Find your key and grant publish permission

### "KEY_REVOKED" error (403)

Your key was revoked by the owner. Re-register with a new key:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/cognitiveos-new -N ""
cpm auth signup --key ~/.ssh/cognitiveos-new
cpm auth login --key ~/.ssh/cognitiveos-new
```

Then claim the new key in the Web UI.

### "PUBLISH_NOT_AUTHORIZED" error (403)

Your key is claimed but publish permission wasn't granted:
1. Go to the Web UI dashboard
2. Find your key
3. Toggle publish permission to enabled

### "VALIDATION_FAILED" error (422)

The manifest failed validation. Check:
- `name` and `version` are present in `cognitive.json`
- `sha256` is 64 hex characters
- `download_urls` (if provided) are valid URLs

### ".cgp exceeds 32 MB" error (P012)

Your package is too large for official hosting. Use notary proxy mode:
```bash
cpm publish ./large-package.cgp --download-url https://your-host/package.cgp
```

Or install directly via UPR:
```bash
cpm install ghr:your-org/your-repo@v1.0.0
```

### Registry unreachable

The registry runs on Cloud Run with `min-instances=0` (scales to zero). First requests may take a few seconds while the instance spins up. If it persists, check:
```bash
curl -s https://registry-us-all-distros-official.cognitive-os.org/v1/health
```

## Reference

### Auth Commands

| Command | Description |
|---------|-------------|
| `cpm auth signup --key <path>` | Register machine identity profile |
| `cpm auth login --key <path>` | Store key locally, verify with server |
| `cpm auth logout` | Clear local auth state |
| `cpm auth register --key <path>` | Register SSH public key only (no profile) |

### Publish Flags

| Flag | Description |
|------|-------------|
| `--key <path>` | SSH private key (default: `~/.ssh/id_ed25519`, or from `auth.json`) |
| `--download-url <url>` | Notary proxy mode (metadata only, .cgp hosted externally) |
| `--tag <name>` | Add tag (repeatable) |
| `--scope <name>` | Package scope |
| `--visibility <val>` | `public` (default) or `private` |

### Registry Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Health check |
| `GET` | `/v1/search?q=` | Search packages |
| `GET` | `/v1/patches/{name}` | Get package metadata |
| `GET` | `/v1/patches/{name}/{version}` | Get specific version |
| `GET` | `/v1/patches/{name}/versions` | List all versions |
| `GET` | `/v1/patches/{name}/dependencies` | Dependency tree |
| `GET` | `/v1/notary/check?path=&version=` | Check notary checksum |
| `POST` | `/v1/patches` | Publish package |
| `POST` | `/v1/auth/register` | Register SSH public key |
| `PUT` | `/v1/auth/status` | Check key registration status |
| `POST` | `/v1/auth/signup` | Submit machine identity profile |
| `POST` | `/v1/patches/{name}/{version}/unlock` | Verify unlock code |
