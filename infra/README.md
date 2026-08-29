# Storefront Design Studio — Infrastructure

This directory contains the OpenTofu infrastructure for the `storefront-design-studio` sandbox deployment on AWS.

## Structure

```
infra/
├── bootstrap/
│   ├── main.tf                       # RAP S3 state bucket with prevent_destroy
│   └── bootstrap-prerequisites.sh   # One-time setup script (local or pipeline)
├── scripts/
│   └── tofu-deploy.sh               # OIDC auth + tofu init/plan/apply/destroy
└── tofu/
    ├── backend.tf                    # S3 remote state backend
    ├── provider.tf                   # AWS provider + mgmt alias
    ├── variables.tf                  # Input variable declarations (no defaults for account IDs)
    ├── locals.tf                     # common_tags and name_prefix
    ├── main.tf                       # Resource definitions
    ├── data.tf                       # Read-only references to shared resources
    ├── outputs.tf                    # Output values
    ├── .tflint.hcl                   # TFLint rules configuration
    └── env_config/
        ├── environments.properties   # Source of truth for all environment config
        ├── generate-tfvars.sh        # Generates sandbox.tfvars from environments.properties
        └── sandbox.tfvars            # Auto-generated — do not edit manually
```

---

## Prerequisites

Before the pipeline can run, the following must be in place in AWS and Bitbucket.

### What already exists (shared, do not recreate)

| Resource | Account | Notes |
|---|---|---|
| `s3-111111111111-statefilebucket` | Sandbox | Shared state bucket — used for bootstrap state only |
| `terraform-state-lock` | Sandbox | Shared DynamoDB lock table |
| `CrossAccountRole` | Sandbox | Shared IAM role |
| `BitbucketOIDCRole` | Mgmt sbx | Shared IAM role |
| OIDC provider | Mgmt sbx | Already registered for your Bitbucket workspace |

### What must be done manually ONCE (before first pipeline run)

These two steps cannot be automated in the pipeline — they are required
for the pipeline to authenticate at all.

**Step 1 — Patch `BitbucketOIDCRole` in mgmt account:**

Allow `BitbucketOIDCRole` to assume `CrossAccountRole` in the sandbox account.
Run from a machine with admin access to the mgmt account:

```bash
aws sso login --sso-session <your-sso-session>
bash infra/bootstrap/bootstrap-prerequisites.sh --local
```

Or manually via AWS CLI with the `Mgmt_sbx` profile — see `infra/bootstrap/bootstrap-prerequisites.sh` for the exact command.

**Step 2 — Patch `CrossAccountRole` trust policy in sandbox account:**

Allow `BitbucketOIDCRole` from mgmt to assume `CrossAccountRole` in sandbox.
Run from a machine with admin access to the sandbox account:

```bash
aws sso login --sso-session <your-sso-session>
bash infra/bootstrap/bootstrap-prerequisites.sh --local
```

> Both steps are handled by `bootstrap-prerequisites.sh --local`. The script is idempotent — safe to re-run.

### What the bootstrap pipeline does (after manual steps above)

Once the manual steps are done, run `bootstrap-sandbox-prerequisites` pipeline once:

| Step | Resource | Account | Notes |
|---|---|---|---|
| 1 | `s3-111111111111-statefilebucket-rap` | Sandbox | RAP-dedicated state bucket with `prevent_destroy` |
| 2 | `terraform-state-lock` | Sandbox | SKIP if already exists |
| 3 | `CrossAccountRole` trust policy | Sandbox | SKIP if `BitbucketOIDCRole` already trusted |

---

## Authentication Flow

```
Bitbucket Pipeline
      │
      │  OIDC token (JWT)
      ▼
BitbucketOIDCRole (Management Account: 222222222222)
      │
      │  sts:AssumeRole
      ▼
CrossAccountRole (Sandbox Account: 111111111111)
      │
      │  Deploy resources
      ▼
AWS Resources + S3 State (RAP bucket) + DynamoDB Lock
```

---

## Pipelines

The original CI configuration (Bitbucket Pipelines) is not included in this repository. It defined the following pipelines, which `infra/scripts/tofu-deploy.sh` still supports:

### Pull requests

Runs automatically on every PR that touches `infra/**` — no manual trigger:

| Step | Tool | Purpose |
|---|---|---|
| `Tofu fmt + validate` | `opentofu:1.8.8` | `tofu fmt -check` + `tofu validate` on `infra/tofu` and `infra/bootstrap` |
| `TFLint` | `tflint:v0.50.3` | Static analysis — naming, deprecated syntax, best practices |
| `Secrets Scan` | `trufflehog:latest` | Detects verified secrets/credentials accidentally committed |

### Custom pipelines

