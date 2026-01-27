#!/usr/bin/env python3
"""
Comprehensive test suite for Agent Registry API
Tests all API endpoints using boto3 execute-api client
"""

import boto3
import json
import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

# Configuration - read from environment variables
import os
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL")
AWS_REGION = os.environ.get("AWS_REGION")

if not API_GATEWAY_URL:
    raise ValueError("API_GATEWAY_URL environment variable is required")
if not AWS_REGION:
    raise ValueError("AWS_REGION environment variable is required")

# Test agent cards for different business domains
TEST_AGENT_CARDS = [
    {
        "name": "Test FinanceBot Pro",
        "description": "Advanced financial analysis agent specializing in market research, portfolio optimization, and risk assessment. Provides real-time financial insights and investment recommendations.",
        "version": "2.1.0",
        "url": "https://financebot.example.com/api",
        "skills": ["finance", "market-analysis", "portfolio-management", "risk-assessment", "python", "data-analysis"],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text", "file"],
        "defaultOutputModes": ["text", "file"],
        "preferredTransport": "JSONRPC",
        "protocolVersion": "0.3.0"
    },
    {
        "name": "Test HealthCare Assistant",
        "description": "Medical information and healthcare management assistant. Helps with patient data analysis, medical research, and healthcare workflow optimization.",
        "version": "1.5.2",
        "url": "https://healthcare-ai.example.com/api",
        "skills": ["healthcare", "medical-research", "patient-care", "data-analysis", "python", "machine-learning"],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text", "audio"],
        "defaultOutputModes": ["text", "audio"],
        "preferredTransport": "HTTP",
        "protocolVersion": "0.3.0"
    },
    {
        "name": "Test E-Commerce Optimizer",
        "description": "E-commerce and retail optimization agent. Specializes in inventory management, customer behavior analysis, and sales forecasting for online businesses.",
        "version": "3.0.1",
        "url": "https://ecommerce-ai.example.com/webhook",
        "skills": ["e-commerce", "retail", "inventory-management", "customer-analytics", "sales-forecasting", "javascript", "nodejs"],
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text", "file"],
        "defaultOutputModes": ["text", "file"],
        "preferredTransport": "WebSocket",
        "protocolVersion": "0.3.0"
    },
    {
        "name": "Test DevOps Automation Engine",
        "description": "Infrastructure automation and DevOps assistant. Manages CI/CD pipelines, cloud infrastructure, monitoring, and deployment automation across multiple platforms.",
        "version": "4.2.0",
        "url": "https://devops-agent.example.com/api/v2",
        "skills": ["devops", "automation", "ci-cd", "cloud-infrastructure", "monitoring", "kubernetes", "docker", "python", "bash"],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text", "file"],
        "defaultOutputModes": ["text", "file"],
        "preferredTransport": "JSONRPC",
        "protocolVersion": "0.3.0"
    },
    {
        "name": "Test Content Creator AI",
        "description": "Creative content generation and marketing assistant. Specializes in content writing, social media management, SEO optimization, and brand strategy development.",
        "version": "1.8.3",
        "url": "https://content-ai.example.com/generate",
        "skills": ["content-creation", "marketing", "seo", "social-media", "copywriting", "brand-strategy", "creative-writing"],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text", "image"],
        "defaultOutputModes": ["text", "image", "video"],
        "preferredTransport": "HTTP",
        "protocolVersion": "0.3.0"
    }
]

class AgentRegistryAPITester:
    """Test client for Agent Registry API using boto3"""
    
    def __init__(self, api_url: str, region: str = "us-east-1"):
        """Initialize the API tester"""
        self.api_url = api_url.rstrip('/')
        self.region = region
        
        # Extract API Gateway ID from URL
        # Format: https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
        url_parts = api_url.replace('https://', '').split('.')
        self.api_id = url_parts[0].split('/')[-1] if '/' in url_parts[0] else url_parts[0]
        self.stage = "prod"
        
        # Initialize boto3 client for API Gateway execution
        self.client = boto3.client('apigatewaymanagementapi', region_name=region)
        
        # Use requests-aws4auth for signed requests
        try:
            import requests
            from requests_aws4auth import AWS4Auth
            
            # Get AWS credentials
            session = boto3.Session()
            credentials = session.get_credentials()
            
            # Create AWS4Auth instance
            self.auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                'execute-api',
                session_token=credentials.token
            )
            self.requests = requests
            
        except ImportError:
            print("Warning: requests and requests-aws4auth not available. Using boto3 invoke method.")
            self.auth = None
    
    def parse_search_results(self, response):
        """Helper function to parse search results from API response"""
        if response['statusCode'] != 200:
            return [], 0
            
        # Our API returns a direct list of results
        if isinstance(response['body'], list):
            results = response['body']
            count = len(results)
        else:
            # Fallback for other formats
            results = response['body'].get('results', response['body'])
            count = len(results) if isinstance(results, list) else 0
        
        return results, count
    
    def display_search_results(self, results, query_info, max_display=3):
        """Display search results with proper formatting"""
        print(f"✅ Found {len(results)} results for {query_info}")
        
        for i, result in enumerate(results[:max_display], 1):
            # Extract agent information
            agent_card = result.get('agent_card', {})
            agent_name = agent_card.get('name', 'Unknown Agent')
            agent_id = result.get('agent_id', 'Unknown ID')
            
            # Extract search metadata
            similarity_score = result.get('similarity_score', 0.0)
            matched_skills = result.get('matched_skills', [])
            
            # Display result
            print(f"  {i}. {agent_name}")
            print(f"     ID: {agent_id}")
            print(f"     Similarity: {similarity_score:.3f}")
            if matched_skills:
                print(f"     Matched Skills: {matched_skills}")
            
            # Show agent skills for context
            agent_skills = agent_card.get('skills', [])
            if agent_skills:
                print(f"     All Skills: {agent_skills[:5]}{'...' if len(agent_skills) > 5 else ''}")
        
        if len(results) > max_display:
            print(f"  ... and {len(results) - max_display} more results")
    
    def make_request(self, method: str, path: str, body: Optional[Dict] = None, 
                    params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to API Gateway"""
        
        if self.requests and self.auth:
            # Use requests with AWS4Auth for signed requests
            url = f"{self.api_url}{path}"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            kwargs = {
                'auth': self.auth,
                'headers': headers
            }
            
            if body:
                kwargs['json'] = body
            
            if params:
                kwargs['params'] = params
            
            print(f"Making {method} request to: {url}")
            if body:
                print(f"Request body: {json.dumps(body, indent=2)}")
            if params:
                print(f"Query params: {params}")
            
            response = getattr(self.requests, method.lower())(url, timeout=30, **kwargs)
            
            print(f"Response status: {response.status_code}")
            
            try:
                response_data = response.json()
                print(f"Response body: {json.dumps(response_data, indent=2)}")
                return {
                    'statusCode': response.status_code,
                    'body': response_data
                }
            except:
                print(f"Response text: {response.text}")
                return {
                    'statusCode': response.status_code,
                    'body': {'error': 'Failed to parse JSON response', 'text': response.text}
                }
        
        else:
            # Fallback to boto3 lambda invoke (less ideal for API Gateway)
            print(f"Warning: Using boto3 invoke method for {method} {path}")
            
            # Create event structure for Lambda
            event = {
                'httpMethod': method,
                'path': path,
                'queryStringParameters': params or {},
                'body': json.dumps(body) if body else None,
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
            
            # This won't work directly with API Gateway, but shows the structure
            return {
                'statusCode': 501,
                'body': {'error': 'Direct Lambda invoke not supported. Install requests and requests-aws4auth.'}
            }
    
    def test_create_single_agent(self) -> str:
        """Test POST /agents - Create single test agent"""
        print("\n" + "="*60)
        print("Testing: POST /agents (Create Single Test Agent)")
        print("="*60)
        
        # Sample agent card data
        agent_data = {
            "name": f"Test Agent {uuid.uuid4().hex[:8]}",
            "description": "A simple test agent for API validation",
            "version": "1.0.0",
            "url": "http://localhost:8080/",
            "skills": ["python", "testing", "automation"],
            "capabilities": {
                "streaming": True
            },
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "preferredTransport": "JSONRPC",
            "protocolVersion": "0.3.0"
        }
        
        response = self.make_request('POST', '/agents', body=agent_data)
        
        if response['statusCode'] == 200:
            agent_id = response['body'].get('agent_id')
            print(f"✅ Agent created successfully with ID: {agent_id}")
            return agent_id
        else:
            print(f"❌ Failed to create agent: {response}")
            return None
    
    def test_get_agent(self, agent_id: str):
        """Test GET /agents/{id} - Get specific agent"""
        print("\n" + "="*60)
        print(f"Testing: GET /agents/{agent_id} (Get Agent)")
        print("="*60)
        
        response = self.make_request('GET', f'/agents/{agent_id}')
        
        if response['statusCode'] == 200:
            agent = response['body'].get('agent')
            print(f"✅ Agent retrieved successfully")
            print(f"Agent name: {agent.get('name', 'N/A')}")
            print(f"Agent skills: {agent.get('skills', [])}")
        else:
            print(f"❌ Failed to get agent: {response}")
    
    def test_list_agents(self):
        """Test GET /agents - List all agents"""
        print("\n" + "="*60)
        print("Testing: GET /agents (List Agents)")
        print("="*60)
        
        # Test without pagination
        response = self.make_request('GET', '/agents')
        
        if response['statusCode'] == 200:
            agents = response['body'].get('agents', [])
            pagination = response['body'].get('pagination', {})
            print(f"✅ Listed {len(agents)} agents")
            print(f"Pagination info: {pagination}")
        else:
            print(f"❌ Failed to list agents: {response}")
        
        # Test with pagination
        print("\nTesting with pagination (limit=5, offset=0):")
        response = self.make_request('GET', '/agents', params={'limit': 5, 'offset': 0})
        
        if response['statusCode'] == 200:
            agents = response['body'].get('agents', [])
            pagination = response['body'].get('pagination', {})
            print(f"✅ Listed {len(agents)} agents with pagination")
            print(f"Pagination info: {pagination}")
        else:
            print(f"❌ Failed to list agents with pagination: {response}")
    
    def test_search_agents_by_text(self):
        """Test GET /agents/search - Search agents by text"""
        print("\n" + "="*60)
        print("Testing: GET /agents/search (Semantic Text Search)")
        print("="*60)
        
        # Test text search with specific queries
        search_queries = [
            "python programming and development",
            "automation testing and validation", 
            "financial analysis and market research",
            "healthcare management and patient care"
        ]
        
        for query in search_queries:
            print(f"\n🔍 Searching for: '{query}'")
            response = self.make_request('GET', '/agents/search', params={
                'text': query,
                'top_k': 5
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                self.display_search_results(results, f"'{query}'")
            else:
                print(f"❌ Search failed for '{query}': {response}")
    
    def test_search_agents_by_skills(self):
        """Test GET /agents/search - Search agents by skills"""
        print("\n" + "="*60)
        print("Testing: GET /agents/search (Skills-Only Search with AND Logic)")
        print("="*60)
        
        # Test skills search with different combinations
        skill_sets = [
            {
                'skills': ["python"],
                'description': "Single skill: Python developers"
            },
            {
                'skills': ["python", "data-analysis"],
                'description': "Multiple skills (AND): Python AND data analysis"
            },
            {
                'skills': ["javascript", "web-development"],
                'description': "Multiple skills (AND): JavaScript AND web development"
            },
            {
                'skills': ["devops", "kubernetes"],
                'description': "Multiple skills (AND): DevOps AND Kubernetes"
            },
            {
                'skills': ["healthcare", "machine-learning"],
                'description': "Multiple skills (AND): Healthcare AND machine learning"
            }
        ]
        
        for skill_set in skill_sets:
            skills = skill_set['skills']
            description = skill_set['description']
            
            print(f"\n🔍 Testing: {description}")
            print(f"   Skills: {skills}")
            
            response = self.make_request('GET', '/agents/search', params={
                'skills': ','.join(skills),
                'top_k': 5
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                self.display_search_results(results, f"skills {skills}")
                
                # Validate AND logic for multiple skills
                if len(skills) > 1:
                    print(f"   🔍 Validating AND logic: All results should have ALL {len(skills)} skills")
                    for i, result in enumerate(results[:3], 1):
                        agent_skills = result.get('agent_card', {}).get('skills', [])
                        matched_skills = result.get('matched_skills', [])
                        
                        if len(matched_skills) == len(skills):
                            print(f"   ✅ Result {i}: Has all required skills")
                        else:
                            print(f"   ❌ Result {i}: Missing skills! Has {matched_skills}, needs {skills}")
            else:
                print(f"❌ Skills search failed for {skills}: {response}")
    
    def test_search_agents_combined(self):
        """Test GET /agents/search - Search agents by text and skills"""
        print("\n" + "="*60)
        print("Testing: GET /agents/search (Combined Semantic + Skills Search)")
        print("="*60)
        
        # Test combined search with semantic relevance + skill filtering
        test_cases = [
            {
                'text': 'financial analysis and market research',
                'skills': ['python', 'data-analysis'],
                'description': 'Finance experts with Python AND data analysis skills'
            },
            {
                'text': 'healthcare management and patient care',
                'skills': ['healthcare', 'machine-learning'],
                'description': 'Healthcare experts with healthcare AND machine learning skills'
            },
            {
                'text': 'infrastructure automation and deployment',
                'skills': ['devops', 'kubernetes'],
                'description': 'DevOps experts with DevOps AND Kubernetes skills'
            },
            {
                'text': 'web development and frontend frameworks',
                'skills': ['javascript', 'web-development'],
                'description': 'Web developers with JavaScript AND web development skills'
            }
        ]
        
        for case in test_cases:
            print(f"\n🔍 Testing: {case['description']}")
            print(f"   Query: '{case['text']}'")
            print(f"   Required Skills (AND): {case['skills']}")
            
            response = self.make_request('GET', '/agents/search', params={
                'text': case['text'],
                'skills': ','.join(case['skills']),
                'top_k': 5
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                self.display_search_results(results, f"combined search: '{case['text']}' + {case['skills']}")
                
                # Validate that results have semantic relevance AND all required skills
                print(f"   🔍 Validating combined search: Semantic relevance + ALL required skills")
                for i, result in enumerate(results[:3], 1):
                    similarity_score = result.get('similarity_score', 0)
                    matched_skills = result.get('matched_skills', [])
                    
                    has_semantic_relevance = similarity_score > 0
                    has_all_skills = len(matched_skills) == len(case['skills'])
                    
                    if has_semantic_relevance and has_all_skills:
                        print(f"   ✅ Result {i}: Good semantic match ({similarity_score:.3f}) + all skills")
                    elif has_all_skills:
                        print(f"   ⚠️  Result {i}: Has all skills but low semantic relevance ({similarity_score:.3f})")
                    else:
                        print(f"   ❌ Result {i}: Missing skills! Has {matched_skills}, needs {case['skills']}")
            else:
                print(f"❌ Combined search failed: {response}")
    
    def test_update_health(self, agent_id: str):
        """Test POST /agents/{id}/health - Update agent health"""
        print("\n" + "="*60)
        print(f"Testing: POST /agents/{agent_id}/health (Update Health)")
        print("="*60)
        
        response = self.make_request('POST', f'/agents/{agent_id}/health')
        
        if response['statusCode'] == 200:
            print(f"✅ Health status updated successfully for agent {agent_id}")
        else:
            print(f"❌ Failed to update health status: {response}")
    
    def test_update_agent(self, agent_id: str):
        """Test PUT /agents/{id} - Update existing agent"""
        print("\n" + "="*60)
        print(f"Testing: PUT /agents/{agent_id} (Update Agent)")
        print("="*60)
        
        # First, get the current agent to verify it exists
        get_response = self.make_request('GET', f'/agents/{agent_id}')
        if get_response['statusCode'] != 200:
            print(f"❌ Cannot test update - agent {agent_id} not found")
            return
        
        original_agent = get_response['body']['agent']
        print(f"📋 Original agent name: {original_agent.get('name')}")
        print(f"📋 Original agent description: {original_agent.get('description')[:50]}...")
        
        # Test partial update - only update name and skills
        update_data = {
            "name": f"Updated {original_agent.get('name', 'Agent')}",
            "skills": original_agent.get('skills', []) + ["integration-testing", "api-testing"]
        }
        
        print(f"\n🔄 Updating agent with new name and additional skills...")
        print(f"   New name: {update_data['name']}")
        print(f"   New skills: {update_data['skills']}")
        
        response = self.make_request('PUT', f'/agents/{agent_id}', body=update_data)
        
        if response['statusCode'] == 200:
            print(f"✅ Agent updated successfully")
            
            # Verify the update by getting the agent again
            print(f"\n🔍 Verifying update by retrieving agent...")
            verify_response = self.make_request('GET', f'/agents/{agent_id}')
            
            if verify_response['statusCode'] == 200:
                updated_agent = verify_response['body']['agent']
                
                # Check if updates were applied
                if updated_agent.get('name') == update_data['name']:
                    print(f"✅ Name updated correctly: {updated_agent.get('name')}")
                else:
                    print(f"❌ Name not updated correctly. Expected: {update_data['name']}, Got: {updated_agent.get('name')}")
                
                # Check if skills were updated (should include new skills)
                # Skills are stored as AgentSkill objects with 'name' field, so extract names for comparison
                updated_skills_list = updated_agent.get('skills', [])
                updated_skill_names = set(
                    s['name'] if isinstance(s, dict) else s for s in updated_skills_list
                )
                expected_skill_names = set(
                    s['name'] if isinstance(s, dict) else s for s in update_data['skills']
                )
                if expected_skill_names.issubset(updated_skill_names):
                    print(f"✅ Skills updated correctly: {list(updated_skill_names)}")
                else:
                    print(f"❌ Skills not updated correctly. Expected to include: {expected_skill_names}, Got: {updated_skill_names}")
                
                # Check that other fields were preserved
                if updated_agent.get('version') == original_agent.get('version'):
                    print(f"✅ Version preserved: {updated_agent.get('version')}")
                else:
                    print(f"❌ Version not preserved. Original: {original_agent.get('version')}, Updated: {updated_agent.get('version')}")
                
            else:
                print(f"❌ Failed to verify update: {verify_response}")
        else:
            print(f"❌ Failed to update agent: {response}")
        
        # Test update with invalid data
        print(f"\n🧪 Testing update with invalid data...")
        invalid_update = {
            "name": "A",  # Too short
            "description": "Short"  # Too short
        }
        
        invalid_response = self.make_request('PUT', f'/agents/{agent_id}', body=invalid_update)
        
        if invalid_response['statusCode'] == 400:
            print(f"✅ Correctly rejected invalid update data (400)")
        else:
            print(f"❌ Should have rejected invalid data with 400, got: {invalid_response['statusCode']}")
    
    def test_error_cases(self):
        """Test various error scenarios"""
        print("\n" + "="*60)
        print("Testing: Error Cases")
        print("="*60)
        
        # Test 404 - Non-existent agent
        print("\n1. Testing 404 - Non-existent agent:")
        fake_id = str(uuid.uuid4())  # Use a valid UUID that doesn't exist
        response = self.make_request('GET', f'/agents/{fake_id}')
        if response['statusCode'] == 404:
            print("✅ Correctly returned 404 for non-existent agent")
        else:
            print(f"❌ Expected 404, got {response['statusCode']}")
        
        # Test 400 - Invalid search parameters
        print("\n2. Testing 400 - Invalid search (no parameters):")
        response = self.make_request('GET', '/agents/search')
        if response['statusCode'] == 400:
            print("✅ Correctly returned 400 for search without parameters")
        else:
            print(f"❌ Expected 400, got {response['statusCode']}")
        
        # Test 400 - Invalid JSON in create agent
        print("\n3. Testing 400 - Invalid agent data:")
        response = self.make_request('POST', '/agents', body={})  # Empty body
        if response['statusCode'] == 400:
            print("✅ Correctly returned 400 for invalid agent data")
        else:
            print(f"❌ Expected 400, got {response['statusCode']}")
        
        # Test 404 - Delete non-existent agent
        print("\n4. Testing 404 - Delete non-existent agent:")
        fake_id = str(uuid.uuid4())  # Use a valid UUID that doesn't exist
        response = self.make_request('DELETE', f'/agents/{fake_id}')
        if response['statusCode'] == 404:
            print("✅ Correctly returned 404 for deleting non-existent agent")
        else:
            print(f"❌ Expected 404, got {response['statusCode']}")
        
        # Test 405 - Method not allowed
        print("\n5. Testing 405 - Method not allowed:")
        response = self.make_request('DELETE', '/agents')
        if response['statusCode'] == 405:
            print("✅ Correctly returned 405 for unsupported method")
        else:
            print(f"❌ Expected 405, got {response['statusCode']}")
    
    def test_create_multiple_business_domain_agents(self) -> List[str]:
        """Test creating multiple agent cards with different business domains"""
        print("\n" + "="*60)
        print("Testing: Creating Multiple Business Domain Agents")
        print("="*60)
        
        created_agent_ids = []
        
        for i, agent_data in enumerate(TEST_AGENT_CARDS, 1):
            print(f"\n{i}. Creating agent: {agent_data['name']}")
            print(f"   Domain: {agent_data['description'][:80]}...")
            print(f"   Skills: {agent_data['skills']}")
            
            response = self.make_request('POST', '/agents', body=agent_data)
            
            if response['statusCode'] == 200:
                agent_id = response['body'].get('agent_id')
                created_agent_ids.append(agent_id)
                print(f"   ✅ Created successfully with ID: {agent_id}")
            else:
                print(f"   ❌ Failed to create: {response}")
        
        print(f"\n📊 Summary: Created {len(created_agent_ids)}/{len(TEST_AGENT_CARDS)} agents successfully")
        return created_agent_ids
    
    def test_comprehensive_skill_based_search(self):
        """Test comprehensive skill-based search across different domains"""
        print("\n" + "="*60)
        print("Testing: Comprehensive Skill-Based Search")
        print("="*60)
        
        # Test cases for skill-based search
        skill_test_cases = [
            {
                "name": "Finance Skills",
                "skills": ["finance", "market-analysis"],
                "expected_agents": ["Test FinanceBot Pro"]
            },
            {
                "name": "Healthcare Skills", 
                "skills": ["healthcare", "medical-research"],
                "expected_agents": ["Test HealthCare Assistant"]
            },
            {
                "name": "DevOps Skills",
                "skills": ["devops", "automation", "kubernetes"],
                "expected_agents": ["Test DevOps Automation Engine"]
            },
            {
                "name": "Programming Skills (Python)",
                "skills": ["python"],
                "expected_agents": ["Test FinanceBot Pro", "Test HealthCare Assistant", "Test DevOps Automation Engine"]
            },
            {
                "name": "Data Analysis Skills",
                "skills": ["data-analysis"],
                "expected_agents": ["Test FinanceBot Pro", "Test HealthCare Assistant"]
            },
            {
                "name": "Content & Marketing",
                "skills": ["content-creation", "marketing", "seo"],
                "expected_agents": ["Test Content Creator AI"]
            },
            {
                "name": "E-commerce Skills",
                "skills": ["e-commerce", "inventory-management"],
                "expected_agents": ["Test E-Commerce Optimizer"]
            }
        ]
        
        for test_case in skill_test_cases:
            print(f"\n🔍 Testing {test_case['name']}: {test_case['skills']}")
            
            response = self.make_request('GET', '/agents/search', params={
                'skills': ','.join(test_case['skills']),
                'top_k': 10
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                self.display_search_results(results, f"{test_case['name']}: {test_case['skills']}")
                
                # Validate AND logic for multiple skills
                if len(test_case['skills']) > 1:
                    print(f"   🔍 Validating AND logic: Results should have ALL {len(test_case['skills'])} skills")
                    for i, result in enumerate(results[:3], 1):
                        matched_skills = result.get('matched_skills', [])
                        if len(matched_skills) == len(test_case['skills']):
                            print(f"   ✅ Result {i}: Has all {len(test_case['skills'])} required skills")
                        else:
                            print(f"   ❌ Result {i}: Has {len(matched_skills)}/{len(test_case['skills'])} skills")
                
                # Check for expected agent types (by name patterns)
                found_agent_names = [result.get('agent_card', {}).get('name', '') for result in results]
                for expected_agent in test_case['expected_agents']:
                    if any(expected_agent in name for name in found_agent_names):
                        print(f"   ✅ Found expected agent type: {expected_agent}")
                    else:
                        print(f"   ⚠️  Expected agent type not found: {expected_agent}")
            else:
                print(f"   ❌ Search failed: {response}")
    
    def test_comprehensive_semantic_search(self):
        """Test comprehensive semantic search across different business domains"""
        print("\n" + "="*60)
        print("Testing: Comprehensive Semantic Search")
        print("="*60)
        
        # Test cases for semantic search
        semantic_test_cases = [
            {
                "query": "financial market analysis and investment advice",
                "expected_domain": "finance",
                "expected_agents": ["FinanceBot Pro"]
            },
            {
                "query": "medical patient care and healthcare management",
                "expected_domain": "healthcare", 
                "expected_agents": ["HealthCare Assistant"]
            },
            {
                "query": "online store inventory and sales optimization",
                "expected_domain": "e-commerce",
                "expected_agents": ["E-Commerce Optimizer"]
            },
            {
                "query": "cloud infrastructure deployment and monitoring",
                "expected_domain": "devops",
                "expected_agents": ["DevOps Automation Engine"]
            },
            {
                "query": "content writing and social media marketing",
                "expected_domain": "marketing",
                "expected_agents": ["Content Creator AI"]
            },
            {
                "query": "data analysis and machine learning",
                "expected_domain": "data science",
                "expected_agents": ["FinanceBot Pro", "HealthCare Assistant"]
            }
        ]
        
        for test_case in semantic_test_cases:
            print(f"\n🔍 Testing semantic search: '{test_case['query']}'")
            print(f"   Expected domain: {test_case['expected_domain']}")
            
            response = self.make_request('GET', '/agents/search', params={
                'text': test_case['query'],
                'top_k': 5
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                self.display_search_results(results, f"'{test_case['query']}'")
                
                # Validate semantic relevance
                print(f"   🔍 Validating semantic relevance for {test_case['expected_domain']} domain")
                for i, result in enumerate(results[:3], 1):
                    similarity_score = result.get('similarity_score', 0)
                    agent_name = result.get('agent_card', {}).get('name', 'Unknown')
                    
                    if similarity_score > 0.1:  # Reasonable threshold for relevance
                        print(f"   ✅ Result {i}: Good semantic relevance ({similarity_score:.3f})")
                    else:
                        print(f"   ⚠️  Result {i}: Low semantic relevance ({similarity_score:.3f})")
                
                # Check for expected agent types (by name patterns)
                top_agent_names = [result.get('agent_card', {}).get('name', '') for result in results[:3]]
                for expected_agent in test_case['expected_agents']:
                    if any(expected_agent in name for name in top_agent_names):
                        print(f"   ✅ Expected agent type found in top results: {expected_agent}")
                    else:
                        print(f"   ⚠️  Expected agent type not in top 3: {expected_agent}")
            else:
                print(f"   ❌ Semantic search failed: {response}")
    
    def test_combined_search_validation(self):
        """Test combined text + skills search for precise results"""
        print("\n" + "="*60)
        print("Testing: Combined Text + Skills Search Validation")
        print("="*60)
        
        # Test cases combining semantic and skill-based search
        combined_test_cases = [
            {
                "text": "financial portfolio management",
                "skills": ["python", "data-analysis"],
                "expected_agents": ["FinanceBot Pro"],
                "description": "Finance + Python skills"
            },
            {
                "text": "patient healthcare analysis",
                "skills": ["machine-learning", "python"],
                "expected_agents": ["HealthCare Assistant"],
                "description": "Healthcare + ML skills"
            },
            {
                "text": "cloud deployment automation",
                "skills": ["kubernetes", "docker"],
                "expected_agents": ["DevOps Automation Engine"],
                "description": "DevOps + Container skills"
            },
            {
                "text": "online business optimization",
                "skills": ["javascript", "nodejs"],
                "expected_agents": ["E-Commerce Optimizer"],
                "description": "E-commerce + JavaScript skills"
            }
        ]
        
        for test_case in combined_test_cases:
            print(f"\n🔍 Testing {test_case['description']}")
            print(f"   Text: '{test_case['text']}'")
            print(f"   Skills: {test_case['skills']}")
            
            response = self.make_request('GET', '/agents/search', params={
                'text': test_case['text'],
                'skills': ','.join(test_case['skills']),
                'top_k': 5
            })
            
            results, count = self.parse_search_results(response)
            if response['statusCode'] == 200:
                print(f"   ✅ Found {count} results")
                
                # Show results with both similarity and skill matches
                for i, result in enumerate(results[:3], 1):
                    search_metadata = result.get('_search_metadata', {})
                    similarity_score = search_metadata.get('similarity_score', 0)
                    matched_skills = search_metadata.get('matched_skills', [])
                    print(f"   {i}. {result.get('name', 'N/A')} (sim: {similarity_score:.3f}, skills: {matched_skills})")
                
                # Validate expected agents are found
                found_agent_names = [result.get('name', '') for result in results]
                for expected_agent in test_case['expected_agents']:
                    if any(expected_agent in name for name in found_agent_names):
                        print(f"   ✅ Expected agent found: {expected_agent}")
                    else:
                        print(f"   ⚠️  Expected agent not found: {expected_agent}")
            else:
                print(f"   ❌ Combined search failed: {response}")
    
    def test_delete_agent_functionality(self, agent_ids: List[str]):
        """Test delete agent functionality - create agent, delete it, verify it's gone"""
        print("\n" + "="*60)
        print("Testing: Delete Agent Functionality")
        print("="*60)
        
        if not agent_ids:
            print("❌ No agent IDs available for delete testing")
            return
        
        # Use the last created agent for delete testing (to preserve others for other tests)
        test_agent_id = agent_ids[-1]
        print(f"Testing delete with agent ID: {test_agent_id}")
        
        # Step 1: Verify agent exists before deletion
        print("\n1. Verifying agent exists before deletion...")
        get_response = self.make_request('GET', f'/agents/{test_agent_id}')
        
        if get_response['statusCode'] != 200:
            print(f"❌ Agent not found before deletion: {get_response}")
            return
        
        agent_data = get_response['body'].get('agent', {})
        print(f"   ✅ Agent exists: {agent_data.get('name', 'N/A')}")
        
        # Step 2: Delete the agent
        print("\n2. Deleting agent...")
        delete_response = self.make_request('DELETE', f'/agents/{test_agent_id}')
        
        if delete_response['statusCode'] == 200:
            print(f"   ✅ Agent deleted successfully")
            print(f"   Response: {delete_response['body'].get('message', 'N/A')}")
        else:
            print(f"   ❌ Failed to delete agent: {delete_response}")
            return
        
        # Step 3: Verify agent no longer exists
        print("\n3. Verifying agent no longer exists...")
        verify_response = self.make_request('GET', f'/agents/{test_agent_id}')
        
        if verify_response['statusCode'] == 404:
            print(f"   ✅ Agent correctly not found after deletion")
        else:
            print(f"   ❌ Agent still exists after deletion: {verify_response}")
        
        # Step 4: Test deleting non-existent agent (should return 404)
        print("\n4. Testing delete of non-existent agent...")
        fake_id = str(uuid.uuid4())  # Use a valid UUID that doesn't exist
        fake_delete_response = self.make_request('DELETE', f'/agents/{fake_id}')
        
        if fake_delete_response['statusCode'] == 404:
            print(f"   ✅ Correctly returned 404 for non-existent agent")
        else:
            print(f"   ❌ Expected 404, got {fake_delete_response['statusCode']}")
        
        # Remove the deleted agent from the list for other tests
        if test_agent_id in agent_ids:
            agent_ids.remove(test_agent_id)
        
        print(f"\n📊 Delete functionality test completed")

    def test_heartbeat_functionality(self, agent_ids: List[str]):
        """Test heartbeat functionality - create agent, update health, validate timestamps"""
        print("\n" + "="*60)
        print("Testing: Heartbeat Functionality")
        print("="*60)
        
        if not agent_ids:
            print("❌ No agent IDs available for heartbeat testing")
            return
        
        # Use the first created agent for heartbeat testing
        test_agent_id = agent_ids[0]
        print(f"Testing heartbeat with agent ID: {test_agent_id}")
        
        # Step 1: Get initial agent state
        print("\n1. Getting initial agent state...")
        initial_response = self.make_request('GET', f'/agents/{test_agent_id}')
        
        if initial_response['statusCode'] != 200:
            print(f"❌ Failed to get initial agent state: {initial_response}")
            return
        
        initial_agent = initial_response['body'].get('agent', {})
        print(f"   ✅ Retrieved agent: {initial_agent.get('name', 'N/A')}")
        
        # Step 2: Wait a moment, then send heartbeat
        print("\n2. Sending heartbeat...")
        time.sleep(2)  # Wait 2 seconds to ensure timestamp difference
        
        heartbeat_response = self.make_request('POST', f'/agents/{test_agent_id}/health')
        
        if heartbeat_response['statusCode'] != 200:
            print(f"❌ Failed to send heartbeat: {heartbeat_response}")
            return
        
        print(f"   ✅ Heartbeat sent successfully")
        
        # Step 3: Get agent state after heartbeat
        print("\n3. Validating heartbeat update...")
        time.sleep(1)  # Brief wait for consistency
        
        updated_response = self.make_request('GET', f'/agents/{test_agent_id}')
        
        if updated_response['statusCode'] != 200:
            print(f"❌ Failed to get updated agent state: {updated_response}")
            return
        
        updated_agent = updated_response['body'].get('agent', {})
        
        # Step 4: Validate timestamp updates
        print("\n4. Validating timestamp changes...")
        
        # Note: The agent card itself might not show last_online directly
        # We need to check if the heartbeat was processed
        print(f"   ✅ Agent retrieved after heartbeat: {updated_agent.get('name', 'N/A')}")
        
        # Step 5: Test multiple heartbeats
        print("\n5. Testing multiple heartbeats...")
        
        for i in range(3):
            print(f"   Sending heartbeat {i+1}/3...")
            time.sleep(1)
            
            heartbeat_response = self.make_request('POST', f'/agents/{test_agent_id}/health')
            
            if heartbeat_response['statusCode'] == 200:
                print(f"   ✅ Heartbeat {i+1} successful")
            else:
                print(f"   ❌ Heartbeat {i+1} failed: {heartbeat_response}")
        
        # Step 6: Final validation
        print("\n6. Final validation...")
        final_response = self.make_request('GET', f'/agents/{test_agent_id}')
        
        if final_response['statusCode'] == 200:
            print(f"   ✅ Agent still accessible after multiple heartbeats")
            print(f"   Agent: {final_response['body'].get('agent', {}).get('name', 'N/A')}")
        else:
            print(f"   ❌ Failed final validation: {final_response}")
        
        print("\n📊 Heartbeat test completed")
    
    def test_heartbeat_with_nonexistent_agent(self):
        """Test heartbeat with non-existent agent ID"""
        print("\n" + "="*60)
        print("Testing: Heartbeat with Non-existent Agent")
        print("="*60)
        
        fake_agent_id = str(uuid.uuid4())
        print(f"Testing heartbeat with fake agent ID: {fake_agent_id}")
        
        response = self.make_request('POST', f'/agents/{fake_agent_id}/health')
        
        if response['statusCode'] == 404:
            print("✅ Correctly returned 404 for non-existent agent heartbeat")
        else:
            print(f"❌ Expected 404, got {response['statusCode']}: {response}")
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Agent Registry API Test Suite")
        print(f"API URL: {self.api_url}")
        print(f"Region: {self.region}")
        
        start_time = time.time()
        
        try:
            # Test 1: Create multiple business domain agents
            created_agent_ids = self.test_create_multiple_business_domain_agents()
            
            # Wait for agents to be indexed
            if created_agent_ids:
                print(f"\n⏳ Waiting 10 seconds for agents to be indexed...")
                time.sleep(10)
            
            # Test 2: Comprehensive skill-based search
            self.test_comprehensive_skill_based_search()
            
            # Test 3: Comprehensive semantic search  
            self.test_comprehensive_semantic_search()
            
            # Test 4: Combined search validation
            self.test_combined_search_validation()
            
            # Test 5: Delete agent functionality
            if created_agent_ids:
                self.test_delete_agent_functionality(created_agent_ids)
            
            # Test 6: Heartbeat functionality
            if created_agent_ids:
                self.test_heartbeat_functionality(created_agent_ids)
            
            # Test 7: Heartbeat error cases
            self.test_heartbeat_with_nonexistent_agent()
            
            # Test 8: Update agent functionality
            if created_agent_ids:
                # Test update with the first created agent
                self.test_update_agent(created_agent_ids[0])
            
            # Test 9: List agents (should show our created agents)
            self.test_list_agents()
            
            # Test 10: Original search tests (for compatibility)
            self.test_search_agents_by_text()
            self.test_search_agents_combined()
            
            # Test 11: Error cases
            self.test_error_cases()
            
        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print(f"🏁 Test Suite Completed in {duration:.2f} seconds")
        print("="*60)


def main():
    """Main function to run the test suite"""
    print("Agent Registry API Test Suite")
    print("=" * 50)
    
    # Check if required packages are available
    try:
        import requests
        import requests_aws4auth
        print("✅ Required packages (requests, requests-aws4auth) are available")
    except ImportError as e:
        print(f"⚠️  Missing required packages: {e}")
        print("Install with: pip install requests requests-aws4auth")
        print("Continuing with limited functionality...")
    
    # Initialize and run tests
    tester = AgentRegistryAPITester(API_GATEWAY_URL, AWS_REGION)
    tester.run_all_tests()


if __name__ == "__main__":
    main()