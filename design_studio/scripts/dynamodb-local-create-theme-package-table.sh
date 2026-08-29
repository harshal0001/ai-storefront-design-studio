#!/usr/bin/env bash
# Create only ThemePackage on DynamoDB Local.
# Schema: ../../DDB_Schema.md — Table 2
#
# Usage:
#   source ../../example.env   # optional
#   ./scripts/dynamodb-local-create-theme-package-table.sh

set -euo pipefail

ENDPOINT="${DYNAMODB_ENDPOINT:-http://127.0.0.1:8001}"
REGION="${AWS_REGION:-eu-north-1}"
PACKAGE_TABLE="${DYNAMODB_THEME_PACKAGE_TABLE:-ThemePackage}"

export AWS_ACCESS_KEY_ID="${DYNAMODB_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${DYNAMODB_SECRET_ACCESS_KEY:-local}"

aws_cmd() {
  aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"
}

if aws_cmd dynamodb describe-table --table-name "$PACKAGE_TABLE" >/dev/null 2>&1; then
  echo "Table ${PACKAGE_TABLE} already exists."
  exit 0
fi

echo "Creating table ${PACKAGE_TABLE} at ${ENDPOINT}..."
aws_cmd dynamodb create-table \
  --table-name "$PACKAGE_TABLE" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=packageId,AttributeType=S \
  --key-schema AttributeName=packageId,KeyType=HASH

aws_cmd dynamodb wait table-exists --table-name "$PACKAGE_TABLE"
echo "Created ${PACKAGE_TABLE}."
