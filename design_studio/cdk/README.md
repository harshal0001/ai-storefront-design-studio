# Design Studio — CDK

CDK TypeScript app that provisions Design Studio AWS infrastructure.

Region: `eu-north-1`.

## Constructs used

The AgentCore stack uses **`@aws-cdk/aws-bedrock-agentcore-alpha`** (L2) on top
of `aws-cdk-lib` (L1 `Cfn*`). See [Alpha module limitations](#alpha-module-limitations)
below for the trade-offs.

The data stack uses `aws-cdk-lib/aws-dynamodb` L2 constructs and mirrors the
local DynamoDB schema in `../../DDB_Schema.md`.

## Resources

| Construct | Underlying CFN | Purpose |
| --- | --- | --- |
| `dynamodb.Table` (`StorefrontStyle`) | `AWS::DynamoDB::Table` | Merchant-scoped style profile, draft, published, versions, undo stack, zone tour, and preview snapshots |
| `dynamodb.Table` (`ThemePackage`) | `AWS::DynamoDB::Table` | Global starter theme packages |
| `agentcore.Runtime` | `AWS::BedrockAgentCore::Runtime` + `AWS::IAM::Role` | Container-backed AgentCore Runtime; role auto-created with trust policy and baseline perms |
| `agentcore.RuntimeEndpoint` | `AWS::BedrockAgentCore::RuntimeEndpoint` | `live` endpoint |
| `lambda.Function` + Function URL | `AWS::Lambda::Function`, `AWS::Lambda::Url` | Request/response API for chat, storefront preview, version history, restore, and related style routes |
| `s3.Bucket` + `cloudfront.Distribution` | `AWS::S3::Bucket`, `AWS::CloudFront::Distribution` | Private SPA hosting with an S3 origin and `/api/*` Function URL origin |
| `DockerImageAsset` (via `AgentRuntimeArtifact.fromAsset`) | Bootstrap ECR repo + image | CDK builds and pushes the image during `cdk deploy` |

## Prerequisites

- Node.js 20+
- AWS CDK v2 bootstrapped in the target account/region: `npx cdk bootstrap aws://<acct>/eu-north-1`
- Docker (with `buildx` for `linux/arm64`)
- A `Dockerfile` at `design_studio/conversational_agent/Dockerfile` — **does not exist yet**, see below.
- AWS credentials with admin or equivalent for first deploy

### Dockerfile

The Docker build context is `design_studio/` so that `pyproject.toml` (the
single source of truth for Python deps) is included. The container installs
`.[runtime]` — base deps plus `bedrock-agentcore` and ADOT.

Files:
- `design_studio/Dockerfile`
- `design_studio/.dockerignore`
- `design_studio/conversational_agent/agentcore_app.py` — `BedrockAgentCoreApp`
  HTTP wrapper that AgentCore Runtime invokes

## Install

```bash
cd design_studio/cdk
npm install
```

## Deploy

```bash
npx cdk deploy DesignStudioDataStack
npx cdk deploy DesignStudioConversationalAgent
npx cdk deploy DesignStudioApiStack
npx cdk deploy DesignStudioFrontendStack
```

`DesignStudioDataStack` creates the two DynamoDB tables used by the current
local implementation:

- `StorefrontStyle`
  - primary key: `PK`, sort key: `SK`
  - on-demand billing
  - point-in-time recovery enabled
  - retained on stack deletion
  - TTL attribute: `ttl`
  - GSIs: `type-updatedAt-index`, `previewToken-index`
- `ThemePackage`
  - primary key: `packageId`
  - on-demand billing
  - point-in-time recovery enabled
  - retained on stack deletion

Starter package rows are not seeded by CDK. Seed them separately when needed,
for example with `design_studio/scripts/seed_theme_packages.py` pointed at the
deployed table names.

CDK builds the agent image from `conversational_agent/Dockerfile`, pushes it to
the bootstrap ECR repo, then creates the runtime + endpoint pointed at that
image. No manual ECR repo, no two-pass.

Outputs:

- `StorefrontStyleTableName`, `StorefrontStyleTableArn`
- `ThemePackageTableName`, `ThemePackageTableArn`
- `AgentRuntimeArn`, `AgentRuntimeId`
- `AgentRuntimeEndpointArn`
- `ExecutionRoleArn`
- `BackendFunctionName`
- `BackendFunctionUrl`
- `BackendOriginSecretArn`
- `FrontendBucketName`
- `FrontendDistributionId`
- `FrontendDistributionDomainName`
- `FrontendUrl`

`DesignStudioApiStack` creates an open Function URL intended to sit behind
CloudFront. The Lambda rejects requests that do not include
`X-CF-Origin-Secret` matching the generated secret value, except for CORS
preflight. The frontend hosting stack passes the same secret as an origin custom
header on the `/api/*` behavior.

`DesignStudioFrontendStack` creates the private SPA bucket, CloudFront
distribution, and `BucketDeployment`. The deployment bundles
`../frontend` in a Node 20 container with `npm ci && npm run build`, uploads the
generated Vite `dist/` assets, and invalidates `/` plus `/index.html`.

## Updating the agent

Edit the agent code, then redeploy:

```bash
npx cdk deploy DesignStudioDataStack
npx cdk deploy DesignStudioConversationalAgent
npx cdk deploy DesignStudioApiStack
npx cdk deploy DesignStudioFrontendStack
```

CDK detects the asset hash change, rebuilds and pushes a new image tag, and
the runtime updates in place (no replacement).

## Destroy

```bash
npx cdk destroy DesignStudioDataStack
npx cdk destroy DesignStudioConversationalAgent
npx cdk destroy DesignStudioApiStack
npx cdk destroy DesignStudioFrontendStack
```

The DynamoDB tables use `RemovalPolicy.RETAIN`, so destroying
`DesignStudioDataStack` removes the CloudFormation stack but keeps the table
data unless you delete the tables manually.

The bootstrap ECR repo and its images are *not* deleted by this stack — they
belong to the CDK bootstrap stack.

## Alpha module limitations

`@aws-cdk/aws-bedrock-agentcore-alpha` is in **developer preview**. We use it
because the L1-only alternative requires a manual two-step deploy
(create-repo → push image → create-runtime). Trade-offs you should know:

1. **Pin the version exactly.** `package.json` uses `2.254.0-alpha.0` (no `^`).
   Alpha modules occasionally rename props between CDK minor versions; an
   accidental upgrade can break compilation. Upgrade `aws-cdk-lib` and the
   alpha module **together**, in a deliberate commit.
2. **Breaking-change risk.** Expect occasional renames in:
   - prop names (`runtimeName` ↔ `agentRuntimeName` has flipped before)
   - `AgentRuntimeArtifact` factory signatures
   - generated logical IDs (which would force replacement)
   Test in a non-prod account when bumping versions.
3. **Eventual graduation rename.** When the module reaches stable, the import
   path changes from `@aws-cdk/aws-bedrock-agentcore-alpha` to
   `aws-cdk-lib.aws_bedrockagentcore` (L2 promoted into core). One-time
   refactor across the stack file.
4. **Image lives in the CDK bootstrap ECR repo.** Not a named repo like
   `design-studio-conversational-agent`. The repo is shared across all CDK
   apps in the account/region (`cdk-hnb659fds-container-assets-…`). Console
   URLs are uglier; pulling the image manually requires checking what URI CDK
   chose. If a named repo matters, switch back to L1 + two-pass deploy or
   manage ECR outside CDK.
5. **The auto-generated IAM role is opinionated.** It sets the trust policy
   for `bedrock-agentcore.amazonaws.com` and adds baseline ECR/Logs/X-Ray
   perms. We add `bedrock:InvokeModel` on top. If you need to *remove* a
   default permission or add tighter conditions, escape-hatch:
   ```ts
   const cfnRole = runtime.role.node.defaultChild as iam.CfnRole;
   // mutate cfnRole.policies, cfnRole.permissionsBoundary, etc.
   ```
6. **No L2 for related resources yet** (Memory, Gateway, GatewayTarget).
   When you add those, you'll mix L2 Runtime with L1 `CfnMemory` /
   `CfnGateway` until the alpha module catches up.
7. **Limited docs.** API reference exists on constructs.dev; conceptual
   docs are sparse. Read the source if a prop is ambiguous:
   `node_modules/@aws-cdk/aws-bedrock-agentcore-alpha/lib/`.

### Reverting to pure L1

If alpha breakage becomes painful, the previous L1 implementation is in
`git log` for `src/conversational-agent-stack.ts`. It uses `CfnRepository`,
`CfnRole`, `CfnRuntime`, `CfnRuntimeEndpoint` directly and requires the
two-step deploy described in the commit message.

## Notes

- Default `NetworkMode` is `PUBLIC` (alpha L2 default). For VPC, set
  `networkConfiguration` on the `Runtime` props.
- `ProtocolConfiguration` defaults to `HTTP`. Override via `protocol` prop
  on the `Runtime`.
- `bedrock:InvokeModel` resources include `inference-profile/*` — the
  conversational agent uses `eu.amazon.nova-pro-v1:0` cross-region inference.

## Enabling AgentCore observability (one-time, per account/region)

Built-in AgentCore traces only show up in the CloudWatch GenAI Observability
dashboard once **CloudWatch Transaction Search** is enabled. This is a one-time
setup per account/region and is **not** done by this stack.

> **Note:** Transaction logging can also be enabled manually via the AWS console
> or by following the official walkthrough:
> [Configure observability for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html).

### Manual setup (current approach)

Run once per account/region:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=eu-north-1

# 1. Resource policy: let X-Ray write spans to CloudWatch Logs
aws logs put-resource-policy \
  --region "$REGION" \
  --policy-name TransactionSearchXRayAccess \
  --policy-document "$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "TransactionSearchXRayAccess",
    "Effect": "Allow",
    "Principal": { "Service": "xray.amazonaws.com" },
    "Action": "logs:PutLogEvents",
    "Resource": [
      "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:aws/spans:*",
      "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/application-signals/data:*"
    ],
    "Condition": {
      "ArnLike": { "aws:SourceArn": "arn:aws:xray:${REGION}:${ACCOUNT_ID}:*" },
      "StringEquals": { "aws:SourceAccount": "${ACCOUNT_ID}" }
    }
  }]
}
EOF
)"

