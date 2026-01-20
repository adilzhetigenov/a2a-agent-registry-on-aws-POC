"""
Embedding service for generating text embeddings using Bedrock
"""
import json
import logging
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    """Base exception for embedding service errors"""
    pass


class BedrockAPIError(EmbeddingServiceError):
    """Exception raised when Bedrock API calls fail"""
    pass


class TextPreprocessingError(EmbeddingServiceError):
    """Exception raised when text preprocessing fails"""
    pass


class EmbeddingService:
    """Service for generating embeddings using AWS Bedrock Titan text-v2"""
    
    # Bedrock Titan text-v2 model configuration
    MODEL_ID = "amazon.titan-embed-text-v2:0"
    MAX_INPUT_TOKENS = 8192
    MAX_INPUT_CHARACTERS = 50000
    OUTPUT_DIMENSION = 1024
    
    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize the embedding service
        
        Args:
            region_name: AWS region name. If None, uses default region
        """
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=region_name
            )
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise EmbeddingServiceError(f"Failed to initialize Bedrock client: {e}")
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for embedding generation
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            Preprocessed text ready for embedding
            
        Raises:
            TextPreprocessingError: If text preprocessing fails
        """
        try:
            if not text or not isinstance(text, str):
                raise TextPreprocessingError("Text must be a non-empty string")
            
            # Strip whitespace and normalize
            processed_text = text.strip()
            
            if not processed_text:
                raise TextPreprocessingError("Text cannot be empty after preprocessing")
            
            # Check character limit
            if len(processed_text) > self.MAX_INPUT_CHARACTERS:
                logger.warning(
                    f"Text length ({len(processed_text)}) exceeds maximum "
                    f"({self.MAX_INPUT_CHARACTERS}). Truncating."
                )
                processed_text = processed_text[:self.MAX_INPUT_CHARACTERS]
            
            return processed_text
            
        except Exception as e:
            logger.error(f"Text preprocessing failed: {e}")
            raise TextPreprocessingError(f"Text preprocessing failed: {e}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Bedrock Titan text-v2
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of float values representing the embedding (1024 dimensions)
            
        Raises:
            TextPreprocessingError: If text preprocessing fails
            BedrockAPIError: If Bedrock API call fails
            EmbeddingServiceError: For other embedding generation errors
        """
        try:
            # Preprocess the input text
            processed_text = self.preprocess_text(text)
            
            # Prepare the request body for Titan text-v2
            request_body = {
                "inputText": processed_text
            }
            
            logger.debug(f"Generating embedding for text length: {len(processed_text)}")
            
            # Make the API call to Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.MODEL_ID,
                body=json.dumps(request_body)
            )
            
            # Parse the response
            response_body = json.loads(response['body'].read())
            
            # Extract the embedding vector
            if 'embedding' not in response_body:
                raise BedrockAPIError("No embedding found in Bedrock response")
            
            embedding = response_body['embedding']
            
            # Validate embedding dimensions
            if len(embedding) != self.OUTPUT_DIMENSION:
                raise BedrockAPIError(
                    f"Unexpected embedding dimension: {len(embedding)}, "
                    f"expected: {self.OUTPUT_DIMENSION}"
                )
            
            logger.debug(f"Successfully generated embedding with {len(embedding)} dimensions")
            return embedding
            
        except TextPreprocessingError:
            # Re-raise preprocessing errors as-is
            raise
        except BedrockAPIError:
            # Re-raise Bedrock API errors as-is
            raise
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Bedrock API error [{error_code}]: {error_message}")
            raise BedrockAPIError(f"Bedrock API error [{error_code}]: {error_message}")
        except BotoCoreError as e:
            logger.error(f"Boto3 client error: {e}")
            raise BedrockAPIError(f"Boto3 client error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock response: {e}")
            raise BedrockAPIError(f"Failed to parse Bedrock response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during embedding generation: {e}")
            raise EmbeddingServiceError(f"Unexpected error during embedding generation: {e}")
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors, one for each input text
            
        Raises:
            EmbeddingServiceError: If batch processing fails
        """
        if not texts:
            return []
        
        embeddings = []
        failed_indices = []
        
        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for text {i}: {e}")
                failed_indices.append(i)
                embeddings.append(None)
        
        if failed_indices:
            logger.warning(f"Failed to generate embeddings for {len(failed_indices)} texts")
        
        return embeddings