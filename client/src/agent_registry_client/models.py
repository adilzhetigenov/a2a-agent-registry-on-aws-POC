"""
Response models for Agent Registry Client
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from a2a.types import AgentCard


@dataclass
class SearchResult:
    """Search result with similarity score"""
    agent_card: AgentCard
    similarity_score: float
    matched_skills: List[str]


@dataclass
class AgentListResponse:
    """Response for list agents API"""
    agents: List[AgentCard]
    total_count: int
    has_more: bool


@dataclass
class HealthStatus:
    """Agent health status"""
    agent_id: str
    last_online: Optional[datetime]
    is_online: bool