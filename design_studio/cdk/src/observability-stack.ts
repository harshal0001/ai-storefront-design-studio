/**
 * CDK stack — Observability setup for the Design Studio.
 *
 * One-time per-account/region setup:
 *  - Resource policy allowing X-Ray to write to CloudWatch Logs (Transaction Search)
 *  - X-Ray trace segment destination config
 *  - Comprehensive CloudWatch dashboard (Lambda + AgentCore + DynamoDB)
 */
import * as cdk from "aws-cdk-lib";
import {
  aws_cloudwatch as cloudwatch,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  custom_resources as cr,
} from "aws-cdk-lib";
import { Construct } from "constructs";

export interface ObservabilityStackProps extends cdk.StackProps {
  readonly apiFunction: lambda.IFunction;
  readonly agentRuntimeName: string;
  readonly styleTableName: string;
  readonly themePackageTableName: string;
  readonly screenshotBucketName: string;
}

export class ObservabilityStack extends cdk.Stack {
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: ObservabilityStackProps) {
    super(scope, id, props);

    const { apiFunction, styleTableName, themePackageTableName } = props;

    // --- X-Ray → CloudWatch Logs resource policy (Transaction Search) ---
    // Required for AgentCore observability: allows X-Ray to ingest spans into
    // CloudWatch Logs for the GenAI Observability dashboard.
    new logs.CfnResourcePolicy(this, "XRayTransactionSearchPolicy", {
      policyName: "TransactionSearchXRayAccess",
      policyDocument: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Sid: "TransactionSearchXRayAccess",
            Effect: "Allow",
            Principal: { Service: "xray.amazonaws.com" },
            Action: "logs:PutLogEvents",
            Resource: [
              `arn:aws:logs:${this.region}:${this.account}:log-group:aws/spans:*`,
              `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/application-signals/data:*`,
            ],
            Condition: {
              ArnLike: {
                "aws:SourceArn": `arn:aws:xray:${this.region}:${this.account}:*`,
              },
              StringEquals: {
                "aws:SourceAccount": this.account,
              },
            },
          },
        ],
      }),
    });

    // --- X-Ray trace segment destination → CloudWatch Logs ---
    // Enabling Transaction Search triggers a chain of internal service calls
    // (application-signals, cloudtrail, iam service-linked roles). Using managed
    // policies avoids chasing individual actions one by one.
    const xrayDestinationRole = new iam.Role(this, "XRayDestinationCustomResourceRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AWSXRayFullAccess"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("CloudWatchFullAccessV2"),
      ],
      inlinePolicies: {
        transactionSearchBootstrap: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                "application-signals:StartDiscovery",
                "cloudtrail:CreateServiceLinkedChannel",
                "iam:CreateServiceLinkedRole",
              ],
              resources: ["*"],
            }),
          ],
        }),
      },
    });

    new cr.AwsCustomResource(this, "XRayTraceDestination", {
      onCreate: {
        service: "XRay",
        action: "updateTraceSegmentDestination",
        parameters: { Destination: "CloudWatchLogs" },
        physicalResourceId: cr.PhysicalResourceId.of("xray-destination-cloudwatch"),
      },
      onUpdate: {
        service: "XRay",
        action: "updateTraceSegmentDestination",
        parameters: { Destination: "CloudWatchLogs" },
        physicalResourceId: cr.PhysicalResourceId.of("xray-destination-cloudwatch"),
      },
      role: xrayDestinationRole,
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // --- Comprehensive CloudWatch Dashboard ---
    this.dashboard = new cloudwatch.Dashboard(this, "DesignStudioDashboard", {
      dashboardName: "DesignStudio-Observability",
      periodOverride: cloudwatch.PeriodOverride.AUTO,
    });

    // Row 1: Lambda overview
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "Lambda Invocations & Errors",
        width: 12,
        left: [
          apiFunction.metricInvocations({ statistic: "Sum" }),
          apiFunction.metricErrors({ statistic: "Sum" }),
          apiFunction.metricThrottles({ statistic: "Sum" }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: "Lambda Duration (p50 / p90 / p99)",
        width: 12,
        left: [
          apiFunction.metricDuration({ statistic: "p50", label: "p50" }),
          apiFunction.metricDuration({ statistic: "p90", label: "p90" }),
          apiFunction.metricDuration({ statistic: "p99", label: "p99" }),
        ],
      }),
    );

    // Row 2: Cold starts & concurrent executions
    this.dashboard.addWidgets(
      new cloudwatch.SingleValueWidget({
        title: "Cold Starts (Powertools)",
        width: 6,
        metrics: [
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "ColdStart",
            dimensionsMap: {
              service: "design-studio-api",
              function_name: apiFunction.functionName,
            },
            statistic: "Sum",
          }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: "Concurrent Executions",
        width: 6,
        left: [apiFunction.metric("ConcurrentExecutions", { statistic: "Maximum" })],
      }),
      new cloudwatch.GraphWidget({
        title: "AgentCore Runtime: Invocations & Errors",
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "AgentInvocation",
            dimensionsMap: { service: "design-studio-agent" },
            statistic: "Sum",
            label: "Agent Invocations",
          }),
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "AgentError",
            dimensionsMap: { service: "design-studio-agent" },
            statistic: "Sum",
            label: "Agent Errors",
          }),
        ],
      }),
    );

    // Row 3: Business metrics
    this.dashboard.addWidgets(
      new cloudwatch.SingleValueWidget({
        title: "Themes Published",
        width: 6,
        metrics: [
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "ThemePublished",
            dimensionsMap: { service: "design-studio-api" },
            statistic: "Sum",
          }),
        ],
      }),
      new cloudwatch.SingleValueWidget({
        title: "Screenshots Captured",
        width: 6,
        metrics: [
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "ScreenshotCaptured",
            dimensionsMap: { service: "design-studio-api" },
            statistic: "Sum",
          }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: "Client & Auth Errors",
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "ClientError",
            dimensionsMap: { service: "design-studio-api" },
            statistic: "Sum",
            label: "4xx Client Errors",
          }),
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "ServerError",
            dimensionsMap: { service: "design-studio-api" },
            statistic: "Sum",
            label: "5xx Server Errors",
          }),
          new cloudwatch.Metric({
            namespace: "DesignStudio",
            metricName: "AuthFailure",
            dimensionsMap: { service: "design-studio-api" },
            statistic: "Sum",
            label: "Auth Failures",
          }),
        ],
      }),
    );

    // Row 4: DynamoDB consumed capacity
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: `DynamoDB: ${styleTableName} Consumed RCU/WCU`,
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "ConsumedReadCapacityUnits",
            dimensionsMap: { TableName: styleTableName },
            statistic: "Sum",
            label: "Read Capacity",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "ConsumedWriteCapacityUnits",
            dimensionsMap: { TableName: styleTableName },
            statistic: "Sum",
            label: "Write Capacity",
          }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: `DynamoDB: ${themePackageTableName} Consumed RCU`,
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "ConsumedReadCapacityUnits",
            dimensionsMap: { TableName: themePackageTableName },
            statistic: "Sum",
            label: "Read Capacity",
          }),
        ],
      }),
    );

    // Row 5: DynamoDB errors
    this.dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "DynamoDB Throttled Requests",
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "ThrottledRequests",
            dimensionsMap: { TableName: styleTableName },
            statistic: "Sum",
            label: styleTableName,
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "ThrottledRequests",
            dimensionsMap: { TableName: themePackageTableName },
            statistic: "Sum",
            label: themePackageTableName,
          }),
        ],
      }),
      new cloudwatch.GraphWidget({
        title: "DynamoDB System Errors",
        width: 12,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "SystemErrors",
            dimensionsMap: { TableName: styleTableName },
            statistic: "Sum",
            label: styleTableName,
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB",
            metricName: "SystemErrors",
            dimensionsMap: { TableName: themePackageTableName },
            statistic: "Sum",
            label: themePackageTableName,
          }),
        ],
      }),
    );

    new cdk.CfnOutput(this, "DashboardUrl", {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=DesignStudio-Observability`,
    });
  }
}
