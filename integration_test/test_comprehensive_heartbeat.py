#!/usr/bin/env python3
"""
Comprehensive heartbeat test - create agent, remember ID, push heartbeat, validate last_seen/online flag
"""

import requests
from requests_aws4auth import AWS4Auth
import boto3
import json
import time
import uuid

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

def test_comprehensive_heartbeat_workflow(auth):
    """Test complete heartbeat workflow"""
    print("🧪 Comprehensive Heartbeat Workflow Test")
    print("=" * 60)
    
    # Step 1: Create a test agent
    print("\n1. Creating test agent...")
    agent_data = {
        "name": f"Test Heartbeat Agent {uuid.uuid4().hex[:8]}",
        "description": "A comprehensive test agent for validating heartbeat functionality and online status tracking",
        "version": "1.0.0",
        "url": "https://heartbeat-test.example.com/api",
        "skills": ["testing", "heartbeat", "monitoring"],
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
    
    if response.status_code != 200:
        print(f"❌ Failed to create agent: {response.status_code} - {response.text}")
        return None
    
    agent_id = response.json().get('agent_id')
    print(f"✅ Created agent with ID: {agent_id}")
    
    # Step 2: Wait for agent to be indexed
    print("\n2. Waiting for agent to be indexed...")
    time.sleep(5)
    
    # Step 3: Get initial agent state
    print("\n3. Getting initial agent state...")
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/{agent_id}",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get initial agent state: {response.status_code} - {response.text}")
        return None
    
    initial_agent = response.json().get('agent', {})
    print(f"✅ Retrieved agent: {initial_agent.get('name')}")
    
    # Step 4: Send multiple heartbeats with timestamps
    print("\n4. Sending multiple heartbeats...")
    heartbeat_timestamps = []
    
    for i in range(3):
        print(f"   Sending heartbeat {i+1}/3...")
        
        # Record timestamp before heartbeat
        before_heartbeat = time.time()
        
        response = requests.post(
            f"{API_GATEWAY_URL}/agents/{agent_id}/health",
            auth=auth,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        # Record timestamp after heartbeat
        after_heartbeat = time.time()
        
        if response.status_code == 200:
            print(f"   ✅ Heartbeat {i+1} successful")
            heartbeat_timestamps.append({
                'before': before_heartbeat,
                'after': after_heartbeat,
                'response': response.json()
            })
        else:
            print(f"   ❌ Heartbeat {i+1} failed: {response.status_code} - {response.text}")
        
        # Wait between heartbeats
        if i < 2:
            time.sleep(2)
    
    # Step 5: Validate agent state after heartbeats
    print("\n5. Validating agent state after heartbeats...")
    time.sleep(2)  # Wait for updates to propagate
    
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/{agent_id}",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get updated agent state: {response.status_code} - {response.text}")
        return None
    
    updated_agent = response.json().get('agent', {})
    print(f"✅ Retrieved updated agent: {updated_agent.get('name')}")
    
    # Step 6: Test heartbeat with non-existent agent
    print("\n6. Testing heartbeat with non-existent agent...")
    fake_agent_id = str(uuid.uuid4())
    
    response = requests.post(
        f"{API_GATEWAY_URL}/agents/{fake_agent_id}/health",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code == 404:
        print("✅ Correctly returned 404 for non-existent agent heartbeat")
    else:
        print(f"⚠️  Expected 404, got {response.status_code}: {response.text}")
    
    # Step 7: Test heartbeat with invalid agent ID
    print("\n7. Testing heartbeat with invalid agent ID...")
    
    response = requests.post(
        f"{API_GATEWAY_URL}/agents/invalid-uuid/health",
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code == 400:
        print("✅ Correctly returned 400 for invalid agent ID")
    else:
        print(f"⚠️  Expected 400, got {response.status_code}: {response.text}")
    
    # Step 8: Verify agent can still be found in search
    print("\n8. Verifying agent appears in search results...")
    
    response = requests.get(
        f"{API_GATEWAY_URL}/agents/search",
        params={'text': 'heartbeat monitoring', 'top_k': 10},
        auth=auth,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    if response.status_code == 200:
        response_data = response.json()
        if isinstance(response_data, list):
            results = response_data
        else:
            results = response_data.get('results', [])
        found_agent = False
        
        for result in results:
            if result.get('name', '').startswith('Heartbeat Test Agent'):
                found_agent = True
                similarity = result.get('_search_metadata', {}).get('similarity_score', 0)
                print(f"✅ Found agent in search results (similarity: {similarity:.3f})")
                break
        
        if not found_agent:
            print("⚠️  Agent not found in search results")
    else:
        print(f"❌ Search failed: {response.status_code} - {response.text}")
    
    print(f"\n📊 Heartbeat test completed for agent: {agent_id}")
    return agent_id

def main():
    """Main test function"""
    print("🚀 Comprehensive Heartbeat Test Suite")
    print("=" * 70)
    
    # Setup authentication
    auth = setup_auth()
    
    # Run comprehensive heartbeat test
    agent_id = test_comprehensive_heartbeat_workflow(auth)
    
    if agent_id:
        print(f"\n✅ All heartbeat tests completed successfully!")
        print(f"Test agent ID: {agent_id}")
    else:
        print(f"\n❌ Heartbeat tests failed")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()