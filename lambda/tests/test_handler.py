"""
Unit tests for Lambda handler
"""
import json
import pytest
from unittest.mock import Mock, patch

from src.handler import lambda_handler, parse_path_parameters, route_request, APIError


class TestLambdaHandler:
    """Test cases for the main Lambda handler"""
    
    def test_lambda_handler_options_request(self):
        """Test CORS preflight OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/agents',
            'queryStringParameters': {},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
    
    def test_lambda_handler_get_agents(self):
        """Test GET /agents endpoint"""
        event = {
            'httpMethod': 'GET',
            'path': '/agents',
            'queryStringParameters': {'limit': '10', 'offset': '0'},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'agents' in body
        assert 'pagination' in body
    
    def test_lambda_handler_get_agent_by_id(self):
        """Test GET /agents/{id} endpoint"""
        event = {
            'httpMethod': 'GET',
            'path': '/agents/123e4567-e89b-12d3-a456-426614174000',
            'queryStringParameters': {},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'agent_id' in body
    
    @patch('src.services.search_service.SearchService')
    def test_lambda_handler_search_agents(self, mock_search_service_class):
        """Test GET /agents/search endpoint"""
        # Mock the search service
        mock_search_service = Mock()
        mock_search_service.search_agents.return_value = [
            {
                'name': 'Test Agent',
                'description': 'A Python developer agent',
                'skills': ['python', 'development'],
                '_search_metadata': {
                    'similarity_score': 0.9,
                    'matched_skills': ['python'],
                    'query': 'python developer'
                }
            }
        ]
        mock_search_service_class.return_value = mock_search_service
        
        event = {
            'httpMethod': 'GET',
            'path': '/agents/search',
            'queryStringParameters': {'text': 'python developer'},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'results' in body
        assert 'query' in body
        assert len(body['results']) == 1
        assert body['results'][0]['name'] == 'Test Agent'
    
    @patch('src.services.search_service.SearchService')
    def test_lambda_handler_search_agents_skills_only(self, mock_search_service_class):
        """Test GET /agents/search endpoint with skills only"""
        # Mock the search service
        mock_search_service = Mock()
        mock_search_service.search_agents_by_skills_only.return_value = [
            {
                'name': 'Python Agent',
                'description': 'An agent specialized in Python',
                'skills': ['python', 'django', 'flask'],
                '_search_metadata': {
                    'matched_skills': ['python'],
                    'search_type': 'skills_only'
                }
            }
        ]
        mock_search_service_class.return_value = mock_search_service
        
        event = {
            'httpMethod': 'GET',
            'path': '/agents/search',
            'queryStringParameters': {'skills': 'python,django'},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'results' in body
        assert 'query' in body
        assert len(body['results']) == 1
        assert body['results'][0]['name'] == 'Python Agent'
        assert body['query']['skills'] == ['python', 'django']
        
        # Verify the correct method was called
        mock_search_service.search_agents_by_skills_only.assert_called_once_with(
            skills=['python', 'django'],
            limit=10
        )
    
    def test_lambda_handler_create_agent(self):
        """Test POST /agents endpoint"""
        agent_data = {
            'name': 'Test Agent',
            'description': 'A test agent for unit testing',
            'provider': 'Test Provider',
            'skills': ['python', 'testing']
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/agents',
            'queryStringParameters': {},
            'body': json.dumps(agent_data)
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'agent_id' in body
    
    @patch('src.services.agent_service.AgentService')
    def test_lambda_handler_update_agent(self, mock_agent_service_class):
        """Test PUT /agents/{id} endpoint"""
        # Mock the agent service
        mock_agent_service = Mock()
        mock_agent_service_class.return_value = mock_agent_service
        mock_agent_service.update_agent.return_value = True
        
        update_data = {
            'name': 'Updated Agent Name',
            'description': 'Updated description for the agent',
            'skills': ['python', 'testing', 'automation']
        }
        
        event = {
            'httpMethod': 'PUT',
            'path': '/agents/123e4567-e89b-12d3-a456-426614174000',
            'queryStringParameters': {},
            'body': json.dumps(update_data)
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'agent_id' in body
        assert body['agent_id'] == '123e4567-e89b-12d3-a456-426614174000'
        assert 'message' in body
        assert 'updated successfully' in body['message']
        
        # Verify the service was called correctly
        mock_agent_service.update_agent.assert_called_once()
        call_args = mock_agent_service.update_agent.call_args
        assert call_args[0][0] == '123e4567-e89b-12d3-a456-426614174000'
        assert call_args[0][1]['name'] == 'Updated Agent Name'
        assert call_args[0][1]['description'] == 'Updated description for the agent'
        assert call_args[0][1]['skills'] == ['python', 'testing', 'automation']
    
    def test_lambda_handler_update_agent_no_body(self):
        """Test PUT /agents/{id} endpoint with no body"""
        event = {
            'httpMethod': 'PUT',
            'path': '/agents/123e4567-e89b-12d3-a456-426614174000',
            'queryStringParameters': {},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'Request body is required' in body['error']['message']
    
    def test_lambda_handler_update_agent_invalid_json(self):
        """Test PUT /agents/{id} endpoint with invalid JSON"""
        event = {
            'httpMethod': 'PUT',
            'path': '/agents/123e4567-e89b-12d3-a456-426614174000',
            'queryStringParameters': {},
            'body': 'invalid json'
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'Invalid JSON' in body['error']['message']
    
    @patch('src.services.agent_service.AgentService')
    def test_lambda_handler_update_health(self, mock_agent_service_class):
        """Test POST /agents/{id}/health endpoint"""
        # Mock the agent service
        mock_agent_service = Mock()
        mock_agent_service_class.return_value = mock_agent_service
        mock_agent_service.update_agent_health.return_value = True
        
        event = {
            'httpMethod': 'POST',
            'path': '/agents/123e4567-e89b-12d3-a456-426614174000/health',
            'queryStringParameters': {},
            'body': '{}'
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'agent_id' in body
        assert body['agent_id'] == '123e4567-e89b-12d3-a456-426614174000'
        assert 'message' in body
        
        # Verify the service was called correctly
        mock_agent_service.update_agent_health.assert_called_once_with('123e4567-e89b-12d3-a456-426614174000')
    
    def test_lambda_handler_invalid_endpoint(self):
        """Test invalid endpoint returns 404"""
        event = {
            'httpMethod': 'GET',
            'path': '/invalid',
            'queryStringParameters': {},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'NOT_FOUND'
    
    def test_lambda_handler_method_not_allowed(self):
        """Test method not allowed returns 405"""
        event = {
            'httpMethod': 'DELETE',
            'path': '/agents',
            'queryStringParameters': {},
            'body': None
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 405
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'METHOD_NOT_ALLOWED'


class TestPathParameterParsing:
    """Test cases for path parameter parsing"""
    
    def test_parse_agent_id(self):
        """Test parsing agent ID from path"""
        path = '/agents/123e4567-e89b-12d3-a456-426614174000'
        params = parse_path_parameters(path)
        
        assert params['id'] == '123e4567-e89b-12d3-a456-426614174000'
    
    def test_parse_health_endpoint(self):
        """Test parsing health endpoint"""
        path = '/agents/123e4567-e89b-12d3-a456-426614174000/health'
        params = parse_path_parameters(path)
        
        assert params['id'] == '123e4567-e89b-12d3-a456-426614174000'
        assert params['resource'] == 'health'
    
    def test_parse_search_endpoint(self):
        """Test that search endpoint doesn't get parsed as agent ID"""
        path = '/agents/search'
        params = parse_path_parameters(path)
        
        assert 'id' not in params
    
    def test_parse_agents_list(self):
        """Test parsing agents list endpoint"""
        path = '/agents'
        params = parse_path_parameters(path)
        
        assert len(params) == 0


