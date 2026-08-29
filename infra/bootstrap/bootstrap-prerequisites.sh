#!/usr/bin/env bash
# bootstrap-prerequisites.sh
# Bootstraps all prerequisites for the RAP sandbox deployment.
# All operations run in the SANDBOX account only.
#
# Modes:
#   --local    : uses AWS CLI profile (Sandbox_non_prod)
#   --pipeline : uses env vars injected by the pipeline (AWS_ACCESS_KEY_ID etc.)
#
# Usage (local):
#   aws sso login --sso-session <your-sso-session>
#   bash infra/bootstrap/bootstrap-prerequisites.sh --local
#
# Usage (pipeline):
#   Called automatically by bootstrap-sandbox-prerequisites pipeline
#
# NOTE: Before running this for the first time, patch BitbucketOIDCRole manually
#   in the management account to allow assuming CrossAccountRole in sandbox.
#   See infra/README.md — Prerequisites section for the exact command.
set -eo pipefail

MODE="${1:---local}"

SBX_ACCOUNT_ID="111111111111"
MGMT_ACCOUNT_ID="222222222222"
REGION_BACKEND="eu-south-1"
DYNAMODB_TABLE="terraform-state-lock"
STATE_BUCKET="s3-${SBX_ACCOUNT_ID}-statefilebucket-rap"
RAP_TAG_KEY="project-name"
RAP_TAG_VALUE="storefront-design-studio"

# ── Credential helper — sandbox only ─────────────────────────────────────────
sbx() {
  if [[ "${MODE}" == "--local" ]]; then
    aws --profile Sandbox_non_prod "$@"
  else
    aws "$@"
  fi
}

echo "================================================"
echo " RAP Bootstrap Prerequisites  [mode: ${MODE}]"
echo " Sandbox : ${SBX_ACCOUNT_ID}"
echo "================================================"

# ── 1. S3 State Bucket — managed via OpenTofu with prevent_destroy ────────────
# Bootstrap state is stored in the SHARED bucket (not the RAP one being created).
echo ""
echo "[1/3] S3 state bucket: ${STATE_BUCKET}"
BOOTSTRAP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${BOOTSTRAP_DIR}"

if [[ "${MODE}" == "--local" ]]; then
  export AWS_PROFILE=Sandbox_non_prod
fi

SHARED_BUCKET="s3-${SBX_ACCOUNT_ID}-statefilebucket"
BOOTSTRAP_STATE_KEY="infra/bootstrap/terraform.tfstate"

tofu init -reconfigure -input=false \
  -backend-config="bucket=${SHARED_BUCKET}" \
  -backend-config="key=${BOOTSTRAP_STATE_KEY}" \
  -backend-config="region=${REGION_BACKEND}" \
  -backend-config="dynamodb_table=${DYNAMODB_TABLE}" \
  -backend-config="encrypt=true"

tofu apply -input=false -auto-approve \
  -var="sbx_account_id=${SBX_ACCOUNT_ID}"

cd - > /dev/null
echo "      DONE — bucket managed by OpenTofu with prevent_destroy"

# ── 2. DynamoDB Lock Table ────────────────────────────────────────────────────
echo ""
echo "[2/3] Checking DynamoDB table: ${DYNAMODB_TABLE}"
if sbx dynamodb describe-table \
    --table-name "${DYNAMODB_TABLE}" \
    --region "${REGION_BACKEND}" 2>/dev/null | grep -q "ACTIVE"; then
  echo "      SKIP — already exists and ACTIVE"
else
  echo "      Creating..."
  sbx dynamodb create-table \
    --table-name "${DYNAMODB_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION_BACKEND}" \
    --tags \
      "Key=project,Value=RAP" \
      "Key=${RAP_TAG_KEY},Value=${RAP_TAG_VALUE}" \
      "Key=managed-by,Value=bootstrap-script"

  echo "      Waiting for ACTIVE..."
  sbx dynamodb wait table-exists \
    --table-name "${DYNAMODB_TABLE}" \
    --region "${REGION_BACKEND}"

  echo "      DONE"
fi

# ── 3. CrossAccountRole trust policy — add BitbucketOIDCRole from mgmt ───────
echo ""
echo "[3/4] Checking CrossAccountRole trust policy in sandbox"
TRUST=$(sbx iam get-role \
  --role-name CrossAccountRole \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json)

if echo "${TRUST}" | grep -q "${MGMT_ACCOUNT_ID}:role/BitbucketOIDCRole"; then
  echo "      SKIP — BitbucketOIDCRole already trusted"
else
  echo "      Adding arn:aws:iam::${MGMT_ACCOUNT_ID}:role/BitbucketOIDCRole..."
  NEW_TRUST=$(echo "${TRUST}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
new_principal = 'arn:aws:iam::${MGMT_ACCOUNT_ID}:role/BitbucketOIDCRole'
stmt = d['Statement'][0]
principals = stmt['Principal']['AWS']
if isinstance(principals, str):
    principals = [principals]
if new_principal not in principals:
    principals.append(new_principal)
stmt['Principal']['AWS'] = principals
print(json.dumps(d))
")
  sbx iam update-assume-role-policy \
    --role-name CrossAccountRole \
    --policy-document "${NEW_TRUST}"
  echo "      DONE"
fi

# ── 4. CrossAccountRole inline policy — ECR, IAM, AgentCore permissions ──────
echo ""
echo "[4/4] Checking CrossAccountRole RAP permissions (ECR, IAM, AgentCore)"
if sbx iam get-role-policy \
    --role-name CrossAccountRole \
    --policy-name rap-ecr-agentcore-policy 2>/dev/null | grep -q "ECRFullAccess"; then
  echo "      SKIP — rap-ecr-agentcore-policy already exists"
else
  echo "      Adding rap-ecr-agentcore-policy..."
  sbx iam put-role-policy \
    --role-name CrossAccountRole \
    --policy-name rap-ecr-agentcore-policy \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "ECRFullAccess",
          "Effect": "Allow",
          "Action": "ecr:*",
          "Resource": "*"
        },
        {
          "Sid": "IAMForAgentCore",
          "Effect": "Allow",
          "Action": [
            "iam:CreateRole",
            "iam:DeleteRole",
            "iam:GetRole",
            "iam:PutRolePolicy",
            "iam:DeleteRolePolicy",
            "iam:GetRolePolicy",
            "iam:ListRolePolicies",
            "iam:AttachRolePolicy",
            "iam:DetachRolePolicy",
            "iam:ListAttachedRolePolicies",
            "iam:TagRole",
            "iam:UntagRole",
            "iam:PassRole"
          ],
          "Resource": "arn:aws:iam::111111111111:role/role-rap-*"
        },
        {
          "Sid": "AgentCoreFullAccess",
          "Effect": "Allow",
          "Action": "bedrock-agentcore:*",
          "Resource": "*"
        }
      ]
    }'
  echo "      DONE"
fi

echo ""
echo "================================================"
echo " Bootstrap complete."
echo "  [1] S3 bucket    : ${STATE_BUCKET} (${REGION_BACKEND}) — prevent_destroy ON"
echo "  [2] DynamoDB     : ${DYNAMODB_TABLE} (${REGION_BACKEND})"
echo "  [3] CrossAccount : trust updated with BitbucketOIDCRole"
echo "  [4] CrossAccount : RAP permissions (ECR, IAM, AgentCore)"
echo "================================================"
