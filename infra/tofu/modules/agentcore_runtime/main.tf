terraform {
  required_version = "~> 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ── IAM Execution Role ────────────────────────────────────────────────────────
resource "aws_iam_role" "agentcore_execution" {
  name        = "role-${var.runtime_name}-execution"
  description = "Execution role for AgentCore Runtime ${var.runtime_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "bedrock-agentcore.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

# Baseline permissions: ECR pull, CloudWatch Logs, X-Ray
resource "aws_iam_role_policy" "agentcore_baseline" {
  name = "agentcore-baseline"
  role = aws_iam_role.agentcore_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/aws/bedrock-agentcore/*"
      },
      {
        Sid    = "XRay"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      }
    ]
  })
}

# Bedrock model invocation — not in baseline, added explicitly
resource "aws_iam_role_policy" "agentcore_bedrock" {
  name = "agentcore-bedrock"
  role = aws_iam_role.agentcore_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "BedrockInvoke"
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:*::foundation-model/*",
        "arn:aws:bedrock:${var.aws_region}:${var.account_id}:inference-profile/*"
      ]
    }]
  })
}

# ── AgentCore Runtime ─────────────────────────────────────────────────────────
resource "aws_bedrock_agent_core_runtime" "this" {
  agent_runtime_name = var.runtime_name
  description        = var.description

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.ecr_image_uri
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  role_arn = aws_iam_role.agentcore_execution.arn

  environment_variables = merge(
    {
      AWS_REGION         = var.aws_region
      AWS_DEFAULT_REGION = var.aws_region
    },
    var.environment_variables
  )

  tags = var.tags
}

# ── AgentCore Runtime Endpoint ────────────────────────────────────────────────
resource "aws_bedrock_agent_core_runtime_endpoint" "this" {
  agent_runtime_id = aws_bedrock_agent_core_runtime.this.agent_runtime_id
  name             = var.endpoint_name
  description      = var.endpoint_description
}
