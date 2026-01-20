"""
Health service for tracking agent online status
"""
from typing import Optional
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from utils.logging import get_logger
from utils.validation import ValidationError, validate_uuid

logger = get_logger(__name__)


class HealthServiceError(Exception):
    """Custom exception for health service errors"""
    def __init__(self, message: str, error_code: str = "HEALTH_SERVICE_ERROR", details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class HealthService:
    """Service for managing agent health status"""
    
    def __init__(self, vector_bucket_name: str = "agent-registry-vectors", index_name: str = "agent-embeddings"):
        """
        Initialize health service
        
        Args:
            vector_bucket_name: S3 Vectors bucket name
            index_name: S3 Vectors index name
        """
        self.vector_bucket_name = vector_bucket_name
        self.index_name = index_name
        
        # Initialize S3 Vectors client
        try:
            self.s3vectors_client = boto3.client('s3vectors')
            logger.info("Initialized S3 Vectors client for health service", bucket=vector_bucket_name, index=index_name)
        except Exception as e:
            logger.error("Failed to initialize S3 Vectors client for health service", error=str(e))
            raise HealthServiceError(f"Failed to initialize health service: {str(e)}", "INITIALIZATION_ERROR")
    
    def update_agent_health(self, agent_id: str) -> bool:
        """
        Update agent health status (last online timestamp)
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if update was successful
            
        Raises:
            ValidationError: If agent_id is invalid
            HealthServiceError: If update operation fails
        """
        logger.info("Updating agent health status", agent_id=agent_id)
        
        # Validate agent ID format
        try:
            validate_uuid(agent_id, "agent_id")
        except ValidationError as e:
            logger.warning("Invalid agent ID format for health update", agent_id=agent_id)
            raise
        
        try:
            # First, try to list vectors to find the agent by key pattern
            # This is more reliable than using query_vectors with dummy vector
            response = self.s3vectors_client.list_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.index_name,
                maxResults=1000,  # Get enough to find our agent
                returnMetadata=True,
                returnData=True  # Need vector data for put_vectors operation
            )
            
            vectors = response.get('vectors', [])
            agent_vector = None
            
            # Find the agent by agent_id in metadata
            for vector in vectors:
                metadata = vector.get('metadata', {})
                if metadata.get('agent_id') == agent_id:
                    agent_vector = vector
                    break
            
            if not agent_vector:
                logger.warning("Cannot update health for non-existent agent", agent_id=agent_id)
                raise HealthServiceError(f"Agent {agent_id} not found", "AGENT_NOT_FOUND")
            
            # Update the metadata with new timestamp
            metadata = agent_vector.get('metadata', {})
            now = datetime.now(timezone.utc)
            metadata['last_online'] = now.isoformat()
            metadata['updated_at'] = now.isoformat()
            
            # Update the vector with new metadata using put_vectors (not put_vector)
            self.s3vectors_client.put_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.index_name,
                vectors=[{
                    "key": agent_vector.get('key'),  # Use the key from the found vector
                    "data": agent_vector.get('data'),  # Keep existing vector data
                    "metadata": metadata
                }]
            )
            
            logger.info("Agent health updated successfully", agent_id=agent_id, last_online=now.isoformat())
            return True
            
        except HealthServiceError:
            # Re-raise HealthServiceError without modification
            raise
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'UNKNOWN')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Failed to update agent health in S3 Vectors", 
                        agent_id=agent_id, error_code=error_code, error_message=error_message)
            
            raise HealthServiceError(
                f"Failed to update agent health: {error_message}",
                "HEALTH_UPDATE_ERROR",
                {"agent_id": agent_id, "aws_error_code": error_code}
            )
        except Exception as e:
            logger.error("Unexpected error updating agent health", agent_id=agent_id, error=str(e))
            raise HealthServiceError(f"Unexpected error updating agent health: {str(e)}", "HEALTH_UPDATE_ERROR")
    
    def get_agent_health_status(self, agent_id: str) -> Optional[dict]:
        """
        Get agent health status information
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary with health status information or None if agent not found
            
        Raises:
            ValidationError: If agent_id is invalid
            HealthServiceError: If retrieval operation fails
        """
        logger.info("Retrieving agent health status", agent_id=agent_id)
        
        # Validate agent ID format
        try:
            validate_uuid(agent_id, "agent_id")
        except ValidationError as e:
            logger.warning("Invalid agent ID format for health status retrieval", agent_id=agent_id)
            raise
        
        try:
            # Use list_vectors to find the agent by agent_id in metadata
            response = self.s3vectors_client.list_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.index_name,
                maxResults=1000,  # Get enough to find our agent
                returnMetadata=True
            )
            
            vectors = response.get('vectors', [])
            agent_vector = None
            
            # Find the agent by agent_id in metadata
            for vector in vectors:
                metadata = vector.get('metadata', {})
                if metadata.get('agent_id') == agent_id:
                    agent_vector = vector
                    break
            
            if not agent_vector:
                logger.info("Agent not found for health status retrieval", agent_id=agent_id)
                return None
            
            # Extract health information from metadata
            metadata = agent_vector.get('metadata', {})
            
            health_status = {
                'agent_id': agent_id,
                'last_online': metadata.get('last_online'),
                'created_at': metadata.get('created_at'),
                'updated_at': metadata.get('updated_at'),
                'is_online': self._is_agent_online(metadata.get('last_online'))
            }
            
            logger.info("Agent health status retrieved successfully", agent_id=agent_id, 
                       last_online=health_status['last_online'], is_online=health_status['is_online'])
            
            return health_status
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'UNKNOWN')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error("Failed to retrieve agent health status from S3 Vectors", 
                        agent_id=agent_id, error_code=error_code, error_message=error_message)
            
            raise HealthServiceError(
                f"Failed to retrieve agent health status: {error_message}",
                "HEALTH_RETRIEVAL_ERROR",
                {"agent_id": agent_id, "aws_error_code": error_code}
            )
        except Exception as e:
            logger.error("Unexpected error retrieving agent health status", agent_id=agent_id, error=str(e))
            raise HealthServiceError(f"Unexpected error retrieving agent health status: {str(e)}", "HEALTH_RETRIEVAL_ERROR")
    
    def _is_agent_online(self, last_online: Optional[str], timeout_minutes: int = 5) -> bool:
        """
        Determine if an agent is considered online based on last_online timestamp
        
        Args:
            last_online: ISO format timestamp string
            timeout_minutes: Minutes after which agent is considered offline
            
        Returns:
            True if agent is considered online
        """
        if not last_online:
            return False
        
        try:
            last_online_dt = datetime.fromisoformat(last_online.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            time_diff = (now - last_online_dt).total_seconds() / 60  # Convert to minutes
            
            return time_diff <= timeout_minutes
        except (ValueError, TypeError):
            logger.warning("Invalid last_online timestamp format", last_online=last_online)
            return False