"""
Integration tests for embedding service with agent service
"""
import pytest
from unittest.mock import Mock, patch

from src.services.embedding_service import EmbeddingService
from src.services.agent_service import AgentService


class TestEmbeddingIntegration:
    """Test embedding service integration with agent service"""
    
    @patch('boto3.client')
    def test_agent_service_initializes_embedding_service(self, mock_boto_client):
        """Test that agent service properly initializes embedding service"""
        # Mock both S3 Vectors and Bedrock clients
        mock_s3vectors_client = Mock()
        mock_bedrock_client = Mock()
        
        def mock_client_factory(service_name, **kwargs):
            if service_name == 's3vectors':
                return mock_s3vectors_client
            elif service_name == 'bedrock-runtime':
                return mock_bedrock_client
            else:
                return Mock()
        
        mock_boto_client.side_effect = mock_client_factory
        
        # Initialize agent service
        agent_service = AgentService()
        
        # Verify that embedding service was initialized
        assert hasattr(agent_service, 'embedding_service')
        assert isinstance(agent_service.embedding_service, EmbeddingService)
        
        # Verify boto3 clients were created
        assert mock_boto_client.call_count >= 2  # At least s3vectors and bedrock-runtime
        mock_boto_client.assert_any_call('s3vectors')
        mock_boto_client.assert_any_call('bedrock-runtime', region_name=None)
    
    @patch('boto3.client')
    def test_embedding_service_can_be_used_independently(self, mock_boto_client):
        """Test that embedding service can be used independently"""
        mock_bedrock_client = Mock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock successful embedding response
        mock_response = {
            'body': Mock()
        }
        mock_embedding = [0.1] * 1024  # 1024-dimensional vector
        import json
        response_data = {"embedding": mock_embedding, "inputTextTokenCount": 5}
        mock_response['body'].read.return_value = json.dumps(response_data).encode('utf-8')
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Test embedding generation
        result = embedding_service.generate_embedding("test text")
        
        # Verify result
        assert result == mock_embedding
        assert len(result) == 1024
        
        # Verify API call
        mock_bedrock_client.invoke_model.assert_called_once()
        call_args = mock_bedrock_client.invoke_model.call_args
        assert call_args[1]['modelId'] == 'amazon.titan-embed-text-v2:0'
    
    def test_embedding_service_constants_match_design(self):
        """Test that embedding service constants match design specifications"""
        assert EmbeddingService.MODEL_ID == "amazon.titan-embed-text-v2:0"
        assert EmbeddingService.MAX_INPUT_TOKENS == 8192
        assert EmbeddingService.MAX_INPUT_CHARACTERS == 50000
        assert EmbeddingService.OUTPUT_DIMENSION == 1024
    
    @patch('boto3.client')
    def test_embedding_service_error_handling(self, mock_boto_client):
        """Test embedding service error handling"""
        mock_bedrock_client = Mock()
        mock_boto_client.return_value = mock_bedrock_client
        
        # Mock Bedrock client error
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}}
        mock_bedrock_client.invoke_model.side_effect = ClientError(error_response, 'InvokeModel')
        
        embedding_service = EmbeddingService()
        
        # Test that error is properly handled
        from src.services.embedding_service import BedrockAPIError
        with pytest.raises(BedrockAPIError, match="Bedrock API error"):
            embedding_service.generate_embedding("test text")