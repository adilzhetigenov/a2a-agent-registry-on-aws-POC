"""
Main Agent Registry Client class
"""
import json
import time
import random
from typing import List, Optional, Dict, Any
import boto3
import requests
from requests_aws4auth import AWS4Auth
from a2a.types import AgentCard
from .exceptions import (
    AgentRegistryError, 
    ValidationError, 
    NotFoundError, 
    AuthenticationError, 
    ServerError
)
from .models import AgentListResponse, SearchResult


class AgentRegistryClient:
    """Client for interacting with Agent Registry API"""
    
    def __init__(self, api_gateway_url: str, region: str = 'us-east-1', 
                 max_retries: int = 3, retry_backoff_factor: float = 0.5):
        """
        Initialize the Agent Registry Client
        
        Args:
            api_gateway_url: API Gateway URL (e.g., https://api-id.execute-api.region.amazonaws.com/stage)
            region: AWS region
            max_retries: Maximum number of retry attempts for failed requests
            retry_backoff_factor: Backoff factor for exponential retry delay
        """
        self.api_gateway_url = api_gateway_url.rstrip('/')
        self.region = region
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.session = boto3.Session()
        
        # Set up AWS authentication for API Gateway
        credentials = self.session.get_credentials()
        if not credentials:
            raise AuthenticationError("AWS credentials not found. Please configure AWS credentials.")
        
        self.auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'execute-api',
            session_token=credentials.token
        )
        
    def _is_retryable_error(self, exception: Exception) -> bool:
        """
        Determine if an error is retryable
        
        Args:
            exception: The exception to check
            
        Returns:
            True if the error should be retried
        """
        # Retry on server errors, timeouts, and connection errors
        if isinstance(exception, (ServerError, requests.exceptions.Timeout, 
                                requests.exceptions.ConnectionError)):
            return True
        
        # Retry on specific HTTP status codes
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                return exception.response.status_code >= 500
        
        return False
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff and jitter
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (2 ^ attempt) * backoff_factor
        base_delay = 1.0
        delay = base_delay * (2 ** attempt) * self.retry_backoff_factor
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
    
    def _make_request(self, method: str, path: str, body: Optional[Dict] = None, 
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make authenticated request to API Gateway with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/agents')
            body: Request body as dictionary
            params: Query parameters
            
        Returns:
            Response data
            
        Raises:
            AgentRegistryError: For various API errors
        """
        url = f"{self.api_gateway_url}{path}"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        kwargs = {
            'auth': self.auth,
            'headers': headers,
            'timeout': 30
        }
        
        if body:
            kwargs['json'] = body
        
        if params:
            kwargs['params'] = params
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = getattr(requests, method.lower())(url, **kwargs)
                
                # Handle different response status codes
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        raise AgentRegistryError(f"Invalid JSON response from API: {response.text}")
                
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_info = error_data.get('error', {})
                        if error_info.get('code') == 'VALIDATION_ERROR':
                            raise ValidationError(error_info.get('message', 'Validation failed'))
                        else:
                            raise AgentRegistryError(error_info.get('message', 'Bad request'))
                    except json.JSONDecodeError:
                        raise AgentRegistryError(f"Bad request: {response.text}")
                
                elif response.status_code == 401:
                    raise AuthenticationError("Authentication failed. Check your AWS credentials.")
                
                elif response.status_code == 403:
                    raise AuthenticationError("Access denied. Check your IAM permissions.")
                
                elif response.status_code == 404:
                    try:
                        error_data = response.json()
                        error_info = error_data.get('error', {})
                        raise NotFoundError(error_info.get('message', 'Resource not found'))
                    except json.JSONDecodeError:
                        raise NotFoundError("Resource not found")
                
                elif response.status_code >= 500:
                    try:
                        error_data = response.json()
                        error_info = error_data.get('error', {})
                        server_error = ServerError(error_info.get('message', 'Internal server error'))
                        
                        # Check if we should retry
                        if attempt < self.max_retries and self._is_retryable_error(server_error):
                            last_exception = server_error
                            delay = self._calculate_retry_delay(attempt)
                            time.sleep(delay)
                            continue
                        else:
                            raise server_error
                    except json.JSONDecodeError:
                        server_error = ServerError(f"Server error: {response.text}")
                        if attempt < self.max_retries and self._is_retryable_error(server_error):
                            last_exception = server_error
                            delay = self._calculate_retry_delay(attempt)
                            time.sleep(delay)
                            continue
                        else:
                            raise server_error
                
                else:
                    raise AgentRegistryError(f"Unexpected response status: {response.status_code}")
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < self.max_retries:
                    last_exception = e
                    delay = self._calculate_retry_delay(attempt)
                    time.sleep(delay)
                    continue
                else:
                    if isinstance(e, requests.exceptions.Timeout):
                        raise AgentRegistryError("Request timeout. The API may be unavailable.")
                    else:
                        raise AgentRegistryError("Connection error. Check your network and API URL.")
            
            except requests.exceptions.RequestException as e:
                raise AgentRegistryError(f"Request failed: {str(e)}")
        
        # If we get here, all retries failed
        if last_exception:
            if isinstance(last_exception, requests.exceptions.Timeout):
                raise AgentRegistryError("Request timeout after retries. The API may be unavailable.")
            elif isinstance(last_exception, requests.exceptions.ConnectionError):
                raise AgentRegistryError("Connection error after retries. Check your network and API URL.")
            else:
                raise last_exception
        
        raise AgentRegistryError("Request failed after all retry attempts")
        
    def create_agent(self, agent_card: AgentCard) -> str:
        """
        Create a new agent card
        
        Args:
            agent_card: AgentCard instance to create
            
        Returns:
            Agent ID
            
        Raises:
            ValidationError: If agent card validation fails
            AgentRegistryError: If API call fails
        """
        # Convert AgentCard to dictionary for JSON serialization
        agent_data = agent_card.model_dump() if hasattr(agent_card, 'model_dump') else agent_card.__dict__
        
        response = self._make_request('POST', '/agents', body=agent_data)
        
        agent_id = response.get('agent_id')
        if not agent_id:
            raise AgentRegistryError("Invalid response: missing agent_id")
        
        return agent_id
    
    def get_agent(self, agent_id: str) -> AgentCard:
        """
        Get agent by ID
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            AgentCard instance
            
        Raises:
            NotFoundError: If agent not found
            AgentRegistryError: If API call fails
        """
        if not agent_id or not agent_id.strip():
            raise ValidationError("Agent ID is required")
        
        response = self._make_request('GET', f'/agents/{agent_id}')
        
        agent_data = response.get('agent')
        if not agent_data:
            raise AgentRegistryError("Invalid response: missing agent data")
        
        # Convert response to AgentCard
        try:
            return AgentCard(**agent_data)
        except Exception as e:
            raise AgentRegistryError(f"Failed to parse agent data: {str(e)}")
    
    def list_agents(self, limit: int = 50, offset: int = 0) -> AgentListResponse:
        """
        List agents with pagination
        
        Args:
            limit: Maximum number of agents to return (1-100)
            offset: Number of agents to skip
            
        Returns:
            AgentListResponse with agents and pagination info
            
        Raises:
            ValidationError: If parameters are invalid
            AgentRegistryError: If API call fails
        """
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        
        if offset < 0:
            raise ValidationError("Offset must be non-negative")
        
        params = {
            'limit': limit,
            'offset': offset
        }
        
        response = self._make_request('GET', '/agents', params=params)
        
        agents_data = response.get('agents', [])
        pagination = response.get('pagination', {})
        
        # Convert agent data to AgentCard instances
        agents = []
        for agent_data in agents_data:
            try:
                agents.append(AgentCard(**agent_data))
            except Exception as e:
                raise AgentRegistryError(f"Failed to parse agent data: {str(e)}")
        
        return AgentListResponse(
            agents=agents,
            total_count=pagination.get('total', len(agents)),
            has_more=pagination.get('has_more', False)
        )
    
    def search_agents(self, query: Optional[str] = None, skills: Optional[List[str]] = None, 
                     top_k: int = 10) -> List[SearchResult]:
        """
        Search agents using text and skills
        
        Args:
            query: Search query text (optional if skills provided)
            skills: Optional list of skills to filter by
            top_k: Maximum number of results to return (1-30)
            
        Returns:
            List of SearchResult instances with similarity scores
            
        Raises:
            ValidationError: If parameters are invalid
            AgentRegistryError: If API call fails
        """
        if not query and not skills:
            raise ValidationError("Either query text or skills must be provided")
        
        if top_k < 1 or top_k > 30:
            raise ValidationError("top_k must be between 1 and 30")
        
        params = {'top_k': top_k}
        
        if query:
            params['text'] = query
        
        if skills:
            params['skills'] = ','.join(skills)
        
        response = self._make_request('GET', '/agents/search', params=params)
        
        # The API returns a list directly, not wrapped in a 'results' key
        results_data = response if isinstance(response, list) else response.get('results', [])
        
        # Convert results to SearchResult instances
        results = []
        for result_data in results_data:
            try:
                agent_card = AgentCard(**result_data['agent_card'])
                search_result = SearchResult(
                    agent_card=agent_card,
                    similarity_score=result_data.get('similarity_score', 0.0),
                    matched_skills=result_data.get('matched_skills', [])
                )
                results.append(search_result)
            except Exception as e:
                raise AgentRegistryError(f"Failed to parse search result: {str(e)}")
        
        return results
    
    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing agent card (partial updates supported)
        
        Args:
            agent_id: Agent identifier
            update_data: Dictionary containing fields to update
            
        Returns:
            True if successful
            
        Raises:
            NotFoundError: If agent not found
            ValidationError: If update data validation fails
            AgentRegistryError: If API call fails
        """
        if not agent_id or not agent_id.strip():
            raise ValidationError("Agent ID is required")
        
        if not update_data:
            raise ValidationError("Update data is required")
        
        response = self._make_request('PUT', f'/agents/{agent_id}', body=update_data)
        
        # Check if the response indicates success
        message = response.get('message', '')
        return 'success' in message.lower()

    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete agent by ID
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful
            
        Raises:
            NotFoundError: If agent not found
            AgentRegistryError: If API call fails
        """
        if not agent_id or not agent_id.strip():
            raise ValidationError("Agent ID is required")
        
        response = self._make_request('DELETE', f'/agents/{agent_id}')
        
        # Check if the response indicates success
        message = response.get('message', '')
        return 'success' in message.lower()

    def update_health(self, agent_id: str) -> bool:
        """
        Update agent health status
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful
            
        Raises:
            NotFoundError: If agent not found
            AgentRegistryError: If API call fails
        """
        if not agent_id or not agent_id.strip():
            raise ValidationError("Agent ID is required")
        
        response = self._make_request('POST', f'/agents/{agent_id}/health')
        
        # Check if the response indicates success
        message = response.get('message', '')
        return 'success' in message.lower()