#!/usr/bin/env bash
# Create StorefrontStyle and ThemePackage on DynamoDB Local.
# Schema: ../../DDB_Schema.md (repo root)
#
# Usage:
#   docker compose up -d dynamodb-local
#   ./scripts/dynamodb-local-create-tables.sh
#
# Requires: aws CLI v2, curl (for optional wait), docker compose (for wait)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESIGN_STUDIO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENDPOINT="${DYNAMODB_ENDPOINT:-http://127.0.0.1:8001}"
REGION="${AWS_REGION:-eu-north-1}"
STYLE_TABLE="${DYNAMODB_STYLE_TABLE:-StorefrontStyle}"
PACKAGE_TABLE="${DYNAMODB_THEME_PACKAGE_TABLE:-ThemePackage}"

export AWS_ACCESS_KEY_ID="${DYNAMODB_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${DYNAMODB_SECRET_ACCESS_KEY:-local}"

aws_cmd() {
  aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"
}

wait_for_dynamodb() {
  local max_attempts="30"
  local attempt=0
  echo "Waiting for DynamoDB Local at ${ENDPOINT}..."
  while [ "$attempt" -lt "$max_attempts" ]; do
    # DynamoDB Local returns HTTP 400 on a bare GET — that means it is up.
    code="$(curl -s -o /dev/null -I -w '%{http_code}' "${ENDPOINT}" 2>/dev/null || true)"
    if [ "$code" = "400" ]; then
      echo "DynamoDB Local is ready."
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  echo "ERROR: DynamoDB Local did not become ready at ${ENDPOINT}" >&2
  echo "Start it with: cd ${DESIGN_STUDIO_DIR} && docker compose up -d dynamodb-local" >&2
  exit 1
}

table_exists() {
  aws_cmd dynamodb describe-table --table-name "$1" >/dev/null 2>&1
}

create_style_table() {
  if table_exists "$STYLE_TABLE"; then
    echo "Table ${STYLE_TABLE} already exists — skipping"
    return 0
  fi

  echo "Creating table ${STYLE_TABLE}..."
  aws_cmd dynamodb create-table \
    --table-name "$STYLE_TABLE" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
      AttributeName=type,AttributeType=S \
      AttributeName=updatedAt,AttributeType=S \
      AttributeName=previewToken,AttributeType=S \
    --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
    --global-secondary-indexes \
      "[
        {
          \"IndexName\": \"type-updatedAt-index\",
          \"KeySchema\": [
            {\"AttributeName\": \"type\", \"KeyType\": \"HASH\"},
            {\"AttributeName\": \"updatedAt\", \"KeyType\": \"RANGE\"}
          ],
          \"Projection\": {\"ProjectionType\": \"ALL\"}
        },
        {
          \"IndexName\": \"previewToken-index\",
          \"KeySchema\": [
            {\"AttributeName\": \"previewToken\", \"KeyType\": \"HASH\"}
          ],
          \"Projection\": {\"ProjectionType\": \"ALL\"}
        }
      ]"

  aws_cmd dynamodb wait table-exists --table-name "$STYLE_TABLE"

  # Native TTL on preview items (CF-12). Local DynamoDB supports TTL.
  aws_cmd dynamodb update-time-to-live \
    --table-name "$STYLE_TABLE" \
    --time-to-live-specification "Enabled=true, AttributeName=ttl" \
    2>/dev/null || echo "Note: TTL on ${STYLE_TABLE} may not be supported on this DynamoDB Local build — skipping."

  echo "Created ${STYLE_TABLE}"
}

create_theme_package_table() {
  if table_exists "$PACKAGE_TABLE"; then
    echo "Table ${PACKAGE_TABLE} already exists — skipping"
    return 0
  fi

  echo "Creating table ${PACKAGE_TABLE}..."
  aws_cmd dynamodb create-table \
    --table-name "$PACKAGE_TABLE" \
    --billing-mode PAY_PER_REQUEST \
    --attribute-definitions \
      AttributeName=packageId,AttributeType=S \
    --key-schema \
      AttributeName=packageId,KeyType=HASH

  aws_cmd dynamodb wait table-exists --table-name "$PACKAGE_TABLE"
  echo "Created ${PACKAGE_TABLE}"
}

main() {
  if ! command -v aws >/dev/null 2>&1; then
    echo "ERROR: aws CLI is required. Install AWS CLI v2." >&2
    exit 1
  fi

  wait_for_dynamodb

  create_style_table
  create_theme_package_table

  echo ""
  echo "Done. Tables at ${ENDPOINT}:"
  aws_cmd dynamodb list-tables --output text
  echo ""
  echo "Use on the host:"
  echo "  export DYNAMODB_ENDPOINT=${ENDPOINT}"
  echo "  export AWS_REGION=${REGION}"
  echo "  export DYNAMODB_STYLE_TABLE=${STYLE_TABLE}"
  echo "  export DYNAMODB_THEME_PACKAGE_TABLE=${PACKAGE_TABLE}"
}

main "$@"
