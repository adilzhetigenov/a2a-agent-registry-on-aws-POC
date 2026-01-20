#!/usr/bin/env python3
"""
Dedicated test suite for Agent Registry API Delete functionality
Tests the DELETE /agents/{id} endpoint comprehensively
"""

import boto3
import json
import uuid
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Configuration - read from environment variables
import os
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL")
AWS_REGION = os.environ.get("AWS_REGION")

if not API_GATEWAY_URL:
    raise ValueError("API_GATEWAY_URL environment variable is required")
if not AWS_REGION:
    raise ValueError("AWS_REGION environment variable is required")

# Test agent card for delete testing
TEST_AGENT_CARD = {
    "name": "Test DeleteTestAgent",
    "description": "Test agent specifically created for delete functionality testing",
    "version": "1.0.0",
    "url": "https://delete-test.example.com/api",
    "skills": ["testing", "delete", "validation"],
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "preferredTransport": "HTTP",
    "protocolVersion": "0.3.0"
}


class DeleteAgentTester:
    """Test client specifically for delete agent functionality"""
    
    def __init__(self, api_url: str, region: str = "us-east-1"):
        """Initialize the delete tester"""
        self.api_url = api_url.rstrip('/')
        self.region = region
        
        # Extract API Gateway ID from URL
        url_parts = api_url.replace('https://', '').split('.')
        self.api_id = url_parts[0].split('/')[-1] if '/' in url_parts[0] else url_parts[0]
        self.stage = "prod"
        
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
            print("Warning: requests and requests-aws4auth not available.")
            self.auth = None
            self.requests = None
    
    def make_request(self, method: str, path: str, body: Optional[Dict] = None, 
                    params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to API Gateway"""
        
        if self.requests and self.auth:
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
            print(f"Error: requests and requests-aws4auth required for testing")
            return {
                'statusCode': 501,
                'body': {'error': 'requests and requests-aws4auth required'}
            }
    
    def test_delete_agent_lifecycle(self):
        """Test complete delete agent lifecycle: create -> verify -> delete -> verify gone"""
        print("\n" + "="*80)
        print("Testing: Complete Delete Agent Lifecycle")
        print("="*80)
        
        # Step 1: Create a test agent
        print("\n1. Creating test agent for deletion...")
        create_response = self.make_request('POST', '/agents', body=TEST_AGENT_CARD)
        
        if create_response['statusCode'] != 200:
            print(f"❌ Failed to create test agent: {create_response}")
            return None
        
        agent_id = create_response['body'].get('agent_id')
        if not agent_id:
            print(f"❌ No agent_id in create response: {create_response}")
            return None
        
        print(f"✅ Test agent created with ID: {agent_id}")
        
        # Step 2: Verify agent exists
        print(f"\n2. Verifying agent {agent_id} exists...")
        get_response = self.make_request('GET', f'/agents/{agent_id}')
        
        if get_response['statusCode'] != 200:
            print(f"❌ Failed to retrieve created agent: {get_response}")
            return agent_id
        
        agent_data = get_response['body'].get('agent', {})
        print(f"✅ Agent verified: {agent_data.get('name', 'N/A')}")
        
        # Step 3: Delete the agent
        print(f"\n3. Deleting agent {agent_id}...")
        delete_response = self.make_request('DELETE', f'/agents/{agent_id}')
        
        if delete_response['statusCode'] != 200:
            print(f"❌ Failed to delete agent: {delete_response}")
            return agent_id
        
        delete_message = delete_response['body'].get('message', '')
        print(f"✅ Agent deleted successfully: {delete_message}")
        
        # Step 4: Verify agent no longer exists
        print(f"\n4. Verifying agent {agent_id} no longer exists...")
        verify_response = self.make_request('GET', f'/agents/{agent_id}')
        
        if verify_response['statusCode'] == 404:
            print(f"✅ Agent correctly not found after deletion")
        else:
            print(f"❌ Agent still exists after deletion: {verify_response}")
            return agent_id
        
        # Step 5: Try to delete again (should return 404)
        print(f"\n5. Attempting to delete already deleted agent...")
        double_delete_response = self.make_request('DELETE', f'/agents/{agent_id}')
        
        if double_delete_response['statusCode'] == 404:
            print(f"✅ Correctly returned 404 for already deleted agent")
        else:
            print(f"❌ Expected 404, got {double_delete_response['statusCode']}")
        
        print(f"\n✅ Complete delete lifecycle test passed for agent {agent_id}")
        return None  # Agent successfully deleted
    
    def test_delete_nonexistent_agent(self):
        """Test deleting a non-existent agent"""
        print("\n" + "="*80)
        print("Testing: Delete Non-existent Agent")
        print("="*80)
        
        fake_agent_id = str(uuid.uuid4())  # Use a valid UUID that doesn't exist
        print(f"Attempting to delete non-existent agent: {fake_agent_id}")
        
        response = self.make_request('DELETE', f'/agents/{fake_agent_id}')
        
        if response['statusCode'] == 404:
            print(f"✅ Correctly returned 404 for non-existent agent")
            error_message = response['body'].get('error', {}).get('message', '')
            print(f"Error message: {error_message}")
        else:
            print(f"❌ Expected 404, got {response['statusCode']}: {response}")
    
    def test_delete_invalid_agent_id(self):
        """Test deleting with invalid agent ID formats"""
        print("\n" + "="*80)
        print("Testing: Delete with Invalid Agent ID Formats")
        print("="*80)
        
        invalid_ids = [
            "",  # Empty string
            "   ",  # Whitespace only
            "invalid-uuid-format",  # Invalid UUID format
            "12345",  # Too short
            "not-a-uuid-at-all",  # Clearly not a UUID
        ]
        
        for i, invalid_id in enumerate(invalid_ids, 1):
            print(f"\n{i}. Testing invalid ID: '{invalid_id}'")
            response = self.make_request('DELETE', f'/agents/{invalid_id}')
            
            # Should return 400 for validation error or 404 for not found
            if response['statusCode'] in [400, 404]:
                print(f"✅ Correctly returned {response['statusCode']} for invalid ID")
            else:
                print(f"❌ Expected 400 or 404, got {response['statusCode']}")
    
    def test_delete_multiple_agents(self):
        """Test deleting multiple agents in sequence"""
        print("\n" + "="*80)
        print("Testing: Delete Multiple Agents")
        print("="*80)
        
        # Create multiple test agents
        agent_ids = []
        num_agents = 3
        
        print(f"Creating {num_agents} test agents...")
        for i in range(num_agents):
            agent_card = TEST_AGENT_CARD.copy()
            agent_card['name'] = f"DeleteTest-{i+1}-{uuid.uuid4().hex[:8]}"
            
            response = self.make_request('POST', '/agents', body=agent_card)
            
            if response['statusCode'] == 200:
                agent_id = response['body'].get('agent_id')
                if agent_id:
                    agent_ids.append(agent_id)
                    print(f"✅ Created agent {i+1}: {agent_id}")
                else:
                    print(f"❌ No agent_id in response for agent {i+1}")
            else:
                print(f"❌ Failed to create agent {i+1}: {response}")
        
        print(f"\nCreated {len(agent_ids)} agents successfully")
        
        # Delete all created agents
        print(f"\nDeleting all {len(agent_ids)} agents...")
        deleted_count = 0
        
        for i, agent_id in enumerate(agent_ids, 1):
            print(f"\nDeleting agent {i}/{len(agent_ids)}: {agent_id}")
            
            response = self.make_request('DELETE', f'/agents/{agent_id}')
            
            if response['statusCode'] == 200:
                print(f"✅ Agent {i} deleted successfully")
                deleted_count += 1
                
                # Verify it's gone
                verify_response = self.make_request('GET', f'/agents/{agent_id}')
                if verify_response['statusCode'] == 404:
                    print(f"✅ Agent {i} verified as deleted")
                else:
                    print(f"❌ Agent {i} still exists after deletion")
            else:
                print(f"❌ Failed to delete agent {i}: {response}")
        
        print(f"\n📊 Successfully deleted {deleted_count}/{len(agent_ids)} agents")
    
    def test_delete_performance(self):
        """Test delete operation performance"""
        print("\n" + "="*80)
        print("Testing: Delete Operation Performance")
        print("="*80)
        
        # Create a test agent
        print("Creating test agent for performance testing...")
        create_response = self.make_request('POST', '/agents', body=TEST_AGENT_CARD)
        
        if create_response['statusCode'] != 200:
            print(f"❌ Failed to create test agent: {create_response}")
            return
        
        agent_id = create_response['body'].get('agent_id')
        if not agent_id:
            print(f"❌ No agent_id in create response")
            return
        
        print(f"✅ Test agent created: {agent_id}")
        
        # Measure delete performance
        print(f"\nMeasuring delete operation performance...")
        start_time = time.time()
        
        delete_response = self.make_request('DELETE', f'/agents/{agent_id}')
        
        end_time = time.time()
        duration = end_time - start_time
        
        if delete_response['statusCode'] == 200:
            print(f"✅ Delete operation completed in {duration:.3f} seconds")
            
            # Performance thresholds
            if duration < 1.0:
                print(f"🚀 Excellent performance: < 1 second")
            elif duration < 3.0:
                print(f"✅ Good performance: < 3 seconds")
            elif duration < 5.0:
                print(f"⚠️  Acceptable performance: < 5 seconds")
            else:
                print(f"❌ Poor performance: > 5 seconds")
        else:
            print(f"❌ Delete operation failed: {delete_response}")
    
    def run_all_delete_tests(self):
        """Run all delete-specific tests"""
        print("🗑️  Agent Registry Delete Functionality Test Suite")
        print("=" * 60)
        print(f"API URL: {self.api_url}")
        print(f"Region: {self.region}")
        
        start_time = time.time()
        
        try:
            # Test 1: Complete delete lifecycle
            self.test_delete_agent_lifecycle()
            
            # Test 2: Delete non-existent agent
            self.test_delete_nonexistent_agent()
            
            # Test 3: Delete with invalid agent IDs
            self.test_delete_invalid_agent_id()
            
            # Test 4: Delete multiple agents
            self.test_delete_multiple_agents()
            
            # Test 5: Delete performance
            self.test_delete_performance()
            
        except Exception as e:
            print(f"\n❌ Delete test suite failed with error: {e}")
            import traceback
            traceback.print_exc()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print(f"🏁 Delete Test Suite Completed in {duration:.2f} seconds")
        print("="*60)


def main():
    """Main function to run the delete test suite"""
    print("Agent Registry API Delete Functionality Test Suite")
    print("=" * 60)
    
    # Check if required packages are available
    try:
        import requests
        import requests_aws4auth
        print("✅ Required packages (requests, requests-aws4auth) are available")
    except ImportError as e:
        print(f"⚠️  Missing required packages: {e}")
        print("Install with: pip install requests requests-aws4auth")
        return
    
    # Initialize and run delete tests
    tester = DeleteAgentTester(API_GATEWAY_URL, AWS_REGION)
    tester.run_all_delete_tests()


if __name__ == "__main__":
    main()