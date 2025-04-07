import os
import re
import ast
import logging
import subprocess
from typing import Dict, List, Set, Optional, Any, Tuple, Union
import importlib.metadata
import pkg_resources
import toml
import json

from backend.analysis.dependency_parser import DependencyParser, DependencyInfo

logger = logging.getLogger(__name__)


class PythonDependencyParser(DependencyParser):
    """Parser for Python project dependencies."""
    
    def __init__(self):
        super().__init__()
        self.ecosystem = "python"
        self.direct_dependencies: Dict[str, DependencyInfo] = {}
        self.transitive_dependencies: Dict[str, DependencyInfo] = {}
        
    def parse_dependencies(self, project_path: str) -> List[DependencyInfo]:
        """
        Parse Python dependencies from a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of dependency information
        """
        dependency_files = self.find_dependency_files(project_path)
        logger.info(f"Found {len(dependency_files)} Python dependency files")
        
        for file_path in dependency_files:
            self._parse_file(file_path, project_path)
        
        # Get transitive dependencies using pip or poetry
        self._get_transitive_dependencies(project_path)
        
        # Extract usage information by analyzing imports
        self._analyze_imports(project_path)
        
        # Combine direct and transitive dependencies
        all_dependencies = list(self.direct_dependencies.values()) + list(self.transitive_dependencies.values())
        return all_dependencies
        
    def find_dependency_files(self, project_path: str) -> List[str]:
        """
        Find Python dependency files in a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of dependency file paths
        """
        dependency_files = []
        
        # Common Python dependency files
        file_patterns = [
            "requirements.txt",
            "requirements/*.txt",
            "setup.py",
            "Pipfile",
            "Pipfile.lock",
            "pyproject.toml",
            "poetry.lock"
        ]
        
        for pattern in file_patterns:
            if "*" in pattern:
                # Handle wildcard patterns
                base_dir = os.path.join(project_path, os.path.dirname(pattern))
                if os.path.exists(base_dir):
                    file_pattern = os.path.basename(pattern)
                    for file in os.listdir(base_dir):
                        if self._match_pattern(file, file_pattern):
                            dependency_files.append(os.path.join(base_dir, file))
            else:
                # Direct file path
                file_path = os.path.join(project_path, pattern)
                if os.path.exists(file_path):
                    dependency_files.append(file_path)
        
        return dependency_files
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """Check if a filename matches a simple wildcard pattern."""
        if pattern == "*.txt":
            return filename.endswith(".txt")
        return filename == pattern
    
    def parse_lock_file(self, lock_file_path: str) -> List[DependencyInfo]:
        """
        Parse Python lock files (poetry.lock, Pipfile.lock).
        
        Args:
            lock_file_path: Path to the lock file
            
        Returns:
            List of dependency information
        """
        dependencies = []
        
        if not os.path.exists(lock_file_path):
            logger.warning(f"Lock file not found: {lock_file_path}")
            return dependencies
        
        filename = os.path.basename(lock_file_path)
        
        if filename == "poetry.lock":
            return self._parse_poetry_lock(lock_file_path)
        elif filename == "Pipfile.lock":
            return self._parse_pipfile_lock(lock_file_path)
        else:
            logger.warning(f"Unsupported lock file format: {filename}")
            
        return dependencies
    
    def _parse_file(self, file_path: str, project_path: str) -> None:
        """Parse a dependency file and update the dependency dictionaries."""
        filename = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, project_path)
        
        logger.info(f"Parsing Python dependency file: {rel_path}")
        
        if filename == "requirements.txt":
            self._parse_requirements_txt(file_path)
        elif filename == "setup.py":
            self._parse_setup_py(file_path)
        elif filename == "Pipfile":
            self._parse_pipfile(file_path)
        elif filename == "Pipfile.lock":
            deps = self._parse_pipfile_lock(file_path)
            for dep in deps:
                if dep.is_direct:
                    self.direct_dependencies[dep.name] = dep
                else:
                    self.transitive_dependencies[dep.name] = dep
        elif filename == "pyproject.toml":
            self._parse_pyproject_toml(file_path)
        elif filename == "poetry.lock":
            deps = self._parse_poetry_lock(file_path)
            for dep in deps:
                if dep.is_direct:
                    self.direct_dependencies[dep.name] = dep
                else:
                    self.transitive_dependencies[dep.name] = dep
    
    def _parse_requirements_txt(self, file_path: str) -> None:
        """Parse requirements.txt file."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                    
                # Skip editable installs and file references
                if line.startswith('-e') or line.startswith('-r') or line.startswith('--'):
                    continue
                
                # Handle URLs
                if line.startswith(('http://', 'https://', 'git+')):
                    continue
                
                # Extract name and version
                parts = re.split(r'[=<>~!]', line, 1)
                name = parts[0].strip()
                version = parts[1].strip() if len(parts) > 1 else "latest"
                
                # Clean up version constraints
                version = re.split(r'[,;]', version, 1)[0].strip()
                
                # Create dependency info
                dep_info = DependencyInfo(
                    name=name,
                    version=version,
                    ecosystem=self.ecosystem,
                    is_direct=True,
                    path=file_path
                )
                
                self.direct_dependencies[name] = dep_info
                
        except Exception as e:
            logger.error(f"Error parsing requirements.txt: {str(e)}")
    
    def _parse_setup_py(self, file_path: str) -> None:
        """Parse setup.py file using AST."""
        try:
            with open(file_path, 'r') as f:
                setup_content = f.read()
            
            tree = ast.parse(setup_content)
            
            # Find setup() function call
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and hasattr(node, 'func'):
                    func_name = None
                    
                    # Get function name
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    if func_name == 'setup':
                        # Extract install_requires and extras_require
                        for kw in node.keywords:
                            if kw.arg == 'install_requires' and isinstance(kw.value, (ast.List, ast.Tuple)):
                                for elt in kw.value.elts:
                                    if isinstance(elt, ast.Str):
                                        req = elt.s
                                        parts = re.split(r'[=<>~!]', req, 1)
                                        name = parts[0].strip()
                                        version = "latest"
                                        if len(parts) > 1:
                                            version = re.split(r'[,;]', parts[1], 1)[0].strip()
                                            
                                        dep_info = DependencyInfo(
                                            name=name,
                                            version=version,
                                            ecosystem=self.ecosystem,
                                            is_direct=True,
                                            path=file_path
                                        )
                                        
                                        self.direct_dependencies[name] = dep_info
                            
                            elif kw.arg == 'extras_require' and isinstance(kw.value, ast.Dict):
                                for i, key in enumerate(kw.value.keys):
                                    if isinstance(key, ast.Str) and isinstance(kw.value.values[i], (ast.List, ast.Tuple)):
                                        for elt in kw.value.values[i].elts:
                                            if isinstance(elt, ast.Str):
                                                req = elt.s
                                                parts = re.split(r'[=<>~!]', req, 1)
                                                name = parts[0].strip()
                                                version = "latest"
                                                if len(parts) > 1:
                                                    version = re.split(r'[,;]', parts[1], 1)[0].strip()
                                                
                                                # Extras are optional, not direct dependencies
                                                dep_info = DependencyInfo(
                                                    name=name,
                                                    version=version,
                                                    ecosystem=self.ecosystem,
                                                    is_direct=False,
                                                    path=file_path
                                                )
                                                dep_info.metadata["extra"] = key.s
                                                
                                                self.transitive_dependencies[name] = dep_info
            
        except Exception as e:
            logger.error(f"Error parsing setup.py: {str(e)}")
    
    def _parse_pipfile(self, file_path: str) -> None:
        """Parse Pipfile for direct dependencies."""
        try:
            import toml
            with open(file_path, 'r') as f:
                data = toml.load(f)
            
            sections = ["packages", "dev-packages"]
            
            for section in sections:
                if section in data:
                    for name, version_spec in data[section].items():
                        is_dev = section == "dev-packages"
                        
                        if isinstance(version_spec, str):
                            version = version_spec.replace("==", "")
                        elif isinstance(version_spec, dict) and "version" in version_spec:
                            version = version_spec["version"].replace("==", "")
                        else:
                            version = "latest"
                        
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=True,
                            path=file_path
                        )
                        
                        if is_dev:
                            dep_info.metadata["dev"] = True
                            
                        self.direct_dependencies[name] = dep_info
                        
        except Exception as e:
            logger.error(f"Error parsing Pipfile: {str(e)}")
    
    def _parse_pipfile_lock(self, file_path: str) -> List[DependencyInfo]:
        """Parse Pipfile.lock for dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            sections = ["default", "develop"]
            
            for section in sections:
                is_dev = section == "develop"
                
                if section in data:
                    # Direct dependencies first
                    for name, pkg_info in data[section].items():
                        version = pkg_info.get("version", "latest")
                        if version.startswith("=="):
                            version = version[2:]
                            
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=True,
                            path=file_path
                        )
                        
                        if is_dev:
                            dep_info.metadata["dev"] = True
                            
                        # Extract dependencies of this package
                        if "dependencies" in pkg_info:
                            for dep_name, dep_version in pkg_info["dependencies"].items():
                                dep_info.required_by.add(dep_name)
                                
                                # Add indirect dependency
                                indirect_dep = DependencyInfo(
                                    name=dep_name,
                                    version=dep_version.replace("==", "") if isinstance(dep_version, str) else "latest",
                                    ecosystem=self.ecosystem,
                                    is_direct=False,
                                    path=file_path,
                                    parent=name
                                )
                                
                                if is_dev:
                                    indirect_dep.metadata["dev"] = True
                                    
                                dependencies.append(indirect_dep)
                                
                        dependencies.append(dep_info)
            
        except Exception as e:
            logger.error(f"Error parsing Pipfile.lock: {str(e)}")
            
        return dependencies
    
    def _parse_pyproject_toml(self, file_path: str) -> None:
        """Parse pyproject.toml file for dependencies."""
        try:
            with open(file_path, 'r') as f:
                data = toml.load(f)
            
            # Poetry dependencies
            if "tool" in data and "poetry" in data["tool"]:
                poetry_data = data["tool"]["poetry"]
                
                # Main dependencies
                if "dependencies" in poetry_data:
                    for name, version_spec in poetry_data["dependencies"].items():
                        # Skip python itself
                        if name == "python":
                            continue
                            
                        if isinstance(version_spec, str):
                            version = version_spec
                        elif isinstance(version_spec, dict) and "version" in version_spec:
                            version = version_spec["version"]
                        else:
                            version = "latest"
                        
                        # Clean version constraint
                        if version.startswith(("^", "~", ">=", "==")):
                            version = version[1:] if version[0] in ["^", "~"] else version[2:]
                        
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=True,
                            path=file_path
                        )
                        
                        self.direct_dependencies[name] = dep_info
                
                # Dev dependencies
                if "dev-dependencies" in poetry_data:
                    for name, version_spec in poetry_data["dev-dependencies"].items():
                        if isinstance(version_spec, str):
                            version = version_spec
                        elif isinstance(version_spec, dict) and "version" in version_spec:
                            version = version_spec["version"]
                        else:
                            version = "latest"
                        
                        # Clean version constraint
                        if version.startswith(("^", "~", ">=", "==")):
                            version = version[1:] if version[0] in ["^", "~"] else version[2:]
                        
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=True,
                            path=file_path
                        )
                        
                        dep_info.metadata["dev"] = True
                        self.direct_dependencies[name] = dep_info
            
            # PEP 621 dependencies
            elif "project" in data and "dependencies" in data["project"]:
                for dep_spec in data["project"]["dependencies"]:
                    parts = re.split(r'[=<>~!]', dep_spec, 1)
                    name = parts[0].strip()
                    version = "latest"
                    
                    if len(parts) > 1:
                        version = re.split(r'[,;]', parts[1], 1)[0].strip()
                    
                    dep_info = DependencyInfo(
                        name=name,
                        version=version,
                        ecosystem=self.ecosystem,
                        is_direct=True,
                        path=file_path
                    )
                    
                    self.direct_dependencies[name] = dep_info
                    
        except Exception as e:
            logger.error(f"Error parsing pyproject.toml: {str(e)}")
    
    def _parse_poetry_lock(self, file_path: str) -> List[DependencyInfo]:
        """Parse poetry.lock file for dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r') as f:
                data = toml.load(f)
            
            if "package" in data:
                # Map for package dependencies
                dep_map = {}
                
                # First pass to collect dependencies
                for package in data["package"]:
                    name = package["name"]
                    version = package.get("version", "latest")
                    
                    is_direct = "category" in package and package["category"] == "main"
                    is_dev = "category" in package and package["category"] == "dev"
                    
                    dep_info = DependencyInfo(
                        name=name,
                        version=version,
                        ecosystem=self.ecosystem,
                        is_direct=is_direct,
                        path=file_path
                    )
                    
                    if is_dev:
                        dep_info.metadata["dev"] = True
                    
                    # Store in map for relationship building
                    dep_map[name] = dep_info
                    
                    # Store dependencies of this package
                    if "dependencies" in package:
                        for dep_name, dep_version in package["dependencies"].items():
                            if dep_name != "python":
                                dep_info.required_by.add(dep_name)
                    
                    dependencies.append(dep_info)
                
                # Second pass to add parent relationships
                for dep in dependencies:
                    for req_by in list(dep.required_by):
                        if req_by in dep_map:
                            parent_dep = dep_map[req_by]
                            if not dep.parent:
                                dep.parent = parent_dep.name
            
        except Exception as e:
            logger.error(f"Error parsing poetry.lock: {str(e)}")
            
        return dependencies
    
    def _get_transitive_dependencies(self, project_path: str) -> None:
        """
        Get transitive dependencies using pip or poetry.
        Note: This may require running in a virtualenv with the project installed.
        """
        # If we already have transitive dependencies from lock files, skip
        if self.transitive_dependencies:
            return
            
        try:
            # Try to get direct dependencies' dependencies using pkg_resources
            for name, dep_info in self.direct_dependencies.items():
                try:
                    dist = pkg_resources.get_distribution(name)
                    
                    for req in dist.requires():
                        req_name = req.project_name
                        req_specs = req.specs
                        
                        version = "latest"
                        if req_specs:
                            # Get first version spec
                            op, ver = req_specs[0]
                            version = ver
                        
                        if req_name not in self.direct_dependencies:
                            trans_dep = DependencyInfo(
                                name=req_name,
                                version=version,
                                ecosystem=self.ecosystem,
                                is_direct=False,
                                parent=name
                            )
                            
                            self.transitive_dependencies[req_name] = trans_dep
                            
                except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting transitive dependencies: {str(e)}")
    
    def _analyze_imports(self, project_path: str) -> None:
        """
        Analyze Python files to find import statements and map to dependencies.
        This helps determine which features of dependencies are actually used.
        """
        try:
            # Walk through Python files
            for root, _, files in os.walk(project_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        self._analyze_file_imports(file_path)
                        
        except Exception as e:
            logger.error(f"Error analyzing imports: {str(e)}")
    
    def _analyze_file_imports(self, file_path: str) -> None:
        """Analyze import statements in a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            try:
                tree = ast.parse(content)
                
                # Find all import statements
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            self._map_import_to_dependency(name.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            # Get top-level module
                            top_module = node.module.split('.')[0]
                            self._map_import_to_dependency(top_module)
                            
                            # Also record the specific import
                            full_import = f"{node.module}"
                            self._map_import_to_dependency(full_import)
                            
                            # Record imported names as used features
                            for name in node.names:
                                feature = f"{node.module}.{name.name}"
                                self._record_used_feature(node.module.split('.')[0], feature)
            except SyntaxError:
                # Skip files with syntax errors
                pass
                
        except Exception as e:
            logger.debug(f"Error analyzing imports in {file_path}: {str(e)}")
    
    def _map_import_to_dependency(self, import_name: str) -> None:
        """Map an import name to a dependency."""
        # Get top-level package name
        top_package = import_name.split('.')[0]
        
        # Check if it's a direct dependency
        if top_package in self.direct_dependencies:
            dep = self.direct_dependencies[top_package]
            dep.used_features.add(import_name)
        # Check if it's a transitive dependency
        elif top_package in self.transitive_dependencies:
            dep = self.transitive_dependencies[top_package]
            dep.used_features.add(import_name)
    
    def _record_used_feature(self, package_name: str, feature: str) -> None:
        """Record a used feature for a package."""
        if package_name in self.direct_dependencies:
            self.direct_dependencies[package_name].used_features.add(feature)
        elif package_name in self.transitive_dependencies:
            self.transitive_dependencies[package_name].used_features.add(feature)