#!/usr/bin/env python3
"""
Test embedding error handling - verify that agents with invalid text fail to create
"""

import requests
from requests_aws4auth import AWS4Auth
import boto3
import json

# Configuration - read from environment variables
import os
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL")
AWS_REGION = os.environ.get("AWS_REGION")

if not API_GATEWAY_URL:
    raise ValueError("API_GATEWAY_URL environment variable is required")
if not AWS_REGION:
    raise ValueError("AWS_REGION environment variable is required")

def setup_auth():
    """Setup AWS authentication"""
    session = boto3.Session()
    credentials = session.get_credentials()
    
    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        AWS_REGION,
        'execute-api',
        session_token=credentials.token
    )

def test_embedding_error_scenarios(auth):
    """Test various scenarios that might cause embedding errors"""
    print("🧪 Testing Embedding Error Handling")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "Empty Description",
            "description": "Test agent with empty description that might cause embedding issues",
            "agent_data": {
                "name": "Test Empty Description Agent",
                "description": "",  # Empty description
                "version": "1.0.0",
                "url": "https://test-agent.example.com/api",
                "skills": ["testing"],
                "capabilities": {"streaming": True},
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "preferredTransport": "JSONRPC",
                "protocolVersion": "0.3.0"
            },
            "expected_status": 400,
            "expected_error": "VALIDATION_ERROR"  # Should fail validation before embedding
        },
        {
            "name": "Very Long Description",
            "description": "Test agent with extremely long description that might exceed embedding limits",
            "agent_data": {
                "name": "Test Long Description Agent",
                "description": "A" * 100000,  # Very long description (100k characters)
                "version": "1.0.0",
                "url": "https://test-agent.example.com/api",
                "skills": ["testing"],
                "capabilities": {"streaming": True},
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "preferredTransport": "JSONRPC",
                "protocolVersion": "0.3.0"
            },
            "expected_status": 400,
            "expected_error": "VALIDATION_ERROR"  # Should fail validation (description too long)
        },
        {
            "name": "Valid Agent",
            "description": "Test that valid agents still work correctly",
            "agent_data": {
                "name": "Test Valid Agent",
                "description": "A properly formatted test agent with reasonable description length",
                "version": "1.0.0",
                "url": "https://test-agent.example.com/api",
                "skills": ["testing", "validation"],
                "capabilities": {"streaming": True},
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "preferredTransport": "JSONRPC",
                "protocolVersion": "0.3.0"
            },
            "expected_status": 200,
            "expected_error": None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   {test_case['description']}")
        
        response = requests.post(
            f"{API_GATEWAY_URL}/agents",
            json=test_case['agent_data'],
            auth=auth,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"   Response status: {response.status_code}")
        
        if response.status_code == test_case['expected_status']:
            print(f"   ✅ Expected status code {test_case['expected_status']}")
            
            if test_case['expected_error']:
                try:
                    response_data = response.json()
                    error_code = response_data.get('error', {}).get('code')
                    if error_code == test_case['expected_error']:
                        print(f"   ✅ Expected error code: {error_code}")
                    else:
                        print(f"   ⚠️  Expected error code {test_case['expected_error']}, got {error_code}")
                except:
                    print(f"   ❌ Failed to parse error response")
            else:
                # Success case
                try:
                    response_data = response.json()
                    agent_id = response_data.get('agent_id')
                    if agent_id:
                        print(f"   ✅ Agent created successfully: {agent_id}")
                    else:
                        print(f"   ⚠️  No agent_id in response")
                except:
                    print(f"   ❌ Failed to parse success response")
        else:
            print(f"   ❌ Expected status {test_case['expected_status']}, got {response.status_code}")
            try:
                response_data = response.json()
                print(f"   Error: {response_data}")
            except:
                print(f"   Raw response: {response.text}")

def test_search_embedding_error(auth):
    """Test search with text that might cause embedding errors"""
    print(f"\n🔍 Testing Search Embedding Error Handling")
    print("=" * 50)
    
    # Test search with empty query (should be caught by validation)
    print("\n1. Testing search with empty query...")
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/search",
        params={'text': ''},
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"   Response status: {response.status_code}")
    if response.status_code == 400:
        print("   ✅ Correctly rejected empty search query")
    else:
        print(f"   ❌ Expected 400, got {response.status_code}")
    
    # Test search with very long query
    print("\n2. Testing search with very long query...")
    long_query = "A" * 1000  # 1000 character query
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/search",
        params={'text': long_query, 'top_k': 5},
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"   Response status: {response.status_code}")
    if response.status_code in [200, 400]:  # Either works or fails validation
        print(f"   ✅ Handled long query appropriately")
    else:
        print(f"   ❌ Unexpected status code: {response.status_code}")
        try:
            print(f"   Error: {response.json()}")
        except:
            print(f"   Raw response: {response.text}")

def main():
    """Main test function"""
    print("🚀 Embedding Error Handling Test Suite")
    print("=" * 60)
    
    # Setup authentication
    auth = setup_auth()
    
    # Test agent creation with various edge cases
    test_embedding_error_scenarios(auth)
    
    # Test search embedding error handling
    test_search_embedding_error(auth)
    
    print("\n" + "=" * 60)
    print("✅ Embedding Error Handling Tests Completed")

if __name__ == "__main__":
    main()