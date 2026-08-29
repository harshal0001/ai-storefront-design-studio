terraform {
  required_version = "~> 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# mgmt provider — read-only, used only for data sources on shared IAM roles
provider "aws" {
  alias  = "mgmt"
  region = var.aws_region
  assume_role {
    role_arn     = "arn:aws:iam::${var.mgmt_account_id}:role/CrossAccountRole"
    session_name = "TerraformRAPMgmtSession"
  }
}
