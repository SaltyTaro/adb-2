import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.db import get_db
from backend.core.models import User, Project, Dependency, Recommendation, Analysis
from backend.api.auth import get_current_active_user

router = APIRouter()


# Models
class RecommendationResponse(BaseModel):
    id: str
    title: str
    description: str
    recommendation_type: str
    severity: str
    impact: Optional[float] = None
    effort: Optional[float] = None
    code_changes: Optional[Dict[str, Any]] = None
    dependency_name: Optional[str] = None
    from_version: Optional[str] = None
    to_version: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True


class RecommendationCreate(BaseModel):
    title: str
    description: str
    recommendation_type: str
    severity: str
    impact: Optional[float] = None
    effort: Optional[float] = None
    code_changes: Optional[Dict[str, Any]] = None
    dependency_name: Optional[str] = None
    from_version: Optional[str] = None
    to_version: Optional[str] = None


# Endpoints
@router.get("/projects/{project_id}/recommendations", response_model=List[RecommendationResponse])
async def get_project_recommendations(
    project_id: str,
    recommendation_type: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendations for a project.
    """
    # Check if project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Query recommendations
    query = db.query(Recommendation).filter(Recommendation.project_id == project_id)
    
    if recommendation_type:
        query = query.filter(Recommendation.recommendation_type == recommendation_type)
    
    if severity:
        query = query.filter(Recommendation.severity == severity)
    
    recommendations = query.order_by(
        Recommendation.severity.desc(),
        Recommendation.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return recommendations


@router.post("/projects/{project_id}/recommendations", response_model=RecommendationResponse)
async def create_recommendation(
    project_id: str,
    recommendation: RecommendationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new recommendation for a project.
    """
    # Check if project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create recommendation
    db_recommendation = Recommendation(
        id=uuid.uuid4(),
        project_id=project_id,
        title=recommendation.title,
        description=recommendation.description,
        recommendation_type=recommendation.recommendation_type,
        severity=recommendation.severity,
        impact=recommendation.impact,
        effort=recommendation.effort,
        code_changes=recommendation.code_changes,
        dependency_name=recommendation.dependency_name,
        from_version=recommendation.from_version,
        to_version=recommendation.to_version
    )
    
    db.add(db_recommendation)
    db.commit()
    db.refresh(db_recommendation)
    
    return db_recommendation


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific recommendation.
    """
    # Get recommendation and check if it belongs to a project owned by the user
    recommendation = db.query(Recommendation).join(Project).filter(
        Recommendation.id == recommendation_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found or you don't have access to it"
        )
    
    return recommendation


@router.delete("/recommendations/{recommendation_id}", response_model=Dict[str, Any])
async def delete_recommendation(
    recommendation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a recommendation.
    """
    # Get recommendation and check if it belongs to a project owned by the user
    recommendation = db.query(Recommendation).join(Project).filter(
        Recommendation.id == recommendation_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found or you don't have access to it"
        )
    
    # Delete recommendation
    db.delete(recommendation)
    db.commit()
    
    return {"message": "Recommendation deleted successfully"}


@router.get("/projects/{project_id}/generate-recommendations", response_model=Dict[str, Any])
async def generate_recommendations(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate recommendations based on existing analyses.
    """
    # Check if project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get completed analyses
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.status == "completed"
    ).order_by(Analysis.created_at.desc()).all()
    
    if not analyses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed analyses found for this project"
        )
    
    # Generate recommendations based on analyses
    recommendations = []
    created_count = 0
    
    for analysis in analyses:
        if not analysis.result:
            continue
            
        new_recommendations = []
        
        if analysis.analysis_type == "impact_scoring":
            # Recommendations for high impact dependencies
            if "high_impact_count" in analysis.result and analysis.result["high_impact_count"] > 0:
                # Need to get specific impact scores
                from backend.core.models import ImpactScore
                high_impact_scores = db.query(ImpactScore).filter(
                    ImpactScore.analysis_id == analysis.id,
                    ImpactScore.overall_score >= 0.8  # High impact threshold
                ).all()
                
                for score in high_impact_scores:
                    new_recommendations.append({
                        "title": f"High impact dependency: {score.dependency_name}",
                        "description": (
                            f"This dependency has a high impact score of {score.overall_score:.2f}, "
                            f"indicating it's critical to your application. Ensure it's well maintained "
                            f"and has a backup plan in case of issues."
                        ),
                        "recommendation_type": "impact_monitoring",
                        "severity": "high",
                        "dependency_name": score.dependency_name
                    })
            
            # Recommendations for low usage
            if "low_usage_count" in analysis.result and analysis.result["low_usage_count"] > 0:
                low_usage_scores = db.query(ImpactScore).filter(
                    ImpactScore.analysis_id == analysis.id,
                    ImpactScore.usage_score <= 0.3  # Low usage threshold
                ).all()
                
                for score in low_usage_scores:
                    new_recommendations.append({
                        "title": f"Low usage efficiency: {score.dependency_name}",
                        "description": (
                            f"You're only using {score.usage_score:.0%} of this dependency's features. "
                            f"Consider using a lighter alternative or importing only what you need."
                        ),
                        "recommendation_type": "usage_optimization",
                        "severity": "medium",
                        "dependency_name": score.dependency_name
                    })
        
        elif analysis.analysis_type == "compatibility_prediction":
            # Recommendations for breaking changes
            if ("issue_counts" in analysis.result and 
                ("critical" in analysis.result["issue_counts"] or "high" in analysis.result["issue_counts"])):
                
                issue_count = (
                    analysis.result["issue_counts"].get("critical", 0) + 
                    analysis.result["issue_counts"].get("high", 0)
                )
                
                if issue_count > 0:
                    new_recommendations.append({
                        "title": f"Potential breaking changes detected",
                        "description": (
                            f"Breaking changes were predicted in {issue_count} dependencies. "
                            f"Review the compatibility prediction analysis for details and plan upgrades carefully."
                        ),
                        "recommendation_type": "breaking_change_planning",
                        "severity": "high"
                    })
        
        elif analysis.analysis_type == "dependency_consolidation":
            # Recommendations for duplicate functionality
            if "potential_removals" in analysis.result and analysis.result["potential_removals"] > 0:
                new_recommendations.append({
                    "title": "Dependency consolidation opportunity",
                    "description": (
                        f"You could potentially remove {analysis.result['potential_removals']} dependencies "
                        f"by consolidating similar functionality. Review the consolidation analysis for details."
                    ),
                    "recommendation_type": "consolidation",
                    "severity": "medium"
                })
        
        elif analysis.analysis_type == "health_monitoring":
            # Recommendations for unhealthy dependencies
            if "health_distribution" in analysis.result and "at_risk" in analysis.result["health_distribution"]:
                at_risk_count = analysis.result["health_distribution"]["at_risk"]
                
                if at_risk_count > 0:
                    new_recommendations.append({
                        "title": "Dependencies with health issues detected",
                        "description": (
                            f"{at_risk_count} dependencies show signs of being abandoned or poorly maintained. "
                            f"Review the health monitoring analysis and consider finding alternatives."
                        ),
                        "recommendation_type": "health_improvement",
                        "severity": "high"
                    })
        
        elif analysis.analysis_type == "license_compliance":
            # Recommendations for license issues
            if "risk_counts" in analysis.result and "high" in analysis.result["risk_counts"]:
                high_risk_count = analysis.result["risk_counts"]["high"]
                
                if high_risk_count > 0:
                    new_recommendations.append({
                        "title": "License compliance risks detected",
                        "description": (
                            f"{high_risk_count} dependencies have high license compliance risks. "
                            f"Review the license compliance analysis and address these issues promptly."
                        ),
                        "recommendation_type": "license_compliance",
                        "severity": "high"
                    })
        
        elif analysis.analysis_type == "performance_profiling":
            # Recommendations for performance issues
            if "profile_type" in analysis.result:
                if analysis.result["profile_type"] == "bundle_size" and "total_size_gzipped" in analysis.result:
                    size_mb = analysis.result["total_size_gzipped"] / (1024 * 1024)
                    
                    if size_mb > 1.0:  # More than 1MB
                        new_recommendations.append({
                            "title": "Large bundle size detected",
                            "description": (
                                f"Your dependencies add up to {size_mb:.2f}MB (gzipped). "
                                f"Consider code splitting or using lighter alternatives for better load times."
                            ),
                            "recommendation_type": "performance_optimization",
                            "severity": "medium"
                        })
        
        # Create recommendations in database
        for rec_data in new_recommendations:
            # Check if a similar recommendation already exists
            existing = db.query(Recommendation).filter(
                Recommendation.project_id == project_id,
                Recommendation.title == rec_data["title"]
            ).first()
            
            if not existing:
                db_recommendation = Recommendation(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    **rec_data
                )
                
                db.add(db_recommendation)
                recommendations.append(db_recommendation)
                created_count += 1
    
    # Commit all new recommendations
    if created_count > 0:
        db.commit()
    
    return {
        "message": f"Generated {created_count} new recommendations",
        "recommendations_count": created_count
    }