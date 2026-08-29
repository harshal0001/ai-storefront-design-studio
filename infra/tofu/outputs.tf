output "environment" {
  description = "Deployed environment name"
  value       = var.environment
}

output "aws_region" {
  description = "Deployed AWS region"
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "ECR repository URL for the Design Studio agent image"
  value       = aws_ecr_repository.design_studio.repository_url
}

output "agent_runtime_arn" {
  description = "ARN of the Design Studio AgentCore Runtime"
  value       = module.design_studio_agent.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "ID of the Design Studio AgentCore Runtime"
  value       = module.design_studio_agent.agent_runtime_id
}

output "agent_runtime_endpoint_arn" {
  description = "ARN of the Design Studio AgentCore Runtime live endpoint"
  value       = module.design_studio_agent.agent_runtime_endpoint_arn
}

output "execution_role_arn" {
  description = "ARN of the AgentCore execution IAM role"
  value       = module.design_studio_agent.execution_role_arn
}
