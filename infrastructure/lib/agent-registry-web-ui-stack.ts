import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as logs from "aws-cdk-lib/aws-logs";

import { NagSuppressions } from "cdk-nag";

export interface AgentRegistryWebUIProps extends cdk.StackProps {}

export class AgentRegistryWebUI extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;
  public readonly identityPool: cognito.CfnIdentityPool;
  public readonly bucket: s3.Bucket;
  public readonly webApi: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: AgentRegistryWebUIProps) {
    super(scope, id, props);

    // Create S3 bucket for storing the React app (private, accessed only by Lambda)
    this.bucket = new s3.Bucket(this, "WebUIBucket", {
      bucketName: `agent-registry-web-ui-${this.account}-${this.region}`,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      accessControl: s3.BucketAccessControl.PRIVATE,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    // Lambda function to serve static files from S3
    const webServerFunction = new lambda.Function(this, "WebServerFunction", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.handler",
      code: lambda.Code.fromInline(`
import json
import boto3
import base64
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']

CONTENT_TYPES = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.map': 'application/json',
}

BINARY_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf'}

def get_content_type(key):
    for ext, ct in CONTENT_TYPES.items():
        if key.endswith(ext):
            return ct, ext in BINARY_TYPES
    return 'application/octet-stream', True

def handler(event, context):
    path = event.get('path', '/')
    
    # Strip leading slash
    key = path.lstrip('/')
    
    # Default to index.html
    if not key or key.endswith('/'):
        key = key + 'index.html'
    
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        body = response['Body'].read()
        content_type, is_binary = get_content_type(key)
        
        if is_binary:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=31536000' if not key.endswith('.html') else 'no-cache',
                },
                'body': base64.b64encode(body).decode('utf-8'),
                'isBase64Encoded': True,
            }
        else:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=31536000' if not key.endswith('.html') else 'no-cache',
                },
                'body': body.decode('utf-8'),
                'isBase64Encoded': False,
            }
    except s3_client.exceptions.NoSuchKey:
        # SPA fallback: serve index.html for any path not found
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key='index.html')
            body = response['Body'].read()
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/html',
                    'Cache-Control': 'no-cache',
                },
                'body': body.decode('utf-8'),
                'isBase64Encoded': False,
            }
        except Exception as e:
            logger.error(f'Error serving index.html fallback: {e}')
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'text/html'},
                'body': '<html><body><h1>Not Found</h1></body></html>',
            }
    except Exception as e:
        logger.error(f'Error serving {key}: {e}')
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': '<html><body><h1>Internal Server Error</h1></body></html>',
        }
`),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    // Grant the Lambda read access to the S3 bucket
    this.bucket.grantRead(webServerFunction);

    // Create API Gateway to serve the static site
    const webApiLogGroup = new logs.LogGroup(this, "WebApiAccessLogs", {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.webApi = new apigateway.RestApi(this, "WebUIApi", {
      restApiName: "agent-registry-web-ui",
      description: "Serves the Agent Registry Web UI static files from S3 via Lambda",
      binaryMediaTypes: [
        "image/*",
        "font/*",
        "application/octet-stream",
      ],
      deployOptions: {
        stageName: "ui",
        accessLogDestination: new apigateway.LogGroupLogDestination(webApiLogGroup),
        accessLogFormat: apigateway.AccessLogFormat.clf(),
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
      },
      cloudWatchRole: true,
      endpointTypes: [apigateway.EndpointType.REGIONAL],
    });

    // Root resource -> Lambda
    this.webApi.root.addMethod(
      "GET",
      new apigateway.LambdaIntegration(webServerFunction)
    );

    // Proxy resource {proxy+} -> Lambda (catches all paths)
    const proxyResource = this.webApi.root.addResource("{proxy+}");
    proxyResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(webServerFunction)
    );

    const webUiBaseUrl = this.webApi.url.replace(/\/$/, "");
    // window.location.origin in the browser won't include the /ui stage path
    const webUiOrigin = `https://${this.webApi.restApiId}.execute-api.${this.region}.amazonaws.com`;

    // Create Cognito User Pool with self-signup disabled
    this.userPool = new cognito.UserPool(this, "UserPool", {
      userPoolName: "agent-registry-users",
      selfSignUpEnabled: false,
      signInAliases: { email: true, username: true },
      autoVerify: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
        givenName: { required: true, mutable: true },
        familyName: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create User Pool Client
    this.userPoolClient = new cognito.UserPoolClient(this, "UserPoolClient", {
      userPool: this.userPool,
      userPoolClientName: "agent-registry-web-client",
      generateSecret: false,
      authFlows: {
        userSrp: true,
        userPassword: false,
        adminUserPassword: false,
        custom: false,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true, implicitCodeGrant: false },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          webUiBaseUrl,
          `${webUiBaseUrl}/`,
          webUiOrigin,
          `${webUiOrigin}/`,
          "http://localhost:3000",
          "http://localhost:3000/",
        ],
        logoutUrls: [
          webUiBaseUrl,
          `${webUiBaseUrl}/`,
          webUiOrigin,
          `${webUiOrigin}/`,
          "http://localhost:3000",
          "http://localhost:3000/",
        ],
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
      refreshTokenValidity: cdk.Duration.days(30),
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      preventUserExistenceErrors: true,
    });

    // Cognito User Pool Domain
    const domainPrefix = `agent-registry-${cdk.Names.uniqueId(this)
      .toLowerCase()
      .substring(0, 8)}`;
    const userPoolDomain = new cognito.UserPoolDomain(this, "UserPoolDomain", {
      userPool: this.userPool,
      cognitoDomain: { domainPrefix },
    });

    // Cognito Identity Pool
    this.identityPool = new cognito.CfnIdentityPool(this, "IdentityPool", {
      identityPoolName: "agent-registry-identity-pool",
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [
        {
          clientId: this.userPoolClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
        },
      ],
    });

    // Import values from the AgentRegistry stack
    const apiGatewayId = cdk.Fn.importValue("AgentRegistryStack-ApiId");
    const apiGatewayUrl = cdk.Fn.importValue("AgentRegistryStack-ApiUrl");

    // IAM role for authenticated users
    const authenticatedRole = new iam.Role(this, "AuthenticatedRole", {
      assumedBy: new iam.FederatedPrincipal(
        "cognito-identity.amazonaws.com",
        {
          StringEquals: {
            "cognito-identity.amazonaws.com:aud": this.identityPool.ref,
          },
          "ForAnyValue:StringLike": {
            "cognito-identity.amazonaws.com:amr": "authenticated",
          },
        },
        "sts:AssumeRoleWithWebIdentity"
      ),
      description: "IAM role for authenticated Cognito users - Agent Registry API access only",
      inlinePolicies: {
        AgentRegistryApiAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["execute-api:Invoke"],
              resources: [
                `arn:aws:execute-api:${this.region}:${this.account}:${apiGatewayId}/*/*`,
              ],
            }),
          ],
        }),
      },
    });

    new cognito.CfnIdentityPoolRoleAttachment(
      this,
      "IdentityPoolRoleAttachment",
      {
        identityPoolId: this.identityPool.ref,
        roles: { authenticated: authenticatedRole.roleArn },
      }
    );

    // Deploy the React app to S3
    const webUIDeployment = new s3deploy.BucketDeployment(
      this,
      "WebUIDeployment",
      {
        sources: [s3deploy.Source.asset("../web-ui/build")],
        destinationBucket: this.bucket,
        prune: true,
      }
    );

    // Lambda to generate and upload aws-config.js
    const configGeneratorFunction = new lambda.Function(
      this,
      "ConfigGenerator",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: "index.handler",
        code: lambda.Code.fromInline(`
import json
import boto3
import cfnresponse
import logging
import hashlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(json.dumps(event, indent=2, default=str))
    response_data = {}
    try:
        s3_client = boto3.client('s3')
        request_type = event['RequestType']
        resource_props = event.get('ResourceProperties', {})
        config_data = {
            'Region': resource_props.get('Region'),
            'UserPoolId': resource_props.get('UserPoolId'),
            'UserPoolClientId': resource_props.get('UserPoolClientId'),
            'IdentityPoolId': resource_props.get('IdentityPoolId'),
            'ApiGatewayUrl': resource_props.get('ApiGatewayUrl'),
            'CognitoDomain': resource_props.get('CognitoDomain'),
            'Version': resource_props.get('Version')
        }
        config_string = json.dumps(config_data, sort_keys=True)
        deployment_hash = hashlib.sha256(config_string.encode()).hexdigest()[:16]
        physical_resource_id = f"ConfigGenerator-{deployment_hash}"
        response_data['DeploymentHash'] = deployment_hash

        if request_type == 'Delete':
            logger.info('Delete request - config file preserved')
            cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_resource_id)
            return

        config_content = f"""window.AWS_CONFIG = {{
  region: "{resource_props.get('Region')}",
  userPoolId: "{resource_props.get('UserPoolId')}",
  userPoolWebClientId: "{resource_props.get('UserPoolClientId')}",
  identityPoolId: "{resource_props.get('IdentityPoolId')}",
  apiGatewayUrl: "{resource_props.get('ApiGatewayUrl')}",
  cognitoDomain: "{resource_props.get('CognitoDomain')}"
}};
"""
        s3_client.put_object(
            Bucket=resource_props.get('BucketName'),
            Key='aws-config.js',
            Body=config_content,
            ContentType='application/javascript',
            CacheControl='no-cache'
        )
        logger.info(f'Config file {request_type.lower()}d successfully')
        response_data['Message'] = f'Config file {request_type.lower()}d successfully'
        cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_resource_id)
    except Exception as e:
        logger.error(f'Error: {e}')
        response_data['Error'] = str(e)
        fallback_id = f"ConfigGenerator-{context.aws_request_id[:16]}"
        cfnresponse.send(event, context, cfnresponse.FAILED, response_data, fallback_id)
`),
        timeout: cdk.Duration.minutes(5),
      }
    );

    this.bucket.grantWrite(configGeneratorFunction);

    const configGeneratorResource = new cdk.CustomResource(
      this,
      "ConfigGeneratorResourceV5",
      {
        serviceToken: configGeneratorFunction.functionArn,
        properties: {
          BucketName: this.bucket.bucketName,
          Region: this.region,
          UserPoolId: this.userPool.userPoolId,
          UserPoolClientId: this.userPoolClient.userPoolClientId,
          IdentityPoolId: this.identityPool.ref,
          ApiGatewayUrl: apiGatewayUrl,
          CognitoDomain: `${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com`,
          Version: "5.0",
          DeploymentTimestamp: Date.now().toString(),
        },
      }
    );
    configGeneratorResource.node.addDependency(webUIDeployment);

    // Stack outputs
    new cdk.CfnOutput(this, "WebUIUrl", {
      value: webUiBaseUrl,
      description: "Web UI URL (API Gateway)",
    });

    new cdk.CfnOutput(this, "CognitoUserPoolConsoleUrl", {
      value: `https://${this.region}.console.aws.amazon.com/cognito/v2/idp/user-pools/${this.userPool.userPoolId}/users?region=${this.region}`,
      description: "Cognito User Pool console URL - use this to add users for Web UI login",
    });

    // ========== CDK-NAG Suppressions ==========

    NagSuppressions.addResourceSuppressions(
      authenticatedRole,
      [
        {
          id: "AwsSolutions-IAM5",
          reason: "Wildcard needed for API Gateway paths/methods, scoped to specific API.",
          appliesTo: [
            {
              regex: "/Resource::arn:aws:execute-api:.*:.*:AgentRegistryStack-ApiId\\/\\*\\/\\*/",
            },
          ],
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      this.bucket,
      [
        {
          id: "AwsSolutions-S1",
          reason: "Access logging not required for static asset bucket in PoC. API Gateway access logs are enabled.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      this.userPool,
      [
        {
          id: "AwsSolutions-COG2",
          reason: "MFA not enforced for internal PoC application.",
        },
        {
          id: "AwsSolutions-COG3",
          reason: "Advanced Security Mode requires Cognito Plus plan. Not needed for PoC.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      this.webApi,
      [
        {
          id: "AwsSolutions-APIG2",
          reason: "Request validation not needed for static file serving API Gateway.",
        },
        {
          id: "AwsSolutions-IAM4",
          reason: "API Gateway CloudWatch role uses AWS managed policy.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
          ],
        },
      ],
      true
    );

    // Suppress on the deployment stage
    NagSuppressions.addResourceSuppressions(
      this.webApi.deploymentStage,
      [
        {
          id: "AwsSolutions-APIG3",
          reason: "WAF not required for internal PoC serving static content behind Cognito auth.",
        },
      ],
      true
    );

    // Suppress method-level auth warnings (static file serving, no IAM auth needed)
    NagSuppressions.addResourceSuppressions(
      this.webApi,
      [
        {
          id: "AwsSolutions-APIG4",
          reason: "Static file serving API does not require authorization. App-level auth is handled by Cognito in the SPA.",
        },
        {
          id: "AwsSolutions-COG4",
          reason: "Static file serving API does not use Cognito authorizer. Auth is handled client-side in the SPA.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      webServerFunction,
      [
        {
          id: "AwsSolutions-IAM4",
          reason: "Lambda uses AWS managed policy for basic execution.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          ],
        },
        {
          id: "AwsSolutions-L1",
          reason: "Using Python 3.12, latest stable Lambda runtime.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressions(
      configGeneratorFunction,
      [
        {
          id: "AwsSolutions-IAM4",
          reason: "Lambda uses AWS managed policy for basic execution.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          ],
        },
        {
          id: "AwsSolutions-L1",
          reason: "Using Python 3.12, latest stable Lambda runtime.",
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryWebUI/WebServerFunction/ServiceRole/DefaultPolicy",
      [
        {
          id: "AwsSolutions-IAM5",
          reason: "Lambda needs S3 read on all objects in the web UI bucket.",
          appliesTo: [
            "Action::s3:GetBucket*",
            "Action::s3:GetObject*",
            "Action::s3:List*",
            "Resource::<WebUIBucketF5DEB462.Arn>/*",
          ],
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryWebUI/ConfigGenerator/ServiceRole/DefaultPolicy",
      [
        {
          id: "AwsSolutions-IAM5",
          reason: "Lambda needs S3 write to upload config file.",
          appliesTo: [
            "Action::s3:Abort*",
            "Action::s3:DeleteObject*",
            "Resource::<WebUIBucketF5DEB462.Arn>/*",
          ],
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryWebUI/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole",
      [
        {
          id: "AwsSolutions-IAM4",
          reason: "CDK BucketDeployment custom resource requires AWSLambdaBasicExecutionRole.",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
          ],
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryWebUI/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/DefaultPolicy",
      [
        {
          id: "AwsSolutions-IAM5",
          reason: "CDK BucketDeployment needs wildcard S3 permissions for deployment.",
          appliesTo: [
            "Action::s3:GetBucket*",
            "Action::s3:GetObject*",
            "Action::s3:List*",
            "Action::s3:Abort*",
            "Action::s3:DeleteObject*",
            "Resource::*",
            {
              regex: "/Resource::arn:.*:s3:::cdk-hnb659fds-assets-.*-.*/",
            },
            "Resource::<WebUIBucketF5DEB462.Arn>/*",
          ],
        },
      ],
      true
    );

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      "/AgentRegistryWebUI/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C",
      [
        {
          id: "AwsSolutions-L1",
          reason: "CDK BucketDeployment runtime is managed by CDK framework.",
        },
      ],
      true
    );
  }
}