class TestRequestRouting:
    """Test cases for request routing"""
    
    def test_route_get_agents(self):
        """Test routing GET /agents"""
        response = route_request('GET', '/agents', {}, None, {})
        
        assert 'agents' in response
        assert 'pagination' in response
    
    def test_route_search_agents(self):
        """Test routing GET /agents/search"""
        query_params = {'text': ['python developer']}
        response = route_request('GET', '/agents/search', query_params, None, {})
        
        assert 'results' in response
        assert 'query' in response
    
    def test_route_create_agent(self):
        """Test routing POST /agents"""
        body = json.dumps({
            'name': 'Test Agent',
            'description': 'A test agent for unit testing',
            'provider': 'Test Provider'
        })
        response = route_request('POST', '/agents', {}, body, {})
        
        assert 'agent_id' in response
    
    @patch('src.services.agent_service.AgentService')
    def test_route_update_agent(self, mock_agent_service_class):
        """Test routing PUT /agents/{id}"""
        # Mock the agent service
        mock_agent_service = Mock()
        mock_agent_service_class.return_value = mock_agent_service
        mock_agent_service.update_agent.return_value = True
        
        body = json.dumps({
            'name': 'Updated Agent Name',
            'description': 'Updated description for the agent'
        })
        path_params = {'id': '123e4567-e89b-12d3-a456-426614174000'}
        
        response = route_request('PUT', '/agents/123e4567-e89b-12d3-a456-426614174000', {}, body, path_params)
        
        assert 'agent_id' in response
        assert 'message' in response
        assert 'updated successfully' in response['message']
    
    def test_route_invalid_path(self):
        """Test routing invalid path raises error"""
        with pytest.raises(APIError) as exc_info:
            route_request('GET', '/invalid', {}, None, {})
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == 'NOT_FOUND'
    
    def test_route_invalid_method(self):
        """Test routing invalid method raises error"""
        with pytest.raises(APIError) as exc_info:
            route_request('DELETE', '/agents', {}, None, {})
        
        assert exc_info.value.status_code == 405
        assert exc_info.value.error_code == 'METHOD_NOT_ALLOWED'


class TestErrorHandling:
    """Test cases for error handling"""
    
    def test_api_error_creation(self):
        """Test APIError creation"""
        error = APIError(400, 'VALIDATION_ERROR', 'Test error', {'field': 'name'})
        
        assert error.status_code == 400
        assert error.error_code == 'VALIDATION_ERROR'
        assert error.message == 'Test error'
        assert error.details == {'field': 'name'}
    
    def test_create_agent_invalid_json(self):
        """Test create agent with invalid JSON"""
        with pytest.raises(APIError) as exc_info:
            route_request('POST', '/agents', {}, 'invalid json', {})
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == 'VALIDATION_ERROR'
    
    def test_create_agent_no_body(self):
        """Test create agent with no body"""
        with pytest.raises(APIError) as exc_info:
            route_request('POST', '/agents', {}, None, {})
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == 'VALIDATION_ERROR'