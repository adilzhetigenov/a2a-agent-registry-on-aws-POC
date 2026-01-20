"""
Input validation utilities
"""
import re
import uuid
from typing import Dict, Any, List, Optional
from a2a.types import AgentCard


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, field: str, message: str, details: Optional[Dict] = None):
        self.field = field
        self.message = message
        self.details = details or {}
        super().__init__(f"Validation error in field '{field}': {message}")


def validate_uuid(value: str, field_name: str) -> str:
    """
    Validate UUID format
    
    Args:
        value: UUID string to validate
        field_name: Field name for error reporting
        
    Returns:
        Validated UUID string
        
    Raises:
        ValidationError: If UUID is invalid
    """
    if not value:
        raise ValidationError(field_name, "UUID is required")
    
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        raise ValidationError(field_name, "Invalid UUID format")


def validate_agent_card(data: Dict[str, Any]) -> AgentCard:
    """
    Validate and create AgentCard from input data
    
    Args:
        data: Raw input data
        
    Returns:
        Validated AgentCard instance
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValidationError("agent_card", "Agent card data must be a dictionary")
    
    # Basic required field validation
    required_fields = ["name", "description", "version", "url"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValidationError(field, f"Field '{field}' is required")
    
    # Validate name
    name = data.get("name", "").strip()
    if not name or len(name) < 2:
        raise ValidationError("name", "Name must be at least 2 characters long")
    
    if len(name) > 100:
        raise ValidationError("name", "Name must be less than 100 characters")
    
    # Validate description
    description = data.get("description", "").strip()
    if not description or len(description) < 10:
        raise ValidationError("description", "Description must be at least 10 characters long")
    
    if len(description) > 1000:
        raise ValidationError("description", "Description must be less than 1000 characters")
    
    # Validate version (required)
    version = data.get("version", "").strip()
    if not version:
        raise ValidationError("version", "Version is required")
    
    # Basic semantic version validation
    version_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
    if not re.match(version_pattern, version):
        raise ValidationError("version", "Version must follow semantic versioning (e.g., 1.0.0)")
    
    # Validate URL (required)
    url = data.get("url", "").strip()
    if not url:
        raise ValidationError("url", "URL is required")
    
    # Basic URL validation
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(url_pattern, url):
        raise ValidationError("url", "URL must be a valid HTTP/HTTPS URL")
    
    # Validate protocolVersion (optional, defaults to "0.3.0")
    protocol_version = data.get("protocolVersion", "0.3.0")
    if not isinstance(protocol_version, str) or not protocol_version.strip():
        raise ValidationError("protocolVersion", "Protocol version must be a non-empty string")
    
    # Validate preferredTransport (optional, defaults to "JSONRPC")
    preferred_transport = data.get("preferredTransport", "JSONRPC")
    valid_transports = ["JSONRPC", "HTTP", "WebSocket"]
    if preferred_transport not in valid_transports:
        raise ValidationError("preferredTransport", f"Preferred transport must be one of: {valid_transports}")
    
    # Validate capabilities (optional)
    capabilities = data.get("capabilities", {})
    if not isinstance(capabilities, dict):
        raise ValidationError("capabilities", "Capabilities must be a dictionary")
    
    # Validate streaming capability
    if "streaming" in capabilities:
        if not isinstance(capabilities["streaming"], bool):
            raise ValidationError("capabilities.streaming", "Streaming capability must be a boolean")
    
    # Validate defaultInputModes (optional, defaults to ["text"])
    default_input_modes = data.get("defaultInputModes", ["text"])
    if not isinstance(default_input_modes, list):
        raise ValidationError("defaultInputModes", "Default input modes must be a list")
    
    valid_modes = ["text", "image", "audio", "video", "file"]
    for i, mode in enumerate(default_input_modes):
        if not isinstance(mode, str) or mode not in valid_modes:
            raise ValidationError("defaultInputModes", f"Input mode at index {i} must be one of: {valid_modes}")
    
    # Validate defaultOutputModes (optional, defaults to ["text"])
    default_output_modes = data.get("defaultOutputModes", ["text"])
    if not isinstance(default_output_modes, list):
        raise ValidationError("defaultOutputModes", "Default output modes must be a list")
    
    for i, mode in enumerate(default_output_modes):
        if not isinstance(mode, str) or mode not in valid_modes:
            raise ValidationError("defaultOutputModes", f"Output mode at index {i} must be one of: {valid_modes}")
    
    # Validate skills (optional, defaults to empty list)
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        raise ValidationError("skills", "Skills must be a list")
    
    for i, skill in enumerate(skills):
        if not isinstance(skill, str) or not skill.strip():
            raise ValidationError("skills", f"Skill at index {i} must be a non-empty string")
    
    # Create validated agent card with defaults
    validated_data = {
        "name": name,
        "description": description,
        "version": version,
        "url": url,
        "protocolVersion": protocol_version,
        "preferredTransport": preferred_transport,
        "capabilities": capabilities,
        "defaultInputModes": default_input_modes,
        "defaultOutputModes": default_output_modes,
        "skills": skills
    }
    
    try:
        # TODO: Use a2a-sdk AgentCard validation when available
        # For now, return the validated data as a dict
        # This will be replaced with proper AgentCard instantiation in task 5
        return validated_data
    except Exception as e:
        raise ValidationError("agent_card", f"AgentCard validation failed: {str(e)}")


def validate_search_params(text_query: Optional[str] = None, skills: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Validate search parameters
    
    Args:
        text_query: Search query text
        skills: Optional list of skills
        
    Returns:
        Validated parameters
        
    Raises:
        ValidationError: If validation fails
    """
    validated_params = {}
    
    # Validate text query
    if text_query is not None:
        text_query = text_query.strip()
        if len(text_query) < 2:
            raise ValidationError("text", "Search text must be at least 2 characters long")
        
        if len(text_query) > 500:
            raise ValidationError("text", "Search text must be less than 500 characters")
        
        validated_params["text"] = text_query
    
    # Validate skills
    if skills is not None:
        if not isinstance(skills, list):
            raise ValidationError("skills", "Skills must be a list")
        
        validated_skills = []
        for i, skill in enumerate(skills):
            if not isinstance(skill, str):
                raise ValidationError("skills", f"Skill at index {i} must be a string")
            
            skill = skill.strip()
            if not skill:
                raise ValidationError("skills", f"Skill at index {i} cannot be empty")
            
            if len(skill) > 50:
                raise ValidationError("skills", f"Skill at index {i} must be less than 50 characters")
            
            validated_skills.append(skill)
        
        if len(validated_skills) > 10:
            raise ValidationError("skills", "Maximum 10 skills allowed in search")
        
        validated_params["skills"] = validated_skills
    
    # Ensure at least one search parameter is provided
    if not validated_params:
        raise ValidationError("search", "Either text or skills parameter must be provided")
    
    return validated_params


def validate_agent_card_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate agent card update data (partial updates allowed)
    
    Args:
        data: Raw update data (can be partial)
        
    Returns:
        Validated update data
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValidationError("agent_card", "Agent card update data must be a dictionary")
    
    if not data:
        raise ValidationError("agent_card", "Update data cannot be empty")
    
    validated_data = {}
    
    # Validate name (if provided)
    if "name" in data:
        name = data.get("name", "").strip()
        if not name or len(name) < 2:
            raise ValidationError("name", "Name must be at least 2 characters long")
        
        if len(name) > 100:
            raise ValidationError("name", "Name must be less than 100 characters")
        
        validated_data["name"] = name
    
    # Validate description (if provided)
    if "description" in data:
        description = data.get("description", "").strip()
        if not description or len(description) < 10:
            raise ValidationError("description", "Description must be at least 10 characters long")
        
        if len(description) > 1000:
            raise ValidationError("description", "Description must be less than 1000 characters")
        
        validated_data["description"] = description
    
    # Validate version (if provided)
    if "version" in data:
        version = data.get("version", "").strip()
        if not version:
            raise ValidationError("version", "Version cannot be empty")
        
        # Basic semantic version validation
        version_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
        if not re.match(version_pattern, version):
            raise ValidationError("version", "Version must follow semantic versioning (e.g., 1.0.0)")
        
        validated_data["version"] = version
    
    # Validate URL (if provided)
    if "url" in data:
        url = data.get("url", "").strip()
        if not url:
            raise ValidationError("url", "URL cannot be empty")
        
        # Basic URL validation
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, url):
            raise ValidationError("url", "URL must be a valid HTTP/HTTPS URL")
        
        validated_data["url"] = url
    
    # Validate protocolVersion (if provided)
    if "protocolVersion" in data:
        protocol_version = data.get("protocolVersion", "").strip()
        if not protocol_version:
            raise ValidationError("protocolVersion", "Protocol version cannot be empty")
        
        validated_data["protocolVersion"] = protocol_version
    
    # Validate preferredTransport (if provided)
    if "preferredTransport" in data:
        preferred_transport = data.get("preferredTransport")
        valid_transports = ["JSONRPC", "HTTP", "WebSocket"]
        if preferred_transport not in valid_transports:
            raise ValidationError("preferredTransport", f"Preferred transport must be one of: {valid_transports}")
        
        validated_data["preferredTransport"] = preferred_transport
    
    # Validate capabilities (if provided)
    if "capabilities" in data:
        capabilities = data.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValidationError("capabilities", "Capabilities must be a dictionary")
        
        # Validate streaming capability
        if "streaming" in capabilities:
            if not isinstance(capabilities["streaming"], bool):
                raise ValidationError("capabilities.streaming", "Streaming capability must be a boolean")
        
        validated_data["capabilities"] = capabilities
    
    # Validate defaultInputModes (if provided)
    if "defaultInputModes" in data:
        default_input_modes = data.get("defaultInputModes", [])
        if not isinstance(default_input_modes, list):
            raise ValidationError("defaultInputModes", "Default input modes must be a list")
        
        valid_modes = ["text", "image", "audio", "video", "file"]
        for i, mode in enumerate(default_input_modes):
            if not isinstance(mode, str) or mode not in valid_modes:
                raise ValidationError("defaultInputModes", f"Input mode at index {i} must be one of: {valid_modes}")
        
        validated_data["defaultInputModes"] = default_input_modes
    
    # Validate defaultOutputModes (if provided)
    if "defaultOutputModes" in data:
        default_output_modes = data.get("defaultOutputModes", [])
        if not isinstance(default_output_modes, list):
            raise ValidationError("defaultOutputModes", "Default output modes must be a list")
        
        valid_modes = ["text", "image", "audio", "video", "file"]
        for i, mode in enumerate(default_output_modes):
            if not isinstance(mode, str) or mode not in valid_modes:
                raise ValidationError("defaultOutputModes", f"Output mode at index {i} must be one of: {valid_modes}")
        
        validated_data["defaultOutputModes"] = default_output_modes
    
    # Validate skills (if provided)
    if "skills" in data:
        skills = data.get("skills", [])
        if not isinstance(skills, list):
            raise ValidationError("skills", "Skills must be a list")
        
        for i, skill in enumerate(skills):
            if not isinstance(skill, str) or not skill.strip():
                raise ValidationError("skills", f"Skill at index {i} must be a non-empty string")
        
        validated_data["skills"] = skills
    
    return validated_data


def validate_pagination_params(limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, int]:
    """
    Validate pagination parameters
    
    Args:
        limit: Number of items to return
        offset: Number of items to skip
        
    Returns:
        Validated pagination parameters
        
    Raises:
        ValidationError: If validation fails
    """
    validated_params = {}
    
    # Validate limit
    if limit is not None:
        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit", "Limit must be a positive integer")
        
        if limit > 100:
            raise ValidationError("limit", "Limit cannot exceed 100")
        
        validated_params["limit"] = limit
    else:
        validated_params["limit"] = 50  # Default limit
    
    # Validate offset
    if offset is not None:
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset", "Offset must be a non-negative integer")
        
        validated_params["offset"] = offset
    else:
        validated_params["offset"] = 0  # Default offset
    
    return validated_params