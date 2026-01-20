#!/usr/bin/env python3
"""
Simple heartbeat test to verify functionality
"""

import requests
from requests_aws4auth import AWS4Auth
import boto3
import json
import time

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

def create_test_agent(auth):
    """Create a simple test agent"""
    agent_data = {
        "name": "Test Heartbeat Agent",
        "description": "A simple agent for testing heartbeat functionality",
        "version": "1.0.0",
        "url": "https://test-agent.example.com/api",
        "skills": ["testing", "heartbeat"],
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "preferredTransport": "JSONRPC",
        "protocolVersion": "0.3.0"
    }
    
    response = requests.post(
        f"{API_GATEWAY_URL}/agents",
        json=agent_data,
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"Create agent response: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        agent_id = result.get('agent_id')
        print(f"Created agent with ID: {agent_id}")
        return agent_id
    else:
        print(f"Failed to create agent: {response.text}")
        return None

def test_heartbeat(auth, agent_id):
    """Test heartbeat functionality"""
    print(f"\nTesting heartbeat for agent: {agent_id}")
    
    # Send heartbeat
    response = requests.post(
        f"{API_GATEWAY_URL}/agents/{agent_id}/health",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"Heartbeat response: {response.status_code}")
    if response.status_code == 200:
        print("✅ Heartbeat successful")
        return True
    else:
        print(f"❌ Heartbeat failed: {response.text}")
        return False

def get_agent(auth, agent_id):
    """Get agent details"""
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/{agent_id}",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    print(f"Get agent response: {response.status_code}")
    if response.status_code == 200:
        agent = response.json().get('agent', {})
        print(f"Agent name: {agent.get('name')}")
        return agent
    else:
        print(f"Failed to get agent: {response.text}")
        return None

def main():
    """Main test function"""
    print("🧪 Simple Heartbeat Test")
    print("=" * 40)
    
    # Setup authentication
    auth = setup_auth()
    
    # Create test agent
    agent_id = create_test_agent(auth)
    if not agent_id:
        print("❌ Failed to create test agent")
        return
    
    # Wait a moment for agent to be indexed
    print("\n⏳ Waiting 5 seconds for agent to be indexed...")
    time.sleep(5)
    
    # Get initial agent state
    print("\n1. Getting initial agent state...")
    initial_agent = get_agent(auth, agent_id)
    
    # Test heartbeat
    print("\n2. Testing heartbeat...")
    heartbeat_success = test_heartbeat(auth, agent_id)
    
    # Get agent state after heartbeat
    if heartbeat_success:
        print("\n3. Getting agent state after heartbeat...")
        time.sleep(2)  # Wait for update to propagate
        updated_agent = get_agent(auth, agent_id)
    
    print("\n✅ Heartbeat test completed")

if __name__ == "__main__":
    main()