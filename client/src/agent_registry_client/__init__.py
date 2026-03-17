"""
Agent Registry Client SDK
"""
from .m2m_client import M2MClient
from .lifecycle import AgentLifecycle
from .exceptions import (
    AgentRegistryError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError,
)
from .models import AgentListResponse, SearchResult, HealthStatus

__version__ = "0.2.0"


def __getattr__(name: str):
    """Lazy import for AgentRegistryClient (requires requests-aws4auth)."""
    if name == "AgentRegistryClient":
        from .client import AgentRegistryClient
        return AgentRegistryClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentRegistryClient",
    "M2MClient",
    "AgentLifecycle",
    "AgentRegistryError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "ServerError",
    "AgentListResponse",
    "SearchResult",
    "HealthStatus",
]
