#!/bin/bash

# Agent Registry API Integration Tests
# Run with: ./run_tests.sh

echo "🚀 Starting Agent Registry API Integration Tests"
echo "================================================"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first."
    echo "Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured or invalid."
    echo "Please configure your AWS credentials using:"
    echo "  aws configure"
    echo "  or set AWS_PROFILE environment variable"
    exit 1
fi

echo "✅ AWS credentials configured"
aws sts get-caller-identity --query 'Account' --output text | xargs echo "Account ID:"

# Run the tests using uv
echo ""
echo "🧪 Running integration tests..."
uv run test_agent_registry_api.py

echo ""
echo "✅ Integration tests completed!"