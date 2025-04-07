import os
import logging
import pickle
import json
import numpy as np
import re
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from datetime import datetime, timedelta

from backend.core.config import get_settings
from backend.ai.models import AIModel

settings = get_settings()
logger = logging.getLogger(__name__)


class CompatibilityPredictor:
    """
    AI-powered compatibility prediction for forecasting future compatibility issues
    between dependency versions.
    
    Key features:
    1. Breaking change prediction - predict potential breaking changes
    2. Version compatibility scoring - score compatibility between versions
    3. Ecosystem-specific predictions - specialized models for each ecosystem
    """
    
    def __init__(self):
        """Initialize the compatibility predictor with required models."""
        self.model = None
        if settings.ENABLE_AI_FEATURES:
            try:
                self.model = AIModel.load_model(settings.MODEL_PATHS["compatibility_predictor"])
                logger.info("Compatibility predictor model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load compatibility predictor model: {str(e)}")
        
        # Initialize ecosystem-specific predictors
        self.ecosystem_predictors = {
            "python": PythonCompatibilityPredictor(),
            "nodejs": NodeJSCompatibilityPredictor()
        }
    
    async def predict_breaking_changes(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "python"
    ) -> List[Dict[str, Any]]:
        """
        Predict potential breaking changes between two versions.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version
            ecosystem: Dependency ecosystem
            
        Returns:
            List of potential breaking changes
        """
        logger.info(f"Predicting breaking changes for {dependency_name}: {current_version} → {target_version}")
        
        # Use ecosystem-specific predictor if available
        if ecosystem in self.ecosystem_predictors:
            return await self.ecosystem_predictors[ecosystem].predict_breaking_changes(
                dependency_name, current_version, target_version
            )
        
        # Fall back to general AI model if available
        if settings.ENABLE_AI_FEATURES and self.model:
            return await self._predict_with_ai(
                dependency_name, current_version, target_version, ecosystem
            )
        
        # Default fallback - limited prediction based on version diff
        return await self._predict_from_version_diff(
            dependency_name, current_version, target_version, ecosystem
        )
    
    async def score_compatibility(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str = "python"
    ) -> Dict[str, Any]:
        """
        Score compatibility between two versions.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version
            ecosystem: Dependency ecosystem
            
        Returns:
            Compatibility score details
        """
        logger.info(f"Scoring compatibility for {dependency_name}: {current_version} → {target_version}")
        
        # Use ecosystem-specific predictor if available
        if ecosystem in self.ecosystem_predictors:
            return await self.ecosystem_predictors[ecosystem].score_compatibility(
                dependency_name, current_version, target_version
            )
        
        # Predict breaking changes
        breaking_changes = await self.predict_breaking_changes(
            dependency_name, current_version, target_version, ecosystem
        )
        
        # Calculate version difference
        version_diff = self._calculate_version_diff(current_version, target_version)
        
        # Calculate compatibility score
        score = self._calculate_compatibility_score(
            breaking_changes, version_diff, current_version, target_version
        )
        
        return {
            "score": score,
            "breaking_changes": breaking_changes,
            "version_diff": version_diff,
            "confidence": self._calculate_confidence(breaking_changes, version_diff),
            "recommendation": self._get_recommendation(score, breaking_changes)
        }
    
    async def predict_future_issues(
        self,
        dependency_name: str,
        current_version: str,
        ecosystem: str = "python",
        time_horizon: int = 180  # days
    ) -> Dict[str, Any]:
        """
        Predict future compatibility issues within a time horizon.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            ecosystem: Dependency ecosystem
            time_horizon: Time horizon in days
            
        Returns:
            Dictionary with future issue predictions
        """
        logger.info(f"Predicting future issues for {dependency_name} ({current_version}) over {time_horizon} days")
        
        # Use ecosystem-specific predictor if available
        if ecosystem in self.ecosystem_predictors:
            return await self.ecosystem_predictors[ecosystem].predict_future_issues(
                dependency_name, current_version, time_horizon
            )
        
        # Default implementation - predict next versions
        future_versions = await self._predict_future_versions(
            dependency_name, current_version, ecosystem, time_horizon
        )
        
        # For each future version, predict compatibility
        compatibility_predictions = []
        for version_info in future_versions:
            version = version_info["version"]
            
            # Skip versions that are older than current
            if self._compare_versions(version, current_version) <= 0:
                continue
                
            # Predict compatibility with this version
            compatibility = await self.score_compatibility(
                dependency_name, current_version, version, ecosystem
            )
            
            compatibility_predictions.append({
                "version": version,
                "predicted_date": version_info["predicted_date"],
                "compatibility_score": compatibility["score"],
                "breaking_changes": compatibility["breaking_changes"],
                "confidence": compatibility["confidence"]
            })
        
        # Sort by predicted date
        compatibility_predictions.sort(key=lambda x: x["predicted_date"])
        
        # Identify potential migration points (where upgrading would be beneficial)
        migration_points = self._identify_migration_points(
            compatibility_predictions, current_version
        )
        
        return {
            "dependency": dependency_name,
            "current_version": current_version,
            "ecosystem": ecosystem,
            "time_horizon_days": time_horizon,
            "future_versions": future_versions,
            "compatibility_predictions": compatibility_predictions,
            "migration_points": migration_points
        }
    
    async def _predict_with_ai(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str
    ) -> List[Dict[str, Any]]:
        """
        Predict breaking changes using AI model.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version
            ecosystem: Dependency ecosystem
            
        Returns:
            List of potential breaking changes
        """
        if not settings.ENABLE_AI_FEATURES or not self.model:
            return []
        
        try:
            # Prepare input for the model
            input_data = {
                "dependency": dependency_name,
                "ecosystem": ecosystem,
                "current_version": current_version,
                "target_version": target_version
            }
            
            # Get prediction from the model
            predictions = await self.model.predict_breaking_changes(input_data)
            
            # Process predictions
            breaking_changes = []
            for prediction in predictions:
                breaking_changes.append({
                    "type": prediction.get("type", "unknown"),
                    "symbol": prediction.get("symbol", ""),
                    "description": prediction.get("description", ""),
                    "impact": prediction.get("impact", "medium"),
                    "confidence": prediction.get("confidence", 0.5)
                })
            
            return breaking_changes
            
        except Exception as e:
            logger.error(f"Error predicting breaking changes with AI: {str(e)}")
            # Fall back to version diff prediction
            return await self._predict_from_version_diff(
                dependency_name, current_version, target_version, ecosystem
            )
    
    async def _predict_from_version_diff(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str,
        ecosystem: str
    ) -> List[Dict[str, Any]]:
        """
        Predict breaking changes based on version difference.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            target_version: Target version
            ecosystem: Dependency ecosystem
            
        Returns:
            List of potential breaking changes
        """
        # Parse versions
        current_parts = self._parse_version(current_version)
        target_parts = self._parse_version(target_version)
        
        if not current_parts or not target_parts:
            return []
        
        breaking_changes = []
        
        # Major version change often indicates breaking changes
        if target_parts[0] > current_parts[0]:
            # Major version increase - high probability of breaking changes
            breaking_changes.append({
                "type": "major_version_change",
                "symbol": f"{dependency_name}",
                "description": f"Major version change from {current_parts[0]} to {target_parts[0]}",
                "impact": "high",
                "confidence": 0.8
            })
            
            # For known packages, add common breaking changes
            common_changes = self._get_common_breaking_changes(
                dependency_name, current_parts[0], target_parts[0], ecosystem
            )
            breaking_changes.extend(common_changes)
        
        elif target_parts[0] == current_parts[0] and target_parts[1] > current_parts[1]:
            # Minor version increase - might include new features or mild breaking changes
            breaking_changes.append({
                "type": "minor_version_change",
                "symbol": f"{dependency_name}",
                "description": f"Minor version change from {current_parts[0]}.{current_parts[1]} to {target_parts[0]}.{target_parts[1]}",
                "impact": "medium",
                "confidence": 0.6
            })
        
        return breaking_changes
    
    def _parse_version(self, version: str) -> Optional[Tuple[int, ...]]:
        """
        Parse a version string into components.
        
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
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        parts1 = self._parse_version(version1)
        parts2 = self._parse_version(version2)
        
        if not parts1 or not parts2:
            # Fall back to string comparison if parsing fails
            return -1 if version1 < version2 else (1 if version1 > version2 else 0)
        
        # Compare component by component
        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
        
        # If we get here, all compared components are equal
        # Check if one version has more components
        if len(parts1) < len(parts2):
            return -1
        elif len(parts1) > len(parts2):
            return 1
        
        # Versions are exactly equal
        return 0
    
    def _calculate_version_diff(
        self,
        current_version: str,
        target_version: str
    ) -> Dict[str, Any]:
        """
        Calculate the difference between two versions.
        
        Args:
            current_version: Current version
            target_version: Target version
            
        Returns:
            Version difference metrics
        """
        current_parts = self._parse_version(current_version)
        target_parts = self._parse_version(target_version)
        
        if not current_parts or not target_parts:
            return {
                "is_upgrade": target_version > current_version,
                "diff_type": "unknown"
            }
        
        # Calculate the difference for each component
        diff = []
        for i in range(min(len(current_parts), len(target_parts))):
            diff.append(target_parts[i] - current_parts[i])
        
        # Determine the type of change
        if diff[0] > 0:
            diff_type = "major"
        elif diff[0] < 0:
            diff_type = "major_downgrade"
        elif diff[1] > 0:
            diff_type = "minor"
        elif diff[1] < 0:
            diff_type = "minor_downgrade"
        elif diff[2] > 0:
            diff_type = "patch"
        elif diff[2] < 0:
            diff_type = "patch_downgrade"
        else:
            diff_type = "same"
        
        return {
            "is_upgrade": diff_type in ["major", "minor", "patch"],
            "is_downgrade": diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"],
            "diff_type": diff_type,
            "diff": diff,
            "diff_magnitude": sum(abs(d) for d in diff)
        }
    
    def _calculate_compatibility_score(
        self,
        breaking_changes: List[Dict[str, Any]],
        version_diff: Dict[str, Any],
        current_version: str,
        target_version: str
    ) -> float:
        """
        Calculate compatibility score between versions.
        
        Args:
            breaking_changes: List of breaking changes
            version_diff: Version difference metrics
            current_version: Current version
            target_version: Target version
            
        Returns:
            Compatibility score (0-1, higher is more compatible)
        """
        # Start with a base score
        score = 1.0
        
        # Adjust based on version difference
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            # Major version increases have higher chance of incompatibility
            score -= 0.3
        elif diff_type == "minor":
            # Minor version increases have medium chance of incompatibility
            score -= 0.1
        elif diff_type == "patch":
            # Patch changes should be compatible, but still a small risk
            score -= 0.02
        elif diff_type == "major_downgrade":
            # Major downgrades are highly risky
            score -= 0.5
        elif diff_type == "minor_downgrade":
            # Minor downgrades are moderately risky
            score -= 0.2
        elif diff_type == "patch_downgrade":
            # Patch downgrades are somewhat risky
            score -= 0.05
        
        # Further reduce score based on number of breaking changes
        high_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "high")
        medium_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "medium")
        low_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "low")
        
        score -= high_impact_changes * 0.15
        score -= medium_impact_changes * 0.08
        score -= low_impact_changes * 0.03
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))
    
    def _calculate_confidence(
        self,
        breaking_changes: List[Dict[str, Any]],
        version_diff: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence in the compatibility prediction.
        
        Args:
            breaking_changes: List of breaking changes
            version_diff: Version difference metrics
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence level
        confidence = 0.7
        
        # Adjust based on version difference
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            # Major version changes have clear patterns
            confidence += 0.15
        elif diff_type in ["minor", "patch"]:
            # Smaller changes have more subtle patterns
            confidence += 0.05
        elif diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"]:
            # Downgrades are less predictable
            confidence -= 0.1
        
        # Adjust based on breaking changes
        if breaking_changes:
            # Average confidence of breaking changes
            change_confidence = [c.get("confidence", 0.5) for c in breaking_changes]
            avg_confidence = sum(change_confidence) / len(change_confidence)
            
            # Weight of breaking changes confidence
            confidence = 0.7 * confidence + 0.3 * avg_confidence
        
        # Ensure confidence is within bounds
        return max(0.1, min(1.0, confidence))
    
    def _get_recommendation(
        self,
        compatibility_score: float,
        breaking_changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get recommendation based on compatibility score.
        
        Args:
            compatibility_score: Compatibility score
            breaking_changes: List of breaking changes
            
        Returns:
            Recommendation details
        """
        if compatibility_score >= 0.9:
            # Highly compatible - safe upgrade
            return {
                "action": "upgrade",
                "risk_level": "low",
                "message": "Safe to upgrade - no significant compatibility issues expected"
            }
        elif compatibility_score >= 0.7:
            # Moderately compatible - cautious upgrade
            return {
                "action": "upgrade_with_caution",
                "risk_level": "medium",
                "message": "Proceed with caution - some minor compatibility issues may arise",
                "affected_apis": [c["symbol"] for c in breaking_changes if c.get("impact") in ["medium", "low"]]
            }
        elif compatibility_score >= 0.4:
            # Limited compatibility - careful testing required
            return {
                "action": "careful_testing",
                "risk_level": "high",
                "message": "Significant compatibility issues expected - extensive testing required",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }
        else:
            # Incompatible - not recommended
            return {
                "action": "not_recommended",
                "risk_level": "critical",
                "message": "Upgrade not recommended - major compatibility issues expected",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }
    
    def _get_common_breaking_changes(
        self,
        dependency_name: str,
        current_major: int,
        target_major: int,
        ecosystem: str
    ) -> List[Dict[str, Any]]:
        """
        Get common breaking changes for known packages.
        
        Args:
            dependency_name: Dependency name
            current_major: Current major version
            target_major: Target major version
            ecosystem: Dependency ecosystem
            
        Returns:
            List of common breaking changes
        """
        # Mock database of known breaking changes for common packages
        known_changes = {}
        
        if ecosystem == "python":
            known_changes = {
                "requests": {
                    "2-3": [
                        {
                            "type": "removed",
                            "symbol": "requests.async",
                            "description": "The async module was removed as it didn't work in Python 3",
                            "impact": "high",
                            "confidence": 0.9
                        },
                        {
                            "type": "behavior_change",
                            "symbol": "requests.request",
                            "description": "Default timeout behavior changed",
                            "impact": "medium",
                            "confidence": 0.8
                        }
                    ]
                },
                "django": {
                    "2-3": [
                        {
                            "type": "removed",
                            "symbol": "django.utils.six",
                            "description": "Removed django.utils.six in favor of the six package",
                            "impact": "high",
                            "confidence": 0.9
                        },
                        {
                            "type": "behavior_change",
                            "symbol": "django.urls.path",
                            "description": "URL path handling changed",
                            "impact": "medium",
                            "confidence": 0.8
                        }
                    ],
                    "3-4": [
                        {
                            "type": "removed",
                            "symbol": "django.utils.encoding.force_text",
                            "description": "Removed force_text in favor of force_str",
                            "impact": "high",
                            "confidence": 0.9
                        }
                    ]
                }
            }
        elif ecosystem == "nodejs":
            known_changes = {
                "lodash": {
                    "3-4": [
                        {
                            "type": "removed",
                            "symbol": "_.pluck",
                            "description": "Removed _.pluck in favor of _.map with property shorthand",
                            "impact": "high",
                            "confidence": 0.9,
                            "alternatives": ["_.map(collection, 'property')"]
                        },
                        {
                            "type": "behavior_change",
                            "symbol": "_.flatten",
                            "description": "_.flatten is now shallow by default",
                            "impact": "high",
                            "confidence": 0.9,
                            "alternatives": ["_.flattenDeep"]
                        }
                    ]
                },
                "react": {
                    "16-17": [
                        {
                            "type": "behavior_change",
                            "symbol": "React.useEffect",
                            "description": "useEffect cleanup timing changed",
                            "impact": "medium",
                            "confidence": 0.8
                        }
                    ],
                    "17-18": [
                        {
                            "type": "removed",
                            "symbol": "ReactDOM.render",
                            "description": "Replaced ReactDOM.render with createRoot",
                            "impact": "high",
                            "confidence": 0.9,
                            "alternatives": ["ReactDOM.createRoot(container).render(<App />)"]
                        }
                    ]
                }
            }
        
        # Get changes for this dependency and major version change
        key = f"{current_major}-{target_major}"
        return known_changes.get(dependency_name, {}).get(key, [])
    
    async def _predict_future_versions(
        self,
        dependency_name: str,
        current_version: str,
        ecosystem: str,
        time_horizon: int
    ) -> List[Dict[str, Any]]:
        """
        Predict future versions of a dependency.
        
        Args:
            dependency_name: Dependency name
            current_version: Current version
            ecosystem: Dependency ecosystem
            time_horizon: Time horizon in days
            
        Returns:
            List of predicted future versions
        """
        # Use ecosystem-specific predictor if available
        if ecosystem in self.ecosystem_predictors:
            return await self.ecosystem_predictors[ecosystem]._predict_future_versions(
                dependency_name, current_version, time_horizon
            )
        
        # Mock implementation for demonstration
        # In a real implementation, this would analyze release history
        predicted_versions = []
        
        # Parse current version
        current_parts = self._parse_version(current_version)
        if not current_parts:
            return []
        
        # Current date for predictions
        current_date = datetime.utcnow()
        
        # Predict patch releases (every 30 days)
        patch_interval = 30
        patch_count = time_horizon // patch_interval
        
        for i in range(1, min(patch_count + 1, 4)):  # Cap at 3 patch releases
            release_date = current_date + timedelta(days=i * patch_interval)
            
            if release_date > current_date + timedelta(days=time_horizon):
                break
                
            new_version = f"{current_parts[0]}.{current_parts[1]}.{current_parts[2] + i}"
            
            predicted_versions.append({
                "version": new_version,
                "predicted_date": release_date,
                "is_major": False,
                "is_minor": False,
                "confidence": 0.8 - (i * 0.1)  # Confidence decreases with time
            })
        
        # Predict minor releases (every 90 days)
        minor_interval = 90
        minor_count = time_horizon // minor_interval
        
        for i in range(1, min(minor_count + 1, 3)):  # Cap at 2 minor releases
            release_date = current_date + timedelta(days=i * minor_interval)
            
            if release_date > current_date + timedelta(days=time_horizon):
                break
                
            new_version = f"{current_parts[0]}.{current_parts[1] + i}.0"
            
            predicted_versions.append({
                "version": new_version,
                "predicted_date": release_date,
                "is_major": False,
                "is_minor": True,
                "confidence": 0.7 - (i * 0.1)
            })
        
        # Predict major release (if within time horizon)
        if time_horizon >= 180:  # 6 months or more
            release_date = current_date + timedelta(days=180)
            
            new_version = f"{current_parts[0] + 1}.0.0"
            
            predicted_versions.append({
                "version": new_version,
                "predicted_date": release_date,
                "is_major": True,
                "is_minor": False,
                "confidence": 0.5
            })
        
        # Sort by release date
        predicted_versions.sort(key=lambda x: x["predicted_date"])
        
        return predicted_versions
    
    def _identify_migration_points(
        self,
        predictions: List[Dict[str, Any]],
        current_version: str
    ) -> List[Dict[str, Any]]:
        """
        Identify optimal migration points in the future.
        
        Args:
            predictions: List of compatibility predictions
            current_version: Current version
            
        Returns:
            List of recommended migration points
        """
        migration_points = []
        
        if not predictions:
            return migration_points
        
        # Find points where staying on current version becomes problematic
        # or where a new version offers significant benefits
        for i, prediction in enumerate(predictions):
            # Skip very incompatible versions
            if prediction["compatibility_score"] < 0.3:
                continue
                
            is_migration_point = False
            
            # First point with good compatibility
            if (not migration_points and prediction["compatibility_score"] >= 0.7):
                is_migration_point = True
                migration_reason = "First stable upgrade path"
            
            # Major version upgrades with decent compatibility
            elif (prediction["is_major"] and prediction["compatibility_score"] >= 0.6):
                is_migration_point = True
                migration_reason = "Compatible major version upgrade"
            
            # Last point before a very incompatible release
            elif (i < len(predictions) - 1 and 
                  predictions[i+1]["compatibility_score"] < 0.4 and
                  prediction["compatibility_score"] >= 0.6):
                is_migration_point = True
                migration_reason = "Last good version before breaking changes"
            
            if is_migration_point:
                migration_points.append({
                    "version": prediction["version"],
                    "predicted_date": prediction["predicted_date"],
                    "compatibility_score": prediction["compatibility_score"],
                    "reason": migration_reason
                })
        
        return migration_points


class PythonCompatibilityPredictor:
    """Python-specific compatibility predictor."""
    
    async def predict_breaking_changes(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str
    ) -> List[Dict[str, Any]]:
        """
        Predict breaking changes for Python packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            target_version: Target version
            
        Returns:
            List of potential breaking changes
        """
        # Python-specific prediction logic
        breaking_changes = []
        
        # Example: Check for major Python framework version changes
        if dependency_name == "django":
            current_major = int(current_version.split('.')[0])
            target_major = int(target_version.split('.')[0])
            
            if target_major > current_major:
                # Django has major breaking changes between major versions
                # Add some known Django changes
                if current_major == 2 and target_major == 3:
                    breaking_changes.extend([
                        {
                            "type": "removed",
                            "symbol": "django.utils.six",
                            "description": "The django.utils.six module was removed in Django 3.0",
                            "impact": "high",
                            "confidence": 0.9,
                            "alternatives": ["import six"]
                        },
                        {
                            "type": "behavior_change",
                            "symbol": "django.http.JsonResponse",
                            "description": "JSON encoding behavior changed in Django 3.0",
                            "impact": "medium",
                            "confidence": 0.8
                        },
                        {
                            "type": "removed",
                            "symbol": "django.utils.encoding.python_2_unicode_compatible",
                            "description": "python_2_unicode_compatible decorator removed",
                            "impact": "medium",
                            "confidence": 0.85
                        }
                    ])
                elif current_major == 3 and target_major == 4:
                    breaking_changes.extend([
                        {
                            "type": "removed",
                            "symbol": "django.utils.encoding.force_text",
                            "description": "force_text was removed in favor of force_str",
                            "impact": "high",
                            "confidence": 0.9,
                            "alternatives": ["django.utils.encoding.force_str"]
                        },
                        {
                            "type": "behavior_change",
                            "symbol": "django.db.models.JSONField",
                            "description": "JSONField behavior changes in Django 4.0",
                            "impact": "medium",
                            "confidence": 0.8
                        }
                    ])
        elif dependency_name == "numpy":
            current_major = int(current_version.split('.')[0])
            target_major = int(target_version.split('.')[0])
            
            if current_major == 1 and target_major == 2:
                breaking_changes.extend([
                    {
                        "type": "behavior_change",
                        "symbol": "numpy.matrix",
                        "description": "numpy.matrix was deprecated and may be removed",
                        "impact": "high",
                        "confidence": 0.85,
                        "alternatives": ["numpy.array"]
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "numpy.random",
                        "description": "Random number generation API changed",
                        "impact": "high",
                        "confidence": 0.9
                    }
                ])
        
        return breaking_changes
    
    async def score_compatibility(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str
    ) -> Dict[str, Any]:
        """
        Score compatibility for Python packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            target_version: Target version
            
        Returns:
            Compatibility score details
        """
        # Predict breaking changes
        breaking_changes = await self.predict_breaking_changes(
            dependency_name, current_version, target_version
        )
        
        # Calculate version difference
        version_diff = self._calculate_version_diff(current_version, target_version)
        
        # Python-specific scoring logic
        # Start with a base score
        score = 1.0
        
        # Adjust based on version difference
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            # Major version increases have higher chance of incompatibility
            # Python packages tend to follow semantic versioning fairly well
            score -= 0.3
        elif diff_type == "minor":
            # Minor version increases have medium chance of incompatibility
            score -= 0.1
        elif diff_type == "patch":
            # Patch changes should be compatible, but still a small risk
            score -= 0.02
        
        # Further reduce score based on breaking changes
        high_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "high")
        medium_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "medium")
        
        score -= high_impact_changes * 0.15
        score -= medium_impact_changes * 0.08
        
        # Ensure score is within bounds
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "breaking_changes": breaking_changes,
            "version_diff": version_diff,
            "confidence": self._calculate_confidence(breaking_changes, version_diff),
            "recommendation": self._get_recommendation(score, breaking_changes)
        }
    
    async def predict_future_issues(
        self,
        dependency_name: str,
        current_version: str,
        time_horizon: int = 180
    ) -> Dict[str, Any]:
        """
        Predict future compatibility issues for Python packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            time_horizon: Time horizon in days
            
        Returns:
            Dictionary with future issue predictions
        """
        # Predict future versions
        future_versions = await self._predict_future_versions(
            dependency_name, current_version, time_horizon
        )
        
        # For each future version, predict compatibility
        compatibility_predictions = []
        for version_info in future_versions:
            version = version_info["version"]
            
            # Predict compatibility with this version
            compatibility = await self.score_compatibility(
                dependency_name, current_version, version
            )
            
            compatibility_predictions.append({
                "version": version,
                "predicted_date": version_info["predicted_date"],
                "compatibility_score": compatibility["score"],
                "breaking_changes": compatibility["breaking_changes"],
                "confidence": compatibility["confidence"]
            })
        
        return {
            "dependency": dependency_name,
            "current_version": current_version,
            "ecosystem": "python",
            "time_horizon_days": time_horizon,
            "future_versions": future_versions,
            "compatibility_predictions": compatibility_predictions
        }
    
    async def _predict_future_versions(
        self,
        dependency_name: str,
        current_version: str,
        time_horizon: int
    ) -> List[Dict[str, Any]]:
        """
        Predict future versions of a Python package.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            time_horizon: Time horizon in days
            
        Returns:
            List of predicted future versions
        """
        # Python-specific version prediction logic
        # This would ideally analyze historical release patterns
        
        # Parse current version
        try:
            version_parts = list(map(int, current_version.split('.')))
            while len(version_parts) < 3:
                version_parts.append(0)
        except ValueError:
            # If version can't be parsed as integers, use a fallback
            return []
        
        # Current date for predictions
        current_date = datetime.utcnow()
        predicted_versions = []
        
        # Python projects typically have slower release cycles than Node.js
        # Predict based on package type
        if dependency_name in ["django", "numpy", "pandas", "scipy"]:
            # Major frameworks have slower, well-defined release cycles
            
            # Patch releases - roughly every 60 days
            for i in range(1, 3):
                release_date = current_date + timedelta(days=i * 60)
                if release_date > current_date + timedelta(days=time_horizon):
                    break
                
                new_version = f"{version_parts[0]}.{version_parts[1]}.{version_parts[2] + i}"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": False,
                    "confidence": 0.75 - (i * 0.1)
                })
            
            # Minor releases - roughly every 6 months
            if time_horizon >= 180:
                release_date = current_date + timedelta(days=180)
                new_version = f"{version_parts[0]}.{version_parts[1] + 1}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.6
                })
            
            # Major releases - yearly or longer
            if time_horizon >= 365:
                release_date = current_date + timedelta(days=365)
                new_version = f"{version_parts[0] + 1}.0.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": True,
                    "is_minor": False,
                    "confidence": 0.5
                })
        else:
            # Smaller packages or utilities have more varied release patterns
            
            # Patch releases - roughly every 45 days
            for i in range(1, 4):
                release_date = current_date + timedelta(days=i * 45)
                if release_date > current_date + timedelta(days=time_horizon):
                    break
                
                new_version = f"{version_parts[0]}.{version_parts[1]}.{version_parts[2] + i}"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": False,
                    "confidence": 0.7 - (i * 0.1)
                })
            
            # Minor releases - roughly every 4 months
            if time_horizon >= 120:
                release_date = current_date + timedelta(days=120)
                new_version = f"{version_parts[0]}.{version_parts[1] + 1}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.6
                })
            
            # Second minor release
            if time_horizon >= 240:
                release_date = current_date + timedelta(days=240)
                new_version = f"{version_parts[0]}.{version_parts[1] + 2}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.5
                })
            
            # Major release - no specific timing for smaller packages
            if time_horizon >= 300:
                release_date = current_date + timedelta(days=300 + (hash(dependency_name) % 60))
                new_version = f"{version_parts[0] + 1}.0.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": True,
                    "is_minor": False,
                    "confidence": 0.4
                })
        
        # Sort by release date
        predicted_versions.sort(key=lambda x: x["predicted_date"])
        
        return predicted_versions
    
    def _calculate_version_diff(
        self,
        current_version: str,
        target_version: str
    ) -> Dict[str, Any]:
        """
        Calculate the difference between two Python package versions.
        
        Args:
            current_version: Current version
            target_version: Target version
            
        Returns:
            Version difference metrics
        """
        # Parse versions
        try:
            current_parts = list(map(int, current_version.split('.')))
            target_parts = list(map(int, target_version.split('.')))
            
            # Ensure at least 3 components
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(target_parts) < 3:
                target_parts.append(0)
                
        except ValueError:
            return {
                "is_upgrade": target_version > current_version,
                "diff_type": "unknown"
            }
        
        # Calculate the difference for each component
        diff = []
        for i in range(min(len(current_parts), len(target_parts))):
            diff.append(target_parts[i] - current_parts[i])
        
        # Determine the type of change
        if diff[0] > 0:
            diff_type = "major"
        elif diff[0] < 0:
            diff_type = "major_downgrade"
        elif diff[1] > 0:
            diff_type = "minor"
        elif diff[1] < 0:
            diff_type = "minor_downgrade"
        elif diff[2] > 0:
            diff_type = "patch"
        elif diff[2] < 0:
            diff_type = "patch_downgrade"
        else:
            diff_type = "same"
        
        return {
            "is_upgrade": diff_type in ["major", "minor", "patch"],
            "is_downgrade": diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"],
            "diff_type": diff_type,
            "diff": diff,
            "diff_magnitude": sum(abs(d) for d in diff)
        }
    
    def _calculate_confidence(
        self,
        breaking_changes: List[Dict[str, Any]],
        version_diff: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence in the compatibility prediction for Python packages.
        
        Args:
            breaking_changes: List of breaking changes
            version_diff: Version difference metrics
            
        Returns:
            Confidence score (0-1)
        """
        # Similar to parent implementation but with Python-specific adjustments
        confidence = 0.7
        
        # Adjust based on version difference
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            confidence += 0.15
        elif diff_type in ["minor", "patch"]:
            confidence += 0.05
        elif diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"]:
            confidence -= 0.1
        
        # Adjust based on breaking changes
        if breaking_changes:
            # Average confidence of breaking changes
            change_confidence = [c.get("confidence", 0.5) for c in breaking_changes]
            avg_confidence = sum(change_confidence) / len(change_confidence)
            
            # Weight of breaking changes confidence
            confidence = 0.7 * confidence + 0.3 * avg_confidence
        
        return max(0.1, min(1.0, confidence))
    
    def _get_recommendation(
        self,
        compatibility_score: float,
        breaking_changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get recommendation for Python package upgrade.
        
        Args:
            compatibility_score: Compatibility score
            breaking_changes: List of breaking changes
            
        Returns:
            Recommendation details
        """
        # Python-specific recommendations
        if compatibility_score >= 0.9:
            return {
                "action": "upgrade",
                "risk_level": "low",
                "message": "Safe to upgrade - no significant compatibility issues expected"
            }
        elif compatibility_score >= 0.7:
            return {
                "action": "upgrade_with_tests",
                "risk_level": "medium",
                "message": "Upgrade with test coverage - some minor compatibility issues may arise",
                "affected_apis": [c["symbol"] for c in breaking_changes if c.get("impact") in ["medium", "low"]]
            }
        elif compatibility_score >= 0.4:
            return {
                "action": "careful_migration",
                "risk_level": "high",
                "message": "Significant compatibility issues expected - prepare migration plan",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }
        else:
            return {
                "action": "not_recommended",
                "risk_level": "critical",
                "message": "Upgrade not recommended - major compatibility issues expected",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }


class NodeJSCompatibilityPredictor:
    """Node.js-specific compatibility predictor."""
    
    async def predict_breaking_changes(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str
    ) -> List[Dict[str, Any]]:
        """
        Predict breaking changes for Node.js packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            target_version: Target version
            
        Returns:
            List of potential breaking changes
        """
        # Node.js-specific prediction logic
        breaking_changes = []
        
        # Example: Check for major frontend framework version changes
        if dependency_name == "react":
            current_major = int(current_version.split('.')[0])
            target_major = int(target_version.split('.')[0])
            
            if current_major == 16 and target_major == 17:
                breaking_changes.extend([
                    {
                        "type": "behavior_change",
                        "symbol": "React.useEffect",
                        "description": "React 17 changes how useEffect cleanup functions are timed",
                        "impact": "medium",
                        "confidence": 0.8
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "React.event",
                        "description": "Event delegation model changed in React 17",
                        "impact": "medium",
                        "confidence": 0.85
                    }
                ])
            elif current_major == 17 and target_major == 18:
                breaking_changes.extend([
                    {
                        "type": "removed",
                        "symbol": "ReactDOM.render",
                        "description": "ReactDOM.render was replaced with ReactDOM.createRoot in React 18",
                        "impact": "high",
                        "confidence": 0.95,
                        "alternatives": ["ReactDOM.createRoot(container).render(<App />)"]
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "React.Suspense",
                        "description": "Suspense behavior changed in React 18",
                        "impact": "medium",
                        "confidence": 0.85
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "React.useEffect",
                        "description": "useEffect timing changed with automatic batching in React 18",
                        "impact": "high",
                        "confidence": 0.9
                    }
                ])
        elif dependency_name == "lodash":
            current_major = int(current_version.split('.')[0])
            target_major = int(target_version.split('.')[0])
            
            if current_major == 3 and target_major == 4:
                breaking_changes.extend([
                    {
                        "type": "removed",
                        "symbol": "_.pluck",
                        "description": "_.pluck was removed in favor of _.map with property shorthand",
                        "impact": "high",
                        "confidence": 0.95,
                        "alternatives": ["_.map(collection, 'property')"]
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "_.flatten",
                        "description": "_.flatten is now shallow by default in Lodash 4",
                        "impact": "high",
                        "confidence": 0.9,
                        "alternatives": ["_.flattenDeep"]
                    },
                    {
                        "type": "behavior_change",
                        "symbol": "_.filter",
                        "description": "_.filter no longer coerces values to objects in Lodash 4",
                        "impact": "medium",
                        "confidence": 0.85
                    }
                ])
        
        return breaking_changes
    
    async def score_compatibility(
        self,
        dependency_name: str,
        current_version: str,
        target_version: str
    ) -> Dict[str, Any]:
        """
        Score compatibility for Node.js packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            target_version: Target version
            
        Returns:
            Compatibility score details
        """
        # Predict breaking changes
        breaking_changes = await self.predict_breaking_changes(
            dependency_name, current_version, target_version
        )
        
        # Calculate version difference
        version_diff = self._calculate_version_diff(current_version, target_version)
        
        # Node.js-specific scoring logic
        # Start with a base score
        score = 1.0
        
        # Adjust based on version difference
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            # Node.js ecosystem tends to follow semantic versioning strictly
            score -= 0.4  # Higher penalty than Python for major version changes
        elif diff_type == "minor":
            score -= 0.1
        elif diff_type == "patch":
            score -= 0.01  # Very small risk for patch changes
        
        # Further reduce score based on breaking changes
        high_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "high")
        medium_impact_changes = sum(1 for c in breaking_changes if c.get("impact") == "medium")
        
        score -= high_impact_changes * 0.15
        score -= medium_impact_changes * 0.08
        
        # Ensure score is within bounds
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "breaking_changes": breaking_changes,
            "version_diff": version_diff,
            "confidence": self._calculate_confidence(breaking_changes, version_diff),
            "recommendation": self._get_recommendation(score, breaking_changes)
        }
    
    async def predict_future_issues(
        self,
        dependency_name: str,
        current_version: str,
        time_horizon: int = 180
    ) -> Dict[str, Any]:
        """
        Predict future compatibility issues for Node.js packages.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            time_horizon: Time horizon in days
            
        Returns:
            Dictionary with future issue predictions
        """
        # Predict future versions
        future_versions = await self._predict_future_versions(
            dependency_name, current_version, time_horizon
        )
        
        # For each future version, predict compatibility
        compatibility_predictions = []
        for version_info in future_versions:
            version = version_info["version"]
            
            # Predict compatibility with this version
            compatibility = await self.score_compatibility(
                dependency_name, current_version, version
            )
            
            compatibility_predictions.append({
                "version": version,
                "predicted_date": version_info["predicted_date"],
                "compatibility_score": compatibility["score"],
                "breaking_changes": compatibility["breaking_changes"],
                "confidence": compatibility["confidence"]
            })
        
        return {
            "dependency": dependency_name,
            "current_version": current_version,
            "ecosystem": "nodejs",
            "time_horizon_days": time_horizon,
            "future_versions": future_versions,
            "compatibility_predictions": compatibility_predictions
        }
    
    async def _predict_future_versions(
        self,
        dependency_name: str,
        current_version: str,
        time_horizon: int
    ) -> List[Dict[str, Any]]:
        """
        Predict future versions of a Node.js package.
        
        Args:
            dependency_name: Package name
            current_version: Current version
            time_horizon: Time horizon in days
            
        Returns:
            List of predicted future versions
        """
        # Node.js-specific version prediction logic
        # This would ideally analyze historical release patterns
        
        # Parse current version
        try:
            version_parts = list(map(int, current_version.split('.')))
            while len(version_parts) < 3:
                version_parts.append(0)
        except ValueError:
            # If version can't be parsed as integers, use a fallback
            return []
        
        # Current date for predictions
        current_date = datetime.utcnow()
        predicted_versions = []
        
        # Node.js projects typically have faster release cycles
        # Adjust based on package type
        if dependency_name in ["react", "angular", "vue"]:
            # Major frontend frameworks have well-defined release cycles
            
            # Patch releases - roughly every 30 days
            for i in range(1, 4):
                release_date = current_date + timedelta(days=i * 30)
                if release_date > current_date + timedelta(days=time_horizon):
                    break
                
                new_version = f"{version_parts[0]}.{version_parts[1]}.{version_parts[2] + i}"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": False,
                    "confidence": 0.8 - (i * 0.1)
                })
            
            # Minor releases - roughly every 3 months
            if time_horizon >= 90:
                release_date = current_date + timedelta(days=90)
                new_version = f"{version_parts[0]}.{version_parts[1] + 1}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.7
                })
            
            # Second minor release
            if time_horizon >= 180:
                release_date = current_date + timedelta(days=180)
                new_version = f"{version_parts[0]}.{version_parts[1] + 2}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.6
                })
            
            # Major releases - yearly
            if time_horizon >= 365:
                release_date = current_date + timedelta(days=365)
                new_version = f"{version_parts[0] + 1}.0.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": True,
                    "is_minor": False,
                    "confidence": 0.5
                })
        else:
            # Smaller packages or utilities have more varied release patterns
            
            # Patch releases - roughly every 15-20 days
            for i in range(1, 6):
                release_date = current_date + timedelta(days=i * 15)
                if release_date > current_date + timedelta(days=time_horizon):
                    break
                
                new_version = f"{version_parts[0]}.{version_parts[1]}.{version_parts[2] + i}"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": False,
                    "confidence": 0.75 - (i * 0.1)
                })
            
            # Minor releases - roughly every 2 months
            minor_release_count = (time_horizon // 60) + 1
            for i in range(1, min(minor_release_count, 4)):
                release_date = current_date + timedelta(days=i * 60)
                if release_date > current_date + timedelta(days=time_horizon):
                    break
                
                new_version = f"{version_parts[0]}.{version_parts[1] + i}.0"
                predicted_versions.append({
                    "version": new_version,
                    "predicted_date": release_date,
                    "is_major": False,
                    "is_minor": True,
                    "confidence": 0.65 - (i * 0.1)
                })
            
            # Major release - varies by package
            if time_horizon >= 180:
                # Use package name hash to create some variance in prediction
                days_to_major = 180 + (hash(dependency_name) % 90)
                release_date = current_date + timedelta(days=days_to_major)
                
                if release_date <= current_date + timedelta(days=time_horizon):
                    new_version = f"{version_parts[0] + 1}.0.0"
                    predicted_versions.append({
                        "version": new_version,
                        "predicted_date": release_date,
                        "is_major": True,
                        "is_minor": False,
                        "confidence": 0.45
                    })
        
        # Sort by release date
        predicted_versions.sort(key=lambda x: x["predicted_date"])
        
        return predicted_versions
    
    def _calculate_version_diff(
        self,
        current_version: str,
        target_version: str
    ) -> Dict[str, Any]:
        """
        Calculate the difference between two Node.js package versions.
        
        Args:
            current_version: Current version
            target_version: Target version
            
        Returns:
            Version difference metrics
        """
        # Similar to Python implementation
        try:
            current_parts = list(map(int, current_version.split('.')))
            target_parts = list(map(int, target_version.split('.')))
            
            # Ensure at least 3 components
            while len(current_parts) < 3:
                current_parts.append(0)
            while len(target_parts) < 3:
                target_parts.append(0)
                
        except ValueError:
            return {
                "is_upgrade": target_version > current_version,
                "diff_type": "unknown"
            }
        
        # Calculate the difference for each component
        diff = []
        for i in range(min(len(current_parts), len(target_parts))):
            diff.append(target_parts[i] - current_parts[i])
        
        # Determine the type of change
        if diff[0] > 0:
            diff_type = "major"
        elif diff[0] < 0:
            diff_type = "major_downgrade"
        elif diff[1] > 0:
            diff_type = "minor"
        elif diff[1] < 0:
            diff_type = "minor_downgrade"
        elif diff[2] > 0:
            diff_type = "patch"
        elif diff[2] < 0:
            diff_type = "patch_downgrade"
        else:
            diff_type = "same"
        
        return {
            "is_upgrade": diff_type in ["major", "minor", "patch"],
            "is_downgrade": diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"],
            "diff_type": diff_type,
            "diff": diff,
            "diff_magnitude": sum(abs(d) for d in diff)
        }
    
    def _calculate_confidence(
        self,
        breaking_changes: List[Dict[str, Any]],
        version_diff: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence in the compatibility prediction for Node.js packages.
        
        Args:
            breaking_changes: List of breaking changes
            version_diff: Version difference metrics
            
        Returns:
            Confidence score (0-1)
        """
        # Similar to parent implementation but with Node.js-specific adjustments
        confidence = 0.7
        
        # Node.js packages tend to follow semver more strictly, so we have higher
        # confidence in semver-based predictions
        diff_type = version_diff["diff_type"]
        if diff_type == "major":
            confidence += 0.2  # Higher confidence for major changes
        elif diff_type in ["minor", "patch"]:
            confidence += 0.1
        elif diff_type in ["major_downgrade", "minor_downgrade", "patch_downgrade"]:
            confidence -= 0.15
        
        # Adjust based on breaking changes
        if breaking_changes:
            # Average confidence of breaking changes
            change_confidence = [c.get("confidence", 0.5) for c in breaking_changes]
            avg_confidence = sum(change_confidence) / len(change_confidence)
            
            # Weight of breaking changes confidence
            confidence = 0.65 * confidence + 0.35 * avg_confidence
        
        return max(0.1, min(1.0, confidence))
    
    def _get_recommendation(
        self,
        compatibility_score: float,
        breaking_changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get recommendation for Node.js package upgrade.
        
        Args:
            compatibility_score: Compatibility score
            breaking_changes: List of breaking changes
            
        Returns:
            Recommendation details
        """
        # Node.js-specific recommendations
        if compatibility_score >= 0.95:
            return {
                "action": "upgrade",
                "risk_level": "very_low",
                "message": "Safe to upgrade - follows semver principles"
            }
        elif compatibility_score >= 0.8:
            return {
                "action": "upgrade_with_review",
                "risk_level": "low",
                "message": "Review code but should be safe to upgrade"
            }
        elif compatibility_score >= 0.6:
            return {
                "action": "upgrade_with_tests",
                "risk_level": "medium",
                "message": "Upgrade with test verification - minor compatibility issues may arise",
                "affected_apis": [c["symbol"] for c in breaking_changes if c.get("impact") in ["medium", "low"]]
            }
        elif compatibility_score >= 0.4:
            return {
                "action": "prepare_migration_plan",
                "risk_level": "high",
                "message": "Create migration plan - significant breaking changes expected",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }
        else:
            return {
                "action": "not_recommended",
                "risk_level": "critical",
                "message": "Major breaking changes - requires substantial code refactoring",
                "affected_apis": [c["symbol"] for c in breaking_changes]
            }