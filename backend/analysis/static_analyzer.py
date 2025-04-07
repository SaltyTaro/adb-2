import os
import re
import ast
import logging
from typing import Dict, List, Set, Optional, Any, Tuple, Union

from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class StaticAnalyzer:
    """
    Static code analyzer for extracting dependency usage information.
    
    Analyzes source code to determine:
    1. Which dependencies are actually used in the code
    2. Which specific features of dependencies are used
    3. Dependency import patterns and frequency
    """
    
    def __init__(self, project_path: str, ecosystem: str = "auto"):
        """
        Initialize the static analyzer.
        
        Args:
            project_path: Path to the project to analyze
            ecosystem: Ecosystem to analyze ("python", "nodejs", or "auto" for detection)
        """
        self.project_path = project_path
        self.ecosystem = ecosystem
        self.import_stats: Dict[str, Any] = {}
        self.feature_usage: Dict[str, Set[str]] = {}
        self.file_count: Dict[str, int] = {
            "python": 0,
            "javascript": 0,
            "typescript": 0,
            "html": 0,
            "css": 0,
            "json": 0,
            "other": 0
        }
    
    def analyze_project(self) -> Dict[str, Any]:
        """
        Analyze the entire project for dependency usage.
        
        Returns:
            Analysis results including import stats and feature usage
        """
        logger.info(f"Starting static analysis for project: {self.project_path}")
        
        # Auto-detect ecosystem if not specified
        if self.ecosystem == "auto":
            self.ecosystem = self._detect_ecosystem()
            logger.info(f"Detected ecosystem: {self.ecosystem}")
        
        # Analyze files based on ecosystem
        if self.ecosystem == "python":
            self._analyze_python_project()
        elif self.ecosystem == "nodejs":
            self._analyze_nodejs_project()
        else:
            # If ecosystem is unknown, try both
            self._analyze_python_project()
            self._analyze_nodejs_project()
        
        # Prepare results
        results = {
            "ecosystem": self.ecosystem,
            "file_count": self.file_count,
            "import_stats": self.import_stats,
            "feature_usage": {k: list(v) for k, v in self.feature_usage.items()},
            "dependency_count": len(self.import_stats),
            "total_files_analyzed": sum(self.file_count.values())
        }
        
        logger.info(f"Completed static analysis. Found {results['dependency_count']} dependencies.")
        return results
    
    def _detect_ecosystem(self) -> str:
        """
        Auto-detect the project ecosystem based on files present.
        
        Returns:
            Detected ecosystem ("python", "nodejs", or "unknown")
        """
        # Check for Python specific files
        python_indicators = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile",
            "poetry.lock"
        ]
        
        # Check for Node.js specific files
        nodejs_indicators = [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "node_modules",
            "tsconfig.json"
        ]
        
        python_score = 0
        nodejs_score = 0
        
        # Check for ecosystem specific files
        for indicator in python_indicators:
            if os.path.exists(os.path.join(self.project_path, indicator)):
                python_score += 2
        
        for indicator in nodejs_indicators:
            if os.path.exists(os.path.join(self.project_path, indicator)):
                nodejs_score += 2
        
        # Count file extensions as additional signals
        for root, _, files in os.walk(self.project_path):
            # Skip node_modules and virtual environments
            if any(exclude in root for exclude in ["node_modules", "venv", "__pycache__", ".git"]):
                continue
                
            for file in files:
                if file.endswith(".py"):
                    python_score += 1
                elif file.endswith((".js", ".jsx", ".ts", ".tsx")):
                    nodejs_score += 1
        
        # Determine ecosystem based on scores
        if python_score > nodejs_score:
            return "python"
        elif nodejs_score > python_score:
            return "nodejs"
        else:
            return "unknown"
    
    def _analyze_python_project(self) -> None:
        """Analyze Python project files for dependency usage."""
        logger.info("Analyzing Python files")
        
        # Walk through project files
        for root, _, files in os.walk(self.project_path):
            # Skip virtual environments and cache directories
            if any(exclude in root for exclude in ["venv", "env", "__pycache__", ".git", ".tox"]):
                continue
                
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    self._analyze_python_file(file_path)
                    self.file_count["python"] += 1
    
    def _analyze_nodejs_project(self) -> None:
        """Analyze Node.js project files for dependency usage."""
        logger.info("Analyzing JavaScript/TypeScript files")
        
        # Walk through project files
        for root, _, files in os.walk(self.project_path):
            # Skip node_modules and other excluded directories
            if any(exclude in root for exclude in ["node_modules", ".git", "dist", "build"]):
                continue
                
            for file in files:
                if file.endswith((".js", ".jsx")):
                    file_path = os.path.join(root, file)
                    self._analyze_javascript_file(file_path)
                    self.file_count["javascript"] += 1
                elif file.endswith((".ts", ".tsx")):
                    file_path = os.path.join(root, file)
                    self._analyze_typescript_file(file_path)
                    self.file_count["typescript"] += 1
                elif file.endswith(".json"):
                    self.file_count["json"] += 1
                elif file.endswith((".html", ".htm")):
                    self.file_count["html"] += 1
                elif file.endswith((".css", ".scss", ".sass", ".less")):
                    self.file_count["css"] += 1
                else:
                    self.file_count["other"] += 1
    
    def _analyze_python_file(self, file_path: str) -> None:
        """
        Analyze a Python file for imports and dependency usage.
        
        Args:
            file_path: Path to the Python file
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse Python file
            try:
                tree = ast.parse(content)
                
                # Find all imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            module_name = name.name.split('.')[0]
                            self._record_python_import(module_name, name.name)
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split('.')[0]
                            self._record_python_import(module_name, node.module)
                            
                            # Record features (imported names)
                            for name in node.names:
                                full_name = f"{node.module}.{name.name}"
                                if module_name not in self.feature_usage:
                                    self.feature_usage[module_name] = set()
                                self.feature_usage[module_name].add(full_name)
            except SyntaxError:
                logger.debug(f"Syntax error in Python file: {file_path}")
        
        except Exception as e:
            logger.debug(f"Error analyzing file {file_path}: {str(e)}")
    
    def _analyze_javascript_file(self, file_path: str) -> None:
        """
        Analyze a JavaScript file for imports and dependency usage.
        
        Args:
            file_path: Path to the JavaScript file
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find ES6 imports
            es6_pattern = r'import\s+(?:{[^}]*}|\*\s+as\s+[^,]+|[^,{]*)\s+from\s+[\'"]([^\'"]+)[\'"]'
            for match in re.finditer(es6_pattern, content):
                module = match.group(1)
                self._record_js_import(module)
            
            # Find require statements
            require_pattern = r'(?:const|let|var)\s+(?:{[^}]*}|[^,{]*)\s*=\s*require\s*\([\'"]([^\'"]+)[\'"]\)'
            for match in re.finditer(require_pattern, content):
                module = match.group(1)
                self._record_js_import(module)
            
            # Find dynamic imports
            dynamic_pattern = r'import\s*\([\'"]([^\'"]+)[\'"]\)'
            for match in re.finditer(dynamic_pattern, content):
                module = match.group(1)
                self._record_js_import(module)
                
        except Exception as e:
            logger.debug(f"Error analyzing file {file_path}: {str(e)}")
    
    def _analyze_typescript_file(self, file_path: str) -> None:
        """
        Analyze a TypeScript file for imports and dependency usage.
        
        Args:
            file_path: Path to the TypeScript file
        """
        # TypeScript uses the same import syntax as JavaScript
        self._analyze_javascript_file(file_path)
    
    def _record_python_import(self, module_name: str, full_name: str) -> None:
        """
        Record a Python import in the stats.
        
        Args:
            module_name: Top-level module name
            full_name: Full import path
        """
        # Skip standard library modules
        std_lib_modules = {
            "os", "sys", "datetime", "collections", "json", "re", "math",
            "random", "time", "logging", "argparse", "unittest", "typing",
            "pathlib", "hashlib", "uuid", "csv", "shutil", "tempfile"
        }
        
        if module_name in std_lib_modules:
            return
        
        # Record import stats
        if module_name not in self.import_stats:
            self.import_stats[module_name] = {
                "count": 0,
                "ecosystem": "python",
                "imports": []
            }
        
        self.import_stats[module_name]["count"] += 1
        self.import_stats[module_name]["imports"].append(full_name)
        
        # Initialize feature usage if needed
        if module_name not in self.feature_usage:
            self.feature_usage[module_name] = set()
    
    def _record_js_import(self, module: str) -> None:
        """
        Record a JavaScript import in the stats.
        
        Args:
            module: Module path
        """
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
        
        # Record import stats
        if package_name not in self.import_stats:
            self.import_stats[package_name] = {
                "count": 0,
                "ecosystem": "nodejs",
                "imports": []
            }
        
        self.import_stats[package_name]["count"] += 1
        self.import_stats[package_name]["imports"].append(module)
        
        # Record feature usage
        if package_name not in self.feature_usage:
            self.feature_usage[package_name] = set()
        
        if submodule:
            self.feature_usage[package_name].add(f"{package_name}/{submodule}")
        else:
            self.feature_usage[package_name].add(package_name)


def analyze_project_dependencies(
    project_path: str, 
    ecosystem: str = "auto"
) -> Dict[str, Any]:
    """
    Analyze a project for dependency usage.
    
    Args:
        project_path: Path to the project
        ecosystem: Target ecosystem or "auto" for detection
        
    Returns:
        Analysis results
    """
    analyzer = StaticAnalyzer(project_path, ecosystem)
    return analyzer.analyze_project()