"""
Unit tests for Agent Registry Client
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import requests
from datetime import datetime
from a2a.types import AgentCard

from agent_registry_client import (
    AgentRegistryClient,
    AgentRegistryError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError,
    AgentListResponse,
    SearchResult
)


class TestAgentRegistryClient:
    """Test cases for AgentRegistryClient"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod",
            region="us-east-1"
        )
    
    @pytest.fixture
    def sample_agent_card(self):
        """Sample AgentCard for testing"""
        from a2a.types import AgentSkill, AgentCapabilities
        
        return AgentCard(
            name="Test Agent",
            description="A test agent",
            version="1.0.0",
            url="http://localhost:8080/",
            skills=[
                AgentSkill(
                    id="python",
                    name="Python Programming",
                    description="Python development and scripting",
                    tags=["programming", "python"]
                ),
                AgentSkill(
                    id="testing",
                    name="Software Testing",
                    description="Automated testing and QA",
                    tags=["testing", "qa"]
                )
            ],
            capabilities=AgentCapabilities(streaming=True),
            default_input_modes=["text"],
            default_output_modes=["text"],
            preferred_transport="JSONRPC",
            protocol_version="0.3.0"
        )
    
    def test_init_success(self, mock_credentials):
        """Test successful client initialization"""
        client = AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        )
        
        assert client.api_gateway_url == "https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        assert client.region == "us-east-1"
        assert client.auth is not None
    
    def test_init_no_credentials(self):
        """Test client initialization without credentials"""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.get_credentials.return_value = None
            
            with pytest.raises(AuthenticationError, match="AWS credentials not found"):
                AgentRegistryClient("https://test-api.execute-api.us-east-1.amazonaws.com/prod")
    
    @patch('requests.post')
    def test_create_agent_success(self, mock_post, client, sample_agent_card):
        """Test successful agent creation"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent_id': 'test-agent-id-123',
            'message': 'Agent created successfully'
        }
        mock_post.return_value = mock_response
        
        # Test create agent
        agent_id = client.create_agent(sample_agent_card)
        
        assert agent_id == 'test-agent-id-123'
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_create_agent_validation_error(self, mock_post, client, sample_agent_card):
        """Test agent creation with validation error"""
        # Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid agent data'
            }
        }
        mock_post.return_value = mock_response
        
        # Test create agent
        with pytest.raises(ValidationError, match="Invalid agent data"):
            client.create_agent(sample_agent_card)
    
    @patch('requests.get')
    def test_get_agent_success(self, mock_get, client):
        """Test successful agent retrieval"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent': {
                'name': 'Test Agent',
                'description': 'A test agent',
                'version': '1.0.0',
                'url': 'http://localhost:8080/',
                'skills': [
                    {
                        'id': 'python',
                        'name': 'Python Programming',
                        'description': 'Python development and scripting',
                        'tags': ['programming', 'python']
                    },
                    {
                        'id': 'testing',
                        'name': 'Software Testing',
                        'description': 'Automated testing and QA',
                        'tags': ['testing', 'qa']
                    }
                ],
                'capabilities': {'streaming': True},
                'default_input_modes': ['text'],
                'default_output_modes': ['text'],
                'preferred_transport': 'JSONRPC',
                'protocol_version': '0.3.0'
            }
        }
        mock_get.return_value = mock_response
        
        # Test get agent
        agent = client.get_agent('test-agent-id')
        
        assert isinstance(agent, AgentCard)
        assert agent.name == 'Test Agent'
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_get_agent_not_found(self, mock_get, client):
        """Test agent retrieval with not found error"""
        # Mock not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': {
                'code': 'AGENT_NOT_FOUND',
                'message': 'Agent not found'
            }
        }
        mock_get.return_value = mock_response
        
        # Test get agent
        with pytest.raises(NotFoundError, match="Agent not found"):
            client.get_agent('invalid-id')
    
    def test_get_agent_invalid_id(self, client):
        """Test get agent with invalid ID"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.get_agent("")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.get_agent("   ")
    
    @patch('requests.get')
    def test_list_agents_success(self, mock_get, client):
        """Test successful agent listing"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agents': [
                {
                    'name': 'Agent 1',
                    'description': 'First agent',
                    'version': '1.0.0',
                    'url': 'http://localhost:8080/',
                    'skills': [
                        {
                            'id': 'python',
                            'name': 'Python Programming',
                            'description': 'Python development and scripting',
                            'tags': ['programming', 'python']
                        }
                    ],
                    'capabilities': {'streaming': True},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'JSONRPC',
                    'protocol_version': '0.3.0'
                }
            ],
            'pagination': {
                'total': 1,
                'has_more': False
            }
        }
        mock_get.return_value = mock_response
        
        # Test list agents
        response = client.list_agents(limit=10, offset=0)
        
        assert isinstance(response, AgentListResponse)
        assert len(response.agents) == 1
        assert response.total_count == 1
        assert response.has_more is False
        mock_get.assert_called_once()
    
    def test_list_agents_invalid_params(self, client):
        """Test list agents with invalid parameters"""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            client.list_agents(limit=0)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            client.list_agents(limit=101)
        
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            client.list_agents(offset=-1)
    
    @patch('requests.get')
    def test_search_agents_success(self, mock_get, client):
        """Test successful agent search"""
        # Mock successful response - API returns a direct list
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'agent_card': {
                    'name': 'Search Result Agent',
                    'description': 'A search result',
                    'version': '1.0.0',
                    'url': 'http://localhost:8080/',
                    'skills': [
                        {
                            'id': 'python',
                            'name': 'Python Programming',
                            'description': 'Python development and scripting',
                            'tags': ['programming', 'python']
                        },
                        {
                            'id': 'search',
                            'name': 'Search Functionality',
                            'description': 'Search and retrieval capabilities',
                            'tags': ['search', 'retrieval']
                        }
                    ],
                    'capabilities': {'streaming': True},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'JSONRPC',
                    'protocol_version': '0.3.0'
                },
                'similarity_score': 0.85,
                'matched_skills': ['python']
            }
        ]
        mock_get.return_value = mock_response
        
        # Test search agents
        results = client.search_agents(query="python search")
        
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].similarity_score == 0.85
        assert results[0].matched_skills == ['python']
        mock_get.assert_called_once()
    
    def test_search_agents_invalid_params(self, client):
        """Test search agents with invalid parameters"""
        with pytest.raises(ValidationError, match="Either query text or skills must be provided"):
            client.search_agents()
        
        with pytest.raises(ValidationError, match="top_k must be between 1 and 30"):
            client.search_agents(query="test", top_k=0)
        
        with pytest.raises(ValidationError, match="top_k must be between 1 and 30"):
            client.search_agents(query="test", top_k=31)
    
    @patch('requests.post')
    def test_update_health_success(self, mock_post, client):
        """Test successful health update"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent_id': 'test-agent-id',
            'message': 'Health status updated successfully'
        }
        mock_post.return_value = mock_response
        
        # Test update health
        success = client.update_health('test-agent-id')
        
        assert success is True
        mock_post.assert_called_once()
    
    def test_update_health_invalid_id(self, client):
        """Test update health with invalid ID"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_health("")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_health("   ")
    
    @patch('requests.put')
    def test_update_agent_success(self, mock_put, client):
        """Test successful agent update"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent_id': 'test-agent-id',
            'message': 'Agent updated successfully'
        }
        mock_put.return_value = mock_response
        
        # Test update agent
        update_data = {
            'name': 'Updated Agent Name',
            'skills': ['python', 'testing', 'new-skill']
        }
        success = client.update_agent('test-agent-id', update_data)
        
        assert success is True
        mock_put.assert_called_once()
        
        # Verify the request was made with correct data
        call_args = mock_put.call_args
        assert call_args[1]['json'] == update_data
    
    @patch('requests.put')
    def test_update_agent_not_found(self, mock_put, client):
        """Test agent update with not found error"""
        # Mock not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': {
                'code': 'AGENT_NOT_FOUND',
                'message': 'Agent not found'
            }
        }
        mock_put.return_value = mock_response
        
        # Test update agent
        with pytest.raises(NotFoundError, match="Agent not found"):
            client.update_agent('invalid-id', {'name': 'New Name'})
    
    def test_update_agent_invalid_params(self, client):
        """Test update agent with invalid parameters"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_agent("", {'name': 'New Name'})
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_agent("   ", {'name': 'New Name'})
        
        with pytest.raises(ValidationError, match="Update data is required"):
            client.update_agent('test-id', {})
        
        with pytest.raises(ValidationError, match="Update data is required"):
            client.update_agent('test-id', None)
    
    @patch('requests.delete')
    def test_delete_agent_success(self, mock_delete, client):
        """Test successful agent deletion"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent_id': 'test-agent-id',
            'message': 'Agent deleted successfully'
        }
        mock_delete.return_value = mock_response
        
        # Test delete agent
        success = client.delete_agent('test-agent-id')
        
        assert success is True
        mock_delete.assert_called_once()
    
    @patch('requests.delete')
    def test_delete_agent_not_found(self, mock_delete, client):
        """Test agent deletion with not found error"""
        # Mock not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': {
                'code': 'AGENT_NOT_FOUND',
                'message': 'Agent not found'
            }
        }
        mock_delete.return_value = mock_response
        
        # Test delete agent
        with pytest.raises(NotFoundError, match="Agent not found"):
            client.delete_agent('invalid-id')
    
    def test_delete_agent_invalid_id(self, client):
        """Test delete agent with invalid ID"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.delete_agent("")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.delete_agent("   ")
    
    @patch('requests.get')
    def test_authentication_error(self, mock_get, client):
        """Test authentication error handling"""
        # Mock authentication error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with pytest.raises(AuthenticationError, match="Authentication failed"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_server_error(self, mock_get, client):
        """Test server error handling"""
        # Mock server error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Internal server error'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(ServerError, match="Internal server error"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_connection_error(self, mock_get, client):
        """Test connection error handling"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(AgentRegistryError, match="Connection error"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_timeout_error(self, mock_get, client):
        """Test timeout error handling"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(AgentRegistryError, match="Request timeout"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_invalid_json_response(self, mock_get, client):
        """Test handling of invalid JSON response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid JSON response"
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Invalid JSON response from API"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_unexpected_status_code(self, mock_get, client):
        """Test handling of unexpected status codes"""
        mock_response = Mock()
        mock_response.status_code = 418  # I'm a teapot
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Unexpected response status: 418"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_403_forbidden_error(self, mock_get, client):
        """Test 403 Forbidden error handling"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with pytest.raises(AuthenticationError, match="Access denied"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_400_bad_request_non_validation(self, mock_get, client):
        """Test 400 Bad Request that's not a validation error"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'code': 'BAD_REQUEST',
                'message': 'Malformed request'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Malformed request"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_400_bad_request_invalid_json(self, mock_get, client):
        """Test 400 Bad Request with invalid JSON"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Bad request text"
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Bad request: Bad request text"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_404_invalid_json(self, mock_get, client):
        """Test 404 Not Found with invalid JSON"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response
        
        with pytest.raises(NotFoundError, match="Resource not found"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_500_invalid_json(self, mock_get, client):
        """Test 500 Server Error with invalid JSON"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Internal server error text"
        mock_get.return_value = mock_response
        
        with pytest.raises(ServerError, match="Server error: Internal server error text"):
            client.get_agent('test-id')


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization flows"""
    
    def test_init_with_custom_region(self):
        """Test client initialization with custom region"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            client = AgentRegistryClient(
                api_gateway_url="https://test-api.execute-api.eu-west-1.amazonaws.com/prod",
                region="eu-west-1"
            )
            
            assert client.region == "eu-west-1"
            assert client.auth.region == "eu-west-1"
    
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from API URL"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            client = AgentRegistryClient(
                api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod/"
            )
            
            assert client.api_gateway_url == "https://test-api.execute-api.us-east-1.amazonaws.com/prod"
    
    @patch('boto3.Session')
    def test_credentials_with_session_token(self, mock_session):
        """Test authentication with session token"""
        mock_creds = Mock()
        mock_creds.access_key = 'test-access-key'
        mock_creds.secret_key = 'test-secret-key'
        mock_creds.token = 'test-session-token'
        mock_session.return_value.get_credentials.return_value = mock_creds
        
        client = AgentRegistryClient("https://test-api.execute-api.us-east-1.amazonaws.com/prod")
        
        # Verify AWS4Auth was created with session token
        assert client.auth.session_token == 'test-session-token'
    
    @patch('boto3.Session')
    def test_credentials_without_session_token(self, mock_session):
        """Test authentication without session token"""
        mock_creds = Mock()
        mock_creds.access_key = 'test-access-key'
        mock_creds.secret_key = 'test-secret-key'
        mock_creds.token = None
        mock_session.return_value.get_credentials.return_value = mock_creds
        
        client = AgentRegistryClient("https://test-api.execute-api.us-east-1.amazonaws.com/prod")
        
        # Verify AWS4Auth was created without session token
        assert client.auth.session_token is None
    
    @patch('requests.get')
    def test_request_headers_and_auth(self, mock_get):
        """Test that requests include proper headers and authentication"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            client = AgentRegistryClient("https://test-api.execute-api.us-east-1.amazonaws.com/prod")
            
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'agent': {'name': 'Test'}}
            mock_get.return_value = mock_response
            
            # Make request
            try:
                client.get_agent('test-id')
            except:
                pass  # We don't care about the result, just the call
            
            # Verify request was made with proper headers and auth
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            
            # Check headers
            headers = call_args[1]['headers']
            assert headers['Content-Type'] == 'application/json'
            assert headers['Accept'] == 'application/json'
            
            # Check auth object is present
            assert 'auth' in call_args[1]
            assert call_args[1]['timeout'] == 30


class TestRequestResponseSerialization:
    """Test request and response serialization"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        )
    
    @pytest.fixture
    def sample_agent_card(self):
        """Sample AgentCard for testing"""
        from a2a.types import AgentSkill, AgentCapabilities
        
        return AgentCard(
            name="Serialization Test Agent",
            description="Agent for testing serialization",
            version="2.0.0",
            url="http://localhost:9000/",
            skills=[
                AgentSkill(
                    id="serialization",
                    name="Data Serialization",
                    description="JSON and data serialization",
                    tags=["json", "serialization"]
                )
            ],
            capabilities=AgentCapabilities(streaming=False),
            default_input_modes=["text", "json"],
            default_output_modes=["text", "json"],
            preferred_transport="HTTP",
            protocol_version="0.3.0"
        )
    
    @patch('requests.post')
    def test_create_agent_serialization(self, mock_post, client, sample_agent_card):
        """Test AgentCard serialization in create_agent"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'agent_id': 'test-id'}
        mock_post.return_value = mock_response
        
        client.create_agent(sample_agent_card)
        
        # Verify the request body was properly serialized
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        request_body = call_args[1]['json']
        
        # Check that AgentCard was properly serialized
        assert request_body['name'] == "Serialization Test Agent"
        assert request_body['version'] == "2.0.0"
        assert request_body['url'] == "http://localhost:9000/"
        assert len(request_body['skills']) == 1
        assert request_body['skills'][0]['id'] == "serialization"
        assert request_body['capabilities']['streaming'] is False
        assert request_body['defaultInputModes'] == ["text", "json"]
        assert request_body['preferredTransport'] == "HTTP"
    
    @patch('requests.get')
    def test_get_agent_deserialization(self, mock_get, client):
        """Test AgentCard deserialization in get_agent"""
        # Mock response with complete agent data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent': {
                'name': 'Deserialization Test Agent',
                'description': 'Agent for testing deserialization',
                'version': '3.0.0',
                'url': 'http://localhost:7000/',
                'skills': [
                    {
                        'id': 'deserialization',
                        'name': 'Data Deserialization',
                        'description': 'JSON and data deserialization',
                        'tags': ['json', 'deserialization']
                    }
                ],
                'capabilities': {'streaming': True},
                'default_input_modes': ['text'],
                'default_output_modes': ['text', 'json'],
                'preferred_transport': 'JSONRPC',
                'protocol_version': '0.3.0'
            }
        }
        mock_get.return_value = mock_response
        
        agent = client.get_agent('test-id')
        
        # Verify proper deserialization
        assert isinstance(agent, AgentCard)
        assert agent.name == 'Deserialization Test Agent'
        assert agent.version == '3.0.0'
        assert agent.url == 'http://localhost:7000/'
        assert len(agent.skills) == 1
        assert agent.skills[0].id == 'deserialization'
        assert agent.capabilities.streaming is True
        assert agent.default_input_modes == ['text']
        assert agent.default_output_modes == ['text', 'json']
        assert agent.preferred_transport == 'JSONRPC'
    
    @patch('requests.get')
    def test_get_agent_malformed_response(self, mock_get, client):
        """Test handling of malformed agent data in response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent': {
                'name': 'Test Agent',
                # Missing required fields
                'invalid_field': 'invalid_value'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Failed to parse agent data"):
            client.get_agent('test-id')
    
    @patch('requests.get')
    def test_get_agent_missing_agent_data(self, mock_get, client):
        """Test handling of missing agent data in response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Success but no agent data'
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Invalid response: missing agent data"):
            client.get_agent('test-id')
    
    @patch('requests.post')
    def test_create_agent_missing_agent_id(self, mock_post, client, sample_agent_card):
        """Test handling of missing agent_id in create response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Agent created but no ID returned'
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Invalid response: missing agent_id"):
            client.create_agent(sample_agent_card)
    
    @patch('requests.get')
    def test_list_agents_deserialization(self, mock_get, client):
        """Test AgentCard list deserialization"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agents': [
                {
                    'name': 'Agent 1',
                    'description': 'First agent',
                    'version': '1.0.0',
                    'url': 'http://localhost:8001/',
                    'skills': [],
                    'capabilities': {'streaming': False},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'HTTP',
                    'protocol_version': '0.3.0'
                },
                {
                    'name': 'Agent 2',
                    'description': 'Second agent',
                    'version': '2.0.0',
                    'url': 'http://localhost:8002/',
                    'skills': [],
                    'capabilities': {'streaming': True},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'JSONRPC',
                    'protocol_version': '0.3.0'
                }
            ],
            'pagination': {
                'total': 2,
                'has_more': False
            }
        }
        mock_get.return_value = mock_response
        
        response = client.list_agents()
        
        assert len(response.agents) == 2
        assert all(isinstance(agent, AgentCard) for agent in response.agents)
        assert response.agents[0].name == 'Agent 1'
        assert response.agents[1].name == 'Agent 2'
        assert response.total_count == 2
        assert response.has_more is False
    
    @patch('requests.get')
    def test_list_agents_malformed_agent_data(self, mock_get, client):
        """Test handling of malformed agent data in list response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agents': [
                {
                    'name': 'Valid Agent',
                    'description': 'Valid agent',
                    'version': '1.0.0',
                    'url': 'http://localhost:8001/',
                    'skills': [],
                    'capabilities': {'streaming': False},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'HTTP',
                    'protocol_version': '0.3.0'
                },
                {
                    'name': 'Invalid Agent',
                    # Missing required fields
                }
            ],
            'pagination': {'total': 2, 'has_more': False}
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Failed to parse agent data"):
            client.list_agents()
    
    @patch('requests.get')
    def test_search_agents_deserialization(self, mock_get, client):
        """Test search results deserialization"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {
                    'agent_card': {
                        'name': 'Search Agent 1',
                        'description': 'First search result',
                        'version': '1.0.0',
                        'url': 'http://localhost:8001/',
                        'skills': [
                            {
                                'id': 'search',
                                'name': 'Search Skill',
                                'description': 'Search functionality',
                                'tags': ['search']
                            }
                        ],
                        'capabilities': {'streaming': False},
                        'default_input_modes': ['text'],
                        'default_output_modes': ['text'],
                        'preferred_transport': 'HTTP',
                        'protocol_version': '0.3.0'
                    },
                    'similarity_score': 0.95,
                    'matched_skills': ['search']
                },
                {
                    'agent_card': {
                        'name': 'Search Agent 2',
                        'description': 'Second search result',
                        'version': '2.0.0',
                        'url': 'http://localhost:8002/',
                        'skills': [],
                        'capabilities': {'streaming': True},
                        'default_input_modes': ['text'],
                        'default_output_modes': ['text'],
                        'preferred_transport': 'JSONRPC',
                        'protocol_version': '0.3.0'
                    },
                    'similarity_score': 0.75,
                    'matched_skills': []
                }
            ]
        }
        mock_get.return_value = mock_response
        
        results = client.search_agents(query="search test")
        
        assert len(results) == 2
        assert all(isinstance(result, SearchResult) for result in results)
        assert results[0].agent_card.name == 'Search Agent 1'
        assert results[0].similarity_score == 0.95
        assert results[0].matched_skills == ['search']
        assert results[1].agent_card.name == 'Search Agent 2'
        assert results[1].similarity_score == 0.75
        assert results[1].matched_skills == []
    
    @patch('requests.get')
    def test_search_agents_malformed_result(self, mock_get, client):
        """Test handling of malformed search result data"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {
                    'agent_card': {
                        'name': 'Invalid Agent',
                        # Missing required fields
                    },
                    'similarity_score': 0.95
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(AgentRegistryError, match="Failed to parse search result"):
            client.search_agents(query="test")


