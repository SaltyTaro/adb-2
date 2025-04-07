import logging
import json
import aiohttp
import re
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session

from backend.core.models import Analysis, Dependency, LicenseReport
from backend.analysis.dependency_parser import DependencyInfo
from backend.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class LicenseManager:
    """
    License compliance management service for tracking and analyzing
    license dependencies throughout the project.
    
    Key features:
    1. License chain analysis - track license dependencies through the tree
    2. Legal risk assessment - flag potential license conflicts
    3. Acquisition impact analysis - alert when dependencies change ownership
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.github_token = settings.GITHUB_API_TOKEN
        self.risk_thresholds = settings.LICENSE_RISK_THRESHOLDS
        
        # License compatibility matrix
        # 0 = Incompatible, 1 = Compatible with attribution, 2 = Fully compatible
        self.compatibility_matrix = {
            "mit": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2, 
                "gpl-2.0": 1, "gpl-3.0": 1, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "bsd": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 1, "gpl-3.0": 1, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "apache-2.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 0, "gpl-3.0": 1, "lgpl-2.1": 0, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "isc": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 1, "gpl-3.0": 1, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "gpl-2.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 0, "isc": 2,
                "gpl-2.0": 2, "gpl-3.0": 0, "lgpl-2.1": 2, "lgpl-3.0": 0,
                "mpl-2.0": 0, "cc0-1.0": 2, "unlicense": 2, "proprietary": 0
            },
            "gpl-3.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 0, "gpl-3.0": 2, "lgpl-2.1": 0, "lgpl-3.0": 2,
                "mpl-2.0": 0, "cc0-1.0": 2, "unlicense": 2, "proprietary": 0
            },
            "lgpl-2.1": {
                "mit": 2, "bsd": 2, "apache-2.0": 0, "isc": 2,
                "gpl-2.0": 1, "gpl-3.0": 0, "lgpl-2.1": 2, "lgpl-3.0": 0,
                "mpl-2.0": 0, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "lgpl-3.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 0, "gpl-3.0": 1, "lgpl-2.1": 0, "lgpl-3.0": 2,
                "mpl-2.0": 0, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "mpl-2.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 0, "gpl-3.0": 0, "lgpl-2.1": 0, "lgpl-3.0": 0,
                "mpl-2.0": 2, "cc0-1.0": 2, "unlicense": 2, "proprietary": 1
            },
            "cc0-1.0": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 1, "gpl-3.0": 1, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 2
            },
            "unlicense": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 1, "gpl-3.0": 1, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 2
            },
            "proprietary": {
                "mit": 2, "bsd": 2, "apache-2.0": 2, "isc": 2,
                "gpl-2.0": 0, "gpl-3.0": 0, "lgpl-2.1": 1, "lgpl-3.0": 1,
                "mpl-2.0": 1, "cc0-1.0": 2, "unlicense": 2, "proprietary": 2
            }
        }
        
        # License types
        self.license_types = {
            "mit": "permissive",
            "bsd": "permissive",
            "apache-2.0": "permissive",
            "isc": "permissive",
            "gpl-2.0": "copyleft",
            "gpl-3.0": "copyleft",
            "lgpl-2.1": "weak-copyleft",
            "lgpl-3.0": "weak-copyleft",
            "mpl-2.0": "weak-copyleft",
            "cc0-1.0": "public-domain",
            "unlicense": "public-domain",
            "proprietary": "proprietary"
        }
        
        # License metadata
        self.license_metadata = {
            "mit": {
                "name": "MIT License",
                "url": "https://opensource.org/licenses/MIT",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": False
            },
            "bsd": {
                "name": "BSD License",
                "url": "https://opensource.org/licenses/BSD-3-Clause",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": False
            },
            "apache-2.0": {
                "name": "Apache License 2.0",
                "url": "https://opensource.org/licenses/Apache-2.0",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": True
            },
            "isc": {
                "name": "ISC License",
                "url": "https://opensource.org/licenses/ISC",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": False
            },
            "gpl-2.0": {
                "name": "GNU General Public License v2.0",
                "url": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "copyleft": True,
                "viral": True,
                "patent_grant": False
            },
            "gpl-3.0": {
                "name": "GNU General Public License v3.0",
                "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "copyleft": True,
                "viral": True,
                "patent_grant": True
            },
            "lgpl-2.1": {
                "name": "GNU Lesser General Public License v2.1",
                "url": "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "copyleft": True,
                "viral": "library-only",
                "patent_grant": False
            },
            "lgpl-3.0": {
                "name": "GNU Lesser General Public License v3.0",
                "url": "https://www.gnu.org/licenses/lgpl-3.0.en.html",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "copyleft": True,
                "viral": "library-only",
                "patent_grant": True
            },
            "mpl-2.0": {
                "name": "Mozilla Public License 2.0",
                "url": "https://www.mozilla.org/en-US/MPL/2.0/",
                "attribution_required": True,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "copyleft": True,
                "viral": "file-only",
                "patent_grant": True
            },
            "cc0-1.0": {
                "name": "Creative Commons Zero v1.0 Universal",
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "attribution_required": False,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": False
            },
            "unlicense": {
                "name": "The Unlicense",
                "url": "https://unlicense.org/",
                "attribution_required": False,
                "modification_allowed": True,
                "private_use_allowed": True,
                "commercial_use_allowed": True,
                "patent_grant": False
            },
            "proprietary": {
                "name": "Proprietary License",
                "url": None,
                "attribution_required": True,
                "modification_allowed": False,
                "private_use_allowed": True,
                "commercial_use_allowed": False,
                "patent_grant": False
            }
        }
    
    async def analyze_licenses(
        self,
        dependencies: List[DependencyInfo],
        project_id: str,
        target_license: str = "mit"
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Analyze licenses across all dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            target_license: Target license for the project
            
        Returns:
            Tuple of (summary, detailed reports)
        """
        logger.info(f"Analyzing licenses for {len(dependencies)} dependencies")
        
        # Create analysis record
        analysis = Analysis(
            project_id=project_id,
            analysis_type="license_compliance",
            status="running",
            config={
                "dependency_count": len(dependencies),
                "target_license": target_license
            }
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        try:
            # Process dependencies to extract licenses
            license_reports = []
            
            for dep in dependencies:
                licenses = await self._detect_licenses(dep)
                
                # Check compatibility with target license
                compatibility_issues = self._check_license_compatibility(
                    licenses, target_license
                )
                
                # Determine risk level
                risk_level = self._determine_risk_level(licenses, compatibility_issues)
                
                # Create report
                report = {
                    "dependency": dep.name,
                    "version": dep.version,
                    "ecosystem": dep.ecosystem,
                    "is_direct": dep.is_direct,
                    "licenses": licenses,
                    "compatibility_issues": compatibility_issues,
                    "risk_level": risk_level,
                    "analysis_time": datetime.utcnow().isoformat()
                }
                
                license_reports.append(report)
                
                # Store in database
                self._store_license_report(dep, licenses, risk_level, compatibility_issues)
            
            # Generate summary
            summary = self._generate_license_summary(license_reports, target_license)
            
            # Update analysis record
            analysis.status = "completed"
            analysis.result = {
                "risk_counts": summary["risk_counts"],
                "license_counts": summary["license_counts"],
                "completion_time": datetime.utcnow().isoformat()
            }
            
            self.db.commit()
            
            return summary, license_reports
            
        except Exception as e:
            logger.error(f"Error analyzing licenses: {str(e)}")
            analysis.status = "failed"
            analysis.error_message = str(e)
            self.db.commit()
            raise
    
    async def _detect_licenses(
        self,
        dependency: DependencyInfo
    ) -> List[Dict[str, Any]]:
        """
        Detect licenses for a dependency.
        
        Args:
            dependency: Dependency information
            
        Returns:
            List of license information
        """
        licenses = []
        
        # First check if we have licenses in the dependency info
        if hasattr(dependency, "licenses") and dependency.licenses:
            for license_id in dependency.licenses:
                license_id = self._normalize_license_id(license_id)
                license_type = self.license_types.get(license_id, "unknown")
                
                licenses.append({
                    "license_id": license_id,
                    "license_name": self.license_metadata.get(license_id, {}).get("name", "Unknown License"),
                    "license_type": license_type,
                    "source": "dependency_info"
                })
        
        # If no licenses found, try to detect from package registry
        if not licenses:
            if dependency.ecosystem == "nodejs":
                npm_licenses = await self._detect_npm_licenses(dependency)
                licenses.extend(npm_licenses)
            elif dependency.ecosystem == "python":
                pypi_licenses = await self._detect_pypi_licenses(dependency)
                licenses.extend(pypi_licenses)
        
        # If still no licenses, try to detect from GitHub repo
        if not licenses and dependency.repository_url and "github.com" in dependency.repository_url:
            github_licenses = await self._detect_github_licenses(dependency)
            licenses.extend(github_licenses)
        
        # If still no licenses, mark as unknown
        if not licenses:
            licenses.append({
                "license_id": "unknown",
                "license_name": "Unknown License",
                "license_type": "unknown",
                "source": "fallback"
            })
        
        return licenses
    
    async def _detect_npm_licenses(
        self,
        dependency: DependencyInfo
    ) -> List[Dict[str, Any]]:
        """
        Detect licenses for an npm package.
        
        Args:
            dependency: Dependency information
            
        Returns:
            List of license information
        """
        licenses = []
        
        try:
            # Query npm registry
            url = f"{settings.NPM_REGISTRY_URL}/{dependency.name}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for license in package info
                        if "license" in data:
                            license_data = data["license"]
                            
                            # Handle both string and object formats
                            if isinstance(license_data, str):
                                license_id = self._normalize_license_id(license_data)
                            elif isinstance(license_data, dict) and "type" in license_data:
                                license_id = self._normalize_license_id(license_data["type"])
                            else:
                                return licenses
                            
                            license_type = self.license_types.get(license_id, "unknown")
                            
                            licenses.append({
                                "license_id": license_id,
                                "license_name": self.license_metadata.get(license_id, {}).get("name", "Unknown License"),
                                "license_type": license_type,
                                "source": "npm_registry"
                            })
                        
                        # Check latest version
                        elif "versions" in data and "dist-tags" in data and "latest" in data["dist-tags"]:
                            latest = data["dist-tags"]["latest"]
                            if latest in data["versions"] and "license" in data["versions"][latest]:
                                license_data = data["versions"][latest]["license"]
                                
                                # Handle both string and object formats
                                if isinstance(license_data, str):
                                    license_id = self._normalize_license_id(license_data)
                                elif isinstance(license_data, dict) and "type" in license_data:
                                    license_id = self._normalize_license_id(license_data["type"])
                                else:
                                    return licenses
                                
                                license_type = self.license_types.get(license_id, "unknown")
                                
                                licenses.append({
                                    "license_id": license_id,
                                    "license_name": self.license_metadata.get(license_id, {}).get("name", "Unknown License"),
                                    "license_type": license_type,
                                    "source": "npm_registry_version"
                                })
        
        except Exception as e:
            logger.error(f"Error detecting npm licenses for {dependency.name}: {str(e)}")
        
        return licenses
    
    async def _detect_pypi_licenses(
        self,
        dependency: DependencyInfo
    ) -> List[Dict[str, Any]]:
        """
        Detect licenses for a PyPI package.
        
        Args:
            dependency: Dependency information
            
        Returns:
            List of license information
        """
        licenses = []
        
        try:
            # Query PyPI
            url = f"{settings.PYPI_URL}/{dependency.name}/json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Get info section
                        info = data.get("info", {})
                        
                        # Check classifiers for license info
                        classifiers = info.get("classifiers", [])
                        for classifier in classifiers:
                            if classifier.startswith("License ::"):
                                license_name = classifier.split(" :: ")[-1]
                                license_id = self._normalize_license_name(license_name)
                                license_type = self.license_types.get(license_id, "unknown")
                                
                                licenses.append({
                                    "license_id": license_id,
                                    "license_name": license_name,
                                    "license_type": license_type,
                                    "source": "pypi_classifier"
                                })
                        
                        # Also check license field
                        if "license" in info and info["license"]:
                            license_text = info["license"]
                            license_id = self._normalize_license_name(license_text)
                            license_type = self.license_types.get(license_id, "unknown")
                            
                            # Only add if not already found in classifiers
                            if not any(l["license_id"] == license_id for l in licenses):
                                licenses.append({
                                    "license_id": license_id,
                                    "license_name": license_text,
                                    "license_type": license_type,
                                    "source": "pypi_license_field"
                                })
        
        except Exception as e:
            logger.error(f"Error detecting PyPI licenses for {dependency.name}: {str(e)}")
        
        return licenses
    
    async def _detect_github_licenses(
        self,
        dependency: DependencyInfo
    ) -> List[Dict[str, Any]]:
        """
        Detect licenses from GitHub repository.
        
        Args:
            dependency: Dependency information
            
        Returns:
            List of license information
        """
        licenses = []
        
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
                return licenses
                
            owner, repo = parts[0], parts[1]
            
            # Set up headers for GitHub API
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            async with aiohttp.ClientSession() as session:
                # Get license info from GitHub API
                api_url = f"https://api.github.com/repos/{owner}/{repo}/license"
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "license" in data and data["license"]:
                            license_data = data["license"]
                            
                            license_id = self._normalize_license_id(license_data.get("spdx_id", ""))
                            license_name = license_data.get("name", "Unknown License")
                            license_type = self.license_types.get(license_id, "unknown")
                            
                            licenses.append({
                                "license_id": license_id,
                                "license_name": license_name,
                                "license_type": license_type,
                                "source": "github_api"
                            })
                            
                            # Also get the license content
                            if "download_url" in data and data["download_url"]:
                                async with session.get(data["download_url"]) as license_response:
                                    if license_response.status == 200:
                                        license_text = await license_response.text()
                                        # Store just the first 1000 chars to avoid huge texts
                                        licenses[-1]["license_text"] = license_text[:1000] + "..."
        
        except Exception as e:
            logger.error(f"Error detecting GitHub licenses for {dependency.name}: {str(e)}")
        
        return licenses
    
    def _normalize_license_id(self, license_id: str) -> str:
        """
        Normalize license ID to a standard format.
        
        Args:
            license_id: Raw license identifier
            
        Returns:
            Normalized license identifier
        """
        if not license_id:
            return "unknown"
            
        # Convert to lowercase
        license_id = license_id.lower()
        
        # Remove common prefixes and parentheses
        license_id = re.sub(r'^license[:\s-]', '', license_id)
        license_id = re.sub(r'\([^)]*\)', '', license_id).strip()
        
        # Common mappings
        mappings = {
            "mit": "mit",
            "expat": "mit",
            "apache2": "apache-2.0",
            "apache-2": "apache-2.0",
            "apache 2": "apache-2.0",
            "apache 2.0": "apache-2.0",
            "apache license 2.0": "apache-2.0",
            "apache software license": "apache-2.0",
            "bsd-2-clause": "bsd",
            "bsd-3-clause": "bsd",
            "bsd 2-clause": "bsd",
            "bsd 3-clause": "bsd",
            "new bsd license": "bsd",
            "simplified bsd": "bsd",
            "isc license": "isc",
            "isc": "isc",
            "gnu gpl v2": "gpl-2.0",
            "gnu gpl v2+": "gpl-2.0",
            "gplv2": "gpl-2.0",
            "gpl2": "gpl-2.0",
            "gpl-2": "gpl-2.0",
            "gnu gpl v3": "gpl-3.0",
            "gnu gpl v3+": "gpl-3.0",
            "gplv3": "gpl-3.0",
            "gpl3": "gpl-3.0",
            "gpl-3": "gpl-3.0",
            "gnu lgpl v2.1": "lgpl-2.1",
            "gnu lgpl v2.1+": "lgpl-2.1",
            "lgplv2.1": "lgpl-2.1",
            "lgpl2.1": "lgpl-2.1",
            "lgpl-2.1": "lgpl-2.1",
            "gnu lgpl v3": "lgpl-3.0",
            "gnu lgpl v3+": "lgpl-3.0",
            "lgplv3": "lgpl-3.0",
            "lgpl3": "lgpl-3.0",
            "lgpl-3": "lgpl-3.0",
            "mpl-2.0": "mpl-2.0",
            "mpl2": "mpl-2.0",
            "mpl 2.0": "mpl-2.0",
            "mozilla public license 2.0": "mpl-2.0",
            "cc0": "cc0-1.0",
            "cc0 1.0": "cc0-1.0",
            "creativecommons0": "cc0-1.0",
            "unlicense": "unlicense",
            "the unlicense": "unlicense",
            "public domain": "cc0-1.0",
            "private": "proprietary",
            "proprietary": "proprietary",
            "commercial": "proprietary"
        }
        
        return mappings.get(license_id, "unknown")
    
    def _normalize_license_name(self, license_name: str) -> str:
        """
        Normalize license name to a standard ID.
        
        Args:
            license_name: License name string
            
        Returns:
            Normalized license identifier
        """
        if not license_name:
            return "unknown"
            
        # Convert to lowercase for matching
        name_lower = license_name.lower()
        
        # Check for common license names
        if "mit" in name_lower:
            return "mit"
        elif "bsd" in name_lower:
            return "bsd"
        elif "apache" in name_lower and ("2" in name_lower or "2.0" in name_lower):
            return "apache-2.0"
        elif "isc" in name_lower:
            return "isc"
        elif "gpl" in name_lower or "gnu general public" in name_lower:
            if "2" in name_lower or "2.0" in name_lower:
                return "gpl-2.0"
            elif "3" in name_lower or "3.0" in name_lower:
                return "gpl-3.0"
        elif "lgpl" in name_lower or "gnu lesser" in name_lower:
            if "2.1" in name_lower:
                return "lgpl-2.1"
            elif "3" in name_lower or "3.0" in name_lower:
                return "lgpl-3.0"
        elif "mpl" in name_lower or "mozilla" in name_lower:
            if "2" in name_lower or "2.0" in name_lower:
                return "mpl-2.0"
        elif "cc0" in name_lower or "creative commons zero" in name_lower:
            return "cc0-1.0"
        elif "unlicense" in name_lower:
            return "unlicense"
        elif "public domain" in name_lower:
            return "cc0-1.0"
        elif "proprietary" in name_lower or "commercial" in name_lower or "private" in name_lower:
            return "proprietary"
        
        # Default to unknown
        return "unknown"
    
    def _check_license_compatibility(
        self,
        licenses: List[Dict[str, Any]],
        target_license: str
    ) -> List[Dict[str, Any]]:
        """
        Check compatibility between detected licenses and target license.
        
        Args:
            licenses: List of detected licenses
            target_license: Target license
            
        Returns:
            List of compatibility issues
        """
        issues = []
        
        # Normalize target license
        target_id = self._normalize_license_id(target_license)
        
        for license_info in licenses:
            license_id = license_info["license_id"]
            
            # Skip unknown licenses
            if license_id == "unknown":
                issues.append({
                    "license_id": license_id,
                    "license_name": license_info["license_name"],
                    "issue_type": "unknown_license",
                    "description": "License could not be definitively identified, which poses a compliance risk",
                    "severity": "medium"
                })
                continue
            
            # Check compatibility matrix
            if target_id in self.compatibility_matrix and license_id in self.compatibility_matrix[target_id]:
                compatibility = self.compatibility_matrix[target_id][license_id]
                
                if compatibility == 0:
                    issues.append({
                        "license_id": license_id,
                        "license_name": license_info["license_name"],
                        "issue_type": "incompatible",
                        "description": f"License {license_id} is incompatible with target license {target_id}",
                        "severity": "high"
                    })
                elif compatibility == 1:
                    issues.append({
                        "license_id": license_id,
                        "license_name": license_info["license_name"],
                        "issue_type": "conditional",
                        "description": f"License {license_id} is compatible with {target_id} only if attribution requirements are met",
                        "severity": "medium"
                    })
            else:
                # If not in matrix, consider it unknown compatibility
                issues.append({
                    "license_id": license_id,
                    "license_name": license_info["license_name"],
                    "issue_type": "unknown_compatibility",
                    "description": f"Compatibility between {license_id} and {target_id} is unknown",
                    "severity": "medium"
                })
        
        return issues
    
    def _determine_risk_level(
        self,
        licenses: List[Dict[str, Any]],
        compatibility_issues: List[Dict[str, Any]]
    ) -> str:
        """
        Determine overall license risk level.
        
        Args:
            licenses: List of detected licenses
            compatibility_issues: List of compatibility issues
            
        Returns:
            Risk level (high, medium, low)
        """
        # If no licenses detected, that's a medium risk
        if not licenses or all(l["license_id"] == "unknown" for l in licenses):
            return "medium"
        
        # If incompatible licenses, that's high risk
        if any(issue["issue_type"] == "incompatible" for issue in compatibility_issues):
            return "high"
        
        # If only permissive licenses and no compatibility issues, that's low risk
        if all(l["license_type"] == "permissive" for l in licenses if l["license_id"] != "unknown") and not compatibility_issues:
            return "low"
        
        # If we have copyleft licenses, that's at least medium risk
        if any(l["license_type"] in ["copyleft", "weak-copyleft"] for l in licenses):
            return "medium"
        
        # If conditional compatibility, that's medium risk
        if any(issue["issue_type"] == "conditional" for issue in compatibility_issues):
            return "medium"
        
        # Default to low risk
        return "low"
    
    def _store_license_report(
        self,
        dependency: DependencyInfo,
        licenses: List[Dict[str, Any]],
        risk_level: str,
        compatibility_issues: List[Dict[str, Any]]
    ) -> None:
        """
        Store license report in database.
        
        Args:
            dependency: Dependency information
            licenses: Detected licenses
            risk_level: Risk level
            compatibility_issues: Compatibility issues
        """
        try:
            # Get or create dependency version
            # This is just a placeholder - in a real implementation, you would
            # query your dependency and dependency version tables
            
            # Create license reports
            for license_info in licenses:
                report = LicenseReport(
                    license_id=license_info["license_id"],
                    license_name=license_info["license_name"],
                    license_type=license_info["license_type"],
                    risk_level=risk_level,
                    is_compliant=not bool(compatibility_issues)
                )
                
                if "license_text" in license_info:
                    report.license_text = license_info["license_text"]
                
                if compatibility_issues:
                    notes = "; ".join(issue["description"] for issue in compatibility_issues)
                    report.compliance_notes = notes[:1000]  # Limit size
                
                self.db.add(report)
                
            # Commit changes
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error storing license report: {str(e)}")
            self.db.rollback()
    
    def _generate_license_summary(
        self,
        license_reports: List[Dict[str, Any]],
        target_license: str
    ) -> Dict[str, Any]:
        """
        Generate summary of license analysis.
        
        Args:
            license_reports: List of license reports
            target_license: Target license
            
        Returns:
            Dictionary with license summary
        """
        # Count licenses by type
        license_counts = {}
        for report in license_reports:
            for license_info in report["licenses"]:
                license_id = license_info["license_id"]
                license_counts[license_id] = license_counts.get(license_id, 0) + 1
        
        # Count risk levels
        risk_counts = {
            "high": 0,
            "medium": 0,
            "low": 0
        }
        
        for report in license_reports:
            risk_level = report["risk_level"]
            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
        
        # Identify dependencies with issues
        high_risk_deps = [
            {
                "name": report["dependency"],
                "ecosystem": report["ecosystem"],
                "version": report["version"],
                "licenses": [l["license_id"] for l in report["licenses"]],
                "issues": report["compatibility_issues"]
            }
            for report in license_reports
            if report["risk_level"] == "high"
        ]
        
        # Sort by direct dependencies first
        high_risk_deps.sort(key=lambda x: 0 if any(r["is_direct"] for r in license_reports if r["dependency"] == x["name"]) else 1)
        
        # Calculate compliance percentage
        compliant_count = risk_counts["low"]
        total_count = sum(risk_counts.values())
        compliance_pct = (compliant_count / total_count * 100) if total_count > 0 else 0
        
        # Create summary
        summary = {
            "target_license": target_license,
            "license_counts": license_counts,
            "risk_counts": risk_counts,
            "compliance_percentage": round(compliance_pct, 1),
            "high_risk_dependencies": high_risk_deps[:5],  # Top 5 high risk deps
            "license_types": {
                "permissive": sum(1 for r in license_reports if any(l["license_type"] == "permissive" for l in r["licenses"])),
                "copyleft": sum(1 for r in license_reports if any(l["license_type"] == "copyleft" for l in r["licenses"])),
                "weak-copyleft": sum(1 for r in license_reports if any(l["license_type"] == "weak-copyleft" for l in r["licenses"])),
                "proprietary": sum(1 for r in license_reports if any(l["license_type"] == "proprietary" for l in r["licenses"])),
                "unknown": sum(1 for r in license_reports if any(l["license_type"] == "unknown" for l in r["licenses"]))
            },
            "overall_risk_level": "high" if risk_counts["high"] > 0 else "medium" if risk_counts["medium"] > 0 else "low"
        }
        
        return summary
    
    async def analyze_acquisitions(
        self,
        dependencies: List[DependencyInfo],
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        Analyze recent acquisitions that might affect dependencies.
        
        Args:
            dependencies: List of dependency information
            project_id: Project ID
            
        Returns:
            List of acquisition alerts
        """
        # This would usually query a database of acquisitions or a third-party API
        # For simplicity, we'll return mock data for demonstration
        
        # Mock recent acquisitions
        acquisitions = [
            {
                "acquired_company": "npm, Inc.",
                "acquiring_company": "GitHub (Microsoft)",
                "date": "2020-03-16",
                "affected_packages": ["npm"]
            },
            {
                "acquired_company": "Auth0",
                "acquiring_company": "Okta",
                "date": "2021-03-03",
                "affected_packages": ["auth0", "auth0-js", "auth0-react"]
            },
            {
                "acquired_company": "Kite",
                "acquiring_company": "Qwoted",
                "date": "2022-01-06",
                "affected_packages": ["kite", "kite-sdk"]
            },
            {
                "acquired_company": "Cratejoy",
                "acquiring_company": "Recharge Payments",
                "date": "2021-11-15",
                "affected_packages": ["cratejoy-api", "cratejoy-client"]
            }
        ]
        
        # Find affected dependencies
        alerts = []
        dep_names = {d.name.lower() for d in dependencies}
        
        for acquisition in acquisitions:
            affected = [pkg for pkg in acquisition["affected_packages"] if pkg.lower() in dep_names]
            
            if affected:
                alerts.append({
                    "acquisition": acquisition,
                    "affected_dependencies": affected,
                    "potential_impact": "ownership_change",
                    "description": f"{acquisition['acquired_company']} was acquired by {acquisition['acquiring_company']} on {acquisition['date']}",
                    "recommendations": [
                        "Review updated terms of service or licensing changes",
                        "Check for changes in pricing, support, or development roadmap",
                        "Consider adding this to your risk register"
                    ]
                })
        
        return alerts


# Factory function
def get_license_manager(db: Session) -> LicenseManager:
    """Get an instance of the license manager."""
    return LicenseManager(db)