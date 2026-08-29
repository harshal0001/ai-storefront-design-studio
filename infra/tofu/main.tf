# All RAP resources must follow the naming convention:
#   <type>-rap-<environment>
# Use local.name_prefix as the base: "${local.name_prefix}" = "rap-sandbox"
# Tags are applied automatically via provider default_tags.

# ── ECR Repository — Design Studio conversational agent ──────────────────────
resource "aws_ecr_repository" "design_studio" {
  name                 = "ecr-${local.name_prefix}-design-studio"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "design_studio" {
  repository = aws_ecr_repository.design_studio.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# ── AgentCore Runtime — Design Studio conversational agent ───────────────────
module "design_studio_agent" {
  source = "./modules/agentcore_runtime"

  runtime_name         = "design-studio-agent-${local.name_prefix}"
  description          = "Design Studio conversational agent runtime"
  ecr_image_uri        = "${aws_ecr_repository.design_studio.repository_url}:latest"
  aws_region           = var.aws_region
  account_id           = var.target_account_id
  endpoint_name        = "live"
  endpoint_description = "Live endpoint for the Design Studio conversational agent"

  environment_variables = {
    AGENT_MODEL = "eu.amazon.nova-pro-v1:0"
  }

  tags = local.common_tags
}