| Pipeline | Steps | When to run |
|---|---|---|
| `bootstrap-sandbox-prerequisites` | Creates RAP S3 bucket, patches `CrossAccountRole` trust | Once, after manual steps above |
| `deploy-sandbox-prototype` | Secrets scan → fmt+validate → tflint → plan → manual apply | Every deployment |
| `destroy-sandbox-prototype` | Plan-destroy → manual destroy | Teardown only |

---

## Configuration

All values are sourced from `env_config/environments.properties`.
`generate-tfvars.sh` reads this file and generates `sandbox.tfvars` at pipeline runtime.
No Bitbucket repository variables are required.

| Property | Value |
|---|---|
| `SBX_ACCOUNT_ID` | `111111111111` |
| `SBX_MGMT_ACCOUNT_ID` | `222222222222` |
| `DEPLOY_REGION` | `eu-north-1` |
| `BACKEND_REGION` | `eu-south-1` |
| `DYNAMODB_TABLE` | `terraform-state-lock` |
| `STATE_BUCKET` | `s3-111111111111-statefilebucket-rap` |

> `sandbox.tfvars` is auto-generated — do not edit it manually.
> The source of truth is `env_config/environments.properties`.

---

## Security

### OIDC token handling

The Bitbucket OIDC token is handled securely in `infra/scripts/tofu-deploy.sh`:

- Written to `/dev/shm` (RAM-backed tmpfs) via `mktemp` — never touches disk
- `chmod 600` applied before writing
- `trap ... EXIT ERR INT TERM` ensures cleanup on any exit — success, error, or signal
- `AWS_WEB_IDENTITY_TOKEN_FILE`, `AWS_ROLE_ARN` and `BITBUCKET_STEP_OIDC_TOKEN` are unset immediately after `sts assume-role` completes
- Raw credentials variables (`CREDS`) are unset after export

### Secrets scanning

`trufflehog` runs on every PR and before every deploy:
- `--only-verified` — only reports secrets confirmed active (no noise)
- `--fail` — pipeline fails immediately if a verified secret is found

---

## State Backend

| Setting | Value |
|---|---|
| S3 bucket | `s3-111111111111-statefilebucket-rap` |
| State key | `infra/tofu/sandbox/terraform.tfstate` |
| Bootstrap state key | `infra/bootstrap/terraform.tfstate` |
| Region | `eu-south-1` |
| Locking | DynamoDB `terraform-state-lock` |

> A dedicated RAP bucket isolates RAP state from other projects in the shared account.
> The bucket has `prevent_destroy = true` — it cannot be accidentally destroyed via OpenTofu.
> Bootstrap state is stored in the shared bucket `s3-111111111111-statefilebucket`.

---

## Shared Resources (data.tf)

The following resources are shared with other projects and are referenced as
read-only `data` sources in `data.tf`. They are **never managed by RAP OpenTofu**.

| Resource | Type | Account |
|---|---|---|
| `s3-111111111111-statefilebucket-rap` | `aws_s3_bucket` | Sandbox |
| `terraform-state-lock` | `aws_dynamodb_table` | Sandbox |
| `CrossAccountRole` | `aws_iam_role` | Sandbox |
| `BitbucketOIDCRole` | `aws_iam_role` | Mgmt sbx (via `mgmt` provider alias) |

---

## Tagging

All RAP resources are automatically tagged via `provider default_tags` in `provider.tf`.

| Tag | Value |
|---|---|
| `project` | `RAP` |
| `project-name` | `storefront-design-studio` |
| `environment` | `sandbox` |
| `managed-by` | `opentofu` |

Additional per-environment tags can be added via the `tags` variable in `sandbox.tfvars`.

---

## Naming Convention

All RAP-owned resources must follow: `<type>-rap-<environment>`

| Resource | Name |
|---|---|
| S3 state bucket | `s3-111111111111-statefilebucket-rap` |
| S3 app bucket | `s3-rap-sandbox` |
| VPC | `vpc-rap-sandbox` |
| EKS cluster | `eks-rap-sandbox` |
| Security group | `sg-rap-sandbox` |

Use `local.name_prefix` in `main.tf` — it resolves to `rap-<environment>` (e.g. `rap-sandbox`).

> Shared infrastructure (`CrossAccountRole`, `BitbucketOIDCRole`, `terraform-state-lock`)
> keeps its existing name as it is shared with other projects.
> RAP ownership of these is identified via tags only.

---

## Adding Resources

Add OpenTofu resources to `main.tf`. Use `local.name_prefix` for naming.
Tags are applied automatically via `provider default_tags` — no need to pass them explicitly.

```hcl
module "s3" {
  source      = "../../../awsinfra/modules/s3"
  bucket_name = "s3-${local.name_prefix}"
  environment = var.environment
}
```
