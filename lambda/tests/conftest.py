"""
Pytest configuration and fixtures
"""
import pytest
from moto import mock_aws


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing"""
    with mock_aws():
        yield