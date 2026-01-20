#!/bin/sh

# Docker entrypoint script for Agent Registry Web UI
# Handles runtime environment variable configuration

set -e

# Default values
DEFAULT_API_GATEWAY_URL="https://api.agent-registry.example.com"
DEFAULT_AWS_REGION="us-east-1"

# Use environment variables or defaults
API_GATEWAY_URL=${REACT_APP_API_GATEWAY_URL:-$DEFAULT_API_GATEWAY_URL}
AWS_REGION=${REACT_APP_AWS_REGION:-$DEFAULT_AWS_REGION}
IDENTITY_POOL_ID=${REACT_APP_IDENTITY_POOL_ID:-""}

echo "Configuring Agent Registry Web UI..."
echo "API Gateway URL: $API_GATEWAY_URL"
echo "AWS Region: $AWS_REGION"
echo "Identity Pool ID: ${IDENTITY_POOL_ID:+[SET]}"

# Create runtime configuration file
cat > /usr/share/nginx/html/config.js << EOF
window.ENV = {
  REACT_APP_API_GATEWAY_URL: '$API_GATEWAY_URL',
  REACT_APP_AWS_REGION: '$AWS_REGION',
  REACT_APP_IDENTITY_POOL_ID: '$IDENTITY_POOL_ID'
};
EOF

echo "Runtime configuration created successfully"

# Execute the main command
exec "$@"