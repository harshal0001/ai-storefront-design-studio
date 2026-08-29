locals {
  # Naming prefix for all RAP resources: <type>-rap-<env>
  # Example: s3-rap-sandbox, vpc-rap-sandbox, eks-rap-sandbox
  name_prefix = "rap-${var.environment}"

  common_tags = merge(
    {
      project      = "RAP"
      project-name = "storefront-design-studio"
      environment  = var.environment
      managed-by   = "opentofu"
      map-migrated = var.map_migrated
    },
    var.tags,
  )
}
