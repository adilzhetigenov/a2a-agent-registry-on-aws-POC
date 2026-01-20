"""
Pytest configuration and fixtures for client tests
"""
import pytest
from unittest.mock import Mock, patch
from a2a.types import AgentCard, AgentSkill, AgentCapabilities
from agent_registry_client import AgentRegistryClient


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials for testing"""
    with patch('boto3.Session') as mock_session:
        mock_creds = Mock()
        mock_creds.access_key = 'test-access-key'
        mock_creds.secret_key = 'test-secret-key'
        mock_creds.token = 'test-token'
        mock_session.return_value.get_credentials.return_value = mock_creds
        yield mock_creds


@pytest.fixture
def client(mock_aws_credentials):
    """Agent Registry Client fixture with mocked credentials"""
    return AgentRegistryClient(
        api_gateway_url="https://test-api.execute-api.us-east-1.amazonaws.com/prod",
        region="us-east-1"
    )


@pytest.fixture
def sample_agent_card():
    """Sample AgentCard for testing"""
    return AgentCard(
        name="Test Agent",
        description="A test agent for unit testing",
        version="1.0.0",
        url="http://localhost:8080/",
        skills=[
            AgentSkill(
                id="python",
                name="Python Programming",
                description="Python development and scripting",
                tags=["programming", "python", "development"]
            ),
            AgentSkill(
                id="testing",
                name="Software Testing",
                description="Automated testing and QA",
                tags=["testing", "qa", "automation"]
            )
        ],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text", "json"],
        preferred_transport="JSONRPC",
        protocol_version="0.3.0"
    )


@pytest.fixture
def mock_successful_response():
    """Mock successful HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def mock_server_error_response():
    """Mock server error HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }
    return mock_response


@pytest.fixture
def mock_validation_error_response():
    """Mock validation error HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        'error': {
            'code': 'VALIDATION_ERROR',
            'message': 'Validation failed'
        }
    }
    return mock_response


@pytest.fixture
def mock_not_found_response():
    """Mock not found HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.json.return_value = {
        'error': {
            'code': 'AGENT_NOT_FOUND',
            'message': 'Agent not found'
        }
    }
    return mock_response


@pytest.fixture
def mock_auth_error_response():
    """Mock authentication error HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 401
    return mock_response


@pytest.fixture
def sample_agent_list_response():
    """Sample agent list response data"""
    return {
        'agents': [
            {
                'name': 'Agent 1',
                'description': 'First test agent',
                'version': '1.0.0',
                'url': 'http://localhost:8001/',
                'skills': [
                    {
                        'id': 'skill1',
                        'name': 'Skill 1',
                        'description': 'First skill',
                        'tags': ['tag1']
                    }
                ],
                'capabilities': {'streaming': True},
                'default_input_modes': ['text'],
                'default_output_modes': ['text'],
                'preferred_transport': 'JSONRPC',
                'protocol_version': '0.3.0'
            },
            {
                'name': 'Agent 2',
                'description': 'Second test agent',
                'version': '2.0.0',
                'url': 'http://localhost:8002/',
                'skills': [],
                'capabilities': {'streaming': False},
                'default_input_modes': ['text'],
                'default_output_modes': ['text'],
                'preferred_transport': 'HTTP',
                'protocol_version': '0.3.0'
            }
        ],
        'pagination': {
            'total': 2,
            'has_more': False
        }
    }


@pytest.fixture
def sample_search_response():
    """Sample search response data"""
    return {
        'results': [
            {
                'agent_card': {
                    'name': 'Search Result Agent',
                    'description': 'Agent found in search',
                    'version': '1.0.0',
                    'url': 'http://localhost:8080/',
                    'skills': [
                        {
                            'id': 'search_skill',
                            'name': 'Search Skill',
                            'description': 'Search functionality',
                            'tags': ['search', 'find']
                        }
                    ],
                    'capabilities': {'streaming': True},
                    'default_input_modes': ['text'],
                    'default_output_modes': ['text'],
                    'preferred_transport': 'JSONRPC',
                    'protocol_version': '0.3.0'
                },
                'similarity_score': 0.85,
                'matched_skills': ['search_skill']
            }
        ]
    }