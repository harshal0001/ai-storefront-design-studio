# data.tf — references to shared infrastructure that already exists.
# These resources are NOT managed by RAP OpenTofu — they are read-only references.
# Do NOT import them into state or add lifecycle rules here.

# ── Shared S3 state bucket (RAP-dedicated, created by bootstrap) ──────────────
# Lifecycle prevent_destroy is enforced via the bucket resource in bootstrap.
# Referenced here so modules can use data.aws_s3_bucket.rap_state.bucket.
data "aws_s3_bucket" "rap_state" {
  bucket = "s3-${var.target_account_id}-statefilebucket-rap"
}

# ── Shared DynamoDB state lock table ─────────────────────────────────────────
# Shared with other projects in this account — do not destroy.
data "aws_dynamodb_table" "state_lock" {
  name = "terraform-state-lock"
}

# ── Shared IAM roles ──────────────────────────────────────────────────────────
# CrossAccountRole and BitbucketOIDCRole are shared across all projects.
# RAP only adds its trust entries via the bootstrap script — never owns these roles.

data "aws_iam_role" "cross_account" {
  name = "CrossAccountRole"
}

data "aws_iam_role" "bitbucket_oidc" {
  provider = aws.mgmt
  name     = "BitbucketOIDCRole"
}