class TestParameterValidation:
    """Test parameter validation for all methods"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        )
    
    def test_list_agents_parameter_validation(self, client):
        """Test comprehensive parameter validation for list_agents"""
        # Test limit validation
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            client.list_agents(limit=0)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            client.list_agents(limit=101)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            client.list_agents(limit=-5)
        
        # Test offset validation
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            client.list_agents(offset=-1)
        
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            client.list_agents(offset=-100)
    
    def test_search_agents_parameter_validation(self, client):
        """Test comprehensive parameter validation for search_agents"""
        # Test missing both query and skills
        with pytest.raises(ValidationError, match="Either query text or skills must be provided"):
            client.search_agents()
        
        with pytest.raises(ValidationError, match="Either query text or skills must be provided"):
            client.search_agents(query=None, skills=None)
        
        with pytest.raises(ValidationError, match="Either query text or skills must be provided"):
            client.search_agents(query="", skills=[])
        
        # Test top_k validation
        with pytest.raises(ValidationError, match="top_k must be between 1 and 30"):
            client.search_agents(query="test", top_k=0)
        
        with pytest.raises(ValidationError, match="top_k must be between 1 and 30"):
            client.search_agents(query="test", top_k=31)
        
        with pytest.raises(ValidationError, match="top_k must be between 1 and 30"):
            client.search_agents(query="test", top_k=-1)
    
    def test_get_agent_parameter_validation(self, client):
        """Test parameter validation for get_agent"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.get_agent("")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.get_agent("   ")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.get_agent("\t\n")
    
    def test_update_health_parameter_validation(self, client):
        """Test parameter validation for update_health"""
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_health("")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_health("   ")
        
        with pytest.raises(ValidationError, match="Agent ID is required"):
            client.update_health("\t\n")


class TestRequestConstruction:
    """Test proper request construction for all methods"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        )
    
    @patch('requests.get')
    def test_list_agents_request_construction(self, mock_get, client):
        """Test proper request construction for list_agents"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'agents': [], 'pagination': {'total': 0, 'has_more': False}}
        mock_get.return_value = mock_response
        
        client.list_agents(limit=25, offset=50)
        
        # Verify request construction
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://test-api.execute-api.us-east-1.amazonaws.com/prod/agents"
        
        # Check parameters
        params = call_args[1]['params']
        assert params['limit'] == 25
        assert params['offset'] == 50
    
    @patch('requests.get')
    def test_search_agents_request_construction_text_only(self, mock_get, client):
        """Test request construction for search_agents with text only"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': []}
        mock_get.return_value = mock_response
        
        client.search_agents(query="python programming", top_k=15)
        
        # Verify request construction
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://test-api.execute-api.us-east-1.amazonaws.com/prod/agents/search"
        
        # Check parameters
        params = call_args[1]['params']
        assert params['text'] == "python programming"
        assert params['top_k'] == 15
        assert 'skills' not in params
    
    @patch('requests.get')
    def test_search_agents_request_construction_skills_only(self, mock_get, client):
        """Test request construction for search_agents with skills only"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': []}
        mock_get.return_value = mock_response
        
        client.search_agents(skills=["python", "testing", "automation"], top_k=20)
        
        # Verify request construction
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://test-api.execute-api.us-east-1.amazonaws.com/prod/agents/search"
        
        # Check parameters
        params = call_args[1]['params']
        assert params['skills'] == "python,testing,automation"
        assert params['top_k'] == 20
        assert 'text' not in params
    
    @patch('requests.get')
    def test_search_agents_request_construction_both(self, mock_get, client):
        """Test request construction for search_agents with both text and skills"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': []}
        mock_get.return_value = mock_response
        
        client.search_agents(query="machine learning", skills=["ml", "ai"], top_k=5)
        
        # Verify request construction
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check parameters
        params = call_args[1]['params']
        assert params['text'] == "machine learning"
        assert params['skills'] == "ml,ai"
        assert params['top_k'] == 5
    
    @patch('requests.get')
    def test_get_agent_request_construction(self, mock_get, client):
        """Test request construction for get_agent"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'agent': {
                'name': 'Test Agent',
                'description': 'Test description',
                'version': '1.0.0',
                'url': 'http://localhost:8080/',
                'skills': [],
                'capabilities': {'streaming': False},
                'default_input_modes': ['text'],
                'default_output_modes': ['text'],
                'preferred_transport': 'HTTP',
                'protocol_version': '0.3.0'
            }
        }
        mock_get.return_value = mock_response
        
        client.get_agent("test-agent-123")
        
        # Verify request construction
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://test-api.execute-api.us-east-1.amazonaws.com/prod/agents/test-agent-123"
        
        # Check no parameters for GET agent
        assert 'params' not in call_args[1] or call_args[1]['params'] is None
    
    @patch('requests.post')
    def test_update_health_request_construction(self, mock_post, client):
        """Test request construction for update_health"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': 'Health updated successfully'}
        mock_post.return_value = mock_response
        
        client.update_health("test-agent-456")
        
        # Verify request construction
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert call_args[0][0] == "https://test-api.execute-api.us-east-1.amazonaws.com/prod/agents/test-agent-456/health"


class TestRetryLogic:
    """Test retry logic and error handling"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client with retry configuration"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod",
            max_retries=3,
            retry_backoff_factor=0.1  # Faster tests
        )
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    @patch('requests.get')
    def test_retry_on_server_error_success(self, mock_get, mock_sleep, client):
        """Test successful retry after server error"""
        # First call fails with 500, second succeeds
        mock_responses = [
            Mock(status_code=500, json=lambda: {'error': {'message': 'Server error'}}),
            Mock(status_code=200, json=lambda: {'agent': {'name': 'Test Agent'}})
        ]
        mock_get.side_effect = mock_responses
        
        # Should succeed after retry
        try:
            result = client.get_agent('test-id')
            # We expect this to fail due to incomplete agent data, but the retry logic worked
        except AgentRegistryError:
            pass  # Expected due to incomplete test data
        
        # Verify retry occurred
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_retry_on_server_error_max_retries(self, mock_get, mock_sleep, client):
        """Test max retries reached with server error"""
        # All calls fail with 500
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': {'message': 'Persistent server error'}}
        mock_get.return_value = mock_response
        
        with pytest.raises(ServerError, match="Persistent server error"):
            client.get_agent('test-id')
        
        # Verify all retries were attempted (initial + 3 retries = 4 total)
        assert mock_get.call_count == 4
        assert mock_sleep.call_count == 3
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_retry_on_timeout_success(self, mock_get, mock_sleep, client):
        """Test successful retry after timeout"""
        # First call times out, second succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            Mock(status_code=200, json=lambda: {'agent': {'name': 'Test Agent'}})
        ]
        
        try:
            result = client.get_agent('test-id')
        except AgentRegistryError:
            pass  # Expected due to incomplete test data
        
        # Verify retry occurred
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_retry_on_connection_error_max_retries(self, mock_get, mock_sleep, client):
        """Test max retries reached with connection error"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(AgentRegistryError, match="Connection error"):
            client.get_agent('test-id')
        
        # Verify all retries were attempted
        assert mock_get.call_count == 4
        assert mock_sleep.call_count == 3
    
    @patch('requests.get')
    def test_no_retry_on_validation_error(self, mock_get, client):
        """Test that validation errors are not retried"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid input'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(ValidationError, match="Invalid input"):
            client.get_agent('test-id')
        
        # Verify no retries occurred
        assert mock_get.call_count == 1
    
    @patch('requests.get')
    def test_no_retry_on_authentication_error(self, mock_get, client):
        """Test that authentication errors are not retried"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with pytest.raises(AuthenticationError, match="Authentication failed"):
            client.get_agent('test-id')
        
        # Verify no retries occurred
        assert mock_get.call_count == 1
    
    @patch('requests.get')
    def test_no_retry_on_not_found_error(self, mock_get, client):
        """Test that not found errors are not retried"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            'error': {
                'message': 'Agent not found'
            }
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(NotFoundError, match="Agent not found"):
            client.get_agent('test-id')
        
        # Verify no retries occurred
        assert mock_get.call_count == 1
    
    @patch('time.sleep')
    def test_retry_delay_calculation(self, mock_sleep, client):
        """Test retry delay calculation with exponential backoff"""
        # Test delay calculation directly
        delay_0 = client._calculate_retry_delay(0)
        delay_1 = client._calculate_retry_delay(1)
        delay_2 = client._calculate_retry_delay(2)
        
        # Delays should increase exponentially (with some jitter)
        assert 0.05 <= delay_0 <= 0.25  # ~0.1 * 1 * 2^0 + jitter
        assert 0.15 <= delay_1 <= 0.35  # ~0.1 * 1 * 2^1 + jitter
        assert 0.35 <= delay_2 <= 0.55  # ~0.1 * 1 * 2^2 + jitter
    
    def test_is_retryable_error(self, client):
        """Test retryable error detection"""
        # Server errors should be retryable
        assert client._is_retryable_error(ServerError("Server error"))
        
        # Timeout should be retryable
        assert client._is_retryable_error(requests.exceptions.Timeout("Timeout"))
        
        # Connection error should be retryable
        assert client._is_retryable_error(requests.exceptions.ConnectionError("Connection failed"))
        
        # Validation errors should not be retryable
        assert not client._is_retryable_error(ValidationError("Validation failed"))
        
        # Authentication errors should not be retryable
        assert not client._is_retryable_error(AuthenticationError("Auth failed"))
        
        # Not found errors should not be retryable
        assert not client._is_retryable_error(NotFoundError("Not found"))
    
    def test_client_init_with_retry_params(self):
        """Test client initialization with custom retry parameters"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            
            client = AgentRegistryClient(
                api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod",
                max_retries=5,
                retry_backoff_factor=2.0
            )
            
            assert client.max_retries == 5
            assert client.retry_backoff_factor == 2.0
    
    @patch('time.sleep')
    @patch('requests.post')
    def test_retry_on_create_agent_server_error(self, mock_post, mock_sleep, client):
        """Test retry logic works for create_agent method"""
        from a2a.types import AgentCard, AgentSkill, AgentCapabilities
        
        agent_card = AgentCard(
            name="Test Agent",
            description="Test",
            version="1.0.0",
            url="http://localhost:8080/",
            skills=[],
            capabilities=AgentCapabilities(streaming=False),
            default_input_modes=["text"],
            default_output_modes=["text"],
            preferred_transport="HTTP",
            protocol_version="0.3.0"
        )
        
        # First call fails with 500, second succeeds
        mock_responses = [
            Mock(status_code=500, json=lambda: {'error': {'message': 'Server error'}}),
            Mock(status_code=200, json=lambda: {'agent_id': 'test-id-123'})
        ]
        mock_post.side_effect = mock_responses
        
        result = client.create_agent(agent_card)
        
        assert result == 'test-id-123'
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_retry_on_list_agents_timeout(self, mock_get, mock_sleep, client):
        """Test retry logic works for list_agents method"""
        # First call times out, second succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            Mock(status_code=200, json=lambda: {
                'agents': [],
                'pagination': {'total': 0, 'has_more': False}
            })
        ]
        
        result = client.list_agents()
        
        assert len(result.agents) == 0
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_retry_on_search_agents_connection_error(self, mock_get, mock_sleep, client):
        """Test retry logic works for search_agents method"""
        # First call has connection error, second succeeds
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {'results': []})
        ]
        
        result = client.search_agents(query="test")
        
        assert len(result) == 0
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    @patch('requests.post')
    def test_retry_on_update_health_server_error(self, mock_post, mock_sleep, client):
        """Test retry logic works for update_health method"""
        # First call fails with 500, second succeeds
        mock_responses = [
            Mock(status_code=500, json=lambda: {'error': {'message': 'Server error'}}),
            Mock(status_code=200, json=lambda: {'message': 'Health updated successfully'})
        ]
        mock_post.side_effect = mock_responses
        
        result = client.update_health('test-id')
        
        assert result is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_creds = Mock()
            mock_creds.access_key = 'test-access-key'
            mock_creds.secret_key = 'test-secret-key'
            mock_creds.token = 'test-token'
            mock_session.return_value.get_credentials.return_value = mock_creds
            yield mock_creds
    
    @pytest.fixture
    def client(self, mock_credentials):
        """Create test client"""
        return AgentRegistryClient(
            api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod"
        )
    
    @patch('requests.get')
    def test_list_agents_empty_response(self, mock_get, client):
        """Test list_agents with empty response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        
        result = client.list_agents()
        
        # Should handle missing fields gracefully
        assert len(result.agents) == 0
        assert result.total_count == 0
        assert result.has_more is False
    
    @patch('requests.get')
    def test_search_agents_empty_results(self, mock_get, client):
        """Test search_agents with empty results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        
        result = client.search_agents(query="nonexistent")
        
        assert len(result) == 0
    
    @patch('requests.get')
    def test_search_agents_missing_similarity_score(self, mock_get, client):
        """Test search_agents with missing similarity score in results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {
                    'agent_card': {
                        'name': 'Test Agent',
                        'description': 'Test',
                        'version': '1.0.0',
                        'url': 'http://localhost:8080/',
                        'skills': [],
                        'capabilities': {'streaming': False},
                        'default_input_modes': ['text'],
                        'default_output_modes': ['text'],
                        'preferred_transport': 'HTTP',
                        'protocol_version': '0.3.0'
                    }
                    # Missing similarity_score and matched_skills
                }
            ]
        }
        mock_get.return_value = mock_response
        
        result = client.search_agents(query="test")
        
        assert len(result) == 1
        assert result[0].similarity_score == 0.0  # Default value
        assert result[0].matched_skills == []  # Default value
    
    @patch('requests.post')
    def test_update_health_non_success_message(self, mock_post, client):
        """Test update_health with non-success message"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Agent health update failed'
        }
        mock_post.return_value = mock_response
        
        result = client.update_health('test-id')
        
        assert result is False  # Should return False for non-success messages
    
    def test_search_agents_with_empty_skills_list(self, client):
        """Test search_agents with empty skills list"""
        with pytest.raises(ValidationError, match="Either query text or skills must be provided"):
            client.search_agents(skills=[])
    
    def test_search_agents_with_whitespace_query(self, client):
        """Test search_agents with whitespace-only query"""
        # This should be allowed as whitespace might be meaningful for search
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'results': []}
            mock_get.return_value = mock_response
            
            result = client.search_agents(query="   ")
            assert len(result) == 0
    
    def test_list_agents_boundary_values(self, client):
        """Test list_agents with boundary values"""
        # Test minimum valid values
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'agents': [], 'pagination': {'total': 0, 'has_more': False}}
            mock_get.return_value = mock_response
            
            result = client.list_agents(limit=1, offset=0)
            assert len(result.agents) == 0
        
        # Test maximum valid values
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'agents': [], 'pagination': {'total': 0, 'has_more': False}}
            mock_get.return_value = mock_response
            
            result = client.list_agents(limit=100, offset=999999)
            assert len(result.agents) == 0
    
    def test_search_agents_boundary_values(self, client):
        """Test search_agents with boundary values"""
        # Test minimum valid top_k
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'results': []}
            mock_get.return_value = mock_response
            
            result = client.search_agents(query="test", top_k=1)
            assert len(result) == 0
        
        # Test maximum valid top_k
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'results': []}
            mock_get.return_value = mock_response
            
            result = client.search_agents(query="test", top_k=30)
            assert len(result) == 0