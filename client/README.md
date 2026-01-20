# Agent Registry Client SDK

Python client SDK for the Agent Registry API platform.

## Installation

```bash
# Install using uv
uv add agent-registry-client

# Or install from source
uv pip install -e .
```

## Usage

### Initialize Client

```python
from agent_registry_client import AgentRegistryClient

# Initialize client
client = AgentRegistryClient(
    api_gateway_url="https://your-api.execute-api.us-east-1.amazonaws.com/prod"
)
```

### Create Agent

```python
from a2a.types import AgentCard

# Create agent card
from a2a.types import AgentSkill, AgentCapabilities

agent_card = AgentCard(
    name="My Test Agent",
    description="A test agent for demonstration",
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
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    preferredTransport="JSONRPC",
    protocolVersion="0.3.0"
)

# Create agent
agent_id = client.create_agent(agent_card)
print(f"Created agent: {agent_id}")
```

### Get Agent

```python
# Get agent by ID
agent = client.get_agent(agent_id)
print(f"Agent name: {agent.name}")
```

### List Agents

```python
# List agents with pagination
response = client.list_agents(limit=10, offset=0)
print(f"Found {len(response.agents)} agents")
print(f"Total: {response.total_count}, Has more: {response.has_more}")
```

### Search Agents

```python
# Search by text
results = client.search_agents(query="python automation")
for result in results:
    print(f"Agent: {result.agent_card.name}, Score: {result.similarity_score}")

# Search by skills
results = client.search_agents(skills=["python", "testing"])
for result in results:
    print(f"Agent: {result.agent_card.name}, Skills: {result.matched_skills}")

# Combined search
results = client.search_agents(
    query="automation tool", 
    skills=["python"], 
    top_k=5
)
```

### Update Health

```python
# Update agent health status
success = client.update_health(agent_id)
print(f"Health update successful: {success}")
```

## Error Handling

```python
from agent_registry_client import (
    AgentRegistryError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError
)

try:
    agent = client.get_agent("invalid-id")
except NotFoundError:
    print("Agent not found")
except ValidationError as e:
    print(f"Validation error: {e}")
except AuthenticationError as e:
    print(f"Authentication error: {e}")
except AgentRegistryError as e:
    print(f"API error: {e}")
```

## Authentication

The client uses AWS IAM authentication. Ensure you have:

1. AWS credentials configured (via AWS CLI, environment variables, or IAM roles)
2. Proper IAM permissions for the API Gateway endpoints

Required IAM permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "execute-api:Invoke"
            ],
            "Resource": "arn:aws:execute-api:*:*:*/*/agents/*"
        }
    ]
}
```