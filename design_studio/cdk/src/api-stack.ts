/** CDK stack — Lambda Function URL backend for the Design Studio SPA. */
import * as cdk from "aws-cdk-lib";
import {
  aws_dynamodb as dynamodb,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_s3 as s3,
  aws_secretsmanager as secretsmanager,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export interface DesignStudioApiStackProps extends cdk.StackProps {
  readonly agentRuntimeArn: string;
  readonly backendSourceDir: string;
  readonly styleTable: dynamodb.ITable;
  readonly themePackageTable: dynamodb.ITable;
  readonly screenshotBucket: s3.IBucket;
  readonly functionUrlSecret?: secretsmanager.ISecret;
  readonly corsAllowOrigin?: string;
}

export class DesignStudioApiStack extends cdk.Stack {
  public readonly apiFunction: lambda.Function;
  public readonly functionUrl: lambda.FunctionUrl;
  public readonly originSecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props: DesignStudioApiStackProps) {
    super(scope, id, props);

    this.originSecret =
      props.functionUrlSecret ??
      new secretsmanager.Secret(this, "FunctionUrlOriginSecret", {
        description:
          "Shared secret expected on CloudFront requests to the Design Studio API Lambda",
        generateSecretString: {
          excludePunctuation: true,
          passwordLength: 48,
        },
      });

    this.apiFunction = new lambda.Function(this, "BackendFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      architecture: lambda.Architecture.ARM_64,
      handler: "lambda_backend.handler.handler",
      memorySize: 512,
      timeout: cdk.Duration.seconds(180),
      tracing: lambda.Tracing.ACTIVE,
      code: lambda.Code.fromAsset(props.backendSourceDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "python -m pip install --no-cache-dir -t /asset-output -r lambda_backend/requirements.txt",
              "cp -R conversational_agent /asset-output/conversational_agent",
              "cp -R lambda_backend /asset-output/lambda_backend",
              "cp storefront.html fonts.json /asset-output/",
              "echo '' > /asset-output/conversational_agent/__init__.py",
              "find /asset-output -type d -name '__pycache__' -prune -exec rm -rf {} +",
            ].join(" && "),
          ],
        },
      }),
      environment: {
        AGENT_RUNTIME_ARN: props.agentRuntimeArn,
        AGENT_RUNTIME_QUALIFIER: "live",
        CORS_ALLOW_ORIGIN: props.corsAllowOrigin ?? "*",
        CF_ORIGIN_SECRET_ARN: this.originSecret.secretArn,
        DYNAMODB_STYLE_TABLE: props.styleTable.tableName,
        DYNAMODB_THEME_PACKAGE_TABLE: props.themePackageTable.tableName,
        USE_DYNAMODB: "true",
        USE_AGENTCORE_BROWSER: "true",
        SCREENSHOT_BUCKET: props.screenshotBucket.bucketName,
        SCREENSHOT_URL_EXPIRY: "600",
        POWERTOOLS_SERVICE_NAME: "design-studio-api",
        POWERTOOLS_METRICS_NAMESPACE: "DesignStudio",
        POWERTOOLS_LOG_LEVEL: "INFO",
        // Storefront HTML and agent responses exceed X-Ray's 64KB subsegment UDP limit.
        POWERTOOLS_TRACER_CAPTURE_RESPONSE: "false",
      },
      description: "Request/response API for Design Studio chat and storefront state",
    });

    this.originSecret.grantRead(this.apiFunction);
    props.styleTable.grantReadWriteData(this.apiFunction);
    props.themePackageTable.grantReadData(this.apiFunction);
    props.screenshotBucket.grantReadWrite(this.apiFunction);

    this.apiFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "bedrock-agentcore:StartBrowserSession",
          "bedrock-agentcore:StopBrowserSession",
          "bedrock-agentcore:UpdateBrowserStream",
          "bedrock-agentcore:ConnectBrowserAutomationStream",
        ],
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:aws:browser/*`,
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:browser/*`,
        ],
      }),
    );

    this.apiFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock-agentcore:InvokeAgentRuntime"],
        resources: [props.agentRuntimeArn, `${props.agentRuntimeArn}/*`],
      }),
    );

    this.functionUrl = this.apiFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedMethods: [lambda.HttpMethod.GET, lambda.HttpMethod.POST],
        allowedOrigins: [props.corsAllowOrigin ?? "*"],
        allowedHeaders: ["content-type", "x-cf-origin-secret"],
      },
    });

    new cdk.CfnOutput(this, "BackendFunctionName", {
      value: this.apiFunction.functionName,
    });
    new cdk.CfnOutput(this, "BackendFunctionUrl", {
      value: this.functionUrl.url,
    });
    new cdk.CfnOutput(this, "BackendOriginSecretArn", {
      value: this.originSecret.secretArn,
    });
  }
}
