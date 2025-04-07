import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple, Union
import aiohttp
import asyncio
import re
from sqlalchemy.orm import Session

from backend.core.models import Analysis, Project, Dependency, DependencyVersion
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CompatibilityPredictor:
    """
    Predictive dependency management service for forecasting future compatibility 
    issues based on library development trajectories and deprecation notices.
    
    Key features:
    1. Compatibility forecasting - predict future compatibility issues
    2. Roadmap alignment - connect with library roadmaps to predict changes
    3. Breaking change timeline - create timelines for breaking changes
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.github_token = settings.GITHUB_API_TOKEN
        self.npm_registry_url = settings.NPM_REGISTRY_URL
        self.pypi_url = settings.PYPI_URL
    
    async def predict_compatibility_issues(
        self,
        dependencies: List[DependencyInfo],
        project_id: str,
        time_horizon: int = 180  # Default: 6 months
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Predict future compatibility issues for a list of dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            time_horizon: Time horizon in days for predictions
            
        Returns:
            Tuple of (timeline of events, aggregated results)
        """
        logger.info(f"Predicting compatibility issues for {len(dependencies)} dependencies")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="compatibility_prediction",
            status="running",
            config={
                "dependency_count": len(dependencies),
                "time_horizon": time_horizon
            }
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Initialize timeline and results
            timeline = {}
            results = {
                "dependency_issues": {},
                "issue_counts": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0
                },
                "total_dependencies": len(dependencies),
                "affected_dependencies": 0,
                "time_horizon_days": time_horizon
            }
            
            # Process direct dependencies first (they're more important)
            direct_deps = [d for d in dependencies if d.is_direct]
            transitive_deps = [d for d in dependencies if not d.is_direct]
            
            # Create tasks for fetching metadata
            tasks = []
            for dep in direct_deps:
                tasks.append(self._analyze_dependency_trajectory(dep, time_horizon))
            
            # Gather direct dependency results
            direct_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Add direct dependency results to timeline
            for dep, result in zip(direct_deps, direct_results):
                if isinstance(result, Exception):
                    logger.error(f"Error analyzing {dep.name}: {str(result)}")
                    continue
                    
                dep_issues, dep_timeline = result
                
                # Add to timeline
                for date_str, events in dep_timeline.items():
                    if date_str not in timeline:
                        timeline[date_str] = []
                    timeline[date_str].extend(events)
                
                # Add to results
                if dep_issues:
                    results["dependency_issues"][dep.name] = dep_issues
                    results["affected_dependencies"] += 1
                    
                    # Count by severity
                    highest_severity = dep_issues.get("severity", "low")
                    results["issue_counts"][highest_severity] += 1
            
            # Process a subset of transitive dependencies to avoid overloading
            max_transitive = min(len(transitive_deps), 50)
            selected_transitive = transitive_deps[:max_transitive]
            
            # Create tasks for transitive dependencies
            tasks = []
            for dep in selected_transitive:
                tasks.append(self._analyze_dependency_trajectory(dep, time_horizon))
            
            # Gather transitive dependency results
            transitive_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Add transitive dependency results to timeline
            for dep, result in zip(selected_transitive, transitive_results):
                if isinstance(result, Exception):
                    continue
                    
                dep_issues, dep_timeline = result
                
                # Add to timeline with lower priority
                for date_str, events in dep_timeline.items():
                    if date_str not in timeline:
                        timeline[date_str] = []
                    
                    # Mark as transitive and add to timeline
                    for event in events:
                        event["is_transitive"] = True
                    timeline[date_str].extend(events)
                
                # Add to results
                if dep_issues:
                    results["dependency_issues"][dep.name] = dep_issues
                    results["affected_dependencies"] += 1
                    
                    # Count by severity
                    highest_severity = dep_issues.get("severity", "low")
                    results["issue_counts"][highest_severity] += 1
            
            # Sort timeline by date
            sorted_timeline = dict(sorted(timeline.items()))
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "summary": results,
                "timeline_count": len(sorted_timeline),
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return sorted_timeline, results
            
        except Exception as e:
            logger.error(f"Error predicting compatibility issues: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _analyze_dependency_trajectory(
        self,
        dependency: DependencyInfo,
        time_horizon: int
    ) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
        """
        Analyze a dependency's trajectory to predict future issues.
        
        Args:
            dependency: Dependency information
            time_horizon: Time horizon in days
            
        Returns:
            Tuple of (dependency issues, timeline events)
        """
        # Initialize results
        dependency_issues = {}
        timeline_events = {}
        
        try:
            # Get current version
            current_version = dependency.version
            
            # Get version history
            version_history = await self._fetch_version_history(dependency)
            
            # Analyze release patterns to predict future releases
            predicted_releases = self._predict_future_releases(
                dependency.name, 
                version_history, 
                time_horizon
            )
            
            # Analyze deprecation signals
            deprecation_info = await self._check_deprecation_signals(dependency)
            
            # Analyze breaking changes in recent versions
            breaking_changes = await self._analyze_breaking_changes(dependency, version_history)
            
            # Check for maintenance issues
            maintenance_issues = await self._check_maintenance_issues(dependency)
            
            # Combine all signals to determine compatibility issues
            severity = "low"
            issues = []
            
            # Add predicted major and minor releases to timeline
            for release in predicted_releases:
                release_date = release["predicted_date"]
                date_str = release_date.strftime("%Y-%m-%d")
                
                event = {
                    "date": date_str,
                    "dependency": dependency.name,
                    "event_type": "predicted_release",
                    "version": release["version"],
                    "is_major": release["is_major"],
                    "is_minor": release["is_minor"],
                    "confidence": release["confidence"],
                    "details": f"Predicted {release['version']} release based on historical patterns"
                }
                
                if date_str not in timeline_events:
                    timeline_events[date_str] = []
                    
                timeline_events[date_str].append(event)
                
                # Major versions are potential breaking changes
                if release["is_major"]:
                    issues.append({
                        "type": "major_version_change",
                        "version": release["version"],
                        "predicted_date": date_str,
                        "confidence": release["confidence"],
                        "details": "Major version update may contain breaking changes"
                    })
                    severity = max(severity, "medium")
            
            # Add deprecation info if found
            if deprecation_info.get("is_deprecated", False):
                date_str = deprecation_info.get("deprecation_date", datetime.utcnow().strftime("%Y-%m-%d"))
                
                event = {
                    "date": date_str,
                    "dependency": dependency.name,
                    "event_type": "deprecation",
                    "details": deprecation_info.get("message", "Package is deprecated"),
                    "alternatives": deprecation_info.get("alternatives", [])
                }
                
                if date_str not in timeline_events:
                    timeline_events[date_str] = []
                    
                timeline_events[date_str].append(event)
                
                issues.append({
                    "type": "deprecation",
                    "date": date_str,
                    "message": deprecation_info.get("message", "Package is deprecated"),
                    "alternatives": deprecation_info.get("alternatives", [])
                })
                
                severity = max(severity, "high")
            
            # Add breaking changes to issues and timeline
            for change in breaking_changes:
                change_version = change.get("version")
                
                # Skip if version is current or older
                if change_version and self._compare_versions(change_version, current_version) <= 0:
                    continue
                
                # Add to issues
                issues.append({
                    "type": "breaking_change",
                    "version": change_version,
                    "description": change.get("description", "Unknown breaking change"),
                    "impact": change.get("impact", "unknown")
                })
                
                # Find or estimate the date for this version
                change_date = change.get("date")
                if not change_date:
                    # Look for this version in predicted releases
                    matching_releases = [r for r in predicted_releases if r["version"] == change_version]
                    if matching_releases:
                        change_date = matching_releases[0]["predicted_date"].strftime("%Y-%m-%d")
                    else:
                        # Use a default date in the middle of the time horizon
                        mid_horizon = datetime.utcnow() + timedelta(days=time_horizon//2)
                        change_date = mid_horizon.strftime("%Y-%m-%d")
                
                # Add to timeline
                if change_date not in timeline_events:
                    timeline_events[change_date] = []
                    
                timeline_events[change_date].append({
                    "date": change_date,
                    "dependency": dependency.name,
                    "event_type": "breaking_change",
                    "version": change_version,
                    "details": change.get("description", "Breaking change expected"),
                    "impact": change.get("impact", "unknown")
                })
                
                severity = max(severity, "high")
            
            # Add maintenance issues
            if maintenance_issues.get("has_issues", False):
                issue_date = maintenance_issues.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
                
                # Add to timeline
                if issue_date not in timeline_events:
                    timeline_events[issue_date] = []
                    
                timeline_events[issue_date].append({
                    "date": issue_date,
                    "dependency": dependency.name,
                    "event_type": "maintenance_issue",
                    "details": maintenance_issues.get("description", "Maintenance issues detected")
                })
                
                issues.append({
                    "type": "maintenance_issue",
                    "details": maintenance_issues.get("description", "Maintenance issues detected"),
                    "metrics": maintenance_issues.get("metrics", {})
                })
                
                severity = max(severity, "medium")
            
            # If we found issues, add them to the result
            if issues:
                dependency_issues = {
                    "name": dependency.name,
                    "current_version": current_version,
                    "issues": issues,
                    "severity": severity,
                    "is_direct": dependency.is_direct
                }
            
            return dependency_issues, timeline_events
            
        except Exception as e:
            logger.error(f"Error analyzing trajectory for {dependency.name}: {str(e)}")
            return {}, {}
    
    async def _fetch_version_history(
        self,
        dependency: DependencyInfo
    ) -> List[Dict[str, Any]]:
        """
        Fetch version history for a dependency.
        
        Args:
            dependency: Dependency information
            
        Returns:
            List of versions with release dates
        """
        versions = []
        
        try:
            if dependency.ecosystem == "nodejs":
                # Fetch from npm registry
                url = f"{self.npm_registry_url}/{dependency.name}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "versions" in data and "time" in data:
                                for version, timestamp in data["time"].items():
                                    if version not in ["created", "modified"]:
                                        try:
                                            release_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                            versions.append({
                                                "version": version,
                                                "date": release_date,
                                                "is_prerelease": self._is_prerelease(version)
                                            })
                                        except ValueError:
                                            pass
            
            elif dependency.ecosystem == "python":
                # Fetch from PyPI
                url = f"{self.pypi_url}/{dependency.name}/json"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "releases" in data:
                                for version, release_info in data["releases"].items():
                                    if release_info and isinstance(release_info, list):
                                        try:
                                            # Get upload time from first release file
                                            upload_time = release_info[0].get("upload_time")
                                            if upload_time:
                                                release_date = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                                                versions.append({
                                                    "version": version,
                                                    "date": release_date,
                                                    "is_prerelease": self._is_prerelease(version)
                                                })
                                        except (ValueError, IndexError):
                                            pass
            
            # Sort versions by date
            versions.sort(key=lambda x: x["date"])
            
        except Exception as e:
            logger.error(f"Error fetching version history for {dependency.name}: {str(e)}")
        
        return versions
    
    def _predict_future_releases(
        self,
        dependency_name: str,
        version_history: List[Dict[str, Any]],
        time_horizon: int
    ) -> List[Dict[str, Any]]:
        """
        Predict future releases based on historical release patterns.
        
        Args:
            dependency_name: Dependency name
            version_history: Version history
            time_horizon: Time horizon in days
            
        Returns:
            List of predicted releases
        """
        predicted_releases = []
        
        if not version_history:
            return predicted_releases
        
        try:
            # Filter out prereleases
            stable_releases = [v for v in version_history if not v["is_prerelease"]]
            
            if len(stable_releases) < 2:
                return predicted_releases
            
            # Get time deltas between releases
            release_intervals = []
            major_intervals = []
            minor_intervals = []
            
            last_major = None
            last_minor = None
            
            for i in range(1, len(stable_releases)):
                current = stable_releases[i]
                previous = stable_releases[i-1]
                
                # Get version components
                curr_parts = self._parse_version(current["version"])
                prev_parts = self._parse_version(previous["version"])
                
                if not curr_parts or not prev_parts:
                    continue
                
                interval = (current["date"] - previous["date"]).days
                
                # Skip unreasonable intervals (e.g., same-day releases or very long gaps)
                if interval <= 0 or interval > 365:
                    continue
                    
                release_intervals.append(interval)
                
                # Track major version changes
                if curr_parts[0] > prev_parts[0]:
                    if last_major:
                        major_interval = (current["date"] - last_major["date"]).days
                        if 30 <= major_interval <= 1000:  # Reasonable range
                            major_intervals.append(major_interval)
                    last_major = current
                
                # Track minor version changes
                if curr_parts[0] == prev_parts[0] and curr_parts[1] > prev_parts[1]:
                    if last_minor:
                        minor_interval = (current["date"] - last_minor["date"]).days
                        if 7 <= minor_interval <= 180:  # Reasonable range
                            minor_intervals.append(minor_interval)
                    last_minor = current
            
            # Calculate average intervals
            avg_interval = sum(release_intervals) / len(release_intervals) if release_intervals else 90
            avg_major_interval = sum(major_intervals) / len(major_intervals) if major_intervals else 365
            avg_minor_interval = sum(minor_intervals) / len(minor_intervals) if minor_intervals else 45
            
            # Get latest version
            latest_release = stable_releases[-1]
            latest_version = latest_release["version"]
            latest_date = latest_release["date"]
            latest_parts = self._parse_version(latest_version)
            
            if not latest_parts:
                return predicted_releases
            
            # Predict patch releases
            next_date = latest_date
            while (next_date - datetime.utcnow()).days < time_horizon:
                next_date = next_date + timedelta(days=int(avg_interval))
                
                # Skip if beyond time horizon
                if (next_date - datetime.utcnow()).days > time_horizon:
                    break
                
                confidence = 0.7  # Base confidence for patch releases
                
                # Adjust confidence based on consistency of release intervals
                if release_intervals:
                    interval_std = (sum((x - avg_interval) ** 2 for x in release_intervals) / len(release_intervals)) ** 0.5
                    consistency = max(0.3, min(0.9, 1.0 - (interval_std / avg_interval / 2)))
                    confidence *= consistency
                
                # Basic patch increment
                next_patch = latest_parts[2] + 1
                next_version = f"{latest_parts[0]}.{latest_parts[1]}.{next_patch}"
                
                predicted_releases.append({
                    "version": next_version,
                    "predicted_date": next_date,
                    "is_major": False,
                    "is_minor": False,
                    "confidence": confidence
                })
            
            # Predict minor releases
            if avg_minor_interval and latest_parts:
                next_minor_date = latest_date
                while (next_minor_date - datetime.utcnow()).days < time_horizon:
                    next_minor_date = next_minor_date + timedelta(days=int(avg_minor_interval))
                    
                    # Skip if beyond time horizon
                    if (next_minor_date - datetime.utcnow()).days > time_horizon:
                        break
                    
                    confidence = 0.6  # Base confidence for minor releases
                    
                    # Adjust confidence based on consistency
                    if minor_intervals:
                        interval_std = (sum((x - avg_minor_interval) ** 2 for x in minor_intervals) / len(minor_intervals)) ** 0.5
                        consistency = max(0.3, min(0.9, 1.0 - (interval_std / avg_minor_interval / 2)))
                        confidence *= consistency
                    
                    next_minor = latest_parts[1] + 1
                    next_version = f"{latest_parts[0]}.{next_minor}.0"
                    
                    predicted_releases.append({
                        "version": next_version,
                        "predicted_date": next_minor_date,
                        "is_major": False,
                        "is_minor": True,
                        "confidence": confidence
                    })
            
            # Predict major releases
            if avg_major_interval and latest_parts:
                next_major_date = latest_date
                while (next_major_date - datetime.utcnow()).days < time_horizon:
                    next_major_date = next_major_date + timedelta(days=int(avg_major_interval))
                    
                    # Skip if beyond time horizon
                    if (next_major_date - datetime.utcnow()).days > time_horizon:
                        break
                    
                    confidence = 0.5  # Base confidence for major releases
                    
                    # Adjust confidence based on consistency
                    if major_intervals:
                        interval_std = (sum((x - avg_major_interval) ** 2 for x in major_intervals) / len(major_intervals)) ** 0.5
                        consistency = max(0.3, min(0.9, 1.0 - (interval_std / avg_major_interval / 2)))
                        confidence *= consistency
                    
                    next_major = latest_parts[0] + 1
                    next_version = f"{next_major}.0.0"
                    
                    predicted_releases.append({
                        "version": next_version,
                        "predicted_date": next_major_date,
                        "is_major": True,
                        "is_minor": False,
                        "confidence": confidence
                    })
            
            # Sort by date
            predicted_releases.sort(key=lambda x: x["predicted_date"])
            
        except Exception as e:
            logger.error(f"Error predicting releases for {dependency_name}: {str(e)}")
        
        return predicted_releases
    
    async def _check_deprecation_signals(
        self,
        dependency: DependencyInfo
    ) -> Dict[str, Any]:
        """
        Check for deprecation signals in package metadata.
        
        Args:
            dependency: Dependency information
            
        Returns:
            Dictionary with deprecation information
        """
        result = {
            "is_deprecated": False,
            "message": "",
            "alternatives": [],
            "deprecation_date": None
        }
        
        try:
            if dependency.ecosystem == "nodejs":
                # Check npm registry for deprecation info
                url = f"{self.npm_registry_url}/{dependency.name}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Check for deprecation flags
                            if "deprecated" in data:
                                result["is_deprecated"] = True
                                result["message"] = data["deprecated"]
                                
                            # Check latest version for deprecation
                            if "versions" in data and "dist-tags" in data and "latest" in data["dist-tags"]:
                                latest = data["dist-tags"]["latest"]
                                if latest in data["versions"] and "deprecated" in data["versions"][latest]:
                                    result["is_deprecated"] = True
                                    result["message"] = data["versions"][latest]["deprecated"]
                            
                            # Look for maintenance notice
                            if "maintainers" in data and not data["maintainers"]:
                                result["is_deprecated"] = True
                                result["message"] = "Package has no maintainers"
            
            elif dependency.ecosystem == "python":
                # Check PyPI for deprecation info
                url = f"{self.pypi_url}/{dependency.name}/json"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Check info for deprecation notices
                            if "info" in data:
                                info = data["info"]
                                
                                # Check description and summary for deprecation keywords
                                description = info.get("description", "").lower()
                                summary = info.get("summary", "").lower()
                                
                                deprecation_keywords = [
                                    "deprecated", 
                                    "no longer maintained", 
                                    "maintenance mode",
                                    "not supported",
                                    "abandoned"
                                ]
                                
                                for keyword in deprecation_keywords:
                                    if keyword in description or keyword in summary:
                                        result["is_deprecated"] = True
                                        result["message"] = f"Package appears to be deprecated (detected '{keyword}')"
                                        break
                                        
                                # Check for alternative packages
                                for keyword in ["use instead", "replaced by", "alternative"]:
                                    if keyword in description or keyword in summary:
                                        # Try to extract alternative package names
                                        alternatives = re.findall(r'`([a-zA-Z0-9_-]+)`', description)
                                        alternatives.extend(re.findall(r'"([a-zA-Z0-9_-]+)"', description))
                                        
                                        if alternatives:
                                            result["alternatives"] = list(set(alternatives))
            
            # Check explicit deprecation in dependency info
            if dependency.metadata.get("deprecated", False) or getattr(dependency, "is_deprecated", False):
                result["is_deprecated"] = True
                result["message"] = dependency.metadata.get("deprecation_message", "Package is deprecated")
                
            # If deprecated, try to set a date
            if result["is_deprecated"] and not result["deprecation_date"]:
                # Default to current date if we don't have a specific deprecation date
                result["deprecation_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                
        except Exception as e:
            logger.error(f"Error checking deprecation for {dependency.name}: {str(e)}")
        
        return result
    
    async def _analyze_breaking_changes(
        self,
        dependency: DependencyInfo,
        version_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze breaking changes in a dependency's version history.
        
        Args:
            dependency: Dependency information
            version_history: Version history
            
        Returns:
            List of breaking changes
        """
        breaking_changes = []
        
        try:
            # Look for major version bumps in history (indicator of breaking changes)
            current_version_parts = self._parse_version(dependency.version)
            if not current_version_parts:
                return breaking_changes
                
            current_major = current_version_parts[0]
            
            # Group versions by major version
            major_versions = {}
            for release in version_history:
                version = release["version"]
                parts = self._parse_version(version)
                if not parts:
                    continue
                    
                major = parts[0]
                if major not in major_versions:
                    major_versions[major] = []
                    
                major_versions[major].append(release)
            
            # Look for major versions after current
            future_majors = [v for v in major_versions.keys() if v > current_major]
            
            for major in future_majors:
                if major in major_versions and major_versions[major]:
                    # Get first release of this major version
                    first_release = sorted(major_versions[major], key=lambda x: x["date"])[0]
                    
                    breaking_changes.append({
                        "version": f"{major}.0.0",
                        "date": first_release["date"].strftime("%Y-%m-%d"),
                        "description": f"Major version {major}.0.0 may contain breaking changes",
                        "impact": "high"
                    })
            
            # If we have GitHub token, try to fetch additional info from repo
            if self.github_token and dependency.repository_url and "github.com" in dependency.repository_url:
                repo_url = dependency.repository_url
                if repo_url.startswith("git+"):
                    repo_url = repo_url[4:]
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                
                # Extract owner and repo
                parts = repo_url.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    
                    # Check release notes for breaking changes
                    headers = {"Authorization": f"token {self.github_token}"}
                    releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(releases_url, headers=headers) as response:
                            if response.status == 200:
                                releases_data = await response.json()
                                
                                for release in releases_data:
                                    body = release.get("body", "").lower()
                                    tag_name = release.get("tag_name", "")
                                    
                                    # Look for breaking change keywords
                                    breaking_keywords = [
                                        "breaking change", 
                                        "breaking changes",
                                        "not backward compatible",
                                        "backwards incompatible",
                                        "api changes"
                                    ]
                                    
                                    for keyword in breaking_keywords:
                                        if keyword in body:
                                            # Check if this is a future version
                                            tag_version = tag_name.lstrip("v")
                                            if self._compare_versions(tag_version, dependency.version) > 0:
                                                # Extract relevant section from release notes
                                                lines = body.split("\n")
                                                breaking_section = []
                                                in_breaking_section = False
                                                
                                                for line in lines:
                                                    if any(kw in line.lower() for kw in breaking_keywords):
                                                        in_breaking_section = True
                                                        breaking_section.append(line.strip())
                                                    elif in_breaking_section and line.strip():
                                                        breaking_section.append(line.strip())
                                                    elif in_breaking_section and not line.strip():
                                                        in_breaking_section = False
                                                
                                                description = " ".join(breaking_section)
                                                if len(description) > 200:
                                                    description = description[:197] + "..."
                                                
                                                breaking_changes.append({
                                                    "version": tag_version,
                                                    "date": release.get("published_at", "").split("T")[0],
                                                    "description": description or f"Breaking changes detected in version {tag_version}",
                                                    "impact": "high",
                                                    "source": "github_release_notes"
                                                })
                                                break
            
        except Exception as e:
            logger.error(f"Error analyzing breaking changes for {dependency.name}: {str(e)}")
        
        return breaking_changes
    
    async def _check_maintenance_issues(
        self,
        dependency: DependencyInfo
    ) -> Dict[str, Any]:
        """
        Check for maintenance issues with a dependency.
        
        Args:
            dependency: Dependency information
            
        Returns:
            Dictionary with maintenance issue information
        """
        result = {
            "has_issues": False,
            "description": "",
            "metrics": {},
            "date": datetime.utcnow().strftime("%Y-%m-%d")
        }
        
        try:
            # Look for GitHub repository info
            if dependency.repository_url and "github.com" in dependency.repository_url:
                repo_url = dependency.repository_url
                if repo_url.startswith("git+"):
                    repo_url = repo_url[4:]
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                
                # Extract owner and repo
                parts = repo_url.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    
                    # Get repo info
                    headers = {}
                    if self.github_token:
                        headers["Authorization"] = f"token {self.github_token}"
                        
                    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(repo_url, headers=headers) as response:
                            if response.status == 200:
                                repo_data = await response.json()
                                
                                # Check for signs of abandonment
                                last_update = repo_data.get("updated_at", "")
                                if last_update:
                                    last_updated = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                                    days_since_update = (datetime.utcnow() - last_updated).days
                                    
                                    result["metrics"]["days_since_update"] = days_since_update
                                    
                                    # If not updated in a year, may be abandoned
                                    if days_since_update > 365:
                                        result["has_issues"] = True
                                        result["description"] = f"Repository not updated in {days_since_update} days"
                                
                                # Check open issues
                                open_issues = repo_data.get("open_issues_count", 0)
                                result["metrics"]["open_issues"] = open_issues
                                
                                # Many open issues could indicate maintenance problems
                                if open_issues > 100:
                                    result["has_issues"] = True
                                    result["description"] = f"Large number of open issues ({open_issues})"
                                
                                # Check archived status
                                if repo_data.get("archived", False):
                                    result["has_issues"] = True
                                    result["description"] = "Repository is archived"
                                    
                                # Check if fork without activity
                                if repo_data.get("fork", False) and days_since_update > 180:
                                    result["has_issues"] = True
                                    result["description"] = "Forked repository with little activity"
                        
                        # Check commit activity
                        commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
                        params = {"per_page": 10}
                        
                        async with session.get(commits_url, headers=headers, params=params) as response:
                            if response.status == 200:
                                commits_data = await response.json()
                                
                                if commits_data:
                                    # Check date of latest commit
                                    latest_commit = commits_data[0]
                                    commit_date = latest_commit.get("commit", {}).get("committer", {}).get("date", "")
                                    
                                    if commit_date:
                                        last_commit = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
                                        days_since_commit = (datetime.utcnow() - last_commit).days
                                        
                                        result["metrics"]["days_since_commit"] = days_since_commit
                                        
                                        # If no commits in 6 months, may have maintenance issues
                                        if days_since_commit > 180:
                                            result["has_issues"] = True
                                            result["description"] = f"No commits in {days_since_commit} days"
            
            # Check package registry for activity
            if dependency.ecosystem == "nodejs":
                url = f"{self.npm_registry_url}/{dependency.name}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Check time of latest version
                            if "time" in data and "modified" in data["time"]:
                                modified = data["time"]["modified"]
                                last_modified = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                                days_since_modified = (datetime.utcnow() - last_modified).days
                                
                                result["metrics"]["days_since_package_update"] = days_since_modified
                                
                                # If not updated in a year, may be abandoned
                                if days_since_modified > 365:
                                    result["has_issues"] = True
                                    result["description"] = f"Package not updated in {days_since_modified} days"
                                    
                            # Check maintainers
                            if "maintainers" in data and not data["maintainers"]:
                                result["has_issues"] = True
                                result["description"] = "Package has no maintainers"
            
            elif dependency.ecosystem == "python":
                url = f"{self.pypi_url}/{dependency.name}/json"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Check last release date
                            if "releases" in data and data["releases"]:
                                latest_version = data.get("info", {}).get("version", "")
                                if latest_version and latest_version in data["releases"]:
                                    release_info = data["releases"][latest_version]
                                    if release_info and isinstance(release_info, list):
                                        upload_time = release_info[0].get("upload_time", "")
                                        if upload_time:
                                            last_release = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                                            days_since_release = (datetime.utcnow() - last_release).days
                                            
                                            result["metrics"]["days_since_release"] = days_since_release
                                            
                                            # If not released in 2 years, may be abandoned
                                            if days_since_release > 730:
                                                result["has_issues"] = True
                                                result["description"] = f"No releases in {days_since_release} days"
            
        except Exception as e:
            logger.error(f"Error checking maintenance for {dependency.name}: {str(e)}")
        
        return result
    
    @staticmethod
    def _parse_version(version: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse a semantic version string.
        
        Args:
            version: Version string
            
        Returns:
            Tuple of (major, minor, patch) or None if parsing fails
        """
        try:
            # Remove leading 'v' if present
            if version.startswith('v'):
                version = version[1:]
                
            # Handle simple semver
            match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-.*)?$', version)
            if match:
                return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                
            # Handle partial versions
            match = re.match(r'^(\d+)\.(\d+)(?:-.*)?$', version)
            if match:
                return (int(match.group(1)), int(match.group(2)), 0)
                
            match = re.match(r'^(\d+)(?:-.*)?$', version)
            if match:
                return (int(match.group(1)), 0, 0)
                
            return None
        except Exception:
            return None
    
    @staticmethod
    def _is_prerelease(version: str) -> bool:
        """
        Check if a version is a prerelease.
        
        Args:
            version: Version string
            
        Returns:
            True if prerelease, False otherwise
        """
        prerelease_patterns = [
            r'alpha', r'beta', r'rc', r'dev', r'pre', 
            r'\d+a\d+', r'\d+b\d+', r'\d+rc\d+', r'-\d+',
            r'preview', r'snapshot'
        ]
        
        return any(re.search(pattern, version.lower()) for pattern in prerelease_patterns)
    
    @staticmethod
    def _compare_versions(version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        parts1 = CompatibilityPredictor._parse_version(version1)
        parts2 = CompatibilityPredictor._parse_version(version2)
        
        if not parts1 or not parts2:
            # Fall back to string comparison if parsing fails
            return -1 if version1 < version2 else (1 if version1 > version2 else 0)
        
        # Compare major version
        if parts1[0] != parts2[0]:
            return -1 if parts1[0] < parts2[0] else 1
        
        # Compare minor version
        if parts1[1] != parts2[1]:
            return -1 if parts1[1] < parts2[1] else 1
        
        # Compare patch version
        if parts1[2] != parts2[2]:
            return -1 if parts1[2] < parts2[2] else 1
        
        # Versions are equal
        return 0


# Factory function for dependency
def get_compatibility_predictor(db: Session) -> CompatibilityPredictor:
    """Get an instance of the compatibility predictor."""
    return CompatibilityPredictor(db)