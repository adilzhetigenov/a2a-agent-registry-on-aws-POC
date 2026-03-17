import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import { PythonFunction } from "@aws-cdk/aws-lambda-python-alpha";
import { s3vectors } from "@cdklabs/generative-ai-cdk-constructs";
import { NagSuppressions } from "cdk-nag";

export interface AgentRegistryStackProps extends cdk.StackProps {
  /**
   * The allowed CORS origin for the API Gateway.
   * Use '*' to allow all origins (default), or specify a specific origin
   * (e.g., 'https://d1234567890.cloudfront.net' or your custom domain).
   * @default '*'
   */
  corsOrigin?: string;
}

export class AgentRegistryStack extends cdk.Stack {
  public readonly vectorBucket: s3vectors.VectorBucket;
  public readonly vectorIndex: s3vectors.VectorIndex;
  public readonly apiLambda: PythonFunction;
  public readonly api: apigateway.RestApi;
  public readonly m2mApi: apigateway.RestApi;

  constructor(scope: Construct, id: string, props?: AgentRegistryStackProps) {
    super(scope, id, props);

    // CORS origin configuration - defaults to '*' (allow all)
    const corsOrigin = props?.corsOrigin ?? "*";

    // Generate unique bucket name with account ID and region
    const bucketName = `agent-registry-vectors-${this.account}-${this.region}`;
    const indexName = "agent-embeddings";

    // S3 Vectors infrastructure using L2 CDK construct
    this.vectorBucket = new s3vectors.VectorBucket(this, "VectorBucket", {
      vectorBucketName: bucketName,
      encryption: s3vectors.VectorBucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Remove CDK automatic tags from VectorBucket as S3 Vectors doesn't allow aws: prefixed tags
    cdk.Tags.of(this.vectorBucket).remove("aws:cdk:path");

    // Create vector index for agent embeddings
    this.vectorIndex = new s3vectors.VectorIndex(this, "VectorIndex", {
      vectorBucket: this.vectorBucket,
      vectorIndexName: indexName,
      dimension: 1024, // Standard embedding dimension for text models
      distanceMetric: s3vectors.VectorIndexDistanceMetric.COSINE,
      nonFilterableMetadataKeys: ["raw_agent_card"], // Large metadata that shouldn't be filtered
    });

    // Remove CDK automatic tags from VectorIndex as S3 Vectors doesn't allow aws: prefixed tags
    cdk.Tags.of(this.vectorIndex).remove("aws:cdk:path");

    // Create IAM role for API Lambda function
    const apiLambdaRole = new iam.Role(this, "ApiLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "IAM role for Agent Registry API Lambda function",
      inlinePolicies: {
        // Custom CloudWatch Logs policy instead of AWS managed policy
        CloudWatchLogs: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
              ],
              resources: [
                `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/lambda/agent-registry-api:*`,
              ],
            }),
          ],
        }),
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
              ],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
              ],
            }),
          ],
        }),
        S3VectorsAccess: new iam.PolicyDocument({
          statements: [
            // Vector bucket operations - scoped to specific bucket
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["s3vectors:GetVectorBucket", "s3vectors:ListIndexes"],
              resources: [this.vectorBucket.vectorBucketArn],
            }),
            // Vector index operations - scoped to specific index
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                "s3vectors:GetIndex",
                "s3vectors:PutVectors",
                "s3vectors:GetVectors",
                "s3vectors:DeleteVectors",
                "s3vectors:QueryVectors",
                "s3vectors:ListVectors",
              ],
              resources: [this.vectorIndex.vectorIndexArn],
            }),
          ],
        }),
      },
    });

    // Create CloudWatch Log Group for API Lambda
    const apiLambdaLogGroup = new logs.LogGroup(this, "ApiLambdaLogGroup", {
      logGroupName: `/aws/lambda/agent-registry-api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create main API Lambda function using PythonFunction for automatic dependency management
    this.apiLambda = new PythonFunction(this, "ApiLambda", {
      entry: "../lambda/src",
      runtime: lambda.Runtime.PYTHON_3_14,
      index: "handler.py",
      handler: "lambda_handler",
      role: apiLambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      description: "Agent Registry API Lambda function",
      logGroup: apiLambdaLogGroup,
      environment: {
        S3_VECTORS_BUCKET_NAME: this.vectorBucket.vectorBucketName,
        S3_VECTORS_INDEX_NAME: this.vectorIndex.vectorIndexName,
        BEDROCK_MODEL_ID: "amazon.titan-embed-text-v2:0",
        LOG_LEVEL: "INFO",
      },
    });

    // Create CloudWatch Log Group for API Gateway access logs
    const apiLogGroup = new logs.LogGroup(this, "ApiGatewayLogGroup", {
      logGroupName: `/aws/apigateway/agent-registry-api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create API Gateway with IAM authentication
    this.api = new apigateway.RestApi(this, "AgentRegistryApi", {
      restApiName: "Agent Registry API",
      description:
        "API for managing and searching agent cards with semantic capabilities",
      defaultCorsPreflightOptions: {
        allowOrigins: corsOrigin === "*" ? apigateway.Cors.ALL_ORIGINS : [corsOrigin],
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          "Content-Type",
          "X-Amz-Date",
          "Authorization",
          "X-Api-Key",
          "X-Amz-Security-Token",
          "X-Amz-User-Agent",
          "X-Amz-Content-Sha256",
          "X-Amz-Target",
        ],
      },
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
        // Enable access logging
        accessLogDestination: new apigateway.LogGroupLogDestination(
          apiLogGroup
        ),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: true,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: true,
        }),
      },
      cloudWatchRole: true, // Enable CloudWatch role for API Gateway logging
      endpointConfiguration: {
        types: [apigateway.EndpointType.REGIONAL],
      },
    });

    // Add request validator for API Gateway
    const requestValidator = new apigateway.RequestValidator(
      this,
      "RequestValidator",
      {
        restApi: this.api,
        requestValidatorName: "agent-registry-validator",
        validateRequestBody: true,
        validateRequestParameters: true,
      }
    );

    // Create Lambda integration for API Gateway
    const lambdaIntegration = new apigateway.LambdaIntegration(this.apiLambda, {
      requestTemplates: { "application/json": '{ "statusCode": "200" }' },
      proxy: true,
      allowTestInvoke: true,
    });

    // Configure proxy integration for all paths and methods
    // This allows the Lambda function to handle all routing internally
    this.api.root.addProxy({
      defaultIntegration: lambdaIntegration,
      defaultMethodOptions: {
        authorizationType: apigateway.AuthorizationType.IAM,
        requestValidator: requestValidator,
        requestParameters: {
          "method.request.path.proxy": true,
        },
      },
      anyMethod: true, // Enable ANY method on proxy to handle all HTTP methods
    });

    // Add root resource method for base path (non-proxy) with IAM auth
    this.api.root.addMethod("GET", lambdaIntegration, {
      authorizationType: apigateway.AuthorizationType.IAM,
      requestValidator: requestValidator,
    });

    // Grant API Gateway permission to invoke Lambda
    this.apiLambda.addPermission("ApiGatewayInvoke", {
      principal: new iam.ServicePrincipal("apigateway.amazonaws.com"),
      action: "lambda:InvokeFunction",
      sourceArn: this.api.arnForExecuteApi("*"),
    });

    // Add CORS headers to error responses - force update
    // Use configured corsOrigin for error responses
    const corsAllowOrigin = corsOrigin === "*" ? "'*'" : `'${corsOrigin}'`;
    
    this.api.addGatewayResponse("Default4XX", {
      type: apigateway.ResponseType.DEFAULT_4XX,
      responseHeaders: {
        "Access-Control-Allow-Origin": corsAllowOrigin,
        "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent,X-Amz-Content-Sha256,X-Amz-Target'",
        "Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD'",
      },
    });

    this.api.addGatewayResponse("Default5XX", {
      type: apigateway.ResponseType.DEFAULT_5XX,
      responseHeaders: {
        "Access-Control-Allow-Origin": corsAllowOrigin,
        "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent,X-Amz-Content-Sha256,X-Amz-Target'",
        "Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD'",
      },
    });

    // Stack outputs for cross-stack references (used by AgentRegistryWebUI)

    // ========== Machine-to-Machine API (API Key Auth) ==========

    const m2mApiLogGroup = new logs.LogGroup(this, "M2MApiGatewayLogGroup", {
      logGroupName: `/aws/apigateway/agent-registry-m2m-api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.m2mApi = new apigateway.RestApi(this, "AgentRegistryM2MApi", {
      restApiName: "Agent Registry M2M API",
      description: "Machine-to-machine API for agent self-registration and discovery (API Key auth)",
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ["Content-Type", "X-Api-Key"],
      },
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 50,
        throttlingBurstLimit: 100,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        metricsEnabled: true,
        accessLogDestination: new apigateway.LogGroupLogDestination(m2mApiLogGroup),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: true,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: true,
        }),
      },
      cloudWatchRole: false, // Reuse the role created by the main API
      endpointConfiguration: {
        types: [apigateway.EndpointType.REGIONAL],
      },
      apiKeySourceType: apigateway.ApiKeySourceType.HEADER,
    });

    // M2M proxy integration — same Lambda
    const m2mLambdaIntegration = new apigateway.LambdaIntegration(this.apiLambda, {
      proxy: true,
      allowTestInvoke: true,
    });

    // M2M root + proxy routes with API Key required
    this.m2mApi.root.addMethod("GET", m2mLambdaIntegration, {
      apiKeyRequired: true,
    });

    this.m2mApi.root.addProxy({
      defaultIntegration: m2mLambdaIntegration,
      defaultMethodOptions: {
        apiKeyRequired: true,
      },
      anyMethod: true,
    });

    // Grant M2M API Gateway permission to invoke Lambda
    this.apiLambda.addPermission("M2MApiGatewayInvoke", {
      principal: new iam.ServicePrincipal("apigateway.amazonaws.com"),
      action: "lambda:InvokeFunction",
      sourceArn: this.m2mApi.arnForExecuteApi("*"),
    });

    // Usage Plan
    const usagePlan = this.m2mApi.addUsagePlan("AgentUsagePlan", {
      name: "agent-registry-agent-plan",
      description: "Usage plan for agents accessing the registry via API Key",
      throttle: {
        rateLimit: 50,
        burstLimit: 100,
      },
      quota: {
        limit: 10000,
        period: apigateway.Period.DAY,
      },
    });

    usagePlan.addApiStage({
      stage: this.m2mApi.deploymentStage,
    });

    // API Key
    const apiKey = this.m2mApi.addApiKey("AgentRegistryApiKey", {
      apiKeyName: "agent-registry-m2m-key",
      description: "API Key for agent self-registration and discovery",
    });

    usagePlan.addApiKey(apiKey);

    // M2M CORS error responses
    this.m2mApi.addGatewayResponse("M2MDefault4XX", {
      type: apigateway.ResponseType.DEFAULT_4XX,
      responseHeaders: {
        "Access-Control-Allow-Origin": "'*'",
        "Access-Control-Allow-Headers": "'Content-Type,X-Api-Key'",
        "Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE'",
      },
    });

    this.m2mApi.addGatewayResponse("M2MDefault5XX", {
      type: apigateway.ResponseType.DEFAULT_5XX,
      responseHeaders: {
        "Access-Control-Allow-Origin": "'*'",
        "Access-Control-Allow-Headers": "'Content-Type,X-Api-Key'",
        "Access-Control-Allow-Methods": "'OPTIONS,GET,PUT,POST,DELETE'",
      },
    });

    // ========== Stack Outputs ==========

    new cdk.CfnOutput(this, "M2MApiUrl", {
      value: this.m2mApi.url,
      description: "Machine-to-Machine API URL (API Key auth)",
      exportName: `${this.stackName}-M2MApiUrl`,
    });

    new cdk.CfnOutput(this, "M2MApiKeyId", {
      value: apiKey.keyId,
      description: "API Key ID — retrieve the key value with: aws apigateway get-api-key --api-key <id> --include-value",
      exportName: `${this.stackName}-M2MApiKeyId`,
    });
    new cdk.CfnOutput(this, "ApiGatewayUrl", {
      value: this.api.url,
      description: "Agent Registry API Gateway URL",
      exportName: `${this.stackName}-ApiUrl`,
    });

    new cdk.CfnOutput(this, "ApiGatewayId", {
      value: this.api.restApiId,
      description: "Agent Registry API Gateway ID",
      exportName: `${this.stackName}-ApiId`,
    });

    // CDK-NAG Suppressions

    // Suppress warnings for S3 Vectors auto-delete custom resource (from L2 construct)
    NagSuppressions.addResourceSuppressionsByPath(
      this,
      [
        "/AgentRegistryStack/S3VectorsAutoDeleteProvider-Custom::S3VectorsAutoDeleteObjects/Role/Resource",
        "/AgentRegistryStack/S3VectorsAutoDeleteProvider-Custom::S3VectorsAutoDeleteObjects/Provider/framework-onEvent/ServiceRole/Resource",
      ],
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "S3 Vectors L2 construct auto-delete custom resource uses AWS managed policy for basic Lambda execution. This is standard CDK custom resource pattern.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          ],
        },
      ]
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryStack/S3VectorsAutoDeleteProvider-Custom::S3VectorsAutoDeleteObjects/Provider/framework-onEvent/ServiceRole/DefaultPolicy/Resource",
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "S3 Vectors auto-delete provider requires invoke permission on handler Lambda with version wildcard for custom resource framework.",
          appliesTo: [
            "Resource::<S3VectorsAutoDeleteProviderCustomS3VectorsAutoDeleteObjectsHandler5A9860AE.Arn>:*",
          ],
        },
      ]
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      [
        "/AgentRegistryStack/S3VectorsAutoDeleteProvider-Custom::S3VectorsAutoDeleteObjects/Handler/Resource",
        "/AgentRegistryStack/S3VectorsAutoDeleteProvider-Custom::S3VectorsAutoDeleteObjects/Provider/framework-onEvent/Resource",
      ],
      [
        {
          id: "AwsSolutions-L1",
          reason:
            "Lambda runtime is managed by the @cdklabs/generative-ai-cdk-constructs L2 construct. Runtime updates will come with package updates.",
        },
      ]
    );

    // Suppress warnings for Log Retention custom resource (CDK internal)
    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryStack/LogRetentionaae0aa3c5b4d4f87b02d85b201efdd8a/ServiceRole/Resource",
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "Log retention Lambda is a CDK internal construct that uses AWS managed policy for basic execution.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          ],
        },
      ]
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryStack/LogRetentionaae0aa3c5b4d4f87b02d85b201efdd8a/ServiceRole/DefaultPolicy/Resource",
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Log retention Lambda requires wildcard permissions to manage log groups across the account. This is a CDK internal construct.",
          appliesTo: ["Resource::*"],
        },
      ]
    );

    // Suppress wildcard permissions for CloudWatch Logs - scoped to specific log group
    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryStack/ApiLambdaRole/Resource",
      [
        {
          id: "AwsSolutions-IAM5",
          reason:
            "Wildcard permission needed for CloudWatch Logs stream creation. The resource is scoped to the specific log group for this Lambda function. See: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-identity-based-access-control-cwl.html",
          appliesTo: [
            {
              regex: "/Resource::arn:aws:logs:.*:.*:log-group:/aws/lambda/agent-registry-api:\\*/"
            },
          ],
        },
      ],
      true
    );

    // Suppress API Gateway security warnings - using IAM authentication
    NagSuppressions.addResourceSuppressions(
      this.api,
      [
        {
          id: "AwsSolutions-COG4",
          reason:
            "Using IAM authentication instead of Cognito for this API. IAM provides sufficient security for this internal service API.",
        },
        {
          id: "AwsSolutions-APIG3",
          reason:
            "WAF is not required for this internal API. This is a backend service API that will be accessed by authenticated AWS services.",
        },
        {
          id: "AwsSolutions-APIG4",
          reason:
            "API uses IAM authentication which provides proper authorization. All methods are protected with IAM auth.",
        },
      ],
      true
    );

    // Suppress CloudWatch role managed policy warning
    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryStack/AgentRegistryApi/CloudWatchRole/Resource",
      [
        {
          id: "AwsSolutions-IAM4",
          reason:
            "API Gateway CloudWatch role uses AWS managed policy for pushing logs. This is the standard CDK pattern for API Gateway logging.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
          ],
        },
      ]
    );

    // ========== M2M API CDK-NAG Suppressions ==========

    NagSuppressions.addResourceSuppressions(
      this.m2mApi,
      [
        {
          id: "AwsSolutions-APIG2",
          reason: "Request validation handled in Lambda. M2M API uses API Key auth with proxy integration.",
        },
        {
          id: "AwsSolutions-COG4",
          reason: "M2M API uses API Key authentication, not Cognito. Designed for agent-to-agent communication.",
        },
        {
          id: "AwsSolutions-APIG4",
          reason: "M2M API uses API Key authentication for machine-to-machine access. No IAM or Cognito auth needed.",
        },
        {
          id: "AwsSolutions-APIG3",
          reason: "WAF not required for internal PoC M2M API behind Cloudflare tunnel.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      this.m2mApi.deploymentStage,
      [
        {
          id: "AwsSolutions-APIG3",
          reason: "WAF not required for internal PoC M2M API behind Cloudflare tunnel.",
        },
      ],
      true
    );
  }
}
