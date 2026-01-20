import { Construct } from "constructs";
import { CustomResource, Duration, CfnOutput } from "aws-cdk-lib";
import { Function, Runtime, Code } from "aws-cdk-lib/aws-lambda";
import { PolicyStatement, Effect } from "aws-cdk-lib/aws-iam";

export interface S3VectorsProps {
  bucketName: string;
  indexName: string;
  dimension?: number;
  distanceMetric?: "euclidean" | "cosine";
  nonFilterableMetadataKeys?: string[];
}

export class S3VectorsConstruct extends Construct {
  public readonly vectorBucketName: string;
  public readonly vectorIndexName: string;
  public readonly vectorBucketArn: string;

  constructor(scope: Construct, id: string, props: S3VectorsProps) {
    super(scope, id);

    this.vectorBucketName = props.bucketName;
    this.vectorIndexName = props.indexName;

    // Lambda function for S3 Vectors management (custom resource)
    const s3VectorsHandler = new Function(this, "S3VectorsHandler", {
      runtime: Runtime.PYTHON_3_13,
      handler: "index.handler",
      code: Code.fromInline(`
import boto3
import json
import logging
import urllib3
from urllib.parse import urlparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_response(event, context, response_status, response_data=None, physical_resource_id=None, reason=None):
    """Send response to CloudFormation"""
    response_data = response_data or {}
    physical_resource_id = physical_resource_id or context.log_stream_name
    
    response_body = {
        'Status': response_status,
        'Reason': reason or f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    logger.info(f"Sending response: {json.dumps(response_body)}")
    
    json_response_body = json.dumps(response_body)
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    try:
        http = urllib3.PoolManager()
        response = http.request(
            'PUT',
            event['ResponseURL'],
            body=json_response_body,
            headers=headers
        )
        logger.info(f"Response sent successfully. Status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response: {str(e)}")

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    s3vectors = boto3.client('s3vectors')
    physical_resource_id = None
    
    try:
        request_type = event['RequestType']
        bucket_name = event['ResourceProperties']['BucketName']
        index_name = event['ResourceProperties']['IndexName']
        dimension = int(event['ResourceProperties']['Dimension'])
        distance_metric = event['ResourceProperties']['DistanceMetric']
        non_filterable_keys = event['ResourceProperties'].get('NonFilterableMetadataKeys', [])
        
        physical_resource_id = f"{bucket_name}-{index_name}"
        
        if request_type == 'Create':
            logger.info(f"Creating vector bucket: {bucket_name}")
            
            # Create vector bucket
            bucket_response = s3vectors.create_vector_bucket(
                vectorBucketName=bucket_name,
                encryptionConfiguration={
                    'sseType': 'AES256'
                }
            )
            
            logger.info(f"Vector bucket created: {bucket_response}")
            
            # Create vector index
            index_config = {
                'vectorBucketName': bucket_name,
                'indexName': index_name,
                'dataType': 'float32',
                'dimension': dimension,
                'distanceMetric': distance_metric
            }
            
            if non_filterable_keys:
                index_config['metadataConfiguration'] = {
                    'nonFilterableMetadataKeys': non_filterable_keys
                }
            
            logger.info(f"Creating vector index with config: {index_config}")
            
            index_response = s3vectors.create_index(**index_config)
            
            logger.info(f"Vector index created: {index_response}")
            
            response_data = {
                'VectorBucketName': bucket_name,
                'VectorIndexName': index_name,
                'VectorBucketArn': bucket_response.get('vectorBucketArn', f"arn:aws:s3vectors:*:*:vector-bucket/{bucket_name}")
            }
            
            send_response(event, context, 'SUCCESS', response_data, physical_resource_id)
            
        elif request_type == 'Delete':
            logger.info(f"Deleting vector index: {index_name} from bucket: {bucket_name}")
            
            try:
                # Delete vector index first
                s3vectors.delete_index(
                    vectorBucketName=bucket_name,
                    indexName=index_name
                )
                logger.info(f"Vector index deleted: {index_name}")
            except Exception as e:
                logger.warning(f"Failed to delete vector index: {e}")
            
            try:
                # Delete vector bucket
                s3vectors.delete_vector_bucket(
                    vectorBucketName=bucket_name
                )
                logger.info(f"Vector bucket deleted: {bucket_name}")
            except Exception as e:
                logger.warning(f"Failed to delete vector bucket: {e}")
            
            send_response(event, context, 'SUCCESS', {}, physical_resource_id)
            
        elif request_type == 'Update':
            logger.info("Update operation - no changes needed for S3 Vectors")
            send_response(event, context, 'SUCCESS', {}, physical_resource_id)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        send_response(
            event, 
            context, 
            'FAILED', 
            {}, 
            physical_resource_id or 'failed-resource',
            str(e)
        )
      `),
      timeout: Duration.minutes(10),
    });

    // Add S3 Vectors permissions for custom resource management
    // Custom resource needs broader permissions for setup/teardown operations
    s3VectorsHandler.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          // Account-level operations (no specific resource)
          "s3vectors:ListVectorBuckets",
        ],
        resources: ["*"],
      })
    );

    // Add specific bucket and index permissions
    s3VectorsHandler.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          // Vector bucket operations
          "s3vectors:CreateVectorBucket",
          "s3vectors:DeleteVectorBucket", 
          "s3vectors:GetVectorBucket",
          "s3vectors:ListIndexes",
        ],
        resources: [
          `arn:aws:s3vectors:*:*:bucket/${props.bucketName}`,
        ],
      })
    );

    // Add index-specific permissions
    s3VectorsHandler.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          // Vector index operations
          "s3vectors:CreateIndex",
          "s3vectors:DeleteIndex",
          "s3vectors:GetIndex",
        ],
        resources: [
          `arn:aws:s3vectors:*:*:bucket/${props.bucketName}/index/${props.indexName}`,
        ],
      })
    );

    // Custom resource for S3 Vectors setup
    const s3VectorsResource = new CustomResource(this, "S3VectorsResource", {
      serviceToken: s3VectorsHandler.functionArn,
      properties: {
        BucketName: props.bucketName,
        IndexName: props.indexName,
        Dimension: props.dimension || 1024,
        DistanceMetric: props.distanceMetric || "cosine",
        NonFilterableMetadataKeys: props.nonFilterableMetadataKeys || [
          "raw_agent_card",
        ],
      },
    });

    // Store the ARN from the custom resource
    this.vectorBucketArn = s3VectorsResource.getAttString("VectorBucketArn");

    // Output important values
    new CfnOutput(this, "VectorBucketName", {
      value: this.vectorBucketName,
      description: "Name of the S3 Vectors bucket",
    });

    new CfnOutput(this, "VectorIndexName", {
      value: this.vectorIndexName,
      description: "Name of the S3 Vectors index",
    });

    new CfnOutput(this, "VectorBucketArn", {
      value: this.vectorBucketArn,
      description: "ARN of the S3 Vectors bucket",
    });
  }
}
