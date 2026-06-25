# chainlink-CRE_PY_toolkit

Python-first toolkit for working with **Chainlink CRE** and for migrating older **Chainlink Functions** projects.

The short idea: you write simple Python commands, and this toolkit helps generate CRE workflow projects, configs, secrets files, receiver contracts, and CLI commands.

## What You Can Do

### CRE Tools

- Create CRE project structure
- Generate hello-world workflows
- Generate scheduled HTTP JSON workflows
- Generate Solidity receiver templates
- Create secrets YAML files
- Create delete-secrets YAML files
- Run workflow simulation
- Build workflow WASM
- Hash workflow artifacts
- Deploy workflows
- Activate workflows
- Pause workflows
- Delete workflows
- List/get deployed workflows
- List supported CRE chains
- Create/update/delete/list CRE Vault secrets
- Scaffold a CRE migration project from an old Chainlink Functions request

### Legacy Chainlink Functions Tools

These are kept for migration, cleanup and old projects:

- Encrypt DON-hosted secrets
- Upload encrypted secrets to the Functions DON
- List DON-hosted secrets slots and versions
- Build old Functions CBOR request payloads
- Decode old Functions response bytes
- Fetch request commitments
- Listen for old Functions responses
- Timeout expired requests
- Manage old Functions subscriptions
- Create/delete GitHub Gists for old offchain storage flows

## Install

Clone the repository:

```bash
git clone https://github.com/<your-username>/chainlink-CRE_PY_toolkit.git
cd chainlink-CRE_PY_toolkit
```

Create a Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -U pip
pip install -r requirements.txt
pip install -r requirements-encrypt.txt
```

Install CRE requirements separately:

```bash
cre whoami      # if this fails, run: cre login
bun --version   # if this fails, install Bun
```

If Bun is missing:

```bash
curl -fsSL https://bun.sh/install | bash
source ~/.zshrc
```

## Environment Files

The root project has:

```text
.env.example
```

Copy it when you need local secrets:

```bash
cp .env.example .env
```

Never commit `.env`.

For generated CRE projects, the toolkit creates both:

```text
my-cre-project/.env
my-cre-project/.env.example
```

Fill the generated `.env` before simulation/deployment:

```bash
CRE_ETH_PRIVATE_KEY=YOUR_PRIVATE_KEY_WITHOUT_0x
ETHEREUM_SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
ETHEREUM_MAINNET_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
```

Note: `CRE_ETH_PRIVATE_KEY` should be a raw 64-character private key without `0x`.

## Quick Start: Create a CRE Project

Create a new CRE project:

```bash
python cre_toolkit.py --project demo-cre create
```

This creates:

```text
demo-cre/
├── .env
├── .env.example
├── .gitignore
├── project.yaml
└── secrets.yaml
```

`project.yaml` contains CRE targets and RPC configuration. `secrets.yaml` is used for CRE Vault secrets.

## Add a Hello World Workflow

Generate a simple cron-based workflow:

```bash
python cre_toolkit.py --project demo-cre add-hello hello --overwrite
```

This creates:

```text
demo-cre/hello/
├── main.ts
├── workflow.yaml
├── config.staging.json
├── config.production.json
├── package.json
├── tsconfig.json
└── README.md
```

What it does:

- creates a TypeScript CRE workflow
- adds a cron trigger
- logs `Hello world! Workflow triggered.`
- returns `"Hello world!"` during simulation

Install workflow dependencies:

```bash
cd demo-cre/hello
bun install
cd ..
```

Simulate it:

```bash
cre workflow simulate hello --target staging-settings
```

If the simulation prints `"Hello world!"`, your CRE setup is working.

## Add an HTTP JSON Workflow

Generate a workflow that fetches an API on a schedule:

```bash
python cre_toolkit.py --project demo-cre add-http-json eth-usd \
  --schedule "*/30 * * * * *" \
  --url "https://api.example.com/eth-usd" \
  --json-path "price" \
  --result-type uint256 \
  --overwrite
```

What it does:

- creates a CRE workflow named `eth-usd`
- runs every 30 seconds in simulation
- fetches JSON from the configured URL
- reads `price` from the response
- prepares a typed result

Generated workflow files live here:

```text
demo-cre/eth-usd/
```

Install deps and simulate:

```bash
cd demo-cre/eth-usd
bun install
cd ..
cre workflow simulate eth-usd --target staging-settings
```

## Generate a Solidity Receiver

CRE reports are delivered to receiver-style contracts.

Generate a basic receiver:

```bash
python cre_toolkit.py --project demo-cre receiver --overwrite
```

This creates:

```text
demo-cre/contracts/CREReceiver.sol
```

What it does:

- creates a simple `IReceiver` interface
- stores the latest metadata and payload
- emits `ReportReceived`

You can use this as a starting point and customize validation/access control for your own app.

## Manage CRE Secrets Files

Create a secrets mapping file:

```bash
python cre_toolkit.py --project demo-cre secrets-write API_KEY=API_KEY
```

This writes:

```text
demo-cre/secrets.yaml
```

The format maps CRE secret identifiers to local environment variable names.

Create a delete-secrets file:

```bash
python cre_toolkit.py --project demo-cre secrets-write-delete API_KEY
```

This writes:

```text
demo-cre/secrets-to-delete.yaml
```

Upload secrets to CRE Vault:

```bash
cd demo-cre
cre secrets create secrets.yaml --target production-settings
```

Update secrets:

```bash
cre secrets update secrets.yaml --target production-settings
```

List secrets:

```bash
cre secrets list --target production-settings --output json
```

Delete secrets:

```bash
cre secrets delete secrets-to-delete.yaml --target production-settings
```

For private registry/browser auth flows, use:

```bash
cre secrets create secrets.yaml --target staging-settings --secrets-auth browser
```

## CRE Workflow Lifecycle

From inside the generated CRE project:

```bash
cd demo-cre
```

Build:

```bash
cre workflow build hello --target staging-settings
```

Simulate:

```bash
cre workflow simulate hello --target staging-settings
```

Hash:

```bash
cre workflow hash hello --target staging-settings --output json
```

Deploy:

```bash
cre workflow deploy hello --target production-settings
```

Activate:

```bash
cre workflow activate hello --target production-settings
```

Pause:

```bash
cre workflow pause hello --target production-settings
```

Update:

```bash
cre workflow deploy hello --target production-settings
```

In CRE, updating means deploying again with the same workflow name and target.

Delete:

```bash
cre workflow delete hello --target production-settings
```

List workflows:

```bash
cre workflow list --output json
```

Get workflow metadata:

```bash
cre workflow get hello --target production-settings --output json
```

List supported chains:

```bash
cre workflow supported-chains --output json
```

## Use It From Python

You can use the toolkit as a library:

```python
from lib.cre import CREProject

