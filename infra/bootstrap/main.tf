terraform {
  required_version = "~> 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Bootstrap state is stored in the SHARED bucket (not the RAP-dedicated one).
  # The RAP bucket is what this config creates, so it cannot store its own state.
  # The shared bucket s3-<account_id>-statefilebucket already exists and is safe to use here.
  backend "s3" {}
}

provider "aws" {
  region = "eu-south-1"
}

variable "sbx_account_id" {
  description = "Sandbox AWS account ID"
  type        = string
  default     = "111111111111"
}

locals {
  bucket_name = "s3-${var.sbx_account_id}-statefilebucket-rap"
  tags = {
    project        = "RAP"
    project-name   = "storefront-design-studio"
    managed-by     = "opentofu"
    map-migrated   = "<map-migration-tag>"
  }
}

resource "aws_s3_bucket" "rap_state" {
  bucket = local.bucket_name
  tags   = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "rap_state" {
  bucket = aws_s3_bucket.rap_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rap_state" {
  bucket = aws_s3_bucket.rap_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "rap_state" {
  bucket                  = aws_s3_bucket.rap_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
