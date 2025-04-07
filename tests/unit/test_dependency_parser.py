import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from backend.analysis.dependency_parser import (
    DependencyInfo,
    DependencyParser,
    DependencyParserFactory,
    detect_project_ecosystems,
    parse_project_dependencies,
    merge_dependency_info
)
from backend.analysis.python_analyzer import PythonDependencyParser
from backend.analysis.nodejs_analyzer import NodeJSDependencyParser


def test_dependency_info_creation():
    """Test creating a DependencyInfo object."""
    dep = DependencyInfo(
        name="requests",
        version="2.28.1",
        ecosystem="python",
        is_direct=True,
        path="/path/to/requirements.txt",
        parent=None
    )
    
    assert dep.name == "requests"
    assert dep.version == "2.28.1"
    assert dep.ecosystem == "python"
    assert dep.is_direct is True
    assert dep.path == "/path/to/requirements.txt"
    assert dep.parent is None
    assert isinstance(dep.used_features, set)
    assert isinstance(dep.required_by, set)
    assert isinstance(dep.licenses, list)
    assert isinstance(dep.metadata, dict)


def test_dependency_info_equality():
    """Test equality comparison for DependencyInfo."""
    dep1 = DependencyInfo(name="requests", version="2.28.1", ecosystem="python")
    dep2 = DependencyInfo(name="requests", version="2.28.1", ecosystem="python")
    dep3 = DependencyInfo(name="requests", version="2.28.0", ecosystem="python")
    
    assert dep1 == dep2
    assert dep1 != dep3
    assert hash(dep1) == hash(dep2)
    assert hash(dep1) != hash(dep3)


def test_dependency_info_to_dict():
    """Test converting DependencyInfo to dictionary."""
    dep = DependencyInfo(
        name="requests",
        version="2.28.1",
        ecosystem="python",
        is_direct=True
    )
    dep.used_features.add("requests.get")
    dep.required_by.add("main_app")
    dep.licenses.append("MIT")
    
    dep_dict = dep.to_dict()
    
    assert dep_dict["name"] == "requests"
    assert dep_dict["version"] == "2.28.1"
    assert dep_dict["ecosystem"] == "python"
    assert dep_dict["is_direct"] is True
    assert "requests.get" in dep_dict["used_features"]
    assert "main_app" in dep_dict["required_by"]
    assert "MIT" in dep_dict["licenses"]


def test_dependency_parser_factory():
    """Test DependencyParserFactory creates correct parsers."""
    python_parser = DependencyParserFactory.create_parser("python")
    nodejs_parser = DependencyParserFactory.create_parser("nodejs")
    
    assert isinstance(python_parser, PythonDependencyParser)
    assert isinstance(nodejs_parser, NodeJSDependencyParser)
    assert python_parser.ecosystem == "python"
    assert nodejs_parser.ecosystem == "nodejs"
    
    # Test with case insensitivity
    python_parser2 = DependencyParserFactory.create_parser("Python")
    assert isinstance(python_parser2, PythonDependencyParser)
    
    # Test with unsupported ecosystem
    with pytest.raises(ValueError, match="Unsupported ecosystem"):
        DependencyParserFactory.create_parser("nonexistent")


def test_detect_project_ecosystems():
    """Test detecting project ecosystems."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Empty directory should return empty list
        assert detect_project_ecosystems(tempdir) == []
        
        # Create a requirements.txt file
        with open(os.path.join(tempdir, "requirements.txt"), "w") as f:
            f.write("requests==2.28.1\n")
        
        # Should detect Python
        assert detect_project_ecosystems(tempdir) == ["python"]
        
        # Create a package.json file
        with open(os.path.join(tempdir, "package.json"), "w") as f:
            f.write('{"name": "test-project", "dependencies": {"axios": "^0.27.2"}}')
        
        # Should detect both Python and Node.js
        ecosystems = detect_project_ecosystems(tempdir)
        assert len(ecosystems) == 2
        assert "python" in ecosystems
        assert "nodejs" in ecosystems


def test_merge_dependency_info():
    """Test merging duplicate dependencies."""
    deps = [
        DependencyInfo(name="requests", version="2.28.1", ecosystem="python"),
        DependencyInfo(name="requests", version="2.28.1", ecosystem="python"),
        DependencyInfo(name="axios", version="0.27.2", ecosystem="nodejs")
    ]
    
    # Add different features and requirements to each copy
    deps[0].used_features.add("requests.get")
    deps[0].required_by.add("service_a")
    deps[0].licenses.append("MIT")
    
    deps[1].used_features.add("requests.post")
    deps[1].required_by.add("service_b")
    deps[1].is_direct = False
    
    # Merge dependencies
    merged = merge_dependency_info(deps)
    
    # Should have 2 unique dependencies
    assert len(merged) == 2
    
    # Find the requests dependency in the merged list
    requests_dep = next(d for d in merged if d.name == "requests")
    
    # Check that features and requirements were merged
    assert "requests.get" in requests_dep.used_features
    assert "requests.post" in requests_dep.used_features
    assert "service_a" in requests_dep.required_by
    assert "service_b" in requests_dep.required_by
    assert "MIT" in requests_dep.licenses
    
    # Direct status should be preserved if any occurrence is direct
    assert requests_dep.is_direct is True


@patch("backend.analysis.dependency_parser.DependencyParserFactory")
def test_parse_project_dependencies(mock_factory):
    """Test the parse_project_dependencies function."""
    # Mock the parser
    mock_parser = MagicMock()
    mock_factory.create_parser.return_value = mock_parser
    
    # Mock dependencies
    mock_deps = [
        DependencyInfo(name="requests", version="2.28.1", ecosystem="python"),
        DependencyInfo(name="numpy", version="1.23.1", ecosystem="python")
    ]
    mock_parser.parse_dependencies.return_value = mock_deps
    
    # Test with explicit ecosystem
    result = parse_project_dependencies("/path/to/project", "python")
    
    mock_factory.create_parser.assert_called_with("python")
    mock_parser.parse_dependencies.assert_called_with("/path/to/project")
    assert "python" in result
    assert result["python"] == mock_deps


@patch("backend.analysis.dependency_parser.detect_project_ecosystems")
@patch("backend.analysis.dependency_parser.DependencyParserFactory")
def test_parse_project_dependencies_auto_detect(mock_factory, mock_detect):
    """Test parsing with auto-detected ecosystems."""
    # Mock ecosystem detection
    mock_detect.return_value = ["python", "nodejs"]
    
    # Mock parsers
    python_parser = MagicMock()
    nodejs_parser = MagicMock()
    
    mock_factory.create_parser.side_effect = lambda eco: {
        "python": python_parser,
        "nodejs": nodejs_parser
    }[eco]
    
    # Mock dependencies
    python_deps = [DependencyInfo(name="requests", version="2.28.1", ecosystem="python")]
    nodejs_deps = [DependencyInfo(name="axios", version="0.27.2", ecosystem="nodejs")]
    
    python_parser.parse_dependencies.return_value = python_deps
    nodejs_parser.parse_dependencies.return_value = nodejs_deps
    
    # Test with auto-detection
    result = parse_project_dependencies("/path/to/project")
    
    mock_detect.assert_called_with("/path/to/project")
    assert "python" in result
    assert "nodejs" in result
    assert result["python"] == python_deps
    assert result["nodejs"] == nodejs_deps