import pytest
from unittest.mock import MagicMock, patch

from backend.analysis.dependency_parser import DependencyInfo
from backend.services.impact_scoring import ImpactScorer


def test_calculate_business_value_score():
    """Test calculating business value score."""
    # Create a mock session
    mock_session = MagicMock()
    
    # Create a scorer
    scorer = ImpactScorer(mock_session)
    
    # Test with different dependencies
    result1 = scorer._calculate_business_value_score("django", "python")
    result2 = scorer._calculate_business_value_score("left-pad", "nodejs")
    result3 = scorer._calculate_business_value_score("unknown-pkg", "python")
    
    # Django should have