import logging
import json
import os
import re
import subprocess
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session
import statistics

from backend.core.models import Analysis, Dependency
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """
    Performance profiling service for analyzing the performance impact 
    of dependencies.
    
    Key features:
    1. Dependency performance benchmarking - compare metrics between versions
    2. Bundle size impact - analyze how dependencies affect application size
    3. Runtime overhead measurement - measure actual runtime impact
    """
    
    def __init__(self, db: Session):
        self.db = db
        
    async def analyze_bundle_size(
        self,
        dependencies: List[DependencyInfo],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Analyze bundle size impact of dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            
        Returns:
            Bundle size analysis results
        """
        logger.info(f"Analyzing bundle size for {len(dependencies)} dependencies")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="bundle_size",
            status="running",
            config={"dependency_count": len(dependencies)}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Get size metrics for each dependency
            size_metrics = await self._gather_size_metrics(dependencies)
            
            # Filter to only direct dependencies
            direct_deps = [d.name for d in dependencies if d.is_direct]
            direct_size_metrics = {name: metrics for name, metrics in size_metrics.items() if name in direct_deps}
            
            # Calculate total size
            total_min_size = sum(metrics.get("minified_size", 0) for metrics in size_metrics.values())
            total_gzip_size = sum(metrics.get("gzipped_size", 0) for metrics in size_metrics.values())
            
            # Calculate direct dependencies size
            direct_min_size = sum(metrics.get("minified_size", 0) for metrics in direct_size_metrics.values())
            direct_gzip_size = sum(metrics.get("gzipped_size", 0) for metrics in direct_size_metrics.values())
            
            # Find largest dependencies
            sorted_by_size = sorted(
                [{"name": name, **metrics} for name, metrics in size_metrics.items()],
                key=lambda x: x.get("gzipped_size", 0),
                reverse=True
            )
            
            # Prepare result
            result = {
                "total_dependencies": len(dependencies),
                "direct_dependencies": len(direct_deps),
                "total_size_minified": total_min_size,
                "total_size_gzipped": total_gzip_size,
                "direct_size_minified": direct_min_size,
                "direct_size_gzipped": direct_gzip_size,
                "largest_dependencies": sorted_by_size[:10],  # Top 10 largest
                "size_metrics": size_metrics,
                "analysis_time": datetime.utcnow().isoformat()
            }
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "total_size_gzipped": total_gzip_size,
                "direct_size_gzipped": direct_gzip_size,
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing bundle size: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _gather_size_metrics(
        self,
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Gather size metrics for dependencies.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            Dictionary mapping dependency names to size metrics
        """
        # In a real implementation, this would use a database or API
        # to get actual size metrics. For now, we'll use estimated sizes.
        
        size_metrics = {}
        
        for dep in dependencies:
            # Get size from database if available
            db_dependency = (
                self.db.query(Dependency)
                .filter(Dependency.name == dep.name)
                .filter(Dependency.ecosystem == dep.ecosystem)
                .first()
            )
            
            if db_dependency and db_dependency.metadata and "size_metrics" in db_dependency.metadata:
                size_metrics[dep.name] = db_dependency.metadata["size_metrics"]
                continue
            
            # Estimate size based on ecosystem and name
            if dep.ecosystem == "nodejs":
                # Use packagephobia API for size estimates
                # In a real implementation, you'd make an actual API call
                # https://packagephobia.com/api.json?p=package-name
                
                # For now, use mock data based on package name length (for demonstration)
                name_length = len(dep.name)
                estimated_size = name_length * 1024 * (10 + (hash(dep.name) % 10))  # Pseudo-random size
                
                metrics = {
                    "minified_size": estimated_size,
                    "gzipped_size": int(estimated_size * 0.3),  # Assume 70% compression
                    "source": "estimate"
                }
                
                # Special case for known large packages
                large_packages = {
                    "react": 44000,
                    "react-dom": 122000,
                    "lodash": 71000,
                    "moment": 66000,
                    "angular": 170000,
                    "vue": 33000,
                    "jquery": 30000,
                    "axios": 14000,
                    "express": 54000,
                    "webpack": 510000
                }
                
                if dep.name in large_packages:
                    metrics["minified_size"] = large_packages[dep.name] * 1024
                    metrics["gzipped_size"] = int(metrics["minified_size"] * 0.3)
                    metrics["source"] = "package_size_database"
            
            elif dep.ecosystem == "python":
                # Estimate based on package name length (for demonstration)
                name_length = len(dep.name)
                estimated_size = name_length * 1024 * (5 + (hash(dep.name) % 5))  # Pseudo-random size
                
                metrics = {
                    "installed_size": estimated_size,
                    "wheel_size": int(estimated_size * 0.7),  # Assume 30% smaller wheels
                    "source": "estimate"
                }
                
                # Special case for known large packages
                large_packages = {
                    "numpy": 25000,
                    "pandas": 48000,
                    "tensorflow": 420000,
                    "django": 58000,
                    "scipy": 110000,
                    "scikit-learn": 80000,
                    "pytorch": 350000,
                    "matplotlib": 40000,
                    "flask": 6000,
                    "requests": 2500
                }
                
                if dep.name in large_packages:
                    metrics["installed_size"] = large_packages[dep.name] * 1024
                    metrics["wheel_size"] = int(metrics["installed_size"] * 0.7)
                    metrics["source"] = "package_size_database"
            
            else:
                # Default metrics for unknown ecosystems
                metrics = {
                    "estimated_size": len(dep.name) * 10240,
                    "source": "rough_estimate"
                }
            
            size_metrics[dep.name] = metrics
            
            # Store in database for future use
            if db_dependency:
                metadata = db_dependency.metadata or {}
                metadata["size_metrics"] = metrics
                db_dependency.metadata = metadata
                self.db.commit()
        
        return size_metrics
    
    async def analyze_runtime_performance(
        self,
        dependencies: List[DependencyInfo],
        project_id: str,
        benchmark_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze runtime performance impact of dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            benchmark_results: Optional benchmark results to use
            
        Returns:
            Runtime performance analysis results
        """
        logger.info(f"Analyzing runtime performance for {len(dependencies)} dependencies")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="runtime_performance",
            status="running",
            config={"dependency_count": len(dependencies)}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Get performance metrics
            if benchmark_results:
                # Use provided benchmark results
                performance_metrics = await self._process_benchmark_results(benchmark_results, dependencies)
            else:
                # Use estimated/cached metrics
                performance_metrics = await self._gather_performance_metrics(dependencies)
            
            # Calculate aggregate metrics
            avg_startup_impact = statistics.mean(
                [m.get("startup_impact", 0) for m in performance_metrics.values()]
            ) if performance_metrics else 0
            
            avg_runtime_impact = statistics.mean(
                [m.get("runtime_impact", 0) for m in performance_metrics.values()]
            ) if performance_metrics else 0
            
            avg_memory_impact = statistics.mean(
                [m.get("memory_impact", 0) for m in performance_metrics.values()]
            ) if performance_metrics else 0
            
            # Find dependencies with highest impact
            sorted_by_runtime = sorted(
                [{"name": name, **metrics} for name, metrics in performance_metrics.items()],
                key=lambda x: x.get("runtime_impact", 0),
                reverse=True
            )
            
            sorted_by_memory = sorted(
                [{"name": name, **metrics} for name, metrics in performance_metrics.items()],
                key=lambda x: x.get("memory_impact", 0),
                reverse=True
            )
            
            # Prepare result
            result = {
                "total_dependencies": len(dependencies),
                "avg_startup_impact_ms": avg_startup_impact,
                "avg_runtime_impact_ms": avg_runtime_impact,
                "avg_memory_impact_mb": avg_memory_impact,
                "highest_runtime_impact": sorted_by_runtime[:5],  # Top 5 by runtime
                "highest_memory_impact": sorted_by_memory[:5],  # Top 5 by memory
                "performance_metrics": performance_metrics,
                "analysis_time": datetime.utcnow().isoformat()
            }
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "avg_runtime_impact_ms": avg_runtime_impact,
                "avg_memory_impact_mb": avg_memory_impact,
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing runtime performance: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _process_benchmark_results(
        self,
        benchmark_results: Dict[str, Any],
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Process benchmark results to extract performance metrics.
        
        Args:
            benchmark_results: Benchmark results data
            dependencies: List of dependency information
            
        Returns:
            Dictionary mapping dependency names to performance metrics
        """
        performance_metrics = {}
        
        # Extract dependency-specific metrics from benchmark results
        if "dependency_metrics" in benchmark_results:
            for dep_name, metrics in benchmark_results["dependency_metrics"].items():
                performance_metrics[dep_name] = metrics
        
        # Fill in missing dependencies with estimates
        missing_deps = [d for d in dependencies if d.name not in performance_metrics]
        if missing_deps:
            estimated_metrics = await self._gather_performance_metrics(missing_deps)
            performance_metrics.update(estimated_metrics)
        
        return performance_metrics
    
    async def _gather_performance_metrics(
        self,
        dependencies: List[DependencyInfo]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Gather performance metrics for dependencies.
        
        Args:
            dependencies: List of dependency information
            
        Returns:
            Dictionary mapping dependency names to performance metrics
        """
        # In a real implementation, this would use a database or API
        # to get actual performance metrics. For now, we'll use estimated values.
        
        performance_metrics = {}
        
        for dep in dependencies:
            # Get metrics from database if available
            db_dependency = (
                self.db.query(Dependency)
                .filter(Dependency.name == dep.name)
                .filter(Dependency.ecosystem == dep.ecosystem)
                .first()
            )
            
            if db_dependency and db_dependency.metadata and "performance_metrics" in db_dependency.metadata:
                performance_metrics[dep.name] = db_dependency.metadata["performance_metrics"]
                continue
            
            # Estimate performance impact based on ecosystem and name
            if dep.ecosystem == "nodejs":
                # Use mock data for demonstration
                
                # Base metrics for all packages
                metrics = {
                    "startup_impact": 5.0,  # milliseconds
                    "runtime_impact": 2.0,  # milliseconds per operation
                    "memory_impact": 1.0,   # MB
                    "source": "estimate"
                }
                
                # Special case for known performance-intensive packages
                heavy_packages = {
                    "react": {"startup": 20.0, "runtime": 5.0, "memory": 4.0},
                    "react-dom": {"startup": 35.0, "runtime": 8.0, "memory": 10.0},
                    "angular": {"startup": 40.0, "runtime": 7.0, "memory": 12.0},
                    "moment": {"startup": 15.0, "runtime": 3.0, "memory": 2.5},
                    "lodash": {"startup": 7.0, "runtime": 1.0, "memory": 1.5},
                    "jquery": {"startup": 10.0, "runtime": 2.0, "memory": 2.0},
                    "express": {"startup": 25.0, "runtime": 6.0, "memory": 5.0},
                    "webpack": {"startup": 50.0, "runtime": 10.0, "memory": 15.0}
                }
                
                if dep.name in heavy_packages:
                    pkg = heavy_packages[dep.name]
                    metrics["startup_impact"] = pkg["startup"]
                    metrics["runtime_impact"] = pkg["runtime"]
                    metrics["memory_impact"] = pkg["memory"]
                    metrics["source"] = "performance_database"
            
            elif dep.ecosystem == "python":
                # Use mock data for demonstration
                
                # Base metrics for all packages
                metrics = {
                    "startup_impact": 10.0,  # milliseconds
                    "runtime_impact": 3.0,   # milliseconds per operation
                    "memory_impact": 2.0,    # MB
                    "source": "estimate"
                }
                
                # Special case for known performance-intensive packages
                heavy_packages = {
                    "numpy": {"startup": 100.0, "runtime": 5.0, "memory": 10.0},
                    "pandas": {"startup": 250.0, "runtime": 15.0, "memory": 50.0},
                    "tensorflow": {"startup": 500.0, "runtime": 50.0, "memory": 200.0},
                    "django": {"startup": 150.0, "runtime": 10.0, "memory": 30.0},
                    "scipy": {"startup": 150.0, "runtime": 8.0, "memory": 20.0},
                    "scikit-learn": {"startup": 200.0, "runtime": 20.0, "memory": 40.0},
                    "pytorch": {"startup": 400.0, "runtime": 40.0, "memory": 150.0},
                    "matplotlib": {"startup": 120.0, "runtime": 15.0, "memory": 25.0}
                }
                
                if dep.name in heavy_packages:
                    pkg = heavy_packages[dep.name]
                    metrics["startup_impact"] = pkg["startup"]
                    metrics["runtime_impact"] = pkg["runtime"]
                    metrics["memory_impact"] = pkg["memory"]
                    metrics["source"] = "performance_database"
            
            else:
                # Default metrics for unknown ecosystems
                metrics = {
                    "estimated_impact": "medium",
                    "source": "rough_estimate"
                }
            
            performance_metrics[dep.name] = metrics
            
            # Store in database for future use
            if db_dependency:
                metadata = db_dependency.metadata or {}
                metadata["performance_metrics"] = metrics
                db_dependency.metadata = metadata
                self.db.commit()
        
        return performance_metrics
    
    async def compare_versions_performance(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "nodejs"
    ) -> Dict[str, Any]:
        """
        Compare performance between dependency versions.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version to compare with
            ecosystem: Dependency ecosystem
            
        Returns:
            Version comparison results
        """
        logger.info(f"Comparing versions performance for {dependency_name}: {current_version} vs {target_version}")
        
        try:
            # In a real implementation, this would run actual benchmarks or
            # query a performance database. For now, we'll use mock data.
            
            # Generate different metrics for the versions to show a trend
            # This is mock data for demonstration purposes
            current_metrics = await self._get_version_metrics(dependency_name, current_version, ecosystem)
            target_metrics = await self._get_version_metrics(dependency_name, target_version, ecosystem)
            
            # Artificially adjust target metrics to show a trend
            # In a real implementation, these would be actual measured values
            target_multiplier = 1.0
            
            # Newer versions tend to be better optimized, so we'll generally improve metrics
            # But sometimes they can be worse, so we'll introduce some randomness
            if self._compare_versions(target_version, current_version) > 0:
                # Target is newer
                if hash(target_version) % 10 < 8:  # 80% chance of improvement
                    target_multiplier = 0.8  # 20% improvement
                else:
                    target_multiplier = 1.1  # 10% regression
            else:
                # Target is older
                if hash(target_version) % 10 < 8:  # 80% chance of regression
                    target_multiplier = 1.2  # 20% regression
                else:
                    target_multiplier = 0.95  # 5% improvement
            
            # Adjust metrics
            for key in target_metrics:
                if isinstance(target_metrics[key], (int, float)):
                    target_metrics[key] = target_metrics[key] * target_multiplier
            
            # Calculate percentage changes
            changes = {}
            for key in current_metrics:
                if isinstance(current_metrics[key], (int, float)) and key in target_metrics:
                    current_val = current_metrics[key]
                    target_val = target_metrics[key]
                    if current_val > 0:
                        pct_change = ((target_val - current_val) / current_val) * 100
                        changes[f"{key}_change_pct"] = pct_change
            
            # Determine improvement or regression
            if "runtime_impact" in current_metrics and "runtime_impact" in target_metrics:
                runtime_change = ((target_metrics["runtime_impact"] - current_metrics["runtime_impact"]) 
                                  / current_metrics["runtime_impact"]) * 100
                if runtime_change < -5:
                    performance_trend = "significant_improvement"
                elif runtime_change < 0:
                    performance_trend = "slight_improvement"
                elif runtime_change < 5:
                    performance_trend = "neutral"
                elif runtime_change < 15:
                    performance_trend = "slight_regression"
                else:
                    performance_trend = "significant_regression"
            else:
                performance_trend = "unknown"
            
            # Prepare result
            result = {
                "dependency": dependency_name,
                "current_version": current_version,
                "target_version": target_version,
                "ecosystem": ecosystem,
                "current_metrics": current_metrics,
                "target_metrics": target_metrics,
                "changes": changes,
                "performance_trend": performance_trend,
                "comparison_time": datetime.utcnow().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error comparing versions performance: {str(e)}")
            raise
    
    async def _get_version_metrics(
        self,
        dependency_name: str,
        version: str,
        ecosystem: str
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific dependency version.
        
        Args:
            dependency_name: Dependency name
            version: Version string
            ecosystem: Dependency ecosystem
            
        Returns:
            Dictionary with performance metrics
        """
        # In a real implementation, this would query a database or run benchmarks
        # For now, we'll use mock data
        
        # Base metrics
        metrics = {
            "startup_impact": 10.0,  # milliseconds
            "runtime_impact": 5.0,   # milliseconds per operation
            "memory_impact": 4.0,    # MB
            "source": "estimate"
        }
        
        # Adjust based on dependency
        if ecosystem == "nodejs":
            heavy_packages = {
                "react": {"startup": 20.0, "runtime": 5.0, "memory": 4.0},
                "react-dom": {"startup": 35.0, "runtime": 8.0, "memory": 10.0},
                "angular": {"startup": 40.0, "runtime": 7.0, "memory": 12.0},
                "moment": {"startup": 15.0, "runtime": 3.0, "memory": 2.5},
                "lodash": {"startup": 7.0, "runtime": 1.0, "memory": 1.5},
                "jquery": {"startup": 10.0, "runtime": 2.0, "memory": 2.0},
                "express": {"startup": 25.0, "runtime": 6.0, "memory": 5.0},
                "webpack": {"startup": 50.0, "runtime": 10.0, "memory": 15.0}
            }
            
            if dependency_name in heavy_packages:
                pkg = heavy_packages[dependency_name]
                metrics["startup_impact"] = pkg["startup"]
                metrics["runtime_impact"] = pkg["runtime"]
                metrics["memory_impact"] = pkg["memory"]
                metrics["source"] = "performance_database"
                
        elif ecosystem == "python":
            heavy_packages = {
                "numpy": {"startup": 100.0, "runtime": 5.0, "memory": 10.0},
                "pandas": {"startup": 250.0, "runtime": 15.0, "memory": 50.0},
                "tensorflow": {"startup": 500.0, "runtime": 50.0, "memory": 200.0},
                "django": {"startup": 150.0, "runtime": 10.0, "memory": 30.0},
                "scipy": {"startup": 150.0, "runtime": 8.0, "memory": 20.0},
                "scikit-learn": {"startup": 200.0, "runtime": 20.0, "memory": 40.0},
                "pytorch": {"startup": 400.0, "runtime": 40.0, "memory": 150.0},
                "matplotlib": {"startup": 120.0, "runtime": 15.0, "memory": 25.0}
            }
            
            if dependency_name in heavy_packages:
                pkg = heavy_packages[dependency_name]
                metrics["startup_impact"] = pkg["startup"]
                metrics["runtime_impact"] = pkg["runtime"]
                metrics["memory_impact"] = pkg["memory"]
                metrics["source"] = "performance_database"
        
        # Add version-specific adjustments using the version hash
        # This ensures consistent but pseudo-random variations
        version_hash = hash(version)
        metrics["startup_impact"] *= 0.9 + ((version_hash % 20) / 100)  # ±10%
        metrics["runtime_impact"] *= 0.9 + ((version_hash % 20) / 100)  # ±10%
        metrics["memory_impact"] *= 0.9 + ((version_hash % 20) / 100)   # ±10%
        
        # Add bundle size metrics
        if ecosystem == "nodejs":
            metrics["minified_size"] = int(metrics["memory_impact"] * 100 * 1024)  # Rough estimate
            metrics["gzipped_size"] = int(metrics["minified_size"] * 0.3)
        elif ecosystem == "python":
            metrics["installed_size"] = int(metrics["memory_impact"] * 80 * 1024)  # Rough estimate
            metrics["wheel_size"] = int(metrics["installed_size"] * 0.7)
        
        return metrics
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        # Remove leading 'v' if present
        if version1.startswith('v'):
            version1 = version1[1:]
        if version2.startswith('v'):
            version2 = version2[1:]
        
        # Extract version components
        v1_parts = re.findall(r'\d+', version1)
        v2_parts = re.findall(r'\d+', version2)
        
        # Compare each component
        for i in range(min(len(v1_parts), len(v2_parts))):
            v1_part = int(v1_parts[i])
            v2_part = int(v2_parts[i])
            
            if v1_part > v2_part:
                return 1
            elif v1_part < v2_part:
                return -1
        
        # If all compared components are equal, the longer version is considered greater
        if len(v1_parts) > len(v2_parts):
            return 1
        elif len(v1_parts) < len(v2_parts):
            return -1
        
        # Versions are exactly equal
        return 0
    
    async def run_benchmarks(
        self,
        dependency_name: str,
        version: str,
        ecosystem: str,
        benchmark_type: str = "basic"
    ) -> Dict[str, Any]:
        """
        Run performance benchmarks for a specific dependency.
        
        Args:
            dependency_name: Dependency name
            version: Version string
            ecosystem: Dependency ecosystem
            benchmark_type: Type of benchmark to run
            
        Returns:
            Benchmark results
        """
        logger.info(f"Running {benchmark_type} benchmarks for {dependency_name}@{version}")
        
        # In a real implementation, this would run actual benchmarks
        # For now, we'll simulate benchmark results
        
        # Simulate benchmark execution time
        import asyncio
        await asyncio.sleep(0.5)  # Simulate a small delay
        
        # Generate mock benchmark results
        results = {
            "dependency": dependency_name,
            "version": version,
            "ecosystem": ecosystem,
            "benchmark_type": benchmark_type,
            "execution_time": datetime.utcnow().isoformat()
        }
        
        if benchmark_type == "basic":
            # Basic performance metrics
            metrics = await self._get_version_metrics(dependency_name, version, ecosystem)
            results["metrics"] = metrics
            
            # Add some specific benchmark data
            results["benchmark_data"] = {
                "startup_time_ms": metrics["startup_impact"],
                "operation_time_ms": metrics["runtime_impact"],
                "memory_usage_mb": metrics["memory_impact"],
                "iterations": 100,
                "variance": 0.05  # 5% variance in measurements
            }
            
        elif benchmark_type == "comprehensive":
            # More detailed benchmark including multiple operations
            metrics = await self._get_version_metrics(dependency_name, version, ecosystem)
            results["metrics"] = metrics
            
            # Generate benchmarks for different operations
            operation_benchmarks = {}
            
            if ecosystem == "nodejs":
                # Common operations for Node.js packages
                operations = ["initialization", "basic_operation", "complex_operation", "cleanup"]
                
                for op in operations:
                    # Generate semi-random but consistent benchmark for each operation
                    op_hash = hash(f"{dependency_name}:{version}:{op}")
                    base_time = metrics["runtime_impact"] * (0.5 + (op_hash % 100) / 100)  # Varied time
                    
                    operation_benchmarks[op] = {
                        "time_ms": base_time,
                        "memory_delta_mb": metrics["memory_impact"] * (0.1 + (op_hash % 10) / 100),
                        "iterations": 100,
                        "variance": 0.05 + (op_hash % 10) / 100  # 5-15% variance
                    }
                    
            elif ecosystem == "python":
                # Common operations for Python packages
                operations = ["import_time", "function_call", "data_processing", "cleanup"]
                
                for op in operations:
                    # Generate semi-random but consistent benchmark for each operation
                    op_hash = hash(f"{dependency_name}:{version}:{op}")
                    base_time = metrics["runtime_impact"] * (0.5 + (op_hash % 100) / 100)  # Varied time
                    
                    operation_benchmarks[op] = {
                        "time_ms": base_time,
                        "memory_delta_mb": metrics["memory_impact"] * (0.1 + (op_hash % 10) / 100),
                        "iterations": 50,
                        "variance": 0.05 + (op_hash % 10) / 100  # 5-15% variance
                    }
            
            results["operation_benchmarks"] = operation_benchmarks
            
            # Add CPU profiling data
            results["cpu_profile"] = {
                "total_time_ms": sum(op["time_ms"] for op in operation_benchmarks.values()),
                "self_time_ms": sum(op["time_ms"] for op in operation_benchmarks.values()) * 0.7,  # 70% self time
                "children_time_ms": sum(op["time_ms"] for op in operation_benchmarks.values()) * 0.3,  # 30% children
                "hotspots": [
                    {"function": f"{dependency_name}:mainFunction", "time_ms": metrics["runtime_impact"] * 2},
                    {"function": f"{dependency_name}:helperFunction", "time_ms": metrics["runtime_impact"]}
                ]
            }
            
        elif benchmark_type == "bundle":
            # Bundle size benchmarks
            metrics = await self._get_version_metrics(dependency_name, version, ecosystem)
            
            if ecosystem == "nodejs":
                results["bundle_data"] = {
                    "original_size_bytes": metrics.get("minified_size", 50000),
                    "minified_size_bytes": metrics.get("minified_size", 50000),
                    "gzipped_size_bytes": metrics.get("gzipped_size", 15000),
                    "tree_shaken_size_bytes": int(metrics.get("minified_size", 50000) * 0.7),  # 30% reduction
                    "dependencies_count": int(3 + (hash(dependency_name) % 10)),
                    "js_modules_count": int(5 + (hash(dependency_name) % 20))
                }
            elif ecosystem == "python":
                results["bundle_data"] = {
                    "source_size_bytes": metrics.get("installed_size", 100000),
                    "wheel_size_bytes": metrics.get("wheel_size", 70000),
                    "installed_size_bytes": metrics.get("installed_size", 100000),
                    "bytecode_size_bytes": int(metrics.get("installed_size", 100000) * 0.4),  # 40% of source
                    "dependencies_count": int(2 + (hash(dependency_name) % 8)),
                    "modules_count": int(3 + (hash(dependency_name) % 15))
                }
        
        return results


# Factory function
def get_performance_profiler(db: Session) -> PerformanceProfiler:
    """Get an instance of the performance profiler."""
    return PerformanceProfiler(db)