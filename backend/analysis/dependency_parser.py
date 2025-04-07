import os
import logging
import json
from typing import Dict, List, Set, Optional, Any, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DependencyInfo:
    """Data class for dependency information."""
    
    def __init__(
        self,
        name: str,
        version: str,
        ecosystem: str,
        is_direct: bool = True,
        path: Optional[str] = None,
        parent: Optional[str] = None,
    ):
        self.name = name
        self.version = version
        self.ecosystem = ecosystem
        self.is_direct = is_direct  # Direct or transitive dependency
        self.path = path  # Path in the project where it's defined
        self.parent = parent  # Parent dependency if transitive
        self.used_features: Set[str] = set()  # Features actually used
        self.required_by: Set[str] = set()  # Dependencies requiring this one
        self.licenses: List[str] = []  # Known licenses
        self.metadata: Dict[str, Any] = {}  # Additional metadata
    
    def __str__(self) -> str:
        return f"{self.name}@{self.version} ({self.ecosystem})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, DependencyInfo):
            return False
        return (self.name == other.name and 
                self.version == other.version and 
                self.ecosystem == other.ecosystem)
    
    def __hash__(self) -> int:
        return hash((self.name, self.version, self.ecosystem))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem,
            "is_direct": self.is_direct,
            "path": self.path,
            "parent": self.parent,
            "used_features": list(self.used_features),
            "required_by": list(self.required_by),
            "licenses": self.licenses,
            "metadata": self.metadata
        }


class DependencyParser(ABC):
    """Base class for dependency parsers."""
    
    def __init__(self):
        self.ecosystem: str = "generic"
    
    @abstractmethod
    def parse_dependencies(self, project_path: str) -> List[DependencyInfo]:
        """
        Parse dependencies from a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of dependency information
        """
        pass
    
    @abstractmethod
    def parse_lock_file(self, lock_file_path: str) -> List[DependencyInfo]:
        """
        Parse dependencies from a lock file.
        
        Args:
            lock_file_path: Path to the lock file
            
        Returns:
            List of dependency information
        """
        pass
    
    @abstractmethod
    def find_dependency_files(self, project_path: str) -> List[str]:
        """
        Find all dependency definition files in a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of file paths
        """
        pass
    
    def extract_version_constraint(self, version_str: str) -> Tuple[str, str]:
        """
        Extract version and constraint type from version string.
        
        Args:
            version_str: Version string (e.g., "^1.2.3", "~2.0.0", ">=3.0.0")
            
        Returns:
            Tuple of (constraint_type, version)
        """
        # Default implementation with common patterns
        constraints = ["^", "~", ">=", "<=", ">", "<", "=="]
        
        constraint_type = "exact"
        version = version_str.strip()
        
        for constraint in constraints:
            if version.startswith(constraint):
                constraint_type = {
                    "^": "caret",
                    "~": "tilde",
                    ">=": "greater_equal",
                    ">": "greater",
                    "<=": "less_equal",
                    "<": "less",
                    "==": "exact"
                }.get(constraint, "custom")
                version = version[len(constraint):].strip()
                break
                
        return constraint_type, version


class DependencyParserFactory:
    """Factory for creating dependency parsers based on ecosystem."""
    
    @staticmethod
    def create_parser(ecosystem: str) -> DependencyParser:
        """
        Create a dependency parser for the specified ecosystem.
        
        Args:
            ecosystem: Ecosystem identifier (e.g., "python", "nodejs")
            
        Returns:
            Dependency parser instance
            
        Raises:
            ValueError: If the ecosystem is not supported
        """
        from backend.analysis.python_analyzer import PythonDependencyParser
        from backend.analysis.nodejs_analyzer import NodeJSDependencyParser
        
        parsers = {
            "python": PythonDependencyParser,
            "nodejs": NodeJSDependencyParser,
        }
        
        parser_class = parsers.get(ecosystem.lower())
        if not parser_class:
            raise ValueError(f"Unsupported ecosystem: {ecosystem}")
        
        return parser_class()


def parse_project_dependencies(
    project_path: str, 
    ecosystem: Optional[str] = None
) -> Dict[str, List[DependencyInfo]]:
    """
    Parse dependencies from a project using the appropriate parser.
    
    Args:
        project_path: Path to the project root
        ecosystem: Optional ecosystem identifier. If not provided, auto-detection is attempted.
        
    Returns:
        Dictionary mapping ecosystem to list of dependencies
    """
    result: Dict[str, List[DependencyInfo]] = {}
    
    # Auto-detect ecosystems if not specified
    if not ecosystem:
        ecosystems = detect_project_ecosystems(project_path)
    else:
        ecosystems = [ecosystem]
    
    for eco in ecosystems:
        try:
            parser = DependencyParserFactory.create_parser(eco)
            dependencies = parser.parse_dependencies(project_path)
            result[eco] = dependencies
            logger.info(f"Parsed {len(dependencies)} dependencies for {eco}")
        except Exception as e:
            logger.error(f"Error parsing {eco} dependencies: {str(e)}")
            result[eco] = []
    
    return result


def detect_project_ecosystems(project_path: str) -> List[str]:
    """
    Detect ecosystems used in a project.
    
    Args:
        project_path: Path to the project root
        
    Returns:
        List of detected ecosystems
    """
    ecosystems = []
    
    # Python detection
    python_files = [
        "requirements.txt",
        "setup.py",
        "Pipfile",
        "pyproject.toml",
        "poetry.lock"
    ]
    for file in python_files:
        if os.path.exists(os.path.join(project_path, file)):
            ecosystems.append("python")
            break
    
    # Node.js detection
    nodejs_files = [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "npm-shrinkwrap.json"
    ]
    for file in nodejs_files:
        if os.path.exists(os.path.join(project_path, file)):
            ecosystems.append("nodejs")
            break
    
    return ecosystems


def merge_dependency_info(
    dependencies: List[DependencyInfo]
) -> List[DependencyInfo]:
    """
    Merge duplicate dependencies, combining their metadata.
    
    Args:
        dependencies: List of dependency information
        
    Returns:
        Deduplicated list of dependency information
    """
    result_dict: Dict[Tuple[str, str, str], DependencyInfo] = {}
    
    for dep in dependencies:
        key = (dep.name, dep.version, dep.ecosystem)
        if key in result_dict:
            # Merge with existing entry
            existing = result_dict[key]
            existing.used_features.update(dep.used_features)
            existing.required_by.update(dep.required_by)
            
            # Combine licenses
            for license_id in dep.licenses:
                if license_id not in existing.licenses:
                    existing.licenses.append(license_id)
            
            # Update to direct if any occurrence is direct
            if dep.is_direct:
                existing.is_direct = True
                
            # Merge metadata
            existing.metadata.update(dep.metadata)
        else:
            # Add new entry
            result_dict[key] = dep
    
    return list(result_dict.values())