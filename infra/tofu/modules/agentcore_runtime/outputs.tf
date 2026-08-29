output "agent_runtime_arn" {
  description = "ARN of the AgentCore Runtime"
  value       = aws_bedrock_agent_core_runtime.this.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "ID of the AgentCore Runtime"
  value       = aws_bedrock_agent_core_runtime.this.agent_runtime_id
}

output "agent_runtime_endpoint_arn" {
  description = "ARN of the AgentCore Runtime Endpoint"
  value       = aws_bedrock_agent_core_runtime_endpoint.this.agent_runtime_endpoint_arn
}

output "execution_role_arn" {
  description = "ARN of the execution IAM role"
  value       = aws_iam_role.agentcore_execution.arn
}
