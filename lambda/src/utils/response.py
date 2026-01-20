"""
Response formatting utilities
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime


def format_success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    """
    Format successful API response
    
    Args:
        data: Response data
        status_code: HTTP status code
        
    Returns:
        Formatted response data
    """
    if isinstance(data, dict):
        return data
    
    return {"data": data}


def format_error_response(error_code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Format error response
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        details: Additional error details
        
    Returns:
        Formatted error response
    """
    error_response = {
        "error": {
            "code": error_code,
            "message": message
        }
    }
    
    if details:
        error_response["error"]["details"] = details
    
    return error_response


def format_pagination_response(items: list, limit: int, offset: int, total: int) -> Dict[str, Any]:
    """
    Format paginated response
    
    Args:
        items: List of items
        limit: Items per page
        offset: Current offset
        total: Total number of items
        
    Returns:
        Formatted paginated response
    """
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + len(items) < total
        }
    }


def format_search_response(results: list, query: Dict[str, Any], total: int = None) -> Dict[str, Any]:
    """
    Format search response
    
    Args:
        results: Search results
        query: Original search query
        total: Total number of results (optional)
        
    Returns:
        Formatted search response
    """
    response = {
        "results": results,
        "query": query,
        "count": len(results)
    }
    
    if total is not None:
        response["total"] = total
    
    return response


def add_timestamps(data: Dict[str, Any], created_at: Optional[datetime] = None, 
                  updated_at: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Add timestamp fields to response data
    
    Args:
        data: Response data
        created_at: Creation timestamp
        updated_at: Update timestamp
        
    Returns:
        Data with timestamps
    """
    if created_at:
        data["created_at"] = created_at.isoformat()
    
    if updated_at:
        data["updated_at"] = updated_at.isoformat()
    
    return data


def sanitize_response_data(data: Any) -> Any:
    """
    Sanitize response data for JSON serialization
    
    Args:
        data: Data to sanitize
        
    Returns:
        JSON-serializable data
    """
    if isinstance(data, dict):
        return {key: sanitize_response_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_response_data(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    elif hasattr(data, '__dict__'):
        # Handle objects with attributes
        return sanitize_response_data(data.__dict__)
    else:
        return data