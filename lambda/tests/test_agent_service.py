"""
Unit tests for agent service
"""
import json
import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from src.services.agent_service import AgentService, AgentServiceError
from src.utils.validation import ValidationError


class TestAgentService:
    """Test cases for AgentService"""
    
    @pytest.fixture
    def mock_s3vectors_client(self):
        """Mock S3 Vectors client"""
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_boto3.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        with patch('src.services.agent_service.EmbeddingService') as mock_embedding_service_class:
            mock_embedding_service = Mock()
            mock_embedding_service_class.return_value = mock_embedding_service
            # Default to successful embedding generation
            mock_embedding_service.generate_embedding.return_value = [0.1] * 1024
            yield mock_embedding_service

    @pytest.fixture
    def agent_service(self, mock_s3vectors_client, mock_embedding_service):
        """Agent service instance with mocked dependencies"""
        with patch('src.services.agent_service.HealthService') as mock_health_service_class:
            mock_health_service = Mock()
            mock_health_service_class.return_value = mock_health_service
            service = AgentService()
            service.health_service = mock_health_service  # Override the health service
            service.embedding_service = mock_embedding_service  # Override the embedding service
            return service
    
    @pytest.fixture
    def valid_agent_data(self):
        """Valid agent card data for testing"""
        return {
            "name": "Test Agent",
            "description": "A test agent for unit testing purposes",
            "provider": "Test Provider",
            "version": "1.0.0",
            "skills": ["testing", "automation"]
        }
    
    @pytest.fixture
    def invalid_agent_data(self):
        """Invalid agent card data for testing"""
        return {
            "name": "",  # Invalid: empty name
            "description": "Short",  # Invalid: too short
            "provider": "Test Provider"
        }
    
    def test_init_success(self, mock_s3vectors_client):
        """Test successful initialization"""
        service = AgentService()
        
        assert service.vector_bucket_name == "agent-registry-vectors"
        assert service.index_name == "agent-embeddings"
        assert service.s3vectors_client is not None
    
    def test_init_with_custom_params(self, mock_s3vectors_client):
        """Test initialization with custom parameters"""
        service = AgentService("custom-bucket", "custom-index")
        
        assert service.vector_bucket_name == "custom-bucket"
        assert service.index_name == "custom-index"
    
    def test_init_client_error(self):
        """Test initialization failure when S3 Vectors client fails"""
        with patch('boto3.client', side_effect=Exception("Client initialization failed")):
            with pytest.raises(AgentServiceError) as exc_info:
                AgentService()
            
            assert exc_info.value.error_code == "INITIALIZATION_ERROR"
            assert "Failed to initialize S3 Vectors client" in exc_info.value.message
    
    def test_create_agent_success(self, agent_service, mock_s3vectors_client, mock_embedding_service, valid_agent_data):
        """Test successful agent creation"""
        # Mock successful S3 Vectors put_vectors call
        mock_s3vectors_client.put_vectors.return_value = {}
        
        # Create agent
        agent_id = agent_service.create_agent(valid_agent_data)
        
        # Verify agent ID is a valid UUID
        assert uuid.UUID(agent_id)
        
        # Verify embedding service was called
        mock_embedding_service.generate_embedding.assert_called_once()
        
        # Verify S3 Vectors put_vectors was called correctly
        mock_s3vectors_client.put_vectors.assert_called_once()
        call_args = mock_s3vectors_client.put_vectors.call_args
        
        assert call_args[1]['vectorBucketName'] == "agent-registry-vectors"
        assert call_args[1]['indexName'] == "agent-embeddings"
        
        # Verify vector data structure
        vectors = call_args[1]['vectors']
        assert len(vectors) == 1
        vector = vectors[0]
        assert vector['key'] == f"agent-{agent_id}"
        
        # Verify vector data (from mocked embedding service)
        vector_data = vector['data']
        assert 'float32' in vector_data
        assert len(vector_data['float32']) == 1024
        assert all(v == 0.1 for v in vector_data['float32'])  # From mock
        
        # Verify metadata
        metadata = vector['metadata']
        assert metadata['agent_id'] == agent_id
        assert metadata['name'] == valid_agent_data['name']
        assert metadata['description'] == valid_agent_data['description']
        assert metadata['skills'] == json.dumps(valid_agent_data['skills'])
        assert metadata['version'] == valid_agent_data['version']
        assert 'created_at' in metadata
        assert 'updated_at' in metadata
        assert metadata['last_online'] == ""
        
        # Verify raw agent card is stored
        raw_agent_card = json.loads(metadata['raw_agent_card'])
        # Remove provider from comparison as it's not in the current schema
        expected_data = {k: v for k, v in valid_agent_data.items() if k != 'provider'}
        assert raw_agent_card == expected_data
    
    def test_create_agent_validation_error(self, agent_service, invalid_agent_data):
        """Test agent creation with invalid data"""
        with pytest.raises(ValidationError) as exc_info:
            agent_service.create_agent(invalid_agent_data)
        
        # Should fail on name validation
        assert exc_info.value.field == "name"

    def test_create_agent_embedding_error(self, agent_service, mock_s3vectors_client, mock_embedding_service, valid_agent_data):
        """Test agent creation with embedding generation error"""
        from src.services.embedding_service import EmbeddingServiceError
        
        # Mock embedding service to raise error
        mock_embedding_service.generate_embedding.side_effect = EmbeddingServiceError("Failed to generate embedding")
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.create_agent(valid_agent_data)
        
        # Should fail with embedding generation error
        assert exc_info.value.error_code == "EMBEDDING_GENERATION_ERROR"
        assert "Failed to generate embedding for agent" in exc_info.value.message
        
        # Verify S3 Vectors put_vectors was NOT called
        mock_s3vectors_client.put_vectors.assert_not_called()
    
    def test_create_agent_storage_error(self, agent_service, mock_s3vectors_client, mock_embedding_service, valid_agent_data):
        """Test agent creation with S3 Vectors storage error"""
        # Mock S3 Vectors client error
        error_response = {
            'Error': {
                'Code': 'InternalError',
                'Message': 'Internal server error'
            }
        }
        mock_s3vectors_client.put_vectors.side_effect = ClientError(error_response, 'PutVectors')
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.create_agent(valid_agent_data)
        
        assert exc_info.value.error_code == "STORAGE_ERROR"
        assert "Failed to store agent" in exc_info.value.message
    
    def test_get_agent_success(self, agent_service, mock_s3vectors_client, valid_agent_data):
        """Test successful agent retrieval"""
        agent_id = str(uuid.uuid4())
        
        # Mock S3 Vectors response
        mock_response = {
            'data': {'float32': [0.1] * 1024},
            'metadata': {
                'agent_id': agent_id,
                'name': valid_agent_data['name'],
                'description': valid_agent_data['description'],
                'provider': valid_agent_data['provider'],
                'skills': valid_agent_data['skills'],
                'version': valid_agent_data['version'],
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z',
                'last_online': None,
                'raw_agent_card': json.dumps(valid_agent_data)
            }
        }
        mock_s3vectors_client.get_vector.return_value = mock_response
        
        # Get agent
        result = agent_service.get_agent(agent_id)
        
        # Verify result
        assert result == valid_agent_data
        
        # Verify S3 Vectors get_vector was called correctly
        mock_s3vectors_client.get_vector.assert_called_once_with(
            vectorBucketName="agent-registry-vectors",
            indexName="agent-embeddings",
            key=f"agent-{agent_id}"
        )
    
    def test_get_agent_not_found(self, agent_service, mock_s3vectors_client):
        """Test agent retrieval when agent doesn't exist"""
        agent_id = str(uuid.uuid4())
        
        # Mock S3 Vectors not found error
        error_response = {
            'Error': {
                'Code': 'NoSuchKey',
                'Message': 'The specified key does not exist'
            }
        }
        mock_s3vectors_client.get_vector.side_effect = ClientError(error_response, 'GetVector')
        
        # Get agent
        result = agent_service.get_agent(agent_id)
        
        # Should return None for not found
        assert result is None
    
    def test_get_agent_invalid_id(self, agent_service):
        """Test agent retrieval with invalid agent ID"""
        with pytest.raises(ValidationError) as exc_info:
            agent_service.get_agent("invalid-uuid")
        
        assert exc_info.value.field == "agent_id"
    
    def test_get_agent_corrupted_data(self, agent_service, mock_s3vectors_client):
        """Test agent retrieval with corrupted stored data"""
        agent_id = str(uuid.uuid4())
        
        # Mock S3 Vectors response with corrupted JSON
        mock_response = {
            'data': {'float32': [0.1] * 1024},
            'metadata': {
                'agent_id': agent_id,
                'raw_agent_card': 'invalid-json{'
            }
        }
        mock_s3vectors_client.get_vector.return_value = mock_response
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.get_agent(agent_id)
        
        assert exc_info.value.error_code == "DATA_CORRUPTION_ERROR"
    
    def test_list_agents_success(self, agent_service, mock_s3vectors_client, valid_agent_data):
        """Test successful agent listing"""
        # Mock S3 Vectors response with multiple agents
        mock_vectors = []
        for i in range(3):
            agent_id = str(uuid.uuid4())
            mock_vectors.append({
                'key': f'agent-{agent_id}',
                'metadata': {
                    'agent_id': agent_id,
                    'name': f'Agent {i}',
                    'created_at': f'2024-01-0{i+1}T00:00:00Z',
                    'raw_agent_card': json.dumps({
                        **valid_agent_data,
                        'name': f'Agent {i}'
                    })
                }
            })
        
        mock_s3vectors_client.list_vectors.return_value = {
            'vectors': mock_vectors
        }
        
        # List agents
        result = agent_service.list_agents(limit=10, offset=0)
        
        # Verify result structure
        assert 'agents' in result
        assert 'pagination' in result
        assert len(result['agents']) == 3
        assert result['pagination']['limit'] == 10
        assert result['pagination']['offset'] == 0
        assert result['pagination']['total'] == 3
        assert result['pagination']['has_more'] is False
        
        # Verify agents are sorted by creation date (newest first)
        agent_names = [agent['name'] for agent in result['agents']]
        assert agent_names == ['Agent 2', 'Agent 1', 'Agent 0']
    
    def test_list_agents_pagination(self, agent_service, mock_s3vectors_client, valid_agent_data):
        """Test agent listing with pagination"""
        # Mock S3 Vectors response with 5 agents
        mock_vectors = []
        for i in range(5):
            agent_id = str(uuid.uuid4())
            mock_vectors.append({
                'key': f'agent-{agent_id}',
                'metadata': {
                    'agent_id': agent_id,
                    'name': f'Agent {i}',
                    'created_at': f'2024-01-0{i+1}T00:00:00Z',
                    'raw_agent_card': json.dumps({
                        **valid_agent_data,
                        'name': f'Agent {i}'
                    })
                }
            })
        
        mock_s3vectors_client.list_vectors.return_value = {
            'vectors': mock_vectors
        }
        
        # List agents with pagination
        result = agent_service.list_agents(limit=2, offset=1)
        
        # Verify pagination
        assert len(result['agents']) == 2
        assert result['pagination']['limit'] == 2
        assert result['pagination']['offset'] == 1
        assert result['pagination']['total'] == 5
        assert result['pagination']['has_more'] is True
        
        # Verify correct agents returned (should skip first agent)
        agent_names = [agent['name'] for agent in result['agents']]
        assert agent_names == ['Agent 3', 'Agent 2']
    
    def test_list_agents_empty(self, agent_service, mock_s3vectors_client):
        """Test agent listing when no agents exist"""
        mock_s3vectors_client.list_vectors.return_value = {
            'vectors': []
        }
        
        result = agent_service.list_agents()
        
        assert result['agents'] == []
        assert result['pagination']['total'] == 0
        assert result['pagination']['has_more'] is False
    
    def test_list_agents_storage_error(self, agent_service, mock_s3vectors_client):
        """Test agent listing with S3 Vectors error"""
        error_response = {
            'Error': {
                'Code': 'InternalError',
                'Message': 'Internal server error'
            }
        }
        mock_s3vectors_client.list_vectors.side_effect = ClientError(error_response, 'ListVectors')
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.list_agents()
        
        assert exc_info.value.error_code == "LISTING_ERROR"
    
    def test_update_agent_health_success(self, agent_service, mock_s3vectors_client, valid_agent_data):
        """Test successful agent health update"""
        agent_id = str(uuid.uuid4())
        
        # Mock the health service (already mocked in fixture)
        agent_service.health_service.update_agent_health.return_value = True
        
        # Update health
        result = agent_service.update_agent_health(agent_id)
        
        # Verify success
        assert result is True
        
        # Verify health service was called correctly
        agent_service.health_service.update_agent_health.assert_called_once_with(agent_id)
    
    def test_update_agent_health_not_found(self, agent_service, mock_s3vectors_client):
        """Test health update for non-existent agent"""
        agent_id = str(uuid.uuid4())
        
        # Mock the health service to raise AGENT_NOT_FOUND error
        from src.services.health_service import HealthServiceError
        agent_service.health_service.update_agent_health.side_effect = HealthServiceError(
            f"Agent {agent_id} not found", "AGENT_NOT_FOUND"
        )
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.update_agent_health(agent_id)
        
        assert exc_info.value.error_code == "AGENT_NOT_FOUND"
    
    def test_update_agent_health_invalid_id(self, agent_service):
        """Test health update with invalid agent ID"""
        # Mock the health service to raise ValidationError
        from src.utils.validation import ValidationError
        agent_service.health_service.update_agent_health.side_effect = ValidationError(
            "agent_id", "Invalid UUID format"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            agent_service.update_agent_health("invalid-uuid")
        
        assert exc_info.value.field == "agent_id"
    
    def test_update_agent_health_storage_error(self, agent_service, mock_s3vectors_client, valid_agent_data):
        """Test health update with S3 Vectors storage error"""
        agent_id = str(uuid.uuid4())
        
        # Mock the health service to raise HEALTH_UPDATE_ERROR
        from src.services.health_service import HealthServiceError
        agent_service.health_service.update_agent_health.side_effect = HealthServiceError(
            "Failed to update agent health: Internal server error", 
            "HEALTH_UPDATE_ERROR",
            {"agent_id": agent_id, "aws_error_code": "InternalError"}
        )
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.update_agent_health(agent_id)
        
        assert exc_info.value.error_code == "HEALTH_UPDATE_ERROR"
    
    def test_update_agent_success(self, agent_service, mock_s3vectors_client, mock_embedding_service, valid_agent_data):
        """Test successful agent update"""
        agent_id = str(uuid.uuid4())
        
        # Mock existing agent data
        existing_agent = {
            "name": "Original Agent",
            "description": "Original description for testing",
            "version": "1.0.0",
            "url": "https://example.com/original",
            "skills": ["python", "testing"],
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        # Mock get_agent to return existing agent
        agent_service.get_agent = Mock(return_value=existing_agent)
        
        # Mock S3 Vectors list_vectors for retrieving existing embedding
        mock_s3vectors_client.list_vectors.return_value = {
            'vectors': [{
                'key': f'agent-{agent_id}',
                'data': {'float32': [0.1] * 1024},
                'metadata': {'agent_id': agent_id}
            }]
        }
        
        # Mock successful S3 Vectors put_vectors call
        mock_s3vectors_client.put_vectors.return_value = {}
        
        # Update data (partial update)
        update_data = {
            "name": "Updated Agent Name",
            "description": "Updated description for the agent"
        }
        
        # Update agent
        result = agent_service.update_agent(agent_id, update_data)
        
        # Verify success
        assert result is True
        
        # Verify get_agent was called to fetch existing data
        agent_service.get_agent.assert_called_once_with(agent_id)
        
        # Verify embedding service was called (name/description changed)
        mock_embedding_service.generate_embedding.assert_called_once()
        
        # Verify S3 Vectors put_vectors was called correctly
        mock_s3vectors_client.put_vectors.assert_called_once()
        call_args = mock_s3vectors_client.put_vectors.call_args
        
        assert call_args[1]['vectorBucketName'] == "agent-registry-vectors"
        assert call_args[1]['indexName'] == "agent-embeddings"
        
        # Verify vector data structure
        vectors = call_args[1]['vectors']
        assert len(vectors) == 1
        vector = vectors[0]
        assert vector['key'] == f"agent-{agent_id}"
        
        # Verify metadata contains updated values
        metadata = vector['metadata']
        assert metadata['agent_id'] == agent_id
        assert metadata['name'] == "Updated Agent Name"
        assert metadata['description'] == "Updated description for the agent"
        assert metadata['version'] == "1.0.0"  # Preserved from original
        assert metadata['created_at'] == "2024-01-01T00:00:00Z"  # Preserved
        assert 'updated_at' in metadata  # Should be updated
    
    def test_update_agent_no_embedding_regeneration(self, agent_service, mock_s3vectors_client, mock_embedding_service, valid_agent_data):
        """Test agent update without name/description change (no embedding regeneration)"""
        agent_id = str(uuid.uuid4())
        
        # Mock existing agent data
        existing_agent = {
            "name": "Test Agent",
            "description": "Test description",
            "version": "1.0.0",
            "url": "https://example.com/original",
            "skills": ["python", "testing"],
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        # Mock get_agent to return existing agent
        agent_service.get_agent = Mock(return_value=existing_agent)
        
        # Mock S3 Vectors list_vectors for retrieving existing embedding
        existing_embedding = [0.2] * 1024
        mock_s3vectors_client.list_vectors.return_value = {
            'vectors': [{
                'key': f'agent-{agent_id}',
                'data': {'float32': existing_embedding},
                'metadata': {'agent_id': agent_id}
            }]
        }
        
        # Mock successful S3 Vectors put_vectors call
        mock_s3vectors_client.put_vectors.return_value = {}
        
        # Update data (only skills, no name/description change)
        update_data = {
            "skills": ["python", "testing", "automation"]
        }
        
        # Update agent
        result = agent_service.update_agent(agent_id, update_data)
        
        # Verify success
        assert result is True
        
        # Verify embedding service was NOT called (no name/description change)
        mock_embedding_service.generate_embedding.assert_not_called()
        
        # Verify S3 Vectors list_vectors was called to get existing embedding
        mock_s3vectors_client.list_vectors.assert_called_once()
        
        # Verify S3 Vectors put_vectors was called with existing embedding
        mock_s3vectors_client.put_vectors.assert_called_once()
        call_args = mock_s3vectors_client.put_vectors.call_args
        
        vectors = call_args[1]['vectors']
        vector = vectors[0]
        assert vector['data']['float32'] == existing_embedding
    
    def test_update_agent_not_found(self, agent_service, mock_s3vectors_client):
        """Test update agent when agent doesn't exist"""
        agent_id = str(uuid.uuid4())
        
        # Mock get_agent to return None (agent not found)
        agent_service.get_agent = Mock(return_value=None)
        
        update_data = {"name": "Updated Name"}
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.update_agent(agent_id, update_data)
        
        assert exc_info.value.error_code == "AGENT_NOT_FOUND"
        assert agent_id in exc_info.value.message
    
    def test_update_agent_invalid_uuid(self, agent_service):
        """Test update agent with invalid UUID"""
        invalid_agent_id = "invalid-uuid"
        update_data = {"name": "Updated Name"}
        
        with pytest.raises(ValidationError) as exc_info:
            agent_service.update_agent(invalid_agent_id, update_data)
        
        assert exc_info.value.field == "agent_id"
        assert "Invalid UUID format" in exc_info.value.message
    
    def test_update_agent_validation_error(self, agent_service, mock_s3vectors_client):
        """Test update agent with invalid update data"""
        agent_id = str(uuid.uuid4())
        
        # Mock existing agent data
        existing_agent = {
            "name": "Test Agent",
            "description": "Test description",
            "version": "1.0.0",
            "url": "https://example.com/test",
            "skills": ["python"]
        }
        
        # Mock get_agent to return existing agent
        agent_service.get_agent = Mock(return_value=existing_agent)
        
        # Invalid update data (name too short after merging)
        update_data = {"name": "A"}  # Too short
        
        with pytest.raises(ValidationError) as exc_info:
            agent_service.update_agent(agent_id, update_data)
        
        assert exc_info.value.field == "name"
        assert "at least 2 characters" in exc_info.value.message
    
    def test_update_agent_embedding_error(self, agent_service, mock_s3vectors_client, mock_embedding_service):
        """Test update agent with embedding generation error"""
        agent_id = str(uuid.uuid4())
        
        # Mock existing agent data
        existing_agent = {
            "name": "Test Agent",
            "description": "Test description",
            "version": "1.0.0",
            "url": "https://example.com/test",
            "skills": ["python"]
        }
        
        # Mock get_agent to return existing agent
        agent_service.get_agent = Mock(return_value=existing_agent)
        
        # Mock embedding service to raise error
        from src.services.embedding_service import EmbeddingServiceError
        mock_embedding_service.generate_embedding.side_effect = EmbeddingServiceError(
            "Bedrock service unavailable", "BEDROCK_ERROR"
        )
        
        # Update data that would trigger embedding regeneration
        update_data = {"name": "Updated Agent Name"}
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.update_agent(agent_id, update_data)
        
        assert exc_info.value.error_code == "EMBEDDING_GENERATION_ERROR"
        assert "Failed to generate embedding" in exc_info.value.message
    
    def test_update_agent_storage_error(self, agent_service, mock_s3vectors_client, mock_embedding_service):
        """Test update agent with S3 Vectors storage error"""
        agent_id = str(uuid.uuid4())
        
        # Mock existing agent data
        existing_agent = {
            "name": "Test Agent",
            "description": "Test description",
            "version": "1.0.0",
            "url": "https://example.com/test",
            "skills": ["python"]
        }
        
        # Mock get_agent to return existing agent
        agent_service.get_agent = Mock(return_value=existing_agent)
        
        # Mock S3 Vectors put_vectors to raise ClientError
        mock_s3vectors_client.put_vectors.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'InternalError',
                    'Message': 'Internal server error'
                }
            },
            operation_name='PutVectors'
        )
        
        update_data = {"skills": ["python", "testing"]}
        
        with pytest.raises(AgentServiceError) as exc_info:
            agent_service.update_agent(agent_id, update_data)
        
        assert exc_info.value.error_code == "UPDATE_ERROR"
        assert "Failed to update agent" in exc_info.value.message