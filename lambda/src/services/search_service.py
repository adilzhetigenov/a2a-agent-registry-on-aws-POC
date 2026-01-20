"""
Search service for semantic and skill-based search
"""
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError

from utils.logging import get_logger
from services.embedding_service import EmbeddingService, EmbeddingServiceError

logger = get_logger(__name__)


class SearchServiceError(Exception):
    """Base exception for search service errors"""
    def __init__(self, message: str, error_code: str = "SEARCH_SERVICE_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class SearchResult:
    """Search result with agent data and relevance information"""
    agent_id: str
    agent_data: Dict[str, Any]  # Raw agent card data
    similarity_score: float
    matched_skills: List[str]
    distance: float


class SearchService:
    """Service for searching agents using S3 Vectors"""
    
    def __init__(self, vector_bucket_name: str = "agent-registry-vectors", index_name: str = "agent-embeddings"):
        """
        Initialize search service
        
        Args:
            vector_bucket_name: S3 Vectors bucket name
            index_name: S3 Vectors index name
        """
        self.vector_bucket_name = vector_bucket_name
        self.index_name = index_name
        
        try:
            self.s3vectors_client = boto3.client('s3vectors')
            self.embedding_service = EmbeddingService()
            logger.info("Initialized S3 Vectors client and embedding service", 
                       bucket=vector_bucket_name, index=index_name)
        except Exception as e:
            logger.error("Failed to initialize search service", error=str(e))
            raise SearchServiceError(f"Failed to initialize search service: {str(e)}", "INITIALIZATION_ERROR")
    
    def _build_metadata_filter(self, skills: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Build metadata filter for S3 Vectors query
        
        Args:
            skills: Optional list of skills to filter by
            
        Returns:
            Metadata filter dictionary or None if no filters
        """
        if not skills:
            return None
        
        # Build S3 Vectors metadata filter for skills
        # Always use AND logic - agent must have ALL specified skills
        
        if len(skills) == 1:
            # Single skill - use $eq operator for exact match
            return {
                "skills": {"$eq": skills[0]}
            }
        else:
            # Multiple skills - use $and with multiple $eq conditions
            # This ensures the agent has ALL the specified skills
            skill_conditions = [{"skills": {"$eq": skill}} for skill in skills]
            return {
                "$and": skill_conditions
            }
    
    def _calculate_skill_matches(self, agent_skills: List[str], query_skills: Optional[List[str]]) -> List[str]:
        """
        Calculate which skills match between agent and query
        
        Args:
            agent_skills: Skills from the agent metadata
            query_skills: Skills from the search query
            
        Returns:
            List of matching skills
        """
        if not query_skills:
            return []
        
        # Find intersection of skills (case-insensitive)
        agent_skills_lower = [skill.lower() for skill in agent_skills]
        query_skills_lower = [skill.lower() for skill in query_skills]
        
        matched_skills = []
        for query_skill in query_skills:
            if query_skill.lower() in agent_skills_lower:
                # Find the original case version from agent skills
                for agent_skill in agent_skills:
                    if agent_skill.lower() == query_skill.lower():
                        matched_skills.append(agent_skill)
                        break
        
        return matched_skills
    
    def _rank_and_format_results(self, vectors: List[Dict], query_skills: Optional[List[str]] = None) -> List[SearchResult]:
        """
        Rank and format search results
        
        Args:
            vectors: Raw vector results from S3 Vectors
            query_skills: Optional skills used in the query for matching
            
        Returns:
            List of formatted and ranked SearchResult objects
        """
        results = []
        
        for vector in vectors:
            try:
                metadata = vector.get('metadata', {})
                distance = vector.get('distance', 1.0)
                
                # Calculate similarity score (1 - cosine distance)
                similarity_score = max(0.0, 1.0 - distance)
                
                # Extract agent data
                raw_agent_card = metadata.get('raw_agent_card')
                if not raw_agent_card:
                    logger.warning("Skipping result with missing agent card data", 
                                 agent_id=metadata.get('agent_id'))
                    continue
                
                try:
                    agent_data = json.loads(raw_agent_card)
                except json.JSONDecodeError as e:
                    logger.warning("Skipping result with corrupted agent data", 
                                 agent_id=metadata.get('agent_id'), error=str(e))
                    continue
                
                # Calculate skill matches
                agent_skills_json = metadata.get('skills', '[]')
                try:
                    agent_skills = json.loads(agent_skills_json) if isinstance(agent_skills_json, str) else agent_skills_json
                except json.JSONDecodeError:
                    agent_skills = []
                matched_skills = self._calculate_skill_matches(agent_skills, query_skills)
                
                result = SearchResult(
                    agent_id=metadata.get('agent_id'),
                    agent_data=agent_data,
                    similarity_score=similarity_score,
                    matched_skills=matched_skills,
                    distance=distance
                )
                
                results.append(result)
                
            except Exception as e:
                logger.warning("Error processing search result", error=str(e))
                continue
        
        # Sort by similarity score (highest first), then by number of matched skills
        results.sort(key=lambda x: (x.similarity_score, len(x.matched_skills)), reverse=True)
        
        return results
    
    def search_agents(self, query: Optional[str] = None, skills: Optional[List[str]] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Unified search method for all search types using S3 Vectors query_vectors
        
        Args:
            query: Optional search query text for semantic search. If None, uses generic "Agent" query
            skills: Optional list of skills to filter by (agent must have ALL specified skills)
            top_k: Maximum number of results to return (default: 10)
            
        Returns:
            List of agent data dictionaries with search metadata
            
        Raises:
            SearchServiceError: If search operation fails
        """
        # Validate that at least one search parameter is provided
        if not query and not skills:
            raise SearchServiceError("Either query text or skills must be provided", "INVALID_SEARCH_PARAMS")
        
        # Use generic query for skills-only search
        search_query = query.strip() if query else "Agent"
        search_type = "semantic" if query else "skills_only"
        if query and skills:
            search_type = "combined"
        
        logger.info("Searching agents", query=search_query, skills=skills, top_k=top_k, search_type=search_type)
        
        try:
            # Generate embedding for the search query (or generic query for skills-only)
            try:
                query_embedding = self.embedding_service.generate_embedding(search_query)
                logger.debug("Generated query embedding", query=search_query, embedding_dim=len(query_embedding))
            except EmbeddingServiceError as e:
                logger.error("Failed to generate query embedding", query=search_query, error=str(e))
                raise SearchServiceError(f"Failed to generate query embedding: {str(e)}", "EMBEDDING_ERROR")
            
            # Build metadata filter for skills (always AND logic)
            metadata_filter = self._build_metadata_filter(skills)
            
            # Prepare query parameters
            query_params = {
                'vectorBucketName': self.vector_bucket_name,
                'indexName': self.index_name,
                'queryVector': {'float32': query_embedding},
                'topK': min(top_k, 30),  # S3 Vectors maximum limit is 30
                'returnDistance': True,
                'returnMetadata': True
            }
            
            # Add metadata filter if skills are specified
            if metadata_filter:
                query_params['filter'] = metadata_filter
                logger.debug("Using S3 Vectors metadata filter", filter=metadata_filter)
            
            # Execute the vector similarity search with metadata filtering
            response = self.s3vectors_client.query_vectors(**query_params)
            
            vectors = response.get('vectors', [])
            logger.info("Vector search completed", 
                       query=search_query, results_count=len(vectors), 
                       search_type=search_type, used_metadata_filter=bool(metadata_filter))
            
            # Convert to output format
            formatted_results = []
            for vector in vectors:
                try:
                    metadata = vector.get('metadata', {})
                    distance = vector.get('distance', 1.0)
                    
                    # Calculate similarity score (1 - cosine distance)
                    similarity_score = max(0.0, 1.0 - distance)
                    
                    # Extract agent data
                    raw_agent_card = metadata.get('raw_agent_card')
                    if not raw_agent_card:
                        logger.warning("Skipping result with missing agent card data", 
                                     agent_id=metadata.get('agent_id'))
                        continue
                    
                    try:
                        agent_data = json.loads(raw_agent_card)
                    except json.JSONDecodeError as e:
                        logger.warning("Skipping result with corrupted agent data", 
                                     agent_id=metadata.get('agent_id'), error=str(e))
                        continue
                    
                    # Calculate skill matches
                    agent_skills_json = metadata.get('skills', [])
                    agent_skills = agent_skills_json if isinstance(agent_skills_json, list) else []
                    matched_skills = self._calculate_skill_matches(agent_skills, skills)
                    
                    # Add agent_id to the result
                    agent_data['agent_id'] = metadata.get('agent_id')
                    
                    # Add search metadata
                    agent_data['_search_metadata'] = {
                        'similarity_score': similarity_score,
                        'distance': distance,
                        'matched_skills': matched_skills,
                        'query': search_query,
                        'search_type': search_type,
                        'agent_id': metadata.get('agent_id')
                    }
                    
                    formatted_results.append(agent_data)
                    
                except Exception as e:
                    logger.warning("Error processing search result", error=str(e))
                    continue
            
            logger.info("Search completed successfully", 
                       query=search_query, search_type=search_type, final_results_count=len(formatted_results))
            
            return formatted_results
            
        except SearchServiceError:
            # Re-raise search service errors as-is
            raise
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'UNKNOWN')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error("S3 Vectors query failed", 
                        query=search_query, error_code=error_code, error_message=error_message)
            
            raise SearchServiceError(
                f"Vector search failed: {error_message}",
                "VECTOR_SEARCH_ERROR",
                {"aws_error_code": error_code, "query": search_query}
            )
        except Exception as e:
            logger.error("Unexpected error during search", query=search_query, error=str(e))
            raise SearchServiceError(f"Unexpected search error: {str(e)}", "SEARCH_ERROR")
    