# 2. Send X-Ray trace segments to CloudWatch Logs (Transaction Search)
aws xray update-trace-segment-destination \
  --region "$REGION" \
  --destination CloudWatchLogs
```

Verify in the [CloudWatch console](https://console.aws.amazon.com/cloudwatch/home#gen-ai-observability)
that the GenAI Observability dashboard starts populating after a runtime invocation.

### Future option: dedicated `ObservabilitySetupStack`

If you add more agent stacks (or want this to be tracked in IaC), promote the
two commands above into a separate CDK stack — kept apart because Transaction
Search is account/region-scoped and only one stack should own it.

Sketch:

- `AWS::Logs::ResourcePolicy` (L1 `CfnResourcePolicy`) for the
  `TransactionSearchXRayAccess` policy above.
- `AwsCustomResource` (from `aws-cdk-lib/custom-resources`) calling
  `xray:UpdateTraceSegmentDestination` with `Destination=CloudWatchLogs` on
  create, and reverting to `XRay` on delete. No native CFN resource exists for
  this API yet.
- Optional second `AwsCustomResource` for `xray:UpdateIndexingRule` if you want
  a sampling percentage other than 100%.

Deploy once per account/region (`cdk deploy ObservabilitySetupStack`), then
keep the agent stacks unaware of it.