project = CREProject("price-feed")
project.create()

workflow = project.add_http_json_workflow(
    "eth-usd",
    schedule="*/30 * * * * *",
    url="https://api.example.com/eth-usd",
    json_path="price",
    result_type="uint256",
    overwrite=True,
)

project.write_receiver_template(overwrite=True)
project.simulate(workflow, target="staging-settings")
```

Use the lower-level CLI wrapper:

```python
from lib.cre import CRECLI

cre = CRECLI(cwd="demo-cre")
cre.workflow_simulate("hello", target="staging-settings")
cre.workflow_deploy("hello", target="production-settings")
```

## Migrate From Chainlink Functions

If you have old Chainlink Functions code, you can scaffold a CRE migration project:

```bash
python - <<'PY'
from lib.cre import scaffold_from_functions_request

migration = scaffold_from_functions_request(
    project_name="migrated-functions-app",
    workflow_name="legacy-flow",
    source="return Functions.encodeUint256(1);",
    args=["1"],
    secrets={"API_KEY": "API_KEY"},
    overwrite=True,
)

print(migration.project.root)
print(migration.workflow.path)
print(migration.notes_path)
PY
```

This creates:

- a CRE project
- a starter workflow
- `MIGRATION.md`
- a receiver contract
- a secrets mapping file

Important: arbitrary old inline Functions JavaScript cannot be perfectly converted automatically. The scaffold gives you the structure and notes so you can move the logic safely into CRE.

## Legacy Chainlink Functions Helpers

These are for existing/old Functions projects.

### Encrypt DON-hosted secrets

Create `secrets.json`:

```json
{
  "AUTHORIZATION": "Bearer <token>"
}
```

Run:

```bash
python encrypt_secrets.py --secrets-json secrets.json
```

This writes:

```text
enc_artifacts.encrypted_secrets.hex.txt
```

### Upload encrypted secrets to DON

```bash
python upload_don_secrets.py \
  --slot-id 1 \
  --encrypted-secrets-hex enc_artifacts.encrypted_secrets.hex.txt
```

### List DON slots and versions

```bash
python list_don_secrets.py --json
```

### Build old Functions CBOR request

```bash
python - <<'PY'
from lib import buildRequestCBOR, Location, CodeLanguage

payload = buildRequestCBOR({
    "codeLocation": Location.Inline,
    "codeLanguage": CodeLanguage.JavaScript,
    "source": "return Functions.encodeUint256(42n);",
    "args": ["42"],
})

print(payload)
PY
```

### Decode old Functions result

```bash
python - <<'PY'
from lib import decodeResult, ReturnType

raw = "0x" + (42).to_bytes(32, "big").hex()
print(decodeResult(raw, ReturnType.uint256))
PY
```

## Common Issues

### `bun: command not found`

Install Bun:

```bash
curl -fsSL https://bun.sh/install | bash
source ~/.zshrc
```

### `no RPC URLs found for target`

Check `project.yaml`. CRE expects target names at the top level:

```yaml
staging-settings:
  rpcs:
    -
      chain-name: "ethereum-testnet-sepolia"
      url: "https://ethereum-sepolia-rpc.publicnode.com"
```

### CRE uses default private key during simulation

Your generated CRE project has its own `.env`. Fill:

```text
demo-cre/.env
```

not only the root `.env`.

### Deployment access is not enabled

CRE deployment is Early Access. Run:

```bash
cre account access
```

Then wait for Chainlink to approve deployment access for your organization.

## Why This Exists

Chainlink Functions is being sunset and new projects should move to **Chainlink Runtime Environment (CRE)**.

CRE workflows are currently written in **TypeScript** or **Go**, but this toolkit gives you a Python-first workflow around CRE:

- generate CRE project files from Python
- generate TypeScript workflow templates
- generate `project.yaml`, `workflow.yaml`, configs and `.env.example`
- generate a simple Solidity receiver contract
- wrap common `cre workflow ...` commands
- wrap common `cre secrets ...` commands
- keep legacy Chainlink Functions helpers for migration and cleanup

Python stays your main developer experience. CRE still runs the generated TypeScript or Go workflow under the hood.

- ncrypted secrets
- build artifacts

## Support

If this project saved you time, a star on GitHub would mean a lot.

Also, I really love cookies. If you want to buy me one, I would be happy.

ETH tip jar:

```text
0x7cb23658373178282CD716A230e5dd4f63a8efAF
```
