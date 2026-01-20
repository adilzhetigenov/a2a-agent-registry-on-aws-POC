"""
Unit tests for the embedding service
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from src.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceError,
    BedrockAPIError,
    TextPreprocessingError
)


class TestEmbeddingService:
    """Test cases for EmbeddingService"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = EmbeddingService()
        
        # Mock embedding response
        self.mock_embedding = [0.1] * 1024  # 1024-dimensional vector
        self.mock_response = {
            'body': Mock()
        }
        self.mock_response['body'].read.return_value = json.dumps({
            'embedding': self.mock_embedding,
            'inputTextTokenCount': 10
        }).encode('utf-8')
    
    @patch('boto3.client')
    def test_init_success(self, mock_boto_client):
        """Test successful initialization"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        service = EmbeddingService(region_name='us-east-1')
        
        mock_boto_client.assert_called_once_with(
            'bedrock-runtime',
            region_name='us-east-1'
        )
        assert service.bedrock_client == mock_client
    
    @patch('boto3.client')
    def test_init_failure(self, mock_boto_client):
        """Test initialization failure"""
        mock_boto_client.side_effect = Exception("Connection failed")
        
        with pytest.raises(EmbeddingServiceError, match="Failed to initialize Bedrock client"):
            EmbeddingService()
    
    def test_preprocess_text_success(self):
        """Test successful text preprocessing"""
        # Test normal text
        result = self.service.preprocess_text("  Hello world  ")
        assert result == "Hello world"
        
        # Test text with newlines
        result = self.service.preprocess_text("Line 1\nLine 2\n")
        assert result == "Line 1\nLine 2"
    
    def test_preprocess_text_empty_input(self):
        """Test preprocessing with empty input"""
        with pytest.raises(TextPreprocessingError, match="Text must be a non-empty string"):
            self.service.preprocess_text("")
        
        with pytest.raises(TextPreprocessingError, match="Text must be a non-empty string"):
            self.service.preprocess_text(None)
        
        with pytest.raises(TextPreprocessingError, match="Text cannot be empty after preprocessing"):
            self.service.preprocess_text("   ")
    
    def test_preprocess_text_invalid_type(self):
        """Test preprocessing with invalid input type"""
        with pytest.raises(TextPreprocessingError, match="Text must be a non-empty string"):
            self.service.preprocess_text(123)
        
        with pytest.raises(TextPreprocessingError, match="Text must be a non-empty string"):
            self.service.preprocess_text(['text'])
    
    def test_preprocess_text_truncation(self):
        """Test text truncation for long inputs"""
        long_text = "a" * (EmbeddingService.MAX_INPUT_CHARACTERS + 100)
        
        result = self.service.preprocess_text(long_text)
        
        assert len(result) == EmbeddingService.MAX_INPUT_CHARACTERS
        assert result == "a" * EmbeddingService.MAX_INPUT_CHARACTERS
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_success(self, mock_preprocess):
        """Test successful embedding generation"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        self.service.bedrock_client.invoke_model.return_value = self.mock_response
        
        result = self.service.generate_embedding("test text")
        
        # Verify preprocessing was called
        mock_preprocess.assert_called_once_with("test text")
        
        # Verify Bedrock API call
        self.service.bedrock_client.invoke_model.assert_called_once_with(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({
                "inputText": "processed text"
            })
        )
        
        # Verify result
        assert result == self.mock_embedding
        assert len(result) == 1024
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_preprocessing_error(self, mock_preprocess):
        """Test embedding generation with preprocessing error"""
        mock_preprocess.side_effect = TextPreprocessingError("Invalid text")
        
        with pytest.raises(TextPreprocessingError, match="Invalid text"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_bedrock_client_error(self, mock_preprocess):
        """Test embedding generation with Bedrock client error"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        
        # Mock ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationException',
                'Message': 'Invalid model ID'
            }
        }
        self.service.bedrock_client.invoke_model.side_effect = ClientError(
            error_response, 'InvokeModel'
        )
        
        with pytest.raises(BedrockAPIError, match="Bedrock API error \\[ValidationException\\]: Invalid model ID"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_botocore_error(self, mock_preprocess):
        """Test embedding generation with BotoCoreError"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        
        self.service.bedrock_client.invoke_model.side_effect = BotoCoreError()
        
        with pytest.raises(BedrockAPIError, match="Boto3 client error"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_invalid_response(self, mock_preprocess):
        """Test embedding generation with invalid response"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        
        # Mock response without embedding
        invalid_response = {
            'body': Mock()
        }
        invalid_response['body'].read.return_value = json.dumps({
            'error': 'No embedding generated'
        }).encode('utf-8')
        
        self.service.bedrock_client.invoke_model.return_value = invalid_response
        
        with pytest.raises(BedrockAPIError, match="No embedding found in Bedrock response"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_wrong_dimensions(self, mock_preprocess):
        """Test embedding generation with wrong dimensions"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        
        # Mock response with wrong dimension
        wrong_dim_response = {
            'body': Mock()
        }
        wrong_dim_response['body'].read.return_value = json.dumps({
            'embedding': [0.1] * 512  # Wrong dimension
        }).encode('utf-8')
        
        self.service.bedrock_client.invoke_model.return_value = wrong_dim_response
        
        with pytest.raises(BedrockAPIError, match="Unexpected embedding dimension: 512, expected: 1024"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'preprocess_text')
    def test_generate_embedding_json_decode_error(self, mock_preprocess):
        """Test embedding generation with JSON decode error"""
        mock_preprocess.return_value = "processed text"
        self.service.bedrock_client = Mock()
        
        # Mock response with invalid JSON
        invalid_json_response = {
            'body': Mock()
        }
        invalid_json_response['body'].read.return_value = b"invalid json"
        
        self.service.bedrock_client.invoke_model.return_value = invalid_json_response
        
        with pytest.raises(BedrockAPIError, match="Failed to parse Bedrock response"):
            self.service.generate_embedding("test text")
    
    @patch.object(EmbeddingService, 'generate_embedding')
    def test_generate_embeddings_batch_success(self, mock_generate):
        """Test successful batch embedding generation"""
        mock_generate.side_effect = [
            [0.1] * 1024,  # First embedding
            [0.2] * 1024,  # Second embedding
        ]
        
        texts = ["text 1", "text 2"]
        result = self.service.generate_embeddings_batch(texts)
        
        assert len(result) == 2
        assert result[0] == [0.1] * 1024
        assert result[1] == [0.2] * 1024
        
        # Verify individual calls
        assert mock_generate.call_count == 2
        mock_generate.assert_any_call("text 1")
        mock_generate.assert_any_call("text 2")
    
    @patch.object(EmbeddingService, 'generate_embedding')
    def test_generate_embeddings_batch_empty_input(self, mock_generate):
        """Test batch embedding generation with empty input"""
        result = self.service.generate_embeddings_batch([])
        
        assert result == []
        mock_generate.assert_not_called()
    
    @patch.object(EmbeddingService, 'generate_embedding')
    def test_generate_embeddings_batch_partial_failure(self, mock_generate):
        """Test batch embedding generation with partial failures"""
        mock_generate.side_effect = [
            [0.1] * 1024,  # First embedding succeeds
            BedrockAPIError("API error"),  # Second embedding fails
            [0.3] * 1024,  # Third embedding succeeds
        ]
        
        texts = ["text 1", "text 2", "text 3"]
        result = self.service.generate_embeddings_batch(texts)
        
        assert len(result) == 3
        assert result[0] == [0.1] * 1024
        assert result[1] is None  # Failed embedding
        assert result[2] == [0.3] * 1024
        
        # Verify all calls were made
        assert mock_generate.call_count == 3


class TestEmbeddingServiceConstants:
    """Test embedding service constants"""
    
    def test_model_configuration(self):
        """Test model configuration constants"""
        assert EmbeddingService.MODEL_ID == "amazon.titan-embed-text-v2:0"
        assert EmbeddingService.MAX_INPUT_TOKENS == 8192
        assert EmbeddingService.MAX_INPUT_CHARACTERS == 50000
        assert EmbeddingService.OUTPUT_DIMENSION == 1024


class TestEmbeddingServiceExceptions:
    """Test custom exceptions"""
    
    def test_embedding_service_error(self):
        """Test base EmbeddingServiceError"""
        error = EmbeddingServiceError("Base error")
        assert str(error) == "Base error"
        assert isinstance(error, Exception)
    
    def test_bedrock_api_error(self):
        """Test BedrockAPIError inheritance"""
        error = BedrockAPIError("API error")
        assert str(error) == "API error"
        assert isinstance(error, EmbeddingServiceError)
        assert isinstance(error, Exception)
    
    def test_text_preprocessing_error(self):
        """Test TextPreprocessingError inheritance"""
        error = TextPreprocessingError("Preprocessing error")
        assert str(error) == "Preprocessing error"
        assert isinstance(error, EmbeddingServiceError)
        assert isinstance(error, Exception)