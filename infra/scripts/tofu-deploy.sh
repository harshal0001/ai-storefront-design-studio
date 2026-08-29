#!/usr/bin/env bash
# tofu-deploy.sh
# Handles OIDC authentication and OpenTofu plan/apply/destroy for RAP sandbox.
#
# Usage:
#   bash infra/scripts/tofu-deploy.sh plan
#   bash infra/scripts/tofu-deploy.sh apply
#   bash infra/scripts/tofu-deploy.sh plan-destroy
#   bash infra/scripts/tofu-deploy.sh destroy
#
# Required env vars (sourced from generate-tfvars.sh):
#   SBX_ACCOUNT_ID, SBX_MGMT_ACCOUNT_ID, DEPLOY_REGION, BACKEND_REGION,
#   DYNAMODB_TABLE, STATE_BUCKET
set -euo pipefail

ACTION="${1:?usage: infra/scripts/tofu-deploy.sh plan|apply|plan-destroy|destroy}"

: "${SBX_ACCOUNT_ID:?missing SBX_ACCOUNT_ID}"
: "${SBX_MGMT_ACCOUNT_ID:?missing SBX_MGMT_ACCOUNT_ID}"
: "${DEPLOY_REGION:?missing DEPLOY_REGION}"
: "${BACKEND_REGION:?missing BACKEND_REGION}"
: "${DYNAMODB_TABLE:?missing DYNAMODB_TABLE}"
: "${STATE_BUCKET:?missing STATE_BUCKET}"

ENVIRONMENT="sandbox"
TERRAFORM_DIR="infra/tofu"
STATEFILE="${TERRAFORM_DIR}/${ENVIRONMENT}"

# ── OIDC authentication ───────────────────────────────────────────────────────
# Write the OIDC token to RAM-backed tmpfs (/dev/shm) so it never touches disk.
# Fall back to /tmp if /dev/shm is unavailable (e.g. macOS local runs).
if [ -n "${BITBUCKET_STEP_OIDC_TOKEN:-}" ]; then
  TOKEN_DIR=$([ -d /dev/shm ] && echo "/dev/shm" || echo "/tmp")
  OIDC_TOKEN_FILE=$(mktemp "${TOKEN_DIR}/oidc-token-XXXXXX")
  chmod 600 "${OIDC_TOKEN_FILE}"
  printf '%s' "${BITBUCKET_STEP_OIDC_TOKEN}" > "${OIDC_TOKEN_FILE}"

  # Clean up token file on any exit — success, error, or signal
  trap 'rm -f "${OIDC_TOKEN_FILE}"; unset BITBUCKET_STEP_OIDC_TOKEN' EXIT ERR INT TERM

  export AWS_WEB_IDENTITY_TOKEN_FILE="${OIDC_TOKEN_FILE}"
  export AWS_ROLE_ARN="arn:aws:iam::${SBX_MGMT_ACCOUNT_ID}:role/BitbucketOIDCRole"
  export AWS_DEFAULT_REGION="${DEPLOY_REGION}"
fi

# ── Assume CrossAccountRole in sandbox ───────────────────────────────────────
CREDS=$(aws sts assume-role \
  --role-arn "arn:aws:iam::${SBX_ACCOUNT_ID}:role/CrossAccountRole" \
  --role-session-name "bb-rap-sbx-${ACTION}-$(date +%s)" \
  --duration-seconds 3600 \
  --query 'Credentials' --output json)

export AWS_ACCESS_KEY_ID=$(echo "${CREDS}" | jq -r '.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo "${CREDS}" | jq -r '.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo "${CREDS}" | jq -r '.SessionToken')

# Unset OIDC vars immediately — assumed role creds are now active
unset AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN
unset CREDS

echo "================================================"
echo " Action      : ${ACTION}"
echo " Environment : ${ENVIRONMENT}"
echo " State bucket: ${STATE_BUCKET}"
echo " State key   : ${STATEFILE}/terraform.tfstate"
echo " Region      : ${DEPLOY_REGION}"
echo "================================================"

# ── OpenTofu init ─────────────────────────────────────────────────────────────
cd "${TERRAFORM_DIR}"

tofu init -reconfigure -input=false \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="key=${STATEFILE}/terraform.tfstate" \
  -backend-config="region=${BACKEND_REGION}" \
  -backend-config="dynamodb_table=${DYNAMODB_TABLE}" \
  -backend-config="encrypt=true"

export AWS_DEFAULT_REGION="${DEPLOY_REGION}"

# ── Actions ───────────────────────────────────────────────────────────────────
if [[ "${ACTION}" == "plan" ]]; then
  tofu plan -input=false -lock=false \
    -var-file="env_config/${ENVIRONMENT}.tfvars" \
    -var="target_account_id=${SBX_ACCOUNT_ID}" \
    -var="map_migrated=${MAP_MIGRATED}" \
    -out="tfplan-${ENVIRONMENT}.out"
  echo "Plan saved to tfplan-${ENVIRONMENT}.out"

elif [[ "${ACTION}" == "apply" ]]; then
  if [[ ! -f "tfplan-${ENVIRONMENT}.out" ]]; then
    echo "Plan file not found. Run 'plan' first." >&2
    exit 1
  fi
  tofu apply -input=false -auto-approve -lock=true "tfplan-${ENVIRONMENT}.out"
  echo "Apply completed successfully"

elif [[ "${ACTION}" == "plan-destroy" ]]; then
  tofu plan -destroy -input=false -lock=false \
    -var-file="env_config/${ENVIRONMENT}.tfvars" \
    -var="target_account_id=${SBX_ACCOUNT_ID}" \
    -var="map_migrated=${MAP_MIGRATED}" \
    -out="tfplan-destroy-${ENVIRONMENT}.out"
  echo "Destroy plan saved to tfplan-destroy-${ENVIRONMENT}.out"

elif [[ "${ACTION}" == "destroy" ]]; then
  if [[ ! -f "tfplan-destroy-${ENVIRONMENT}.out" ]]; then
    echo "Destroy plan file not found. Run 'plan-destroy' first." >&2
    exit 1
  fi
  tofu apply -input=false -auto-approve -lock=true "tfplan-destroy-${ENVIRONMENT}.out"
  echo "Destroy completed successfully"

else
  echo "Unknown action: ${ACTION}" >&2
  exit 1
fi
