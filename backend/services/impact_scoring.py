import logging
import json
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session
import numpy as np

from backend.core.models import ImpactScore, Analysis
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class ImpactScorer:
    """
    Calculates impact scores for dependencies based on various factors.
    
    Impact scoring considers:
    1. Business value - how critical is the dependency to core functionality
    2. Usage metrics - how much of the dependency is actually used
    3. Complexity - how complex is the dependency tree
    4. Health - how healthy is the dependency project
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.thresholds = settings.DEPENDENCY_HEALTH_THRESHOLDS
    
    async def score_dependencies(
        self,
        dependencies: List[DependencyInfo],
        project_id: str,
        context: Dict[str, Any] = None
    ) -> Tuple[List[ImpactScore], Dict[str, Any]]:
        """
        Score a list of dependencies for a project.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            context: Additional context (e.g., static analysis results)
            
        Returns:
            Tuple of (list of impact scores, aggregated results)
        """
        logger.info(f"Scoring {len(dependencies)} dependencies for project {project_id}")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="impact_scoring",
            status="running",
            config={"dependency_count": len(dependencies)}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Score each dependency
            impact_scores = []
            
            for dep in dependencies:
                score = await self._score_dependency(dep, context)
                impact_scores.append(score)
                
            # Save scores to database
            db_scores = []
            for score in impact_scores:
                db_score = ImpactScore(
                    analysis_id=analysis.id,
                    dependency_name=score["name"],
                    version=score["version"],
                    business_value_score=score["scores"]["business_value"],
                    usage_score=score["scores"]["usage"],
                    complexity_score=score["scores"]["complexity"],
                    health_score=score["scores"]["health"],
                    overall_score=score["overall_score"],
                    used_features=score["used_features"],
                    unused_features=score["unused_features"]
                )
                self.db.add(db_score)
                db_scores.append(db_score)
            
            # Calculate aggregate metrics
            aggregates = self._calculate_aggregates(impact_scores)
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "aggregate_scores": aggregates,
                "dependency_count": len(dependencies),
                "high_impact_count": len([s for s in impact_scores if s["overall_score"] >= 0.8]),
                "low_usage_count": len([s for s in impact_scores if s["scores"]["usage"] <= 0.3]),
                "health_issues_count": len([s for s in impact_scores if s["scores"]["health"] <= 0.6])
            }
            
            self.db.commit()
            
            return db_scores, analysis.result
            
        except Exception as e:
            logger.error(f"Error scoring dependencies: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _score_dependency(
        self,
        dependency: DependencyInfo,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Score a single dependency.
        
        Args:
            dependency: Dependency information
            context: Additional context
            
        Returns:
            Dictionary with score components and overall score
        """
        context = context or {}
        
        # 1. Business value assessment
        business_value = await self._assess_business_value(dependency, context)
        
        # 2. Usage metrics
        usage_score, used, unused = await self._assess_usage(dependency, context)
        
        # 3. Complexity assessment
        complexity_score = await self._assess_complexity(dependency, context)
        
        # 4. Health assessment
        health_score = await self._assess_health(dependency, context)
        
        # Calculate weighted overall score
        # Weights can be adjusted based on importance
        weights = {
            "business_value": 0.4,
            "usage": 0.3,
            "complexity": 0.1,
            "health": 0.2
        }
        
        scores = {
            "business_value": business_value,
            "usage": usage_score,
            "complexity": complexity_score,
            "health": health_score
        }
        
        overall_score = sum(score * weights[component] for component, score in scores.items())
        
        return {
            "name": dependency.name,
            "version": dependency.version,
            "ecosystem": dependency.ecosystem,
            "scores": scores,
            "overall_score": overall_score,
            "used_features": list(used),
            "unused_features": list(unused),
            "is_direct": dependency.is_direct,
            "metadata": dependency.metadata
        }
    
    async def _assess_business_value(
        self,
        dependency: DependencyInfo,
        context: Dict[str, Any]
    ) -> float:
        """
        Assess business value of a dependency.
        
        This measures how critical the dependency is to core functionality.
        
        Args:
            dependency: Dependency information
            context: Additional context
            
        Returns:
            Business value score (0-1)
        """
        # Default starting score
        score = 0.5
        
        # If we have static analysis results
        if "static_analysis" in context:
            static_data = context["static_analysis"]
            
            # Check if this dependency is used in core modules
            if dependency.name in static_data.get("core_dependencies", []):
                score += 0.3
            
            # Check dependency usage frequency across codebase
            usage_frequency = static_data.get("dependency_usage", {}).get(dependency.name, 0)
            normalized_freq = min(usage_frequency / 100, 0.3)  # Cap at 0.3
            score += normalized_freq
        
        # Adjust based on dependency metadata
        if dependency.metadata.get("dev", False):
            # Dev dependencies are less critical to business functionality
            score *= 0.5
        
        # Check if it's a direct dependency (more important than transitive)
        if dependency.is_direct:
            score = min(score * 1.2, 1.0)
        
        # If it has many dependents, it's likely more critical
        if hasattr(dependency, "required_by") and dependency.required_by:
            dependent_factor = min(len(dependency.required_by) * 0.05, 0.2)
            score += dependent_factor
        
        return min(score, 1.0)  # Cap at 1.0
    
    async def _assess_usage(
        self,
        dependency: DependencyInfo,
        context: Dict[str, Any]
    ) -> Tuple[float, Set[str], Set[str]]:
        """
        Assess how much of the dependency is actually used.
        
        Args:
            dependency: Dependency information
            context: Additional context
            
        Returns:
            Tuple of (usage score, used features, unused features)
        """
        # Get used features from dependency info
        used_features = dependency.used_features
        
        # If we have package metadata, we can determine what's available vs used
        available_features: Set[str] = set()
        
        # Try to get available features from context
        if "package_metadata" in context:
            pkg_data = context["package_metadata"].get(dependency.name, {})
            available_features = set(pkg_data.get("exports", []))
        
        # If we don't have metadata, we'll make a rough guess
        if not available_features and "static_analysis" in context:
            static_data = context["static_analysis"]
            available_features = set(static_data.get("available_features", {}).get(dependency.name, []))
        
        # If we still don't have available features, assume a base set
        if not available_features:
            # Just use the module name itself as minimum available feature
            available_features = {dependency.name}
            
            # Use imports as proxy for available features
            available_features.update(used_features)
            
            # Add common feature patterns based on conventions
            for feature in list(used_features):
                parts = feature.split('.')
                if len(parts) > 1:
                    # Add parent modules as available features
                    for i in range(1, len(parts)):
                        parent = '.'.join(parts[:i])
                        available_features.add(parent)
        
        # Determine unused features
        unused_features = available_features - used_features
        
        # Calculate usage ratio
        if available_features:
            usage_ratio = len(used_features) / len(available_features)
        else:
            # If we don't know available features, use a default score
            usage_ratio = 0.5
        
        # Adjust for special cases
        if dependency.metadata.get("dev", False):
            # Dev dependencies often have low usage, but that's fine
            usage_ratio = max(usage_ratio, 0.7)
            
        if not dependency.is_direct:
            # Transitive dependencies aren't directly imported, so usage is harder to measure
            usage_ratio = max(usage_ratio, 0.6)
            
        # If it's a small library with few features, it's more likely to be fully used
        if len(available_features) <= 3:
            usage_ratio = max(usage_ratio, 0.8)
            
        return usage_ratio, used_features, unused_features
    
    async def _assess_complexity(
        self,
        dependency: DependencyInfo,
        context: Dict[str, Any]
    ) -> float:
        """
        Assess complexity of a dependency.
        
        Lower scores indicate higher complexity (which is worse).
        
        Args:
            dependency: Dependency information
            context: Additional context
            
        Returns:
            Complexity score (0-1)
        """
        # Start with a default score
        score = 0.7
        
        # If we have dependency graph data
        if "dependency_graph" in context:
            graph_data = context["dependency_graph"]
            
            # Check depth in dependency tree
            depth = graph_data.get("depths", {}).get(dependency.name, 1)
            depth_factor = max(0, 1 - (depth / 10))  # Deeper is more complex
            
            # Check number of transitive dependencies
            transitive_count = len(graph_data.get("transitive_deps", {}).get(dependency.name, []))
            transitive_factor = max(0, 1 - (transitive_count / 100))  # More deps is more complex
            
            # Update score based on structural complexity
            score = (score + depth_factor + transitive_factor) / 3
        
        # Adjust for size of the dependency if available
        if "package_metadata" in context:
            pkg_data = context["package_metadata"].get(dependency.name, {})
            size_kb = pkg_data.get("size", 0) / 1024
            
            # Larger packages tend to be more complex
            if size_kb > 0:
                size_factor = max(0, 1 - (size_kb / 10000))  # Adjust scale as needed
                score = (score + size_factor) / 2
                
        return score
    
    async def _assess_health(
        self,
        dependency: DependencyInfo,
        context: Dict[str, Any]
    ) -> float:
        """
        Assess health of a dependency project.
        
        Args:
            dependency: Dependency information
            context: Additional context
            
        Returns:
            Health score (0-1)
        """
        # Start with a moderate score
        score = 0.6
        
        # If we have health metrics data
        if "health_metrics" in context:
            metrics = context["health_metrics"].get(dependency.name, {})
            
            # Contributor activity
            activity_score = metrics.get("activity_score", 0.5)
            
            # Issue responsiveness
            issue_score = metrics.get("issue_responsiveness", 0.5)
            
            # Release frequency
            release_score = metrics.get("release_frequency", 0.5)
            
            # Security vulnerabilities (inverse: higher is better)
            vuln_count = metrics.get("vulnerability_count", 0)
            security_score = max(0, 1 - (vuln_count / 10))
            
            # Combine factors
            score = (activity_score * 0.3 + 
                     issue_score * 0.2 + 
                     release_score * 0.2 + 
                     security_score * 0.3)
        
        # Check if dependency is deprecated
        if dependency.metadata.get("deprecated", False) or getattr(dependency, "is_deprecated", False):
            score *= 0.4
        
        # Age of current version can affect health score
        if "package_metadata" in context:
            pkg_data = context["package_metadata"].get(dependency.name, {})
            days_since_release = pkg_data.get("days_since_release", 0)
            
            if days_since_release > 0:
                # Very new (< 30 days) or very old (> 2 years) decrease score
                if days_since_release < 30:
                    age_factor = 0.9  # Slight penalty for very new
                elif days_since_release > 730:  # 2 years
                    age_factor = 0.7  # Larger penalty for old and unmaintained
                else:
                    age_factor = 1.0  # Ideal age range
                    
                score = score * age_factor
        
        return max(0.1, min(score, 1.0))  # Ensure score is between 0.1 and 1.0
    
    def _calculate_aggregates(
        self,
        scores: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate aggregate metrics from all dependency scores.
        
        Args:
            scores: List of dependency scores
            
        Returns:
            Dictionary of aggregate metrics
        """
        if not scores:
            return {
                "average_score": 0,
                "median_score": 0,
                "high_impact_ratio": 0,
                "low_usage_ratio": 0,
                "health_issues_ratio": 0
            }
            
        overall_scores = [s["overall_score"] for s in scores]
        business_value_scores = [s["scores"]["business_value"] for s in scores]
        usage_scores = [s["scores"]["usage"] for s in scores]
        complexity_scores = [s["scores"]["complexity"] for s in scores]
        health_scores = [s["scores"]["health"] for s in scores]
        
        # Calculate key metrics
        high_impact = len([s for s in scores if s["overall_score"] >= 0.8])
        low_usage = len([s for s in scores if s["scores"]["usage"] <= 0.3])
        health_issues = len([s for s in scores if s["scores"]["health"] <= 0.6])
        
        return {
            "dependency_count": len(scores),
            "average_score": np.mean(overall_scores),
            "median_score": np.median(overall_scores),
            "score_percentiles": {
                "p25": np.percentile(overall_scores, 25),
                "p50": np.percentile(overall_scores, 50),
                "p75": np.percentile(overall_scores, 75),
                "p90": np.percentile(overall_scores, 90)
            },
            "component_averages": {
                "business_value": np.mean(business_value_scores),
                "usage": np.mean(usage_scores),
                "complexity": np.mean(complexity_scores),
                "health": np.mean(health_scores)
            },
            "high_impact_count": high_impact,
            "high_impact_ratio": high_impact / len(scores),
            "low_usage_count": low_usage,
            "low_usage_ratio": low_usage / len(scores),
            "health_issues_count": health_issues,
            "health_issues_ratio": health_issues / len(scores),
            "direct_dependencies": len([s for s in scores if s.get("is_direct", False)]),
            "transitive_dependencies": len([s for s in scores if not s.get("is_direct", False)])
        }


# Factory function for dependency
def get_impact_scorer(db: Session) -> ImpactScorer:
    """Get an instance of the impact scorer."""
    return ImpactScorer(db)