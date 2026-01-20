"""
Unit tests for validation utilities
"""
import pytest

from src.utils.validation import ValidationError, validate_agent_card_update


class TestValidateAgentCardUpdate:
    """Test cases for validate_agent_card_update function"""
    
    def test_validate_update_success(self):
        """Test successful validation of update data"""
        update_data = {
            "name": "Updated Agent Name",
            "description": "Updated description for the agent",
            "skills": ["python", "testing", "automation"]
        }
        
        result = validate_agent_card_update(update_data)
        
        assert result["name"] == "Updated Agent Name"
        assert result["description"] == "Updated description for the agent"
        assert result["skills"] == ["python", "testing", "automation"]
    
    def test_validate_partial_update(self):
        """Test validation of partial update data"""
        update_data = {
            "name": "New Name Only"
        }
        
        result = validate_agent_card_update(update_data)
        
        assert result["name"] == "New Name Only"
        assert len(result) == 1  # Only name should be in result
    
    def test_validate_empty_data_error(self):
        """Test validation error for empty update data"""
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update({})
        
        assert exc_info.value.field == "agent_card"
        assert "cannot be empty" in exc_info.value.message
    
    def test_validate_non_dict_error(self):
        """Test validation error for non-dictionary data"""
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update("not a dict")
        
        assert exc_info.value.field == "agent_card"
        assert "must be a dictionary" in exc_info.value.message
    
    def test_validate_name_too_short(self):
        """Test validation error for name too short"""
        update_data = {"name": "A"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "name"
        assert "at least 2 characters" in exc_info.value.message
    
    def test_validate_name_too_long(self):
        """Test validation error for name too long"""
        update_data = {"name": "A" * 101}  # 101 characters
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "name"
        assert "less than 100 characters" in exc_info.value.message
    
    def test_validate_description_too_short(self):
        """Test validation error for description too short"""
        update_data = {"description": "Short"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "description"
        assert "at least 10 characters" in exc_info.value.message
    
    def test_validate_description_too_long(self):
        """Test validation error for description too long"""
        update_data = {"description": "A" * 1001}  # 1001 characters
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "description"
        assert "less than 1000 characters" in exc_info.value.message
    
    def test_validate_invalid_version(self):
        """Test validation error for invalid version format"""
        update_data = {"version": "invalid-version"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "version"
        assert "semantic versioning" in exc_info.value.message
    
    def test_validate_invalid_url(self):
        """Test validation error for invalid URL"""
        update_data = {"url": "not-a-url"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "url"
        assert "valid HTTP/HTTPS URL" in exc_info.value.message
    
    def test_validate_invalid_transport(self):
        """Test validation error for invalid preferred transport"""
        update_data = {"preferredTransport": "INVALID"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "preferredTransport"
        assert "must be one of" in exc_info.value.message
    
    def test_validate_invalid_capabilities(self):
        """Test validation error for invalid capabilities"""
        update_data = {"capabilities": "not a dict"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "capabilities"
        assert "must be a dictionary" in exc_info.value.message
    
    def test_validate_invalid_skills(self):
        """Test validation error for invalid skills"""
        update_data = {"skills": "not a list"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "skills"
        assert "must be a list" in exc_info.value.message
    
    def test_validate_empty_skill(self):
        """Test validation error for empty skill in list"""
        update_data = {"skills": ["python", "", "testing"]}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_card_update(update_data)
        
        assert exc_info.value.field == "skills"
        assert "non-empty string" in exc_info.value.message
    
    def test_validate_valid_version_formats(self):
        """Test validation success for various valid version formats"""
        valid_versions = [
            "1.0.0",
            "2.1.3",
            "1.0.0-alpha",
            "1.0.0-beta.1",
            "1.0.0-rc.1.2"
        ]
        
        for version in valid_versions:
            update_data = {"version": version}
            result = validate_agent_card_update(update_data)
            assert result["version"] == version
    
    def test_validate_valid_urls(self):
        """Test validation success for various valid URLs"""
        valid_urls = [
            "https://example.com",
            "http://localhost:8080",
            "https://api.example.com/v1/agent",
            "https://subdomain.example.com/path?query=value"
        ]
        
        for url in valid_urls:
            update_data = {"url": url}
            result = validate_agent_card_update(update_data)
            assert result["url"] == url