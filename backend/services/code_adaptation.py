import logging
import os
import json
import re
import ast
import difflib
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from backend.core.models import Analysis, Project
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings
from backend.ai.code_transformer import CodeTransformer

settings = get_settings()
logger = logging.getLogger(__name__)


class CodeAdaptationService:
    """
    AI-powered code adaptation service for analyzing and transforming code
    to adapt to dependency changes.
    
    Key features:
    1. Update impact analysis - predict how dependency changes affect code
    2. Automated code transformation - generate code changes for new API versions
    3. Learning system - build knowledge from successful and failed updates
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.transformer = CodeTransformer()
        self.max_files_to_analyze = 50  # Limit for large projects
    
    async def analyze_update_impact(
        self,
        project_id: str,
        source_path: str,
        current_dependency: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "python"
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Analyze how a dependency update will impact the project code.
        
        Args:
            project_id: Project ID
            source_path: Path to project source code
            current_dependency: Dependency name
            current_version: Current version
            target_version: Target version to update to
            ecosystem: Dependency ecosystem
            
        Returns:
            Tuple of (impact summary, detailed impact by file)
        """
        logger.info(f"Analyzing update impact for {current_dependency}: {current_version} → {target_version}")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="update_impact",
            status="running",
            config={
                "dependency": current_dependency,
                "current_version": current_version,
                "target_version": target_version,
                "ecosystem": ecosystem
            }
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # 1. Find files that import the dependency
            affected_files = await self._find_affected_files(
                source_path, current_dependency, ecosystem
            )
            
            # 2. Get breaking changes between versions
            breaking_changes = await self._get_breaking_changes(
                current_dependency, current_version, target_version, ecosystem
            )
            
            # 3. Analyze impact on each file
            file_impacts = []
            
            for file_info in affected_files[:self.max_files_to_analyze]:
                impact = await self._analyze_file_impact(
                    file_info, current_dependency, breaking_changes, ecosystem
                )
                file_impacts.append(impact)
            
            # 4. Generate impact summary
            impact_summary = self._generate_impact_summary(
                file_impacts, breaking_changes, current_dependency
            )
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "impact_level": impact_summary["impact_level"],
                "affected_files_count": len(affected_files),
                "analyzed_files_count": len(file_impacts),
                "high_impact_files_count": sum(1 for f in file_impacts if f["impact_level"] == "high"),
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return impact_summary, file_impacts
            
        except Exception as e:
            logger.error(f"Error analyzing update impact: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def generate_code_changes(
        self,
        project_id: str,
        file_path: str,
        current_dependency: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "python",
        transformation_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Generate code changes to adapt to a new dependency version.
        
        Args:
            project_id: Project ID
            file_path: Path to file to transform
            current_dependency: Dependency name
            current_version: Current version
            target_version: Target version to update to
            ecosystem: Dependency ecosystem
            transformation_type: Type of transformation to apply
            
        Returns:
            Dictionary with transformation results
        """
        logger.info(f"Generating code changes for {file_path} to update {current_dependency}")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="code_transformation",
            status="running",
            config={
                "file_path": file_path,
                "dependency": current_dependency,
                "current_version": current_version,
                "target_version": target_version,
                "ecosystem": ecosystem,
                "transformation_type": transformation_type
            }
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # 1. Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                original_code = f.read()
            
            # 2. Get breaking changes between versions
            breaking_changes = await self._get_breaking_changes(
                current_dependency, current_version, target_version, ecosystem
            )
            
            # 3. Generate transformations
            transformed_code, transformation_details = await self.transformer.transform_code(
                original_code,
                current_dependency,
                breaking_changes,
                ecosystem,
                transformation_type
            )
            
            # 4. Generate diff
            diff = self._generate_diff(original_code, transformed_code, file_path)
            
            # 5. Prepare result
            result = {
                "file_path": file_path,
                "original_code": original_code,
                "transformed_code": transformed_code,
                "diff": diff,
                "transformation_details": transformation_details,
                "has_changes": original_code != transformed_code,
                "confidence": transformation_details.get("confidence", 0.5)
            }
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "has_changes": result["has_changes"],
                "confidence": result["confidence"],
                "change_count": len(transformation_details.get("changes", [])),
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating code changes: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def batch_transform_files(
        self,
        project_id: str,
        source_path: str,
        current_dependency: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "python",
        max_files: int = 10,
        only_high_impact: bool = True
    ) -> Dict[str, Any]:
        """
        Batch transform multiple files to adapt to a new dependency version.
        
        Args:
            project_id: Project ID
            source_path: Path to project source code
            current_dependency: Dependency name
            current_version: Current version
            target_version: Target version to update to
            ecosystem: Dependency ecosystem
            max_files: Maximum number of files to transform
            only_high_impact: Only transform high impact files
            
        Returns:
            Dictionary with batch transformation results
        """
        logger.info(f"Batch transforming files for {current_dependency} update")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="batch_transformation",
            status="running",
            config={
                "dependency": current_dependency,
                "current_version": current_version,
                "target_version": target_version,
                "ecosystem": ecosystem,
                "max_files": max_files,
                "only_high_impact": only_high_impact
            }
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # 1. Get impact analysis to find files to transform
            impact_summary, file_impacts = await self.analyze_update_impact(
                project_id, source_path, current_dependency, 
                current_version, target_version, ecosystem
            )
            
            # 2. Filter files based on impact and max files
            if only_high_impact:
                files_to_transform = [
                    f for f in file_impacts 
                    if f["impact_level"] in ["high", "medium"]
                ][:max_files]
            else:
                files_to_transform = file_impacts[:max_files]
            
            # 3. Transform each file
            transformation_results = []
            
            for file_info in files_to_transform:
                try:
                    file_path = file_info["file_path"]
                    result = await self.generate_code_changes(
                        project_id, file_path, current_dependency,
                        current_version, target_version, ecosystem
                    )
                    
                    # Only include key information to avoid huge response
                    transformation_results.append({
                        "file_path": file_path,
                        "has_changes": result["has_changes"],
                        "confidence": result["confidence"],
                        "diff": result["diff"] if result["has_changes"] else None,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"Error transforming {file_info['file_path']}: {str(e)}")
                    transformation_results.append({
                        "file_path": file_info["file_path"],
                        "status": "error",
                        "error": str(e)
                    })
            
            # 4. Generate summary
            batch_summary = {
                "dependency": current_dependency,
                "current_version": current_version,
                "target_version": target_version,
                "total_affected_files": len(file_impacts),
                "transformed_files_count": len(transformation_results),
                "successful_transformations": sum(1 for r in transformation_results if r["status"] == "success"),
                "files_with_changes": sum(1 for r in transformation_results if r.get("has_changes", False)),
                "average_confidence": sum(r.get("confidence", 0) for r in transformation_results if r["status"] == "success") / 
                                    max(1, sum(1 for r in transformation_results if r["status"] == "success"))
            }
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "summary": batch_summary,
                "transformed_files_count": batch_summary["transformed_files_count"],
                "successful_transformations": batch_summary["successful_transformations"],
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return {
                "summary": batch_summary,
                "transformations": transformation_results
            }
            
        except Exception as e:
            logger.error(f"Error in batch transformation: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _find_affected_files(
        self,
        source_path: str,
        dependency_name: str,
        ecosystem: str
    ) -> List[Dict[str, Any]]:
        """
        Find files that import the specified dependency.
        
        Args:
            source_path: Path to project source code
            dependency_name: Dependency name
            ecosystem: Dependency ecosystem
            
        Returns:
            List of affected files with import information
        """
        affected_files = []
        
        try:
            if ecosystem == "python":
                for root, _, files in os.walk(source_path):
                    for file in files:
                        if file.endswith(".py"):
                            file_path = os.path.join(root, file)
                            imports = await self._extract_python_imports(file_path, dependency_name)
                            
                            if imports:
                                affected_files.append({
                                    "file_path": file_path,
                                    "imports": imports,
                                    "import_count": len(imports)
                                })
            
            elif ecosystem == "nodejs":
                for root, _, files in os.walk(source_path):
                    for file in files:
                        if file.endswith((".js", ".jsx", ".ts", ".tsx")):
                            file_path = os.path.join(root, file)
                            imports = await self._extract_js_imports(file_path, dependency_name)
                            
                            if imports:
                                affected_files.append({
                                    "file_path": file_path,
                                    "imports": imports,
                                    "import_count": len(imports)
                                })
            
            # Sort by import count (most affected first)
            affected_files.sort(key=lambda x: x["import_count"], reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding affected files: {str(e)}")
        
        return affected_files
    
    async def _extract_python_imports(
        self,
        file_path: str,
        dependency_name: str
    ) -> List[Dict[str, Any]]:
        """
        Extract Python import statements for a specific dependency.
        
        Args:
            file_path: Path to Python file
            dependency_name: Dependency name
            
        Returns:
            List of import information
        """
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse the Python file
            try:
                tree = ast.parse(content)
                
                # Find all import statements
                for node in ast.walk(tree):
                    # Regular imports: import foo, import foo.bar
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            module = name.name
                            if module == dependency_name or module.startswith(f"{dependency_name}."):
                                alias = name.asname or module
                                imports.append({
                                    "type": "import",
                                    "module": module,
                                    "alias": alias,
                                    "line": node.lineno,
                                    "import_type": "module"
                                })
                    
                    # From imports: from foo import bar
                    elif isinstance(node, ast.ImportFrom):
                        if node.module == dependency_name or (node.module and node.module.startswith(f"{dependency_name}.")):
                            for name in node.names:
                                imports.append({
                                    "type": "from_import",
                                    "module": node.module,
                                    "name": name.name,
                                    "alias": name.asname or name.name,
                                    "line": node.lineno,
                                    "import_type": "symbol"
                                })
            except SyntaxError:
                # Fall back to regex for files with syntax errors
                # This won't be as accurate but can still identify imports
                import_pattern = r'^import\s+(\S+)(?:\s+as\s+(\S+))?'
                from_pattern = r'^from\s+(\S+)\s+import\s+(.+)$'
                
                for i, line in enumerate(content.splitlines(), 1):
                    # Check for regular imports
                    match = re.match(import_pattern, line)
                    if match:
                        module = match.group(1)
                        alias = match.group(2) or module
                        
                        if module == dependency_name or module.startswith(f"{dependency_name}."):
                            imports.append({
                                "type": "import",
                                "module": module,
                                "alias": alias,
                                "line": i,
                                "import_type": "module"
                            })
                    
                    # Check for from imports
                    match = re.match(from_pattern, line)
                    if match:
                        module = match.group(1)
                        imported = match.group(2)
                        
                        if module == dependency_name or module.startswith(f"{dependency_name}."):
                            # Handle multiple imports on one line
                            for part in imported.split(','):
                                name_parts = part.strip().split(' as ')
                                name = name_parts[0].strip()
                                alias = name_parts[1].strip() if len(name_parts) > 1 else name
                                
                                imports.append({
                                    "type": "from_import",
                                    "module": module,
                                    "name": name,
                                    "alias": alias,
                                    "line": i,
                                    "import_type": "symbol"
                                })
                
        except Exception as e:
            logger.error(f"Error extracting Python imports from {file_path}: {str(e)}")
        
        return imports
    
    async def _extract_js_imports(
        self,
        file_path: str,
        dependency_name: str
    ) -> List[Dict[str, Any]]:
        """
        Extract JavaScript/TypeScript import statements for a specific dependency.
        
        Args:
            file_path: Path to JS/TS file
            dependency_name: Dependency name
            
        Returns:
            List of import information
        """
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # ES6 imports: import foo from 'dependency'
            es6_pattern = r'import\s+(?:{([^}]*)}|(\*)\s+as\s+([^;]+)|([^{;]+?))\s+from\s+[\'"]([^\'"]+)[\'"]'
            
            for match in re.finditer(es6_pattern, content):
                destructured = match.group(1)  # {foo, bar}
                star = match.group(2)  # * as foo
                star_alias = match.group(3)
                default = match.group(4)  # foo
                module = match.group(5)  # 'dependency'
                
                # Check if this import is for our dependency
                if module == dependency_name or module.startswith(f"{dependency_name}/"):
                    line_number = content[:match.start()].count('\n') + 1
                    
                    if destructured:
                        # Destructured import: import {foo, bar} from 'dependency'
                        for part in destructured.split(','):
                            part = part.strip()
                            if part:
                                # Handle renamed imports: {foo as bar}
                                name_parts = part.split(' as ')
                                name = name_parts[0].strip()
                                alias = name_parts[1].strip() if len(name_parts) > 1 else name
                                
                                imports.append({
                                    "type": "es6_import",
                                    "module": module,
                                    "name": name,
                                    "alias": alias,
                                    "line": line_number,
                                    "import_type": "named"
                                })
                    
                    if star and star_alias:
                        # Namespace import: import * as foo from 'dependency'
                        imports.append({
                            "type": "es6_import",
                            "module": module,
                            "name": "*",
                            "alias": star_alias.strip(),
                            "line": line_number,
                            "import_type": "namespace"
                        })
                    
                    if default:
                        # Default import: import foo from 'dependency'
                        imports.append({
                            "type": "es6_import",
                            "module": module,
                            "name": "default",
                            "alias": default.strip(),
                            "line": line_number,
                            "import_type": "default"
                        })
            
            # CommonJS requires: const foo = require('dependency')
            require_pattern = r'(?:const|let|var)\s+(?:{([^}]*)}|([^=\s]+))\s*=\s*require\s*\([\'"]([^\'"]+)[\'"]\)'
            
            for match in re.finditer(require_pattern, content):
                destructured = match.group(1)  # {foo, bar}
                variable = match.group(2)  # foo
                module = match.group(3)  # 'dependency'
                
                # Check if this require is for our dependency
                if module == dependency_name or module.startswith(f"{dependency_name}/"):
                    line_number = content[:match.start()].count('\n') + 1
                    
                    if destructured:
                        # Destructured require: const {foo, bar} = require('dependency')
                        for part in destructured.split(','):
                            part = part.strip()
                            if part:
                                # Handle renamed requires: {foo: bar}
                                name_parts = part.split(':')
                                name = name_parts[0].strip()
                                alias = name_parts[1].strip() if len(name_parts) > 1 else name
                                
                                imports.append({
                                    "type": "require",
                                    "module": module,
                                    "name": name,
                                    "alias": alias,
                                    "line": line_number,
                                    "import_type": "named"
                                })
                    
                    if variable:
                        # Regular require: const foo = require('dependency')
                        imports.append({
                            "type": "require",
                            "module": module,
                            "name": "module",
                            "alias": variable,
                            "line": line_number,
                            "import_type": "module"
                        })
                        
        except Exception as e:
            logger.error(f"Error extracting JS imports from {file_path}: {str(e)}")
        
        return imports
    
    async def _get_breaking_changes(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str
    ) -> List[Dict[str, Any]]:
        """
        Get breaking changes between versions.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version
            ecosystem: Dependency ecosystem
            
        Returns:
            List of breaking changes
        """
        # In a real implementation, this would query an API or database
        # to get actual breaking changes. For now, we'll return mock data.
        breaking_changes = []
        
        # Mock breaking changes for demonstration
        if dependency_name == "requests" and ecosystem == "python":
            breaking_changes = [
                {
                    "type": "signature_change",
                    "symbol": "requests.get",
                    "old": "requests.get(url, params=None, **kwargs)",
                    "new": "requests.get(url, params=None, timeout=None, **kwargs)",
                    "description": "Added explicit timeout parameter",
                    "impact": "low"
                },
                {
                    "type": "removed",
                    "symbol": "requests.async",
                    "description": "Async module removed, use aiohttp instead",
                    "impact": "high",
                    "alternatives": ["aiohttp.ClientSession"]
                }
            ]
        elif dependency_name == "lodash" and ecosystem == "nodejs":
            breaking_changes = [
                {
                    "type": "signature_change",
                    "symbol": "_.flatten",
                    "old": "_.flatten(array)",
                    "new": "_.flatten(array, depth=1)",
                    "description": "Now only flattens one level deep by default",
                    "impact": "medium",
                    "alternatives": ["_.flattenDeep"]
                },
                {
                    "type": "removed",
                    "symbol": "_.pluck",
                    "description": "Function removed, use _.map with property shorthand instead",
                    "impact": "high",
                    "alternatives": ["_.map(collection, 'property')"]
                }
            ]
            
        # TODO: Query real breaking changes from a database or API
        # This would integrate with the predictive dependency management service
        
        return breaking_changes
    
    async def _analyze_file_impact(
        self,
        file_info: Dict[str, Any],
        dependency_name: str,
        breaking_changes: List[Dict[str, Any]],
        ecosystem: str
    ) -> Dict[str, Any]:
        """
        Analyze how breaking changes will impact a specific file.
        
        Args:
            file_info: File information with imports
            dependency_name: Dependency name
            breaking_changes: List of breaking changes
            ecosystem: Dependency ecosystem
            
        Returns:
            File impact analysis
        """
        file_path = file_info["file_path"]
        imports = file_info["imports"]
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Initialize impact analysis
        impact = {
            "file_path": file_path,
            "affected_imports": [],
            "affected_symbols": [],
            "usage_count": 0,
            "impact_level": "low",
            "affected_lines": []
        }
        
        # Match imports against breaking changes
        for import_info in imports:
            affected_imports = []
            
            if ecosystem == "python":
                # Process Python imports
                if import_info["type"] == "import":
                    module = import_info["module"]
                    alias = import_info["alias"]
                    
                    # Check if any breaking changes affect this module
                    for change in breaking_changes:
                        symbol = change["symbol"]
                        symbol_parts = symbol.split(".")
                        
                        # Check if importing the exact module that changed
                        if module == ".".join(symbol_parts[:-1]):
                            affected_imports.append({
                                "import_info": import_info,
                                "breaking_change": change
                            })
                
                elif import_info["type"] == "from_import":
                    module = import_info["module"]
                    name = import_info["name"]
                    alias = import_info["alias"]
                    
                    # Check if importing the exact symbol that changed
                    for change in breaking_changes:
                        symbol = change["symbol"]
                        symbol_parts = symbol.split(".")
                        
                        if module == dependency_name and name == symbol_parts[-1]:
                            affected_imports.append({
                                "import_info": import_info,
                                "breaking_change": change
                            })
                        elif module == ".".join(symbol_parts[:-1]) and name == symbol_parts[-1]:
                            affected_imports.append({
                                "import_info": import_info,
                                "breaking_change": change
                            })
            
            elif ecosystem == "nodejs":
                # Process JavaScript/TypeScript imports
                module = import_info["module"]
                name = import_info["name"]
                alias = import_info["alias"]
                
                for change in breaking_changes:
                    symbol = change["symbol"]
                    
                    # Handle namespaced symbols like _.flatten
                    if symbol.startswith("_."): 
                        # For lodash-style APIs
                        if (import_info["import_type"] == "default" and alias == "_") or \
                           (import_info["import_type"] == "namespace" and alias == "_"):
                            affected_imports.append({
                                "import_info": import_info,
                                "breaking_change": change
                            })
                    else:
                        # For named exports
                        if import_info["import_type"] == "named" and name == symbol:
                            affected_imports.append({
                                "import_info": import_info,
                                "breaking_change": change
                            })
            
            # Add affected imports to impact analysis
            impact["affected_imports"].extend(affected_imports)
        
        # Look for actual usage of affected symbols in code
        for affected in impact["affected_imports"]:
            change = affected["breaking_change"]
            import_info = affected["import_info"]
            symbol = change["symbol"]
            
            affected_symbol = {
                "symbol": symbol,
                "breaking_change": change,
                "usage_locations": []
            }
            
            # Search for usage in file
            if ecosystem == "python":
                alias = import_info["alias"]
                
                if import_info["type"] == "import":
                    # For regular imports, look for alias.symbol
                    symbol_parts = symbol.split(".")
                    if len(symbol_parts) > 1:
                        # Only check the last part if it's a nested symbol
                        search_pattern = fr'{alias}\.{symbol_parts[-1]}\('
                        for match in re.finditer(search_pattern, content):
                            line_num = content[:match.start()].count('\n') + 1
                            affected_symbol["usage_locations"].append(line_num)
                
                elif import_info["type"] == "from_import":
                    # For from imports, look for the alias directly
                    search_pattern = fr'{alias}\('
                    for match in re.finditer(search_pattern, content):
                        line_num = content[:match.start()].count('\n') + 1
                        affected_symbol["usage_locations"].append(line_num)
            
            elif ecosystem == "nodejs":
                alias = import_info["alias"]
                
                if symbol.startswith("_."):
                    # For lodash-style APIs
                    symbol_parts = symbol.split(".")
                    if len(symbol_parts) > 1:
                        search_pattern = fr'{alias}\.{symbol_parts[1]}\('
                        for match in re.finditer(search_pattern, content):
                            line_num = content[:match.start()].count('\n') + 1
                            affected_symbol["usage_locations"].append(line_num)
                else:
                    # For regular symbols
                    search_pattern = fr'{alias}\('
                    for match in re.finditer(search_pattern, content):
                        line_num = content[:match.start()].count('\n') + 1
                        affected_symbol["usage_locations"].append(line_num)
            
            # Only add symbol if it's actually used
            if affected_symbol["usage_locations"]:
                impact["affected_symbols"].append(affected_symbol)
                impact["usage_count"] += len(affected_symbol["usage_locations"])
                impact["affected_lines"].extend(affected_symbol["usage_locations"])
        
        # Determine overall impact level
        if impact["usage_count"] == 0:
            impact["impact_level"] = "none"
        elif impact["usage_count"] <= 2:
            impact["impact_level"] = "low"
        elif impact["usage_count"] <= 5:
            impact["impact_level"] = "medium"
        else:
            impact["impact_level"] = "high"
            
        # Elevate impact level based on breaking change severity
        for symbol in impact["affected_symbols"]:
            change_impact = symbol["breaking_change"].get("impact", "low")
            if change_impact == "high" and impact["impact_level"] != "high":
                impact["impact_level"] = "medium"
                
            if change_impact == "high" and impact["usage_count"] > 1:
                impact["impact_level"] = "high"
        
        return impact
    
    def _generate_impact_summary(
        self,
        file_impacts: List[Dict[str, Any]],
        breaking_changes: List[Dict[str, Any]],
        dependency_name: str
    ) -> Dict[str, Any]:
        """
        Generate summary of update impact across files.
        
        Args:
            file_impacts: List of file impact analyses
            breaking_changes: List of breaking changes
            dependency_name: Dependency name
            
        Returns:
            Impact summary
        """
        # Count impact levels
        impact_counts = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "none": 0
        }
        
        total_usage = 0
        affected_files = 0
        
        for impact in file_impacts:
            impact_counts[impact["impact_level"]] += 1
            total_usage += impact["usage_count"]
            
            if impact["impact_level"] != "none":
                affected_files += 1
        
        # Determine overall impact level
        overall_impact = "low"
        if impact_counts["high"] > 0:
            overall_impact = "high"
        elif impact_counts["medium"] > 0 or (impact_counts["low"] >= 3):
            overall_impact = "medium"
        
        # Group affected symbols
        affected_symbols = {}
        for impact in file_impacts:
            for symbol in impact["affected_symbols"]:
                symbol_name = symbol["symbol"]
                if symbol_name not in affected_symbols:
                    affected_symbols[symbol_name] = {
                        "symbol": symbol_name,
                        "breaking_change": symbol["breaking_change"],
                        "usage_count": len(symbol["usage_locations"]),
                        "files": 1
                    }
                else:
                    affected_symbols[symbol_name]["usage_count"] += len(symbol["usage_locations"])
                    affected_symbols[symbol_name]["files"] += 1
        
        # Create ordered list of most used symbols
        top_affected_symbols = sorted(
            affected_symbols.values(),
            key=lambda x: x["usage_count"],
            reverse=True
        )
        
        summary = {
            "dependency": dependency_name,
            "total_files": len(file_impacts),
            "affected_files": affected_files,
            "impact_level": overall_impact,
            "impact_counts": impact_counts,
            "total_usage": total_usage,
            "top_affected_symbols": top_affected_symbols[:5],  # Top 5 most used symbols
            "breaking_changes": breaking_changes
        }
        
        return summary
    
    def _generate_diff(
        self,
        original_code: str,
        transformed_code: str,
        file_path: str
    ) -> str:
        """
        Generate a diff between original and transformed code.
        
        Args:
            original_code: Original code
            transformed_code: Transformed code
            file_path: Path to file
            
        Returns:
            Diff string
        """
        original_lines = original_code.splitlines()
        transformed_lines = transformed_code.splitlines()
        
        # Generate unified diff
        filename = os.path.basename(file_path)
        diff = difflib.unified_diff(
            original_lines,
            transformed_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        
        return "\n".join(diff)


# Factory function
def get_code_adaptation_service(db: Session) -> CodeAdaptationService:
    """Get an instance of the code adaptation service."""
    return CodeAdaptationService(db)