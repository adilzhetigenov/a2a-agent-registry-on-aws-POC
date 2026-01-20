"""
Unit tests for health service
"""
import json
import uuid
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from src.services.health_service import HealthService, HealthServiceError
from src.utils.validation import ValidationError


class TestHealthService:
    """Test cases for HealthService"""
    
    @pytest.fixture
    def mock_s3vectors_client(self):
        """Mock S3 Vectors client"""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_boto3.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def health_service(self, mock_s3vectors_client):
        """Health service instance with mocked dependencies"""
        return HealthService()
    
    def test_update_agent_health_success(self, health_service, mock_s3vectors_client):
        """Test successful agent health update"""
        agent_id = str(uuid.uuid4())
        
        # Mock query_vectors response with the target agent
        mock_query_response = {
            'vectors': [
                {
                    'key': f'agent-{agent_id}',
                    'data': {'float32': [0.1] * 1024},
                    'metadata': {
                        'agent_id': agent_id,
                        'name': 'Test Agent',
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-01T00:00:00Z',
                        'last_online': None
                    }
                }
            ]
        }
        
        mock_s3vectors_client.query_vectors.return_value = mock_query_response
        mock_s3vectors_client.put_vector.return_value = {}
        
        # Mock datetime to ensure consistent timestamps
        with patch('src.services.health_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Update health
            result = health_service.update_agent_health(agent_id)
        
        # Verify success
        assert result is True
        
        # Verify query_vectors was called with metadata filter
        mock_s3vectors_client.query_vectors.assert_called_once_with(
            vectorBucketName="agent-registry-vectors",
            indexName="agent-embeddings",
            queryVector={"float32": [0.0] * 1024},
            topK=1,
            filter={"agent_id": {"$eq": agent_id}},
            returnDistance=False,
            returnMetadata=True
        )
        
        # Verify put_vector was called with updated metadata
        mock_s3vectors_client.put_vector.assert_called_once()
        call_args = mock_s3vectors_client.put_vector.call_args
        
        updated_metadata = call_args[1]['metadata']
        assert updated_metadata['last_online'] == '2024-01-02T12:00:00+00:00'
        assert updated_metadata['updated_at'] == '2024-01-02T12:00:00+00:00'
    
    def test_update_agent_health_not_found(self, health_service, mock_s3vectors_client):
        """Test health update for non-existent agent"""
        agent_id = str(uuid.uuid4())
        
        # Mock query_vectors response with no matching agent
        mock_query_response = {
            'vectors': []  # Empty list means agent not found
        }
        mock_s3vectors_client.query_vectors.return_value = mock_query_response
        
        with pytest.raises(HealthServiceError) as exc_info:
            health_service.update_agent_health(agent_id)
        
        assert exc_info.value.error_code == "AGENT_NOT_FOUND"
    
    def test_update_agent_health_invalid_id(self, health_service):
        """Test health update with invalid agent ID"""
        with pytest.raises(ValidationError) as exc_info:
            health_service.update_agent_health("invalid-uuid")
        
        assert exc_info.value.field == "agent_id"
    
    def test_get_agent_health_status_success(self, health_service, mock_s3vectors_client):
        """Test successful agent health status retrieval"""
        agent_id = str(uuid.uuid4())
        
        # Mock query_vectors response with the target agent
        mock_query_response = {
            'vectors': [
                {
                    'key': f'agent-{agent_id}',
                    'metadata': {
                        'agent_id': agent_id,
                        'name': 'Test Agent',
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-02T12:00:00Z',
                        'last_online': '2024-01-02T12:00:00Z'
                    }
                }
            ]
        }
        
        mock_s3vectors_client.query_vectors.return_value = mock_query_response
        
        # Mock datetime for online status calculation
        with patch('src.services.health_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 2, 12, 3, 0, tzinfo=timezone.utc)  # 3 minutes later
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
            
            # Get health status
            result = health_service.get_agent_health_status(agent_id)
        
        # Verify result
        assert result is not None
        assert result['agent_id'] == agent_id
        assert result['last_online'] == '2024-01-02T12:00:00Z'
        assert result['created_at'] == '2024-01-01T00:00:00Z'
        assert result['updated_at'] == '2024-01-02T12:00:00Z'
        assert result['is_online'] is True  # Within 5-minute timeout
    
    def test_get_agent_health_status_not_found(self, health_service, mock_s3vectors_client):
        """Test health status retrieval for non-existent agent"""
        agent_id = str(uuid.uuid4())
        
        # Mock query_vectors response with no matching agent
        mock_query_response = {
            'vectors': []  # Empty list means agent not found
        }
        mock_s3vectors_client.query_vectors.return_value = mock_query_response
        
        result = health_service.get_agent_health_status(agent_id)
        
        assert result is None
    
    def test_is_agent_online_within_timeout(self, health_service):
        """Test agent online status within timeout"""
        # Mock current time
        with patch('src.services.health_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 2, 12, 3, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
            
            # Test with timestamp 3 minutes ago (within 5-minute timeout)
            last_online = '2024-01-02T12:00:00+00:00'
            result = health_service._is_agent_online(last_online)
            
            assert result is True
    
    def test_is_agent_online_outside_timeout(self, health_service):
        """Test agent online status outside timeout"""
        # Mock current time
        with patch('src.services.health_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 2, 12, 10, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
            
            # Test with timestamp 10 minutes ago (outside 5-minute timeout)
            last_online = '2024-01-02T12:00:00+00:00'
            result = health_service._is_agent_online(last_online)
            
            assert result is False
    
    def test_is_agent_online_no_timestamp(self, health_service):
        """Test agent online status with no timestamp"""
        result = health_service._is_agent_online(None)
        assert result is False
        
        result = health_service._is_agent_online("")
        assert result is False
    
    def test_is_agent_online_invalid_timestamp(self, health_service):
        """Test agent online status with invalid timestamp"""
        result = health_service._is_agent_online("invalid-timestamp")
        assert result is False