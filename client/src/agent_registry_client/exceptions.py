"""
Custom exceptions for Agent Registry Client
"""


class AgentRegistryError(Exception):
    """Base exception for Agent Registry Client"""
    pass


class ValidationError(AgentRegistryError):
    """Raised when validation fails"""
    pass


class NotFoundError(AgentRegistryError):
    """Raised when resource is not found"""
    pass


class AuthenticationError(AgentRegistryError):
    """Raised when authentication fails"""
    pass


class ServerError(AgentRegistryError):
    """Raised when server error occurs"""
    pass