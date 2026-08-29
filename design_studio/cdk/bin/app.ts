#!/usr/bin/env node
/** CDK app entry — instantiates Design Studio infrastructure stacks. */
import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { DesignStudioApiStack } from "../src/api-stack";
import { ConversationalAgentStack } from "../src/conversational-agent-stack";
import { DesignStudioDataStack } from "../src/data-stack";
import { ObservabilityStack } from "../src/observability-stack";
import { DesignStudioFrontendStack } from "../src/frontend-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "eu-north-1",
};

const dataStack = new DesignStudioDataStack(app, "DesignStudioDataStack", {
  env,
  description: "DynamoDB tables for Design Studio style persistence",
  tags: {
    app: "design_studio",
    component: "data",
  },
});

const agentStack = new ConversationalAgentStack(app, "DesignStudioConversationalAgent", {
  env,
  agentRuntimeName: "design_studio_conversational_agent",
  agentSourceDir: path.resolve(__dirname, "..", ".."),
  styleTable: dataStack.styleTable,
  themePackageTable: dataStack.themePackageTable,
  description: "AgentCore Runtime for the Design Studio conversational agent (alpha L2)",
  tags: {
    app: "design_studio",
    component: "conversational_agent",
  },
});

const apiStack = new DesignStudioApiStack(app, "DesignStudioApiStack", {
  env,
  agentRuntimeArn: agentStack.agentRuntimeArn,
  backendSourceDir: path.resolve(__dirname, "..", ".."),
  styleTable: dataStack.styleTable,
  themePackageTable: dataStack.themePackageTable,
  screenshotBucket: agentStack.screenshotBucket,
  description: "Lambda Function URL backend for the Design Studio SPA",
  tags: {
    app: "design_studio",
    component: "api",
  },
});

new ObservabilityStack(app, "DesignStudioObservability", {
  env,
  apiFunction: apiStack.apiFunction,
  agentRuntimeName: "design_studio_conversational_agent",
  styleTableName: dataStack.styleTable.tableName,
  themePackageTableName: dataStack.themePackageTable.tableName,
  screenshotBucketName: agentStack.screenshotBucket.bucketName,
  description: "Observability: X-Ray tracing, CloudWatch dashboard, and resource policies",
  tags: {
    app: "design_studio",
    component: "observability",
  },
});

new DesignStudioFrontendStack(app, "DesignStudioFrontendStack", {
  env,
  frontendSourceDir: path.resolve(__dirname, "..", "..", "frontend"),
  functionUrl: apiStack.functionUrl,
  originSecret: apiStack.originSecret,
  description: "S3 and CloudFront hosting for the Design Studio SPA",
  tags: {
    app: "design_studio",
    component: "frontend",
  },
});
