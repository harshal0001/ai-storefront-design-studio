variable "environment" {
  description = "Environment name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "target_account_id" {
  description = "Target AWS account ID"
  type        = string
}

variable "mgmt_account_id" {
  description = "Management AWS account ID (for shared IAM role data sources)"
  type        = string
}

variable "map_migrated" {
  description = "AWS MAP migration tag value"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags merged on top of common_tags"
  type        = map(string)
  default     = {}
}
