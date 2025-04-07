import os
import json
import re
import logging
from typing import Dict, List, Set, Optional, Any, Tuple
import subprocess

from backend.analysis.dependency_parser import DependencyParser, DependencyInfo

logger = logging.getLogger(__name__)


class NodeJSDependencyParser(DependencyParser):
    """Parser for Node.js project dependencies."""
    
    def __init__(self):
        super().__init__()
        self.ecosystem = "nodejs"
        self.direct_dependencies: Dict[str, DependencyInfo] = {}
        self.dev_dependencies: Dict[str, DependencyInfo] = {}
        self.transitive_dependencies: Dict[str, DependencyInfo] = {}
        
    def parse_dependencies(self, project_path: str) -> List[DependencyInfo]:
        """
        Parse Node.js dependencies from a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of dependency information
        """
        dependency_files = self.find_dependency_files(project_path)
        logger.info(f"Found {len(dependency_files)} Node.js dependency files")
        
        for file_path in dependency_files:
            self._parse_file(file_path, project_path)
        
        # Extract usage information by analyzing imports
        self._analyze_imports(project_path)
        
        # Combine all dependencies
        all_dependencies = list(self.direct_dependencies.values()) + list(self.dev_dependencies.values()) + list(self.transitive_dependencies.values())
        return all_dependencies
        
    def find_dependency_files(self, project_path: str) -> List[str]:
        """
        Find Node.js dependency files in a project.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            List of dependency file paths
        """
        dependency_files = []
        
        # Common Node.js dependency files
        file_patterns = [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "npm-shrinkwrap.json"
        ]
        
        for pattern in file_patterns:
            file_path = os.path.join(project_path, pattern)
            if os.path.exists(file_path):
                dependency_files.append(file_path)
        
        return dependency_files
    
    def parse_lock_file(self, lock_file_path: str) -> List[DependencyInfo]:
        """
        Parse Node.js lock files (package-lock.json, yarn.lock).
        
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
        
        if filename == "package-lock.json":
            return self._parse_package_lock(lock_file_path)
        elif filename == "yarn.lock":
            return self._parse_yarn_lock(lock_file_path)
        else:
            logger.warning(f"Unsupported lock file format: {filename}")
            
        return dependencies
    
    def _parse_file(self, file_path: str, project_path: str) -> None:
        """Parse a dependency file and update the dependency dictionaries."""
        filename = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, project_path)
        
        logger.info(f"Parsing Node.js dependency file: {rel_path}")
        
        if filename == "package.json":
            self._parse_package_json(file_path)
        elif filename == "package-lock.json":
            deps = self._parse_package_lock(file_path)
            for dep in deps:
                if dep.is_direct:
                    if dep.metadata.get("dev", False):
                        self.dev_dependencies[dep.name] = dep
                    else:
                        self.direct_dependencies[dep.name] = dep
                else:
                    self.transitive_dependencies[dep.name] = dep
        elif filename == "yarn.lock":
            deps = self._parse_yarn_lock(file_path)
            for dep in deps:
                if dep.is_direct:
                    if dep.metadata.get("dev", False):
                        self.dev_dependencies[dep.name] = dep
                    else:
                        self.direct_dependencies[dep.name] = dep
                else:
                    self.transitive_dependencies[dep.name] = dep
    
    def _parse_package_json(self, file_path: str) -> None:
        """Parse package.json file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Parse dependencies
            if "dependencies" in data:
                self._process_dep_section(data["dependencies"], file_path, False)
            
            # Parse dev dependencies
            if "devDependencies" in data:
                self._process_dep_section(data["devDependencies"], file_path, True)
                
            # Parse peer dependencies (these are typically not installed directly)
            if "peerDependencies" in data:
                self._process_dep_section(data["peerDependencies"], file_path, False, is_peer=True)
                
            # Parse optional dependencies
            if "optionalDependencies" in data:
                self._process_dep_section(data["optionalDependencies"], file_path, False, is_optional=True)
                
        except Exception as e:
            logger.error(f"Error parsing package.json: {str(e)}")
    
    def _process_dep_section(
        self, 
        deps: Dict[str, str], 
        file_path: str, 
        is_dev: bool = False,
        is_peer: bool = False,
        is_optional: bool = False
    ) -> None:
        """Process a dependency section from package.json."""
        for name, version_spec in deps.items():
            # Clean version spec
            constraint_type, version = self.extract_version_constraint(version_spec)
            
            dep_info = DependencyInfo(
                name=name,
                version=version,
                ecosystem=self.ecosystem,
                is_direct=True,
                path=file_path
            )
            
            # Add metadata
            dep_info.metadata["constraint_type"] = constraint_type
            
            if is_dev:
                dep_info.metadata["dev"] = True
                self.dev_dependencies[name] = dep_info
            elif is_peer:
                dep_info.metadata["peer"] = True
                # Peer dependencies aren't necessarily installed
                self.transitive_dependencies[name] = dep_info
            elif is_optional:
                dep_info.metadata["optional"] = True
                self.direct_dependencies[name] = dep_info
            else:
                self.direct_dependencies[name] = dep_info
    
    def _parse_package_lock(self, file_path: str) -> List[DependencyInfo]:
        """Parse package-lock.json file."""
        dependencies = []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check lockfile version
            lockfile_version = data.get("lockfileVersion", 1)
            
            # Handle different package-lock.json versions
            if lockfile_version >= 2:
                # For v2+, use the packages section
                if "packages" in data:
                    for path, pkg_info in data["packages"].items():
                        # Skip the root package
                        if path == "":
                            continue
                            
                        # Extract the package name
                        if path.startswith("node_modules/"):
                            path_parts = path.split("/")
                            if len(path_parts) >= 2:
                                name = path_parts[1]
                                # Handle scoped packages
                                if name.startswith("@") and len(path_parts) >= 3:
                                    name = f"{name}/{path_parts[2]}"
                        else:
                            # Use the name property if present
                            name = pkg_info.get("name", path.split("/")[-1])
                        
                        version = pkg_info.get("version", "latest")
                        
                        # Determine if it's a direct dependency
                        is_direct = False
                        is_dev = pkg_info.get("dev", False)
                        
                        # Check if it's a top-level dependency
                        if path.count("/") == 1 or (path.startswith("node_modules/@") and path.count("/") == 2):
                            is_direct = True
                        
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=is_direct,
                            path=file_path
                        )
                        
                        if is_dev:
                            dep_info.metadata["dev"] = True
                            
                        # Get dependencies
                        if "dependencies" in pkg_info:
                            for dep_name in pkg_info["dependencies"]:
                                dep_info.required_by.add(dep_name)
                                
                        dependencies.append(dep_info)
            else:
                # For v1, use the dependencies section
                if "dependencies" in data:
                    for name, pkg_info in data["dependencies"].items():
                        version = pkg_info.get("version", "latest")
                        
                        # Check if this is a direct dependency
                        is_direct = pkg_info.get("requires", False) or name in data.get("dependencies", {})
                        is_dev = pkg_info.get("dev", False)
                        
                        dep_info = DependencyInfo(
                            name=name,
                            version=version,
                            ecosystem=self.ecosystem,
                            is_direct=is_direct,
                            path=file_path
                        )
                        
                        if is_dev:
                            dep_info.metadata["dev"] = True
                            
                        # Get dependencies
                        if "requires" in pkg_info:
                            for dep_name in pkg_info["requires"]:
                                dep_info.required_by.add(dep_name)
                                
                        dependencies.append(dep_info)
                        
                        # Recursively process nested dependencies
                        if "dependencies" in pkg_info:
                            for sub_name, sub_pkg in pkg_info["dependencies"].items():
                                sub_version = sub_pkg.get("version", "latest")
                                
                                sub_dep = DependencyInfo(
                                    name=sub_name,
                                    version=sub_version,
                                    ecosystem=self.ecosystem,
                                    is_direct=False,
                                    path=file_path,
                                    parent=name
                                )
                                
                                if is_dev:
                                    sub_dep.metadata["dev"] = True
                                    
                                dependencies.append(sub_dep)
            
        except Exception as e:
            logger.error(f"Error parsing package-lock.json: {str(e)}")
            
        return dependencies
    
    def _parse_yarn_lock(self, file_path: str) -> List[DependencyInfo]:
        """Parse yarn.lock file."""
        dependencies = []
        
        try:
            # Yarn.lock uses a custom format, we'll parse it line by line
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Naive parsing of yarn.lock entries
            # This is a simplified approach and may not handle all edge cases
            entry_pattern = r'"([^"]+)":\n\s+version\s+"([^"]+)"'
            entries = re.findall(entry_pattern, content)
            
            for spec, version in entries:
                # Extract name and version constraint from spec
                name = spec.split('@')[0] if '@' in spec else spec
                
                # Skip empty names (happens with namespaced packages)
                if name == "":
                    name_parts = spec.split('@')
                    if len(name_parts) >= 3:
                        name = '@' + name_parts[1]
                
                # Create dependency info
                dep_info = DependencyInfo(
                    name=name,
                    version=version,
                    ecosystem=self.ecosystem,
                    is_direct=False,  # We can't tell directly from yarn.lock
                    path=file_path
                )
                
                # Check if it's a direct dependency by comparing with package.json
                if name in self.direct_dependencies:
                    dep_info.is_direct = True
                elif name in self.dev_dependencies:
                    dep_info.is_direct = True
                    dep_info.metadata["dev"] = True
                
                dependencies.append(dep_info)
            
        except Exception as e:
            logger.error(f"Error parsing yarn.lock: {str(e)}")
            
        return dependencies
    
    def _analyze_imports(self, project_path: str) -> None:
        """
        Analyze JavaScript/TypeScript files to find import/require statements.
        This helps determine which features of dependencies are actually used.
        """
        try:
            # Walk through JS/TS files
            for root, _, files in os.walk(project_path):
                for file in files:
                    if file.endswith(('.js', '.jsx', '.ts', '.tsx')):
                        file_path = os.path.join(root, file)
                        self._analyze_file_imports(file_path)
                        
        except Exception as e:
            logger.error(f"Error analyzing imports: {str(e)}")
    
    def _analyze_file_imports(self, file_path: str) -> None:
        """Analyze import statements in a JavaScript/TypeScript file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Look for ES6 imports
            import_pattern = r'import\s+(?:{[^}]*}|\*\s+as\s+[^,]+|[^,{]*)\s+from\s+[\'"]([^\'"]+)[\'"]'
            for match in re.finditer(import_pattern, content):
                module = match.group(1)
                self._map_import_to_dependency(module, file_path)
            
            # Look for require statements
            require_pattern = r'(?:const|let|var)\s+(?:{[^}]*}|[^,{]*)\s*=\s*require\s*\([\'"]([^\'"]+)[\'"]\)'
            for match in re.finditer(require_pattern, content):
                module = match.group(1)
                self._map_import_to_dependency(module, file_path)
                
            # Look for dynamic imports
            dynamic_import_pattern = r'import\s*\([\'"]([^\'"]+)[\'"]\)'
            for match in re.finditer(dynamic_import_pattern, content):
                module = match.group(1)
                self._map_import_to_dependency(module, file_path)
                
        except Exception as e:
            logger.debug(f"Error analyzing imports in {file_path}: {str(e)}")
    
    def _map_import_to_dependency(self, module: str, file_path: str) -> None:
        """Map an import statement to a dependency."""
        # Skip relative imports and built-in modules
        if module.startswith('.') or module.startswith('/'):
            return
            
        # Handle namespaced packages
        if module.startswith('@'):
            parts = module.split('/')
            if len(parts) >= 2:
                package_name = f"{parts[0]}/{parts[1]}"
                submodule = '/'.join(parts[2:]) if len(parts) > 2 else ''
            else:
                return
        else:
            # Extract the package name
            parts = module.split('/')
            package_name = parts[0]
            submodule = '/'.join(parts[1:]) if len(parts) > 1 else ''
            
        # Look in direct dependencies
        if package_name in self.direct_dependencies:
            dep = self.direct_dependencies[package_name]
            if submodule:
                feature = f"{package_name}/{submodule}"
                dep.used_features.add(feature)
            else:
                dep.used_features.add(package_name)
        
        # Look in dev dependencies
        elif package_name in self.dev_dependencies:
            dep = self.dev_dependencies[package_name]
            if submodule:
                feature = f"{package_name}/{submodule}"
                dep.used_features.add(feature)
            else:
                dep.used_features.add(package_name)
        
        # Look in transitive dependencies
        elif package_name in self.transitive_dependencies:
            dep = self.transitive_dependencies[package_name]
            if submodule:
                feature = f"{package_name}/{submodule}"
                dep.used_features.add(feature)
            else:
                dep.used_features.add(package_name)
        
        # If not found, it might be a built-in module or not installed
        else:
            logger.debug(f"Dependency not found for import: {module} in {file_path}")