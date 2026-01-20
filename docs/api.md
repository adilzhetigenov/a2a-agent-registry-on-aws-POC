# Agent Registry API Documentation

## Overview

The Agent Registry API provides endpoints for managing agent cards with semantic search capabilities using Amazon S3 Vectors and AWS Bedrock Titan embeddings.

## Authentication

All endpoints require IAM authentication using AWS Signature Version 4.

## Endpoints

### Create Agent

- **POST** `/agents`
- Creates a new agent card
- Generates embedding using Bedrock Titan text-v2 (1024 dimensions)
- Stores agent data and embedding in S3 Vectors

### Get Agent

- **GET** `/agents/{id}`
- Retrieves a specific agent card by UUID

### List Agents

- **GET** `/agents`
- Lists all agents with pagination
- Query parameters: `limit` (1-100, default: 50), `offset` (default: 0)

### Search Agents

- **GET** `/agents/search`
- Searches agents using semantic text search, skill-based filtering, or both
- Query parameters:
  - `text`: Search query text (min 2, max 500 characters)
  - `skills`: Comma-separated list of skills (max 10 skills, AND logic)
  - `top_k`: Maximum results (1-30, default: 10)

### Update Agent

- **PUT** `/agents/{id}`
- Updates an existing agent card (partial updates supported)
- Regenerates embedding only when name or description changes

### Delete Agent

- **DELETE** `/agents/{id}`
- Deletes a specific agent card

### Update Health

- **POST** `/agents/{id}/health`
- Updates agent health status (last_online timestamp)

## Request/Response Examples

### Create Agent

**Request:**
```http
POST /agents
Content-Type: application/json

{
  "name": "FinanceBot Pro",
  "description": "Advanced financial analysis agent specializing in market research and portfolio optimization.",
  "version": "2.1.0",
  "url": "https://financebot.example.com/api",
  "skills": ["finance", "market-analysis", "python"],
  "capabilities": {"streaming": true},
  "defaultInputModes": ["text", "file"],
  "defaultOutputModes": ["text", "file"],
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0"
}
```

**Response (200):**
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Agent created successfully"
}
```

### Get Agent

**Request:**
```http
GET /agents/550e8400-e29b-41d4-a716-446655440000
```

**Response (200):**
```json
{
  "agent": {
    "name": "FinanceBot Pro",
    "description": "Advanced financial analysis agent specializing in market research and portfolio optimization.",
    "version": "2.1.0",
    "url": "https://financebot.example.com/api",
    "skills": ["finance", "market-analysis", "python"],
    "capabilities": {"streaming": true},
    "defaultInputModes": ["text", "file"],
    "defaultOutputModes": ["text", "file"],
    "preferredTransport": "JSONRPC",
    "protocolVersion": "0.3.0",
    "agent_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### List Agents

**Request:**
```http
GET /agents?limit=2&offset=0
```

**Response (200):**
```json
{
  "agents": [
    {
      "name": "FinanceBot Pro",
      "description": "Advanced financial analysis agent...",
      "version": "2.1.0",
      "url": "https://financebot.example.com/api",
      "skills": ["finance", "market-analysis", "python"],
      "agent_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "pagination": {
    "limit": 2,
    "offset": 0,
    "total": 5,
    "has_more": true
  }
}
```

### Search Agents

**Semantic Search:**
```http
GET /agents/search?text=financial%20market%20analysis&top_k=3
```

**Skill-Based Search:**
```http
GET /agents/search?skills=python,machine-learning&top_k=3
```

**Combined Search:**
```http
GET /agents/search?text=medical%20diagnosis&skills=healthcare,machine-learning&top_k=3
```

**Response:**
```json
[
  {
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_card": {
      "name": "FinanceBot Pro",
      "description": "Advanced financial analysis agent...",
      "version": "2.1.0",
      "url": "https://financebot.example.com/api",
      "skills": ["finance", "market-analysis", "python"]
    },
    "similarity_score": 0.345,
    "matched_skills": ["python"]
  }
]
```

### Update Agent

**Request:**
```http
PUT /agents/550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "name": "Enhanced Agent Name",
  "skills": ["python", "machine-learning", "new-skill"]
}
```

**Response (200):**
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Agent updated successfully"
}
```

### Delete Agent

**Request:**
```http
DELETE /agents/550e8400-e29b-41d4-a716-446655440000
```

**Response (200):**
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Agent deleted successfully"
}
```

### Update Health

**Request:**
```http
POST /agents/550e8400-e29b-41d4-a716-446655440000/health
```

**Response (200):**
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Health status updated successfully"
}
```

## Validation Rules

### Agent Card Fields

| Field | Required | Validation |
|-------|----------|------------|
| `name` | Yes | 2-100 characters |
| `description` | Yes | 10-1000 characters |
| `version` | Yes | Semantic versioning (e.g., "1.0.0") |
| `url` | Yes | Valid HTTP/HTTPS URL |
| `skills` | No | Array of non-empty strings |
| `preferredTransport` | No | "JSONRPC", "HTTP", or "WebSocket" (default: "JSONRPC") |
| `protocolVersion` | No | Non-empty string (default: "0.3.0") |
| `capabilities` | No | Object with boolean `streaming` field |
| `defaultInputModes` | No | Array of: "text", "image", "audio", "video", "file" |
| `defaultOutputModes` | No | Array of: "text", "image", "audio", "video", "file" |

### Search Parameters

| Parameter | Validation |
|-----------|------------|
| `text` | 2-500 characters |
| `skills` | Max 10 skills, each max 50 characters |
| `top_k` | 1-30 (default: 10) |

### Pagination Parameters

| Parameter | Validation |
|-----------|------------|
| `limit` | 1-100 (default: 50) |
| `offset` | Non-negative integer (default: 0) |

## Error Responses

All errors follow this format:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "requestId": "uuid"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `AGENT_NOT_FOUND` | 404 | Agent does not exist |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not supported |
| `INTERNAL_ERROR` | 500 | Server error |
| `EMBEDDING_GENERATION_ERROR` | 400 | Failed to generate embedding |
| `STORAGE_ERROR` | 500 | S3 Vectors operation failed |

## Data Storage

Agent data is stored in Amazon S3 Vectors with the following metadata structure:
- `agent_id`: UUID identifier
- `name`: Agent name
- `description`: Agent description
- `skills`: Array of skills (filterable)
- `version`: Semantic version
- `url`: Agent URL
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp
- `last_online`: ISO timestamp (health status)
- `raw_agent_card`: Full agent card JSON (non-filterable)

Vector embeddings are 1024-dimensional float32 arrays generated using Amazon Bedrock Titan text-v2 model with cosine distance metric.
