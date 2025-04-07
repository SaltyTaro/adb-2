import logging
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from collections import defaultdict
import difflib
from sqlalchemy.orm import Session
from datetime import datetime
import numpy as np

from backend.core.models import Analysis, Project, Dependency, DependencyVersion
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class DependencyConsolidator:
    """
    Service for intelligent dependency consolidation.
    
    Key features:
    1. Duplicate functionality detection - identify similar dependencies
    2. Transitive dependency analysis - flatten complex dependency trees
    3. Version harmonization - align dependency versions across projects
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.similarity_threshold = 0.75  # Minimum similarity to consider packages related
    
    async def analyze_dependencies(
        self,
        dependencies: List[DependencyInfo],
        project_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Analyze dependencies for consolidation opportunities.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            
        Returns:
            Tuple of (recommendations, summary metrics)
        """
        logger.info(f"Analyzing {len(dependencies)} dependencies for consolidation")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="dependency_consolidation",
            status="running",
            config={"dependency_count": len(dependencies)}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Group dependencies by ecosystem
            ecosystem_deps = defaultdict(list)
            for dep in dependencies:
                ecosystem_deps[dep.ecosystem].append(dep)
            
            # Find duplicate functionality
            duplicate_groups = await self._detect_duplicate_functionality(dependencies)
            
            # Analyze transitive dependencies
            transitive_analysis = await self._analyze_transitive_dependencies(dependencies)
            
            # Find version inconsistencies
            version_inconsistencies = await self._find_version_inconsistencies(dependencies)
            
            # Generate recommendations
            recommendations = {
                "duplicates": self._generate_duplicate_recommendations(duplicate_groups),
                "transitive": self._generate_transitive_recommendations(transitive_analysis),
                "versions": self._generate_version_recommendations(version_inconsistencies)
            }
            
            # Calculate metrics
            metrics = {
                "total_dependencies": len(dependencies),
                "direct_dependencies": len([d for d in dependencies if d.is_direct]),
                "transitive_dependencies": len([d for d in dependencies if not d.is_direct]),
                "duplicate_groups": len(duplicate_groups),
                "potential_removals": sum(len(group) - 1 for group in duplicate_groups),
                "transitive_chains": len(transitive_analysis["chains"]),
                "version_inconsistencies": len(version_inconsistencies),
                "estimated_reduction": self._calculate_reduction_potential(
                    dependencies, duplicate_groups, transitive_analysis
                ),
                "ecosystems": list(ecosystem_deps.keys()),
                "ecosystem_counts": {eco: len(deps) for eco, deps in ecosystem_deps.items()}
            }
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "summary": metrics,
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return recommendations, metrics
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies for consolidation: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _detect_duplicate_functionality(
        self,
        dependencies: List[DependencyInfo]
    ) -> List[List[DependencyInfo]]:
        """
        Detect dependencies with similar functionality.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            List of duplicate groups (each group is a list of similar dependencies)
        """
        duplicate_groups = []
        
        try:
            # Group by ecosystem first
            ecosystem_deps = defaultdict(list)
            for dep in dependencies:
                ecosystem_deps[dep.ecosystem].append(dep)
            
            # Process each ecosystem separately
            for ecosystem, eco_deps in ecosystem_deps.items():
                # Skip if too few dependencies
                if len(eco_deps) < 2:
                    continue
                
                # Create name comparison matrix
                dep_names = [dep.name for dep in eco_deps]
                similarity_matrix = np.zeros((len(dep_names), len(dep_names)))
                
                # Calculate similarity scores
                for i in range(len(dep_names)):
                    for j in range(i+1, len(dep_names)):
                        name_similarity = self._calculate_name_similarity(dep_names[i], dep_names[j])
                        similarity_matrix[i, j] = name_similarity
                        similarity_matrix[j, i] = name_similarity
                
                # Find potential groups based on name similarity
                potential_groups = []
                visited = set()
                
                for i in range(len(eco_deps)):
                    if i in visited:
                        continue
                    
                    group = [i]
                    visited.add(i)
                    
                    for j in range(len(eco_deps)):
                        if j in visited:
                            continue
                        
                        # Check if similar to any existing group member
                        for group_idx in group:
                            if similarity_matrix[group_idx, j] >= self.similarity_threshold:
                                group.append(j)
                                visited.add(j)
                                break
                    
                    if len(group) > 1:
                        potential_groups.append([eco_deps[idx] for idx in group])
                
                # Further analyze potential groups to confirm duplicate functionality
                for group in potential_groups:
                    confirmed_group = self._analyze_dependency_functions(group)
                    if confirmed_group and len(confirmed_group) > 1:
                        duplicate_groups.append(confirmed_group)
            
        except Exception as e:
            logger.error(f"Error detecting duplicate functionality: {str(e)}")
        
        return duplicate_groups
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between dependency names.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score (0-1)
        """
        # Normalize names
        def normalize(name):
            # Remove common prefixes and suffixes
            prefixes = ["node-", "py-", "python-", "js-", "react-", "vue-"]
            suffixes = ["-js", "-py", "-node", "-lib", "-utils", "-tools"]
            
            norm_name = name.lower()
            for prefix in prefixes:
                if norm_name.startswith(prefix):
                    norm_name = norm_name[len(prefix):]
                    break
                    
            for suffix in suffixes:
                if norm_name.endswith(suffix):
                    norm_name = norm_name[:-len(suffix)]
                    break
            
            # Replace hyphens, underscores with spaces
            norm_name = norm_name.replace("-", " ").replace("_", " ")
            
            return norm_name
        
        norm1 = normalize(name1)
        norm2 = normalize(name2)
        
        # If the names are too short, rely on exact matching
        if len(norm1) < 3 or len(norm2) < 3:
            return 1.0 if norm1 == norm2 else 0.0
        
        # If names are the same after normalization
        if norm1 == norm2:
            return 1.0
            
        # Use string similarity
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        
        # Check for substring match (often indicates related functionality)
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.8)
            
        return similarity
    
    def _analyze_dependency_functions(
        self,
        similar_deps: List[DependencyInfo]
    ) -> List[DependencyInfo]:
        """
        Analyze dependencies to confirm functional similarity.
        
        Args:
            similar_deps: List of potentially similar dependencies
            
        Returns:
            List of confirmed similar dependencies
        """
        # If we don't have enough usage information, default to name-based similarity
        if all(not dep.used_features for dep in similar_deps):
            return similar_deps
        
        # We have usage information, so we can better analyze functionality
        confirmed_group = []
        feature_sets = []
        
        # Get feature sets for dependencies with usage information
        for dep in similar_deps:
            if dep.used_features:
                confirmed_group.append(dep)
                feature_sets.append(dep.used_features)
        
        # If we don't have enough data, return the group as-is
        if len(confirmed_group) <= 1:
            return similar_deps
        
        # Calculate feature similarity between pairs
        similar_pairs = []
        for i in range(len(confirmed_group)):
            for j in range(i+1, len(confirmed_group)):
                feature_similarity = self._calculate_feature_similarity(
                    feature_sets[i], feature_sets[j]
                )
                if feature_similarity >= self.similarity_threshold:
                    similar_pairs.append((i, j))
        
        # If we don't have similar pairs, return None
        if not similar_pairs:
            return []
        
        # Build groups from similar pairs
        # For simplicity, we'll just check if each dep is in any pair
        included = set()
        for i, j in similar_pairs:
            included.add(i)
            included.add(j)
        
        if len(included) <= 1:
            return []
        
        result_group = [confirmed_group[i] for i in included]
        return result_group
    
    def _calculate_feature_similarity(
        self,
        features1: Set[str],
        features2: Set[str]
    ) -> float:
        """
        Calculate similarity between feature sets.
        
        Args:
            features1: First feature set
            features2: Second feature set
            
        Returns:
            Similarity score (0-1)
        """
        if not features1 or not features2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(features1.intersection(features2))
        union = len(features1.union(features2))
        
        return intersection / union if union > 0 else 0.0
    
    async def _analyze_transitive_dependencies(
        self,
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Any]:
        """
        Analyze transitive dependencies to find optimization opportunities.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            Dictionary with analysis results
        """
        result = {
            "chains": [],  # Long dependency chains
            "common_transitive": [],  # Common transitive dependencies
            "unnecessary_indirect": []  # Dependencies that could be direct
        }
        
        try:
            # Build dependency graph
            graph = self._build_dependency_graph(dependencies)
            
            # Find long dependency chains
            chains = self._find_long_chains(graph)
            result["chains"] = chains
            
            # Find common transitive dependencies
            common_transitive = self._find_common_transitive(graph)
            result["common_transitive"] = common_transitive
            
            # Find unnecessary indirect dependencies
            unnecessary_indirect = self._find_unnecessary_indirect(graph)
            result["unnecessary_indirect"] = unnecessary_indirect
            
        except Exception as e:
            logger.error(f"Error analyzing transitive dependencies: {str(e)}")
        
        return result
    
    def _build_dependency_graph(
        self,
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a graph representation of dependencies.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            Dependency graph
        """
        graph = {}
        
        # Map of dependency name to object
        dep_map = {dep.name: dep for dep in dependencies}
        
        # Build graph
        for dep in dependencies:
            graph[dep.name] = {
                "info": dep,
                "parents": set(),
                "children": set()
            }
        
        # Add relationships
        for dep in dependencies:
            if dep.parent and dep.parent in graph:
                graph[dep.name]["parents"].add(dep.parent)
                graph[dep.parent]["children"].add(dep.name)
            
            # Add relationships from required_by
            if hasattr(dep, "required_by") and dep.required_by:
                for parent in dep.required_by:
                    if parent in graph:
                        graph[dep.name]["parents"].add(parent)
                        graph[parent]["children"].add(dep.name)
        
        return graph
    
    def _find_long_chains(
        self,
        graph: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find long dependency chains.
        
        Args:
            graph: Dependency graph
            
        Returns:
            List of long chains
        """
        long_chains = []
        
        # Find root dependencies (direct deps)
        root_deps = [name for name, data in graph.items() 
                     if data["info"].is_direct]
        
        # For each root, find longest path
        for root in root_deps:
            visited = set()
            stack = [(root, [root])]
            
            while stack:
                node, path = stack.pop()
                
                # Skip if already visited
                if node in visited:
                    continue
                    
                visited.add(node)
                
                # Check children
                for child in graph[node]["children"]:
                    # Skip if creates a cycle
                    if child in path:
                        continue
                    
                    new_path = path + [child]
                    stack.append((child, new_path))
                    
                    # If path is long enough, add to result
                    if len(new_path) >= 4:  # Arbitrary threshold for "long"
                        long_chains.append({
                            "root": root,
                            "leaf": child,
                            "path": new_path,
                            "length": len(new_path)
                        })
        
        # Sort by length (longest first)
        long_chains.sort(key=lambda x: x["length"], reverse=True)
        
        return long_chains[:10]  # Return top 10 longest chains
    
    def _find_common_transitive(
        self,
        graph: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find common transitive dependencies.
        
        Args:
            graph: Dependency graph
            
        Returns:
            List of common transitive dependencies
        """
        common_transitive = []
        
        # Count parent references for each node
        for name, data in graph.items():
            # Skip direct dependencies
            if data["info"].is_direct:
                continue
            
            parents = data["parents"]
            
            # If this transitive dep has multiple parents, it's common
            if len(parents) >= 3:  # Arbitrary threshold
                common_transitive.append({
                    "name": name,
                    "parents": list(parents),
                    "parent_count": len(parents),
                    "ecosystem": data["info"].ecosystem,
                    "version": data["info"].version
                })
        
        # Sort by parent count (most referenced first)
        common_transitive.sort(key=lambda x: x["parent_count"], reverse=True)
        
        return common_transitive[:10]  # Return top 10
    
    def _find_unnecessary_indirect(
        self,
        graph: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find unnecessary indirect dependencies.
        
        Args:
            graph: Dependency graph
            
        Returns:
            List of unnecessary indirect dependencies
        """
        unnecessary_indirect = []
        
        # Find transitive dependencies referenced by many direct dependencies
        direct_deps = [name for name, data in graph.items() 
                       if data["info"].is_direct]
        
        # For each transitive dependency
        for name, data in graph.items():
            # Skip direct dependencies
            if data["info"].is_direct:
                continue
            
            # Check if it's used directly in code despite being indirect
            has_used_features = bool(data["info"].used_features)
            
            # If it has many direct dependency parents or is directly used,
            # it might make sense to make it a direct dependency
            direct_parents = [p for p in data["parents"] if p in direct_deps]
            
            if len(direct_parents) >= 2 or (has_used_features and direct_parents):
                unnecessary_indirect.append({
                    "name": name,
                    "direct_parents": direct_parents,
                    "direct_parent_count": len(direct_parents),
                    "has_direct_usage": has_used_features,
                    "ecosystem": data["info"].ecosystem,
                    "version": data["info"].version
                })
        
        # Sort by direct parent count (most referenced first)
        unnecessary_indirect.sort(key=lambda x: x["direct_parent_count"], reverse=True)
        
        return unnecessary_indirect[:10]  # Return top 10
    
    async def _find_version_inconsistencies(
        self,
        dependencies: List[DependencyInfo]
    ) -> List[Dict[str, Any]]:
        """
        Find version inconsistencies across dependencies.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            List of version inconsistencies
        """
        inconsistencies = []
        
        try:
            # Group dependencies by name
            name_groups = defaultdict(list)
            for dep in dependencies:
                name_groups[dep.name].append(dep)
            
            # Check each group for inconsistencies
            for name, group in name_groups.items():
                if len(group) <= 1:
                    continue
                
                # Get unique versions
                versions = set(dep.version for dep in group)
                
                if len(versions) > 1:
                    # Get version objects for comparison
                    version_objects = []
                    for version in versions:
                        parsed = self._parse_version(version)
                        if parsed:
                            version_objects.append({
                                "version": version,
                                "parsed": parsed
                            })
                    
                    # Sort versions
                    version_objects.sort(key=lambda x: x["parsed"])
                    
                    # Get paths where each version is used
                    version_paths = defaultdict(list)
                    for dep in group:
                        version_paths[dep.version].append(
                            dep.parent or "direct" if hasattr(dep, "parent") else "unknown"
                        )
                    
                    # Create inconsistency entry
                    inconsistencies.append({
                        "name": name,
                        "ecosystem": group[0].ecosystem,
                        "versions": [v["version"] for v in version_objects],
                        "latest_version": version_objects[-1]["version"] if version_objects else None,
                        "version_paths": dict(version_paths),
                        "version_count": len(versions),
                        "is_direct": any(dep.is_direct for dep in group)
                    })
            
            # Sort by version count and direct first
            inconsistencies.sort(key=lambda x: (x["is_direct"], x["version_count"]), reverse=True)
            
        except Exception as e:
            logger.error(f"Error finding version inconsistencies: {str(e)}")
        
        return inconsistencies
    
    def _parse_version(self, version: str) -> Optional[Tuple[int, ...]]:
        """
        Parse a version string into comparable components.
        
        Args:
            version: Version string
            
        Returns:
            Tuple of version components or None if parsing fails
        """
        try:
            # Remove leading 'v' if present
            if version.startswith('v'):
                version = version[1:]
                
            # Split version by common separators
            parts = []
            for part in version.split('.'):
                # Handle common suffixes
                for sep in ['-', '+', '~']:
                    if sep in part:
                        part = part.split(sep)[0]
                        break
                
                # Try to convert to integer
                try:
                    parts.append(int(part))
                except ValueError:
                    # If not a number, use 0 to keep structure
                    parts.append(0)
            
            # Ensure we have at least 3 parts (major, minor, patch)
            while len(parts) < 3:
                parts.append(0)
                
            return tuple(parts)
        except Exception:
            return None
    
    def _generate_duplicate_recommendations(
        self,
        duplicate_groups: List[List[DependencyInfo]]
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for duplicate dependencies.
        
        Args:
            duplicate_groups: List of duplicate groups
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for group in duplicate_groups:
            # Sort by direct first, then by usage (most used first)
            sorted_group = sorted(
                group,
                key=lambda x: (not x.is_direct, -len(x.used_features or []))
            )
            
            # Determine which dependency to keep
            keep = sorted_group[0]
            remove = sorted_group[1:]
            
            recommendations.append({
                "type": "duplicate_functionality",
                "description": f"Multiple dependencies with similar functionality found: {', '.join(d.name for d in group)}",
                "recommendation": f"Consider consolidating on {keep.name} and removing {', '.join(d.name for d in remove)}",
                "keep": {
                    "name": keep.name,
                    "version": keep.version,
                    "ecosystem": keep.ecosystem,
                    "is_direct": keep.is_direct,
                    "used_features": list(keep.used_features) if hasattr(keep, "used_features") else []
                },
                "remove": [
                    {
                        "name": dep.name,
                        "version": dep.version,
                        "ecosystem": dep.ecosystem,
                        "is_direct": dep.is_direct,
                        "used_features": list(dep.used_features) if hasattr(dep, "used_features") else []
                    }
                    for dep in remove
                ],
                "similarity": "high",
                "effort": "medium",
                "savings": "high" if any(dep.is_direct for dep in remove) else "medium"
            })
        
        return recommendations
    
    def _generate_transitive_recommendations(
        self,
        transitive_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for transitive dependencies.
        
        Args:
            transitive_analysis: Transitive dependency analysis
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Recommendations for long chains
        if transitive_analysis["chains"]:
            for chain in transitive_analysis["chains"][:3]:  # Top 3 longest chains
                recommendations.append({
                    "type": "long_dependency_chain",
                    "description": f"Long dependency chain detected ({chain['length']} levels)",
                    "recommendation": f"Consider flattening dependency chain from {chain['root']} to {chain['leaf']}",
                    "path": chain["path"],
                    "effort": "medium",
                    "savings": "medium"
                })
        
        # Recommendations for common transitive dependencies
        if transitive_analysis["common_transitive"]:
            for dep in transitive_analysis["common_transitive"][:3]:  # Top 3 most common
                recommendations.append({
                    "type": "common_transitive",
                    "description": f"{dep['name']} is used as a transitive dependency by {dep['parent_count']} packages",
                    "recommendation": f"Consider adding {dep['name']} as a direct dependency to standardize version",
                    "dependency": {
                        "name": dep["name"],
                        "version": dep["version"],
                        "ecosystem": dep["ecosystem"],
                        "parent_count": dep["parent_count"],
                        "parents": dep["parents"]
                    },
                    "effort": "low",
                    "savings": "medium"
                })
        
        # Recommendations for unnecessary indirect dependencies
        if transitive_analysis["unnecessary_indirect"]:
            for dep in transitive_analysis["unnecessary_indirect"][:3]:  # Top 3
                reason = "it is used directly in code" if dep["has_direct_usage"] else f"it is a common dependency of {len(dep['direct_parents'])} direct dependencies"
                
                recommendations.append({
                    "type": "unnecessary_indirect",
                    "description": f"{dep['name']} is an indirect dependency, but {reason}",
                    "recommendation": f"Consider adding {dep['name']} as a direct dependency",
                    "dependency": {
                        "name": dep["name"],
                        "version": dep["version"],
                        "ecosystem": dep["ecosystem"],
                        "direct_parents": dep["direct_parents"],
                        "has_direct_usage": dep["has_direct_usage"]
                    },
                    "effort": "low",
                    "savings": "low"
                })
        
        return recommendations
    
    def _generate_version_recommendations(
        self,
        version_inconsistencies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for version inconsistencies.
        
        Args:
            version_inconsistencies: List of version inconsistencies
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for inconsistency in version_inconsistencies[:5]:  # Top 5 issues
            latest = inconsistency["latest_version"]
            
            recommendations.append({
                "type": "version_inconsistency",
                "description": f"{inconsistency['name']} is used with {inconsistency['version_count']} different versions",
                "recommendation": f"Standardize on version {latest}",
                "dependency": {
                    "name": inconsistency["name"],
                    "ecosystem": inconsistency["ecosystem"],
                    "versions": inconsistency["versions"],
                    "recommended_version": latest,
                    "version_paths": inconsistency["version_paths"],
                    "is_direct": inconsistency["is_direct"]
                },
                "effort": "low" if inconsistency["is_direct"] else "medium",
                "savings": "medium"
            })
        
        return recommendations
    
    def _calculate_reduction_potential(
        self,
        dependencies: List[DependencyInfo],
        duplicate_groups: List[List[DependencyInfo]],
        transitive_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate potential dependency reduction.
        
        Args:
            dependencies: List of dependency information
            duplicate_groups: List of duplicate groups
            transitive_analysis: Transitive dependency analysis
            
        Returns:
            Reduction metrics
        """
        total_deps = len(dependencies)
        direct_deps = len([d for d in dependencies if d.is_direct])
        transitive_deps = total_deps - direct_deps
        
        # Count potential removals from duplicates
        duplicate_removals = sum(len(group) - 1 for group in duplicate_groups)
        
        # Estimate chain reduction
        chain_reduction = min(10, len(transitive_analysis["chains"]))
        
        # Calculate percentages
        reduction_count = duplicate_removals + chain_reduction
        reduction_percent = (reduction_count / total_deps) * 100 if total_deps else 0
        
        return {
            "total_dependencies": total_deps,
            "potential_removals": reduction_count,
            "reduction_percent": round(reduction_percent, 2),
            "duplicate_removals": duplicate_removals,
            "chain_reduction": chain_reduction
        }


# Factory function for dependency consolidator
def get_dependency_consolidator(db: Session) -> DependencyConsolidator:
    """Get an instance of the dependency consolidator."""
    return DependencyConsolidator(db)