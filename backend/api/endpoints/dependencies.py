import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel

from backend.core.db import get_db
from backend.core.models import User, Dependency, DependencyVersion, LicenseReport, VulnerabilityReport
from backend.api.auth import get_current_active_user
from backend.services.health_monitoring import get_health_monitor

router = APIRouter()


# Models
class DependencyResponse(BaseModel):
    id: str
    name: str
    ecosystem: str
    latest_version: Optional[str] = None
    description: Optional[str] = None
    repository_url: Optional[str] = None
    homepage_url: Optional[str] = None
    health_score: Optional[float] = None
    is_deprecated: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True


class DependencyVersionResponse(BaseModel):
    id: str
    version: str
    published_at: Optional[datetime] = None
    size_bytes: Optional[int] = None
    is_yanked: Optional[bool] = None
    licenses: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[Dict[str, Any]] = None
    security_vulnerabilities: Optional[int] = None
    performance_score: Optional[float] = None
    
    class Config:
        orm_mode = True


class DependencyDetailResponse(DependencyResponse):
    versions: Optional[List[DependencyVersionResponse]] = None
    license_reports: Optional[List[Dict[str, Any]]] = None
    vulnerability_reports: Optional[List[Dict[str, Any]]] = None


# Endpoints
@router.get("/", response_model=List[DependencyResponse])
async def get_dependencies(
    ecosystem: Optional[str] = None,
    name: Optional[str] = None,
    deprecated: Optional[bool] = None,
    min_health: Optional[float] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all dependencies with optional filtering.
    """
    query = db.query(Dependency)
    
    # Apply filters
    if ecosystem:
        query = query.filter(Dependency.ecosystem == ecosystem)
    
    if name:
        query = query.filter(Dependency.name.ilike(f"%{name}%"))
    
    if deprecated is not None:
        query = query.filter(Dependency.is_deprecated == deprecated)
    
    if min_health is not None:
        query = query.filter(Dependency.health_score >= min_health)
    
    dependencies = query.offset(skip).limit(limit).all()
    return dependencies


@router.get("/{dependency_id}", response_model=DependencyDetailResponse)
async def get_dependency(
    dependency_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a dependency.
    """
    dependency = db.query(Dependency).filter(Dependency.id == dependency_id).first()
    
    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found"
        )
    
    # Get versions
    versions = db.query(DependencyVersion).filter(
        DependencyVersion.dependency_id == dependency_id
    ).all()
    
    # Get license reports
    license_reports = []
    for version in versions:
        reports = db.query(LicenseReport).filter(
            LicenseReport.version_id == version.id
        ).all()
        
        for report in reports:
            license_reports.append({
                "id": str(report.id),
                "version": version.version,
                "license_id": report.license_id,
                "license_name": report.license_name,
                "license_type": report.license_type,
                "risk_level": report.risk_level,
                "is_compliant": report.is_compliant,
                "compliance_notes": report.compliance_notes
            })
    
    # Get vulnerability reports
    vulnerability_reports = []
    for version in versions:
        reports = db.query(VulnerabilityReport).filter(
            VulnerabilityReport.version_id == version.id
        ).all()
        
        for report in reports:
            vulnerability_reports.append({
                "id": str(report.id),
                "version": version.version,
                "cve_id": report.cve_id,
                "title": report.title,
                "description": report.description,
                "severity": report.severity,
                "fixed_in": report.fixed_in,
                "exploitability_score": report.exploitability_score
            })
    
    # Combine all information
    result = DependencyDetailResponse(
        **{key: getattr(dependency, key) for key in DependencyResponse.__fields__},
        versions=[
            DependencyVersionResponse(
                **{key: getattr(version, key) for key in DependencyVersionResponse.__fields__}
            ) for version in versions
        ],
        license_reports=license_reports,
        vulnerability_reports=vulnerability_reports
    )
    
    return result


@router.get("/search/", response_model=List[DependencyResponse])
async def search_dependencies(
    q: str = Query(..., min_length=2),
    ecosystem: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Search for dependencies by name, description, or other fields.
    """
    query = db.query(Dependency).filter(
        or_(
            Dependency.name.ilike(f"%{q}%"),
            Dependency.description.ilike(f"%{q}%")
        )
    )
    
    if ecosystem:
        query = query.filter(Dependency.ecosystem == ecosystem)
    
    dependencies = query.offset(skip).limit(limit).all()
    return dependencies


@router.post("/{dependency_id}/refresh", response_model=DependencyResponse)
async def refresh_dependency_data(
    dependency_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Refresh dependency data from package registries and sources.
    """
    dependency = db.query(Dependency).filter(Dependency.id == dependency_id).first()
    
    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found"
        )
    
    # Create a DependencyInfo object for the health monitor
    from backend.analysis.dependency_parser import DependencyInfo
    dep_info = DependencyInfo(
        name=dependency.name,
        version=dependency.latest_version or "latest",
        ecosystem=dependency.ecosystem,
        repository_url=dependency.repository_url
    )
    
    # Refresh health data
    health_monitor = get_health_monitor(db)
    health_report = await health_monitor._check_dependency_health(dep_info)
    
    # Update dependency with new data
    dependency.health_score = health_report["health_score"]
    dependency.is_deprecated = health_report["maintenance_status"] in ["deprecated", "archived"]
    
    # Update metadata
    metadata = dependency.metadata or {}
    metadata.update({
        "last_refresh": datetime.utcnow().isoformat(),
        "last_release": health_report["last_release"],
        "days_since_update": health_report["days_since_update"],
        "maintenance_status": health_report["maintenance_status"],
        "community_metrics": health_report["community_metrics"],
        "funding_status": health_report["funding_status"],
        "risk_factors": health_report["risk_factors"]
    })
    dependency.metadata = metadata
    
    db.commit()
    db.refresh(dependency)
    
    return dependency


@router.get("/{dependency_id}/versions", response_model=List[DependencyVersionResponse])
async def get_dependency_versions(
    dependency_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all versions of a dependency.
    """
    dependency = db.query(Dependency).filter(Dependency.id == dependency_id).first()
    
    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found"
        )
    
    versions = db.query(DependencyVersion).filter(
        DependencyVersion.dependency_id == dependency_id
    ).order_by(
        DependencyVersion.published_at.desc()
    ).all()
    
    return versions


@router.get("/{dependency_id}/recommendations", response_model=List[Dict[str, Any]])
async def get_dependency_recommendations(
    dependency_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendations for a dependency.
    """
    dependency = db.query(Dependency).filter(Dependency.id == dependency_id).first()
    
    if not dependency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found"
        )
    
    # Create a DependencyInfo object for the health monitor
    from backend.analysis.dependency_parser import DependencyInfo
    dep_info = DependencyInfo(
        name=dependency.name,
        version=dependency.latest_version or "latest",
        ecosystem=dependency.ecosystem,
        repository_url=dependency.repository_url
    )
    
    # Get health monitor
    health_monitor = get_health_monitor(db)
    
    # Get recommendations
    recommendations = await health_monitor._find_alternative(
        {"name": dependency.name, "ecosystem": dependency.ecosystem}
    )
    
    if recommendations:
        return [recommendations]
    
    # If no specific recommendations found, generate generic ones
    generic_recommendations = []
    
    # Check health score and provide generic advice
    if dependency.health_score is not None:
        if dependency.health_score < 0.4:
            generic_recommendations.append({
                "type": "health",
                "message": "This dependency has a low health score and may need attention.",
                "action": "Consider finding an alternative or contributing to the project."
            })
    
    # Check if deprecated
    if dependency.is_deprecated:
        generic_recommendations.append({
            "type": "deprecation",
            "message": "This dependency is deprecated.",
            "action": "Look for an actively maintained alternative."
        })
    
    return generic_recommendations or [{"type": "info", "message": "No specific recommendations available."}]