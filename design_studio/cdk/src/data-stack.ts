/** CDK stack — DynamoDB tables for Design Studio style persistence. */
import * as cdk from "aws-cdk-lib";
import { aws_dynamodb as dynamodb } from "aws-cdk-lib";
import { Construct } from "constructs";

export interface DesignStudioDataStackProps extends cdk.StackProps {
  readonly styleTableName?: string;
  readonly themePackageTableName?: string;
}

export class DesignStudioDataStack extends cdk.Stack {
  public readonly styleTable: dynamodb.Table;
  public readonly themePackageTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: DesignStudioDataStackProps = {}) {
    super(scope, id, props);

    const styleTableName = props.styleTableName ?? "StorefrontStyle";
    const themePackageTableName = props.themePackageTableName ?? "ThemePackage";

    this.styleTable = new dynamodb.Table(this, "StorefrontStyleTable", {
      tableName: styleTableName,
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    this.styleTable.addGlobalSecondaryIndex({
      indexName: "type-updatedAt-index",
      partitionKey: { name: "type", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "updatedAt", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    this.styleTable.addGlobalSecondaryIndex({
      indexName: "previewToken-index",
      partitionKey: { name: "previewToken", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    this.themePackageTable = new dynamodb.Table(this, "ThemePackageTable", {
      tableName: themePackageTableName,
      partitionKey: { name: "packageId", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    new cdk.CfnOutput(this, "StorefrontStyleTableName", {
      value: this.styleTable.tableName,
    });
    new cdk.CfnOutput(this, "StorefrontStyleTableArn", {
      value: this.styleTable.tableArn,
    });
    new cdk.CfnOutput(this, "ThemePackageTableName", {
      value: this.themePackageTable.tableName,
    });
    new cdk.CfnOutput(this, "ThemePackageTableArn", {
      value: this.themePackageTable.tableArn,
    });
  }
}
