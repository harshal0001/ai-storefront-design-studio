variable "runtime_name" {
  description = "Name of the AgentCore Runtime"
  type        = string
}

variable "description" {
  description = "Description of the AgentCore Runtime"
  type        = string
  default     = ""
}

variable "ecr_image_uri" {
  description = "ECR image URI for the runtime container (e.g. 123456789.dkr.ecr.eu-north-1.amazonaws.com/repo:tag)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables to pass to the runtime container"
  type        = map(string)
  default     = {}
}

variable "endpoint_name" {
  description = "Name of the runtime endpoint"
  type        = string
  default     = "live"
}

variable "endpoint_description" {
  description = "Description of the runtime endpoint"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
