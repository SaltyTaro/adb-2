import logging
import json
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session
import numpy as np

from backend.core.models import Analysis, Dependency
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Dependency health monitoring service for tracking the vitality of
    open-source projects beyond just version numbers.
    
    Key features:
    1. Community vitality metrics - track project health indicators
    2. Abandoned dependency alerts - detect signs of project abandonment
    3. Maintenance cost prediction - estimate future maintenance costs
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.github_token = settings.GITHUB_API_TOKEN
        self.check_interval = settings.DEPENDENCY_HEALTH_CHECK_INTERVAL
        self.thresholds = settings.DEPENDENCY_HEALTH_THRESHOLDS
    
    async def analyze_dependencies_health(
        self,
        dependencies: List[DependencyInfo],
        project_id: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Analyze the health of multiple dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            
        Returns:
            Tuple of (health summary, detailed health reports)
        """
        logger.info(f"Analyzing health for {len(dependencies)} dependencies")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="dependency_health",
            status="running",
            config={"dependency_count": len(dependencies)}
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Process direct dependencies first (they're more important)
            direct_deps = [d for d in dependencies if d.is_direct]
            transitive_deps = [d for d in dependencies if not d.is_direct]
            
            # Keep only a subset of transitive dependencies to avoid excessive API calls
            max_transitive = min(len(transitive_deps), 50)
            selected_deps = direct_deps + transitive_deps[:max_transitive]
            
            # Create tasks for health checks
            tasks = []
            for dep in selected_deps:
                tasks.append(self._check_dependency_health(dep))
            
            # Gather results
            health_reports = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results, skipping exceptions
            valid_reports = []
            for dep, report in zip(selected_deps, health_reports):
                if isinstance(report, Exception):
                    logger.error(f"Error checking health for {dep.name}: {str(report)}")
                    continue
                    
                valid_reports.append(report)
            
            # Generate summary
            health_summary = self._generate_health_summary(valid_reports)
            
            # Find abandoned dependencies
            abandoned_deps = [
                r for r in valid_reports 
                if r["health_score"] < self.thresholds["abandoned"]
            ]
            
            # Find critical dependencies with health issues
            critical_deps_with_issues = [
                r for r in valid_reports 
                if r["is_direct"] and r["health_score"] < 0.6
            ]
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "average_health_score": health_summary["average_health_score"],
                "abandoned_count": len(abandoned_deps),
                "critical_with_issues_count": len(critical_deps_with_issues),
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            # Store health scores in database
            self._store_health_scores(valid_reports)
            
            return health_summary, valid_reports
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies health: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _check_dependency_health(
        self,
        dependency: DependencyInfo
    ) -> Dict[str, Any]:
        """
        Check the health of a single dependency.
        
        Args:
            dependency: Dependency information
            
        Returns:
            Dictionary with health metrics
        """
        health_report = {
            "name": dependency.name,
            "version": dependency.version,
            "ecosystem": dependency.ecosystem,
            "is_direct": dependency.is_direct,
            "health_score": 0.5,  # Default score
            "last_release": None,
            "days_since_update": None,
            "maintenance_status": "unknown",
            "community_metrics": {},
            "funding_status": "unknown",
            "risk_factors": [],
            "metadata": {}
        }
        
        try:
            # Check if we have the dependency in database
            db_dependency = (
                self.db.query(Dependency)
                .filter(Dependency.name == dependency.name)
                .filter(Dependency.ecosystem == dependency.ecosystem)
                .first()
            )
            
            if db_dependency and db_dependency.health_score is not None:
                # Check if the health score is recent enough
                if hasattr(db_dependency, "updated_at"):
                    last_check = db_dependency.updated_at
                    if (datetime.utcnow() - last_check).total_seconds() < self.check_interval:
                        # Use cached health score
                        health_report["health_score"] = db_dependency.health_score
                        health_report["metadata"] = db_dependency.metadata or {}
                        
                        if health_report["metadata"]:
                            health_report.update({
                                "last_release": health_report["metadata"].get("last_release"),
                                "days_since_update": health_report["metadata"].get("days_since_update"),
                                "maintenance_status": health_report["metadata"].get("maintenance_status", "unknown"),
                                "community_metrics": health_report["metadata"].get("community_metrics", {}),
                                "funding_status": health_report["metadata"].get("funding_status", "unknown"),
                                "risk_factors": health_report["metadata"].get("risk_factors", [])
                            })
                        
                        return health_report
            
            # Otherwise, fetch fresh data
            if dependency.ecosystem == "nodejs":
                await self._check_npm_package_health(dependency, health_report)
            elif dependency.ecosystem == "python":
                await self._check_pypi_package_health(dependency, health_report)
            
            # Check GitHub repository if available
            if dependency.repository_url and "github.com" in dependency.repository_url:
                await self._check_github_repo_health(dependency, health_report)
            
            # Calculate overall health score
            health_report["health_score"] = self._calculate_health_score(health_report)
            
            # Determine maintenance status
            if health_report["health_score"] >= self.thresholds["active"]:
                health_report["maintenance_status"] = "active"
            elif health_report["health_score"] <= self.thresholds["abandoned"]:
                health_report["maintenance_status"] = "abandoned"
                health_report["risk_factors"].append("abandoned_project")
            else:
                health_report["maintenance_status"] = "minimal"
            
        except Exception as e:
            logger.error(f"Error checking health for {dependency.name}: {str(e)}")
            health_report["risk_factors"].append("health_check_failed")
        
        return health_report
    
    async def _check_npm_package_health(
        self,
        dependency: DependencyInfo,
        health_report: Dict[str, Any]
    ) -> None:
        """
        Check health metrics for an npm package.
        
        Args:
            dependency: Dependency information
            health_report: Health report to update
        """
        try:
            # Query npm registry
            url = f"{settings.NPM_REGISTRY_URL}/{dependency.name}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for deprecation
                        if "deprecated" in data:
                            health_report["maintenance_status"] = "deprecated"
                            health_report["risk_factors"].append("deprecated")
                        
                        # Get download stats
                        downloads_url = f"https://api.npmjs.org/downloads/point/last-month/{dependency.name}"
                        async with session.get(downloads_url) as downloads_response:
                            if downloads_response.status == 200:
                                downloads_data = await downloads_response.json()
                                health_report["community_metrics"]["monthly_downloads"] = downloads_data.get("downloads", 0)
                        
                        # Get last release date
                        if "time" in data and "modified" in data["time"]:
                            modified_date = data["time"]["modified"]
                            last_update = datetime.fromisoformat(modified_date.replace("Z", "+00:00"))
                            days_since = (datetime.utcnow() - last_update).days
                            
                            health_report["last_release"] = modified_date
                            health_report["days_since_update"] = days_since
                            
                            # Add risk factor if not updated in a long time
                            if days_since > 365:
                                health_report["risk_factors"].append("outdated")
                        
                        # Check maintainers
                        if "maintainers" in data:
                            maintainers = data["maintainers"]
                            health_report["community_metrics"]["maintainer_count"] = len(maintainers)
                            
                            if not maintainers:
                                health_report["risk_factors"].append("no_maintainers")
                        
                        # Check repository info
                        if "repository" in data and isinstance(data["repository"], dict):
                            repo_url = data["repository"].get("url", "")
                            if repo_url and "github.com" not in repo_url:
                                health_report["metadata"]["repository"] = repo_url
        
        except Exception as e:
            logger.error(f"Error checking npm package health for {dependency.name}: {str(e)}")
            health_report["risk_factors"].append("npm_check_failed")
    
    async def _check_pypi_package_health(
        self,
        dependency: DependencyInfo,
        health_report: Dict[str, Any]
    ) -> None:
        """
        Check health metrics for a PyPI package.
        
        Args:
            dependency: Dependency information
            health_report: Health report to update
        """
        try:
            # Query PyPI
            url = f"{settings.PYPI_URL}/{dependency.name}/json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Get info section
                        info = data.get("info", {})
                        
                        # Check for yanked releases
                        yanked_releases = 0
                        if "releases" in data:
                            for version, files in data["releases"].items():
                                for file_info in files:
                                    if file_info.get("yanked", False):
                                        yanked_releases += 1
                            
                            health_report["metadata"]["yanked_releases"] = yanked_releases
                            if yanked_releases > 2:
                                health_report["risk_factors"].append("multiple_yanked_releases")
                        
                        # Check for last release date
                        if "releases" in data and data["releases"]:
                            latest_version = info.get("version", "")
                            if latest_version and latest_version in data["releases"]:
                                release_files = data["releases"][latest_version]
                                if release_files:
                                    upload_time = release_files[0].get("upload_time", "")
                                    if upload_time:
                                        last_update = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                                        days_since = (datetime.utcnow() - last_update).days
                                        
                                        health_report["last_release"] = upload_time
                                        health_report["days_since_update"] = days_since
                                        
                                        # Add risk factor if not updated in a long time
                                        if days_since > 730:  # 2 years
                                            health_report["risk_factors"].append("outdated")
                        
                        # Get description to check for abandonment messages
                        description = info.get("description", "").lower()
                        if any(term in description for term in ["deprecated", "abandoned", "no longer maintained"]):
                            health_report["maintenance_status"] = "deprecated"
                            health_report["risk_factors"].append("self_reported_deprecated")
                        
                        # Get project URLs for funding info
                        project_urls = info.get("project_urls", {})
                        funding_keys = ["funding", "sponsor", "donate", "donation"]
                        
                        for key, url in project_urls.items():
                            if any(term in key.lower() for term in funding_keys):
                                health_report["funding_status"] = "funded"
                                health_report["metadata"]["funding_url"] = url
                                break
                                
                        # Check download stats from PyPI Stats API if available
                        # Note: PyPI doesn't provide an official download stats API,
                        # so this is a placeholder for integration with services like pypistats.org
                        # stats_url = f"https://pypistats.org/api/packages/{dependency.name}/recent"
                        # async with session.get(stats_url) as stats_response:
                        #     if stats_response.status == 200:
                        #         stats_data = await stats_response.json()
                        #         health_report["community_metrics"]["monthly_downloads"] = stats_data.get("last_month", 0)
                        
                        # Check for GitHub repository
                        if "project_urls" in info:
                            for key, url in info["project_urls"].items():
                                if "github.com" in url:
                                    health_report["metadata"]["repository"] = url
                                    break
                        
                        # Check for Requires Python
                        if "requires_python" in info:
                            health_report["metadata"]["requires_python"] = info["requires_python"]
                            
                            # Check for very old Python version requirements
                            if "python_version < '3'" in info["requires_python"]:
                                health_report["risk_factors"].append("python2_only")
        
        except Exception as e:
            logger.error(f"Error checking PyPI package health for {dependency.name}: {str(e)}")
            health_report["risk_factors"].append("pypi_check_failed")
    
    async def _check_github_repo_health(
        self,
        dependency: DependencyInfo,
        health_report: Dict[str, Any]
    ) -> None:
        """
        Check health metrics for a GitHub repository.
        
        Args:
            dependency: Dependency information
            health_report: Health report to update
        """
        try:
            repo_url = dependency.repository_url
            
            # Clean up URL for API
            if repo_url.startswith("git+"):
                repo_url = repo_url[4:]
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]
            
            # Extract owner and repo name
            parts = repo_url.replace("https://github.com/", "").split("/")
            if len(parts) < 2:
                return
                
            owner, repo = parts[0], parts[1]
            
            # Set up headers for GitHub API
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            async with aiohttp.ClientSession() as session:
                # Get repository info
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Get basic stats
                        health_report["community_metrics"]["stars"] = data.get("stargazers_count", 0)
                        health_report["community_metrics"]["forks"] = data.get("forks_count", 0)
                        health_report["community_metrics"]["open_issues"] = data.get("open_issues_count", 0)
                        health_report["community_metrics"]["watchers"] = data.get("subscribers_count", 0)
                        
                        # Check if repo is archived
                        if data.get("archived", False):
                            health_report["maintenance_status"] = "archived"
                            health_report["risk_factors"].append("archived_repository")
                        
                        # Check last update
                        if "updated_at" in data:
                            updated_at = data["updated_at"]
                            last_update = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                            days_since = (datetime.utcnow() - last_update).days
                            
                            if not health_report["days_since_update"] or days_since < health_report["days_since_update"]:
                                health_report["days_since_update"] = days_since
                            
                            # Add risk factor if not updated in a long time
                            if days_since > 365:
                                health_report["risk_factors"].append("inactive_repository")
                        
                        # Check for funding
                        if data.get("has_sponsorship_file", False) or data.get("has_funding_file", False):
                            health_report["funding_status"] = "funded"
                    
                    elif response.status == 404:
                        health_report["risk_factors"].append("repository_not_found")
                    else:
                        health_report["risk_factors"].append("github_api_error")
                
                # Get commit activity
                commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
                params = {"per_page": 1}
                
                async with session.get(commits_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        last_commit_date = response.headers.get("Last-Modified")
                        if last_commit_date:
                            last_commit = datetime.strptime(last_commit_date, "%a, %d %b %Y %H:%M:%S GMT")
                            days_since_commit = (datetime.utcnow() - last_commit).days
                            health_report["community_metrics"]["days_since_last_commit"] = days_since_commit
                            
                            # Add risk factor if no commits in a long time
                            if days_since_commit > 180:
                                health_report["risk_factors"].append("stale_repository")
                
                # Check for contributor activity
                contributors_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
                params = {"per_page": 10}
                
                async with session.get(contributors_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        contributors_data = await response.json()
                        health_report["community_metrics"]["contributor_count"] = len(contributors_data)
                        
                        # Calculate distribution of contributions
                        if contributors_data:
                            total_contributions = sum(c.get("contributions", 0) for c in contributors_data)
                            max_contributions = max(c.get("contributions", 0) for c in contributors_data)
                            
                            # Gini coefficient for contribution inequality (0 = equal, 1 = unequal)
                            if total_contributions > 0:
                                main_contributor_share = max_contributions / total_contributions
                                health_report["community_metrics"]["main_contributor_share"] = main_contributor_share
                                
                                # Risk factor if one contributor made almost all changes
                                if main_contributor_share > 0.9 and len(contributors_data) > 1:
                                    health_report["risk_factors"].append("bus_factor_1")
                
                # Check issue response time
                issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
                params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": 10}
                
                async with session.get(issues_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        issues_data = await response.json()
                        
                        if issues_data:
                            # Check how many issues were closed
                            closed_issues = sum(1 for i in issues_data if i.get("state") == "closed")
                            closed_ratio = closed_issues / len(issues_data) if issues_data else 0
                            health_report["community_metrics"]["closed_issue_ratio"] = closed_ratio
                            
                            # Check average age of open issues
                            open_issues = [i for i in issues_data if i.get("state") == "open"]
                            if open_issues:
                                avg_age_days = 0
                                for issue in open_issues:
                                    created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                                    age_days = (datetime.utcnow() - created_at).days
                                    avg_age_days += age_days
                                
                                avg_age_days /= len(open_issues)
                                health_report["community_metrics"]["avg_issue_age_days"] = avg_age_days
                                
                                # Risk factor if average issue age is very high
                                if avg_age_days > 180:
                                    health_report["risk_factors"].append("slow_issue_response")
                
                # Check pull request merge ratio
                prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
                params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": 10}
                
                async with session.get(prs_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        prs_data = await response.json()
                        
                        if prs_data:
                            # Check how many PRs were merged
                            merged_prs = sum(1 for pr in prs_data if pr.get("merged_at") is not None)
                            merged_ratio = merged_prs / len(prs_data) if prs_data else 0
                            health_report["community_metrics"]["pr_merge_ratio"] = merged_ratio
                            
                            # Risk factor if very few PRs are being merged
                            if merged_ratio < 0.2 and len(prs_data) >= 5:
                                health_report["risk_factors"].append("low_pr_acceptance")
        
        except Exception as e:
            logger.error(f"Error checking GitHub repo health for {dependency.name}: {str(e)}")
            health_report["risk_factors"].append("github_check_failed")
    
    def _calculate_health_score(self, health_report: Dict[str, Any]) -> float:
        """
        Calculate overall health score from metrics.
        
        Args:
            health_report: Health report with metrics
            
        Returns:
            Health score (0-1)
        """
        score = 0.5  # Default score
        metrics_count = 0
        
        # Adjust based on activity
        if health_report["days_since_update"] is not None:
            days = health_report["days_since_update"]
            
            # Logarithmic scaling for days since update
            # Fresh: 0-30 days = 0.9-1.0
            # Recent: 30-180 days = 0.7-0.9
            # Aging: 180-365 days = 0.5-0.7
            # Old: 365-730 days = 0.3-0.5
            # Ancient: >730 days = 0.1-0.3
            
            if days <= 30:
                activity_score = 1.0 - (days / 300)
            elif days <= 180:
                activity_score = 0.9 - ((days - 30) / 1500)
            elif days <= 365:
                activity_score = 0.7 - ((days - 180) / 1850)
            elif days <= 730:
                activity_score = 0.5 - ((days - 365) / 3650)
            else:
                activity_score = 0.3 - min(0.2, (days - 730) / 10000)
            
            score += activity_score
            metrics_count += 1
        
        # Adjust based on community metrics
        community_metrics = health_report["community_metrics"]
        
        if "stars" in community_metrics:
            stars = community_metrics["stars"]
            # Logarithmic scaling for stars
            star_score = min(0.8, 0.2 + (0.2 * np.log10(stars + 1)))
            score += star_score
            metrics_count += 1
        
        if "monthly_downloads" in community_metrics:
            downloads = community_metrics["monthly_downloads"]
            # Logarithmic scaling for downloads
            if downloads > 0:
                download_score = min(0.8, 0.2 + (0.2 * np.log10(downloads)))
                score += download_score
                metrics_count += 1
        
        if "contributor_count" in community_metrics:
            contributors = community_metrics["contributor_count"]
            # More contributors is better, but with diminishing returns
            contributor_score = min(0.8, 0.3 + (0.1 * np.log10(contributors + 1)))
            score += contributor_score
            metrics_count += 1
        
        if "days_since_last_commit" in community_metrics:
            days = community_metrics["days_since_last_commit"]
            # Fresh commits are good
            if days <= 30:
                commit_score = 0.8
            elif days <= 90:
                commit_score = 0.6
            elif days <= 180:
                commit_score = 0.4
            else:
                commit_score = 0.2
            
            score += commit_score
            metrics_count += 1
        
        if "closed_issue_ratio" in community_metrics:
            ratio = community_metrics["closed_issue_ratio"]
            # Higher close ratio is better, but not if it's suspiciously high
            if ratio > 0.95:
                issue_score = 0.7  # Might be ignoring issues
            else:
                issue_score = 0.4 + (ratio * 0.4)
            
            score += issue_score
            metrics_count += 1
        
        if "pr_merge_ratio" in community_metrics:
            ratio = community_metrics["pr_merge_ratio"]
            # Higher merge ratio is better, but not if it's suspiciously high
            if ratio > 0.95:
                pr_score = 0.7  # Might be auto-merging everything
            else:
                pr_score = 0.4 + (ratio * 0.4)
            
            score += pr_score
            metrics_count += 1
        
        if "main_contributor_share" in community_metrics:
            share = community_metrics["main_contributor_share"]
            # Lower share is better (more distributed maintenance)
            contrib_score = 0.8 - (share * 0.6)
            score += contrib_score
            metrics_count += 1
        
        # Adjust for maintenance status
        status = health_report["maintenance_status"]
        if status == "active":
            score += 0.8
            metrics_count += 1
        elif status == "minimal":
            score += 0.4
            metrics_count += 1
        elif status == "deprecated" or status == "archived":
            score += 0.1
            metrics_count += 1
        
        # Adjust for funding
        if health_report["funding_status"] == "funded":
            score += 0.7
            metrics_count += 1
        
        # Penalize for risk factors
        risk_count = len(health_report["risk_factors"])
        if risk_count > 0:
            # Penalize more severely for more risk factors
            risk_penalty = min(0.6, risk_count * 0.15)
            score -= risk_penalty
        
        # Calculate average score
        if metrics_count > 0:
            score = score / metrics_count
        
        # Ensure score is between 0.1 and 1.0
        return max(0.1, min(score, 1.0))
    
    def _generate_health_summary(
        self,
        health_reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a summary of dependency health metrics.
        
        Args:
            health_reports: List of health reports
            
        Returns:
            Summary of health metrics
        """
        if not health_reports:
            return {
                "dependency_count": 0,
                "average_health_score": 0,
                "health_distribution": {},
                "risk_factors": {}
            }
        
        # Extract health scores
        health_scores = [r["health_score"] for r in health_reports]
        
        # Calculate health distribution
        health_distribution = {
            "healthy": len([s for s in health_scores if s >= 0.7]),
            "moderate": len([s for s in health_scores if 0.4 <= s < 0.7]),
            "at_risk": len([s for s in health_scores if s < 0.4])
        }
        
        # Calculate percentages
        total = len(health_scores)
        health_distribution_pct = {
            k: round((v / total) * 100, 1) if total > 0 else 0 
            for k, v in health_distribution.items()
        }
        
        # Count risk factors
        risk_factors = {}
        for report in health_reports:
            for risk in report["risk_factors"]:
                risk_factors[risk] = risk_factors.get(risk, 0) + 1
        
        # Find top risk factors
        top_risks = sorted(
            [{"name": k, "count": v} for k, v in risk_factors.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        # Create summary
        summary = {
            "dependency_count": len(health_reports),
            "average_health_score": round(sum(health_scores) / len(health_scores), 2) if health_scores else 0,
            "median_health_score": round(np.median(health_scores), 2) if health_scores else 0,
            "health_distribution": health_distribution,
            "health_distribution_pct": health_distribution_pct,
            "risk_factors": top_risks[:5],  # Top 5 risk factors
            "active_dependencies": len([r for r in health_reports if r["maintenance_status"] == "active"]),
            "deprecated_dependencies": len([r for r in health_reports if r["maintenance_status"] in ["deprecated", "archived"]]),
            "outdated_dependencies": len([r for r in health_reports if r.get("days_since_update", 0) and r["days_since_update"] > 365])
        }
        
        return summary
    
    def _store_health_scores(self, health_reports: List[Dict[str, Any]]) -> None:
        """
        Store health scores in the database.
        
        Args:
            health_reports: List of health reports
        """
        try:
            for report in health_reports:
                name = report["name"]
                ecosystem = report["ecosystem"]
                
                # Get or create dependency record
                dependency = (
                    self.db.query(Dependency)
                    .filter(Dependency.name == name)
                    .filter(Dependency.ecosystem == ecosystem)
                    .first()
                )
                
                if not dependency:
                    dependency = Dependency(
                        name=name,
                        ecosystem=ecosystem
                    )
                    self.db.add(dependency)
                
                # Update health data
                dependency.health_score = report["health_score"]
                dependency.is_deprecated = report["maintenance_status"] in ["deprecated", "archived"]
                
                # Store metadata
                metadata = dependency.metadata or {}
                metadata.update({
                    "last_release": report["last_release"],
                    "days_since_update": report["days_since_update"],
                    "maintenance_status": report["maintenance_status"],
                    "community_metrics": report["community_metrics"],
                    "funding_status": report["funding_status"],
                    "risk_factors": report["risk_factors"],
                    "last_check": datetime.utcnow().isoformat()
                })
                dependency.metadata = metadata
                
                # Store latest version if available
                if not dependency.latest_version:
                    dependency.latest_version = report["version"]
            
            # Commit changes
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error storing health scores: {str(e)}")
            self.db.rollback()
    
    async def get_update_recommendations(
        self,
        dependencies: List[DependencyInfo],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations for updating dependencies based on health metrics.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            
        Returns:
            List of update recommendations
        """
        # Check health first
        health_summary, health_reports = await self.analyze_dependencies_health(
            dependencies, project_id
        )
        
        recommendations = []
        
        # Find deprecated dependencies
        deprecated_deps = [
            r for r in health_reports 
            if r["maintenance_status"] in ["deprecated", "archived"]
        ]
        
        for dep in deprecated_deps:
            rec = {
                "dependency": dep["name"],
                "ecosystem": dep["ecosystem"],
                "current_version": dep["version"],
                "recommendation_type": "replace",
                "urgency": "high" if dep["is_direct"] else "medium",
                "reason": f"Dependency is {dep['maintenance_status']}",
                "risk_level": "high"
            }
            
            # Try to suggest an alternative
            alternative = await self._find_alternative(dep)
            if alternative:
                rec["suggested_action"] = f"Replace with {alternative['name']}"
                rec["alternative"] = alternative
            else:
                rec["suggested_action"] = "Find a replacement"
            
            recommendations.append(rec)
        
        # Find unhealthy but active dependencies
        at_risk_deps = [
            r for r in health_reports 
            if r["health_score"] < 0.4 and r["maintenance_status"] not in ["deprecated", "archived"]
        ]
        
        for dep in at_risk_deps:
            risk_reasons = ", ".join(dep["risk_factors"][:3])
            
            rec = {
                "dependency": dep["name"],
                "ecosystem": dep["ecosystem"],
                "current_version": dep["version"],
                "recommendation_type": "monitor",
                "urgency": "medium" if dep["is_direct"] else "low",
                "reason": f"Dependency has health issues: {risk_reasons}",
                "risk_level": "medium"
            }
            
            # Check if we should suggest an alternative
            if dep["health_score"] < 0.3:
                alternative = await self._find_alternative(dep)
                if alternative:
                    rec["recommendation_type"] = "consider_replacement"
                    rec["suggested_action"] = f"Consider replacing with {alternative['name']}"
                    rec["alternative"] = alternative
                else:
                    rec["suggested_action"] = "Closely monitor for further deterioration"
            else:
                rec["suggested_action"] = "Monitor health metrics"
            
            recommendations.append(rec)
        
        # Find outdated dependencies
        outdated_deps = [
            r for r in health_reports 
            if r.get("days_since_update", 0) and r["days_since_update"] > 365
            and r["health_score"] >= 0.4  # Don't duplicate recommendations
            and r["maintenance_status"] not in ["deprecated", "archived"]
        ]
        
        for dep in outdated_deps:
            rec = {
                "dependency": dep["name"],
                "ecosystem": dep["ecosystem"],
                "current_version": dep["version"],
                "recommendation_type": "update_available",
                "urgency": "low",
                "reason": f"No updates in {dep['days_since_update']} days",
                "risk_level": "low",
                "suggested_action": "Check for newer alternatives"
            }
            
            recommendations.append(rec)
        
        return sorted(recommendations, key=lambda x: 
            (0 if x["urgency"] == "high" else 
             1 if x["urgency"] == "medium" else 2)
        )
    
    async def _find_alternative(self, dependency: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find an alternative for a problematic dependency.
        
        Args:
            dependency: Dependency information
            
        Returns:
            Suggested alternative or None
        """
        # This would ideally query a service or database to find alternatives
        # For now, we'll return mock data for demonstration
        
        name = dependency["name"]
        ecosystem = dependency["ecosystem"]
        
        # Some common alternatives for popular packages
        alternatives = {
            "python": {
                "requests": {"name": "httpx", "reason": "More modern HTTP client with async support"},
                "django": {"name": "fastapi", "reason": "Modern, high-performance web framework"},
                "flask": {"name": "fastapi", "reason": "More performant alternative with automatic docs"},
                "numpy": {"name": "jax", "reason": "Drop-in replacement with GPU support"},
                "matplotlib": {"name": "plotly", "reason": "Interactive visualizations"},
                "opencv-python": {"name": "pillow", "reason": "Lighter alternative for basic image processing"}
            },
            "nodejs": {
                "request": {"name": "axios", "reason": "Maintained alternative with Promise support"},
                "moment": {"name": "date-fns", "reason": "Lighter, more modular date library"},
                "underscore": {"name": "lodash", "reason": "More comprehensive utility library"},
                "express": {"name": "fastify", "reason": "More performant web framework"},
                "jade": {"name": "pug", "reason": "Maintained fork of Jade"},
                "gulp": {"name": "webpack", "reason": "More modern build tool"}
            }
        }
        
        return alternatives.get(ecosystem, {}).get(name)


# Factory function
def get_health_monitor(db: Session) -> HealthMonitor:
    """Get an instance of the health monitor."""
    return HealthMonitor(db)