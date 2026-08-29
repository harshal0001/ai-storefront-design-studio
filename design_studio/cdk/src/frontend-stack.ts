/** CDK stack — S3 + CloudFront hosting for the Design Studio SPA. */
import * as cdk from "aws-cdk-lib";
import {
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
  aws_lambda as lambda,
  aws_s3 as s3,
  aws_s3_deployment as s3deploy,
  aws_secretsmanager as secretsmanager,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export interface DesignStudioFrontendStackProps extends cdk.StackProps {
  readonly frontendSourceDir: string;
  readonly functionUrl: lambda.IFunctionUrl;
  readonly originSecret: secretsmanager.ISecret;
}

export class DesignStudioFrontendStack extends cdk.Stack {
  public readonly siteBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: DesignStudioFrontendStackProps) {
    super(scope, id, props);

    const isProduction = this.node.tryGetContext("production") === "true";

    this.siteBucket = new s3.Bucket(this, "SiteBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: isProduction ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: !isProduction,
    });

    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(this.siteBucket);
    const apiOrigin = new origins.FunctionUrlOrigin(props.functionUrl, {
      customHeaders: {
        "x-cf-origin-secret": props.originSecret.secretValue.unsafeUnwrap(),
      },
      readTimeout: cdk.Duration.seconds(120),
      keepaliveTimeout: cdk.Duration.seconds(5),
    });

    this.distribution = new cloudfront.Distribution(this, "Distribution", {
      comment: "Design Studio SPA and API distribution",
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        compress: true,
      },
      additionalBehaviors: {
        "/api/*": {
          origin: apiOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          compress: true,
        },
        "index.html": {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          compress: true,
        },
      },
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.minutes(1),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.minutes(1),
        },
      ],
    });

    new s3deploy.BucketDeployment(this, "DeployFrontend", {
      sources: [
        s3deploy.Source.asset(props.frontendSourceDir, {
          exclude: ["node_modules", "dist"],
          bundling: {
            image: cdk.DockerImage.fromRegistry("public.ecr.aws/docker/library/node:20"),
            environment: {
              HOME: "/tmp",
              npm_config_cache: "/tmp/npm-cache",
            },
            command: [
              "bash",
              "-c",
              [
                "mkdir -p /tmp/frontend /tmp/npm-cache",
                "tar --exclude='./node_modules' --exclude='./dist' -cf - . | tar -xf - -C /tmp/frontend",
                "cd /tmp/frontend",
                "npm ci",
                `VITE_REGION=${this.region} npm run build`,
                "cp -R dist/. /asset-output/",
              ].join(" && "),
            ],
            outputType: cdk.BundlingOutput.NOT_ARCHIVED,
          },
        }),
      ],
      destinationBucket: this.siteBucket,
      distribution: this.distribution,
      distributionPaths: ["/", "/index.html"],
      prune: true,
      retainOnDelete: isProduction,
    });

    new cdk.CfnOutput(this, "FrontendBucketName", {
      value: this.siteBucket.bucketName,
    });
    new cdk.CfnOutput(this, "FrontendDistributionId", {
      value: this.distribution.distributionId,
    });
    new cdk.CfnOutput(this, "FrontendDistributionDomainName", {
      value: this.distribution.distributionDomainName,
    });
    new cdk.CfnOutput(this, "FrontendUrl", {
      value: `https://${this.distribution.distributionDomainName}`,
    });
  }
}
