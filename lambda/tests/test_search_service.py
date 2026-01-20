"""
Tests for search service
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.services.search_service import SearchService, SearchServiceError, SearchResult
from src.services.embedding_service import EmbeddingServiceError


class TestSearchService:
    """Test cases for SearchService"""
    
    @pytest.fixture
    def mock_s3vectors_client(self):
        """Mock S3 Vectors client"""
        return Mock()
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service"""
        mock_service = Mock()
        mock_service.generate_embedding.return_value = [0.1] * 1024  # Mock 1024-dim embedding
        return mock_service
    
    @pytest.fixture
    def search_service(self, mock_s3vectors_client, mock_embedding_service):
        """Create SearchService instance with mocked dependencies"""
        with patch('boto3.client', return_value=mock_s3vectors_client), \
             patch('src.services.search_service.EmbeddingService', return_value=mock_embedding_service):
            service = SearchService()
            service.s3vectors_client = mock_s3vectors_client
            service.embedding_service = mock_embedding_service
            return service
    
    @pytest.fixture
    def sample_agent_data(self):
        """Sample agent data for testing"""
        return {
            "name": "Test Agent",
            "description": "A test agent for unit testing",
            "skills": ["python", "testing", "automation"],
            "provider": "Test Provider",
            "version": "1.0.0"
        }
    
    @pytest.fixture
    def sample_vector_response(self, sample_agent_data):
        """Sample S3 Vectors query response"""
        return {
            'vectors': [
                {
                    'key': 'agent-123e4567-e89b-12d3-a456-426614174000',
                    'distance': 0.2,
                    'metadata': {
                        'agent_id': '123e4567-e89b-12d3-a456-426614174000',
                        'name': 'Test Agent',
                        'description': 'A test agent for unit testing',
                        'skills': ['python', 'testing', 'automation'],
                        'provider': 'Test Provider',
                        'version': '1.0.0',
                        'created_at': '2024-01-01T00:00:00Z',
                        'raw_agent_card': json.dumps(sample_agent_data)
                    }
                },
                {
                    'key': 'agent-456e7890-e89b-12d3-a456-426614174001',
                    'distance': 0.4,
                    'metadata': {
                        'agent_id': '456e7890-e89b-12d3-a456-426614174001',
                        'name': 'Another Agent',
                        'description': 'Another test agent',
                        'skills': ['javascript', 'testing'],
                        'provider': 'Another Provider',
                        'version': '2.0.0',
                        'created_at': '2024-01-02T00:00:00Z',
                        'raw_agent_card': json.dumps({
                            "name": "Another Agent",
                            "description": "Another test agent",
                            "skills": ["javascript", "testing"],
                            "provider": "Another Provider",
                            "version": "2.0.0"
                        })
                    }
                }
            ]
        }
    
    def test_initialization_success(self):
        """Test successful SearchService initialization"""
        with patch('boto3.client') as mock_boto3, \
             patch('src.services.search_service.EmbeddingService'):
            
            service = SearchService()
            
            assert service.vector_bucket_name == "agent-registry-vectors"
            assert service.index_name == "agent-embeddings"
            mock_boto3.assert_called_with('s3vectors')
    
    def test_initialization_with_custom_params(self):
        """Test SearchService initialization with custom parameters"""
        with patch('boto3.client') as mock_boto3, \
             patch('src.services.search_service.EmbeddingService'):
            
            service = SearchService("custom-bucket", "custom-index")
            
            assert service.vector_bucket_name == "custom-bucket"
            assert service.index_name == "custom-index"
    
    def test_initialization_failure(self):
        """Test SearchService initialization failure"""
        with patch('boto3.client', side_effect=Exception("Connection failed")):
            with pytest.raises(SearchServiceError) as exc_info:
                SearchService()
            
            assert exc_info.value.error_code == "INITIALIZATION_ERROR"
            assert "Failed to initialize search service" in str(exc_info.value)
    
    def test_build_metadata_filter_no_skills(self, search_service):
        """Test metadata filter building with no skills"""
        result = search_service._build_metadata_filter(None)
        assert result is None
        
        result = search_service._build_metadata_filter([])
        assert result is None
    
    def test_build_metadata_filter_single_skill(self, search_service):
        """Test metadata filter building with single skill"""
        result = search_service._build_metadata_filter(["python"])
        
        expected = {
            "skills": {
                "contains": "python"
            }
        }
        assert result == expected
    
    def test_build_metadata_filter_multiple_skills(self, search_service):
        """Test metadata filter building with multiple skills"""
        result = search_service._build_metadata_filter(["python", "testing"])
        
        expected = {
            "or": [
                {"skills": {"contains": "python"}},
                {"skills": {"contains": "testing"}}
            ]
        }
        assert result == expected
    
    def test_calculate_skill_matches_no_query_skills(self, search_service):
        """Test skill matching with no query skills"""
        agent_skills = ["python", "testing"]
        result = search_service._calculate_skill_matches(agent_skills, None)
        assert result == []
        
        result = search_service._calculate_skill_matches(agent_skills, [])
        assert result == []
    
    def test_calculate_skill_matches_exact_match(self, search_service):
        """Test skill matching with exact matches"""
        agent_skills = ["python", "testing", "automation"]
        query_skills = ["python", "testing"]
        
        result = search_service._calculate_skill_matches(agent_skills, query_skills)
        assert set(result) == {"python", "testing"}
    
    def test_calculate_skill_matches_case_insensitive(self, search_service):
        """Test skill matching is case insensitive"""
        agent_skills = ["Python", "Testing", "Automation"]
        query_skills = ["python", "TESTING"]
        
        result = search_service._calculate_skill_matches(agent_skills, query_skills)
        assert set(result) == {"Python", "Testing"}
    
    def test_calculate_skill_matches_partial_match(self, search_service):
        """Test skill matching with partial matches"""
        agent_skills = ["python", "javascript"]
        query_skills = ["python", "testing", "automation"]
        
        result = search_service._calculate_skill_matches(agent_skills, query_skills)
        assert result == ["python"]
    
    def test_rank_and_format_results(self, search_service, sample_vector_response):
        """Test ranking and formatting of search results"""
        vectors = sample_vector_response['vectors']
        query_skills = ["python", "testing"]
        
        results = search_service._rank_and_format_results(vectors, query_skills)
        
        assert len(results) == 2
        
        # First result should have higher similarity (lower distance)
        assert results[0].distance == 0.2
        assert results[0].similarity_score == 0.8
        assert results[0].agent_id == '123e4567-e89b-12d3-a456-426614174000'
        assert set(results[0].matched_skills) == {"python", "testing"}
        
        # Second result
        assert results[1].distance == 0.4
        assert results[1].similarity_score == 0.6
        assert results[1].agent_id == '456e7890-e89b-12d3-a456-426614174001'
        assert results[1].matched_skills == ["testing"]
    
    def test_rank_and_format_results_corrupted_data(self, search_service):
        """Test handling of corrupted agent data"""
        vectors = [
            {
                'key': 'agent-123',
                'distance': 0.2,
                'metadata': {
                    'agent_id': '123',
                    'raw_agent_card': 'invalid json'
                }
            },
            {
                'key': 'agent-456',
                'distance': 0.3,
                'metadata': {
                    'agent_id': '456'
                    # Missing raw_agent_card
                }
            }
        ]
        
        results = search_service._rank_and_format_results(vectors)
        assert len(results) == 0  # Both should be filtered out
    
    def test_search_agents_success(self, search_service, sample_vector_response):
        """Test successful agent search"""
        search_service.s3vectors_client.query_vectors.return_value = sample_vector_response
        
        results = search_service.search_agents("test query", ["python"], top_k=10)
        
        assert len(results) == 2
        assert '_search_metadata' in results[0]
        assert results[0]['_search_metadata']['query'] == "test query"
        assert results[0]['_search_metadata']['similarity_score'] == 0.8
        assert results[0]['name'] == "Test Agent"
        
        # Verify S3 Vectors was called correctly
        search_service.s3vectors_client.query_vectors.assert_called_once()
        call_args = search_service.s3vectors_client.query_vectors.call_args[1]
        assert call_args['vectorBucketName'] == "agent-registry-vectors"
        assert call_args['indexName'] == "agent-embeddings"
        assert call_args['topK'] == 10
        assert 'filter' in call_args
    
    def test_search_agents_empty_query(self, search_service):
        """Test search with empty query"""
        with pytest.raises(SearchServiceError) as exc_info:
            search_service.search_agents("")
        
        assert exc_info.value.error_code == "INVALID_QUERY"
    
    def test_search_agents_embedding_error(self, search_service):
        """Test search with embedding generation error"""
        search_service.embedding_service.generate_embedding.side_effect = EmbeddingServiceError("Embedding failed")
        
        with pytest.raises(SearchServiceError) as exc_info:
            search_service.search_agents("test query")
        
        assert exc_info.value.error_code == "EMBEDDING_ERROR"
    
    def test_search_agents_s3vectors_error(self, search_service):
        """Test search with S3 Vectors error"""
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access denied to vector bucket'
            }
        }
        search_service.s3vectors_client.query_vectors.side_effect = ClientError(error_response, 'QueryVectors')
        
        with pytest.raises(SearchServiceError) as exc_info:
            search_service.search_agents("test query")
        
        assert exc_info.value.error_code == "VECTOR_SEARCH_ERROR"
        assert "Access denied" in str(exc_info.value)
    
    def test_search_agents_no_skills_filter(self, search_service, sample_vector_response):
        """Test search without skills filter"""
        search_service.s3vectors_client.query_vectors.return_value = sample_vector_response
        
        results = search_service.search_agents("test query")
        
        # Verify no filter was applied
        call_args = search_service.s3vectors_client.query_vectors.call_args[1]
        assert 'filter' not in call_args
    
    def test_search_agents_by_skills_only_success(self, search_service):
        """Test successful skills-only search"""
        mock_response = {
            'vectors': [
                {
                    'key': 'agent-123',
                    'metadata': {
                        'agent_id': '123',
                        'skills': ['python', 'testing'],
                        'raw_agent_card': json.dumps({
                            "name": "Test Agent",
                            "skills": ["python", "testing"]
                        })
                    }
                }
            ]
        }
        search_service.s3vectors_client.list_vectors.return_value = mock_response
        
        results = search_service.search_agents_by_skills_only(["python"])
        
        assert len(results) == 1
        assert results[0]['_search_metadata']['search_type'] == 'skills_only'
        assert results[0]['_search_metadata']['matched_skills'] == ['python']
        
        # Verify list_vectors was called correctly
        search_service.s3vectors_client.list_vectors.assert_called_once()
        call_args = search_service.s3vectors_client.list_vectors.call_args[1]
        assert call_args['vectorBucketName'] == "agent-registry-vectors"
        assert call_args['indexName'] == "agent-embeddings"
        assert 'filter' in call_args
    
    def test_search_agents_by_skills_only_empty_skills(self, search_service):
        """Test skills-only search with empty skills list"""
        with pytest.raises(SearchServiceError) as exc_info:
            search_service.search_agents_by_skills_only([])
        
        assert exc_info.value.error_code == "INVALID_SKILLS"
    
    def test_search_agents_by_skills_only_s3vectors_error(self, search_service):
        """Test skills-only search with S3 Vectors error"""
        error_response = {
            'Error': {
                'Code': 'InvalidParameter',
                'Message': 'Invalid filter parameter'
            }
        }
        search_service.s3vectors_client.list_vectors.side_effect = ClientError(error_response, 'ListVectors')
        
        with pytest.raises(SearchServiceError) as exc_info:
            search_service.search_agents_by_skills_only(["python"])
        
        assert exc_info.value.error_code == "SKILL_SEARCH_ERROR"
    
    def test_search_result_dataclass(self):
        """Test SearchResult dataclass"""
        result = SearchResult(
            agent_id="123",
            agent_data={"name": "Test"},
            similarity_score=0.8,
            matched_skills=["python"],
            distance=0.2
        )
        
        assert result.agent_id == "123"
        assert result.agent_data == {"name": "Test"}
        assert result.similarity_score == 0.8
        assert result.matched_skills == ["python"]
        assert result.distance == 0.2
    
    def test_search_service_error_creation(self):
        """Test SearchServiceError creation"""
        error = SearchServiceError("Test message", "TEST_ERROR", {"detail": "value"})
        
        assert error.message == "Test message"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"detail": "value"}
        assert str(error) == "Test message"
    
    def test_search_service_error_defaults(self):
        """Test SearchServiceError with default values"""
        error = SearchServiceError("Test message")
        
        assert error.error_code == "SEARCH_SERVICE_ERROR"
        assert error.details == {}