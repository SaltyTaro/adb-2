import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.db import get_db
from backend.core.models import User, Project, Analysis, Dependency
from backend.api.auth import get_current_active_user
from backend.services.impact_scoring import get_impact_scorer
from backend.services.predictive_management import get_compatibility_predictor
from backend.services.dependency_consolidation import get_dependency_consolidator
from backend.services.health_monitoring import get_health_monitor
from backend.services.license_compliance import get_license_manager
from backend.services.performance_profiling import get_performance_profiler

router = APIRouter()


# Models
class AnalysisRequest(BaseModel):
    analysis_type: str
    config: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    id: str
    project_id: str
    analysis_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True


# Background tasks for analysis
async def run_impact_scoring(project_id: str, analysis_id: str, db: Session):
    """Background task for impact scoring analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        impact_scorer = get_impact_scorer(db)
        impact_scores, summary = await impact_scorer.score_dependencies(
            dep_infos, project_id
        )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = summary
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


async def run_compatibility_prediction(project_id: str, analysis_id: str, db: Session, time_horizon: int = 180):
    """Background task for compatibility prediction analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        compatibility_predictor = get_compatibility_predictor(db)
        timeline, results = await compatibility_predictor.predict_compatibility_issues(
            dep_infos, project_id, time_horizon
        )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = {
            "summary": results,
            "timeline_count": len(timeline)
        }
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


async def run_dependency_consolidation(project_id: str, analysis_id: str, db: Session):
    """Background task for dependency consolidation analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        dependency_consolidator = get_dependency_consolidator(db)
        recommendations, metrics = await dependency_consolidator.analyze_dependencies(
            dep_infos, project_id
        )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = {
            "metrics": metrics,
            "recommendation_count": (
                len(recommendations.get("duplicates", [])) +
                len(recommendations.get("transitive", [])) +
                len(recommendations.get("versions", []))
            )
        }
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


async def run_health_monitoring(project_id: str, analysis_id: str, db: Session):
    """Background task for health monitoring analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        health_monitor = get_health_monitor(db)
        summary, reports = await health_monitor.analyze_dependencies_health(
            dep_infos, project_id
        )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = summary
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


async def run_license_compliance(project_id: str, analysis_id: str, db: Session, target_license: str = "mit"):
    """Background task for license compliance analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        license_manager = get_license_manager(db)
        summary, reports = await license_manager.analyze_licenses(
            dep_infos, project_id, target_license
        )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = summary
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


async def run_performance_profiling(project_id: str, analysis_id: str, db: Session, profile_type: str = "bundle_size"):
    """Background task for performance profiling analysis."""
    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        # Get dependencies
        dependencies = project.dependencies
        if not dependencies:
            return
        
        # Convert to DependencyInfo objects
        from backend.analysis.dependency_parser import DependencyInfo
        dep_infos = []
        for dep in dependencies:
            dep_info = DependencyInfo(
                name=dep.name,
                version=dep.latest_version or "latest",
                ecosystem=dep.ecosystem,
                is_direct=True,  # Assume all are direct for now
                repository_url=dep.repository_url
            )
            dep_infos.append(dep_info)
        
        # Update analysis status
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        
        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.commit()
        
        # Run analysis
        performance_profiler = get_performance_profiler(db)
        
        if profile_type == "bundle_size":
            result = await performance_profiler.analyze_bundle_size(
                dep_infos, project_id
            )
        else:  # Runtime performance
            result = await performance_profiler.analyze_runtime_performance(
                dep_infos, project_id
            )
        
        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.result = {
            "profile_type": profile_type,
            "total_dependencies": result["total_dependencies"],
            "direct_dependencies": result["direct_dependencies"]
        }
        
        if profile_type == "bundle_size":
            analysis.result.update({
                "total_size_gzipped": result["total_size_gzipped"],
                "direct_size_gzipped": result["direct_size_gzipped"]
            })
        else:
            analysis.result.update({
                "avg_runtime_impact_ms": result["avg_runtime_impact_ms"],
                "avg_memory_impact_mb": result["avg_memory_impact_mb"]
            })
        
        db.commit()
        
    except Exception as e:
        # Update analysis with error
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()


# Endpoints
@router.post("/projects/{project_id}/analyze", response_model=AnalysisResponse)
async def start_analysis(
    project_id: str,
    analysis_req: AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Start a new analysis for a project.
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
    
    # Check if dependencies exist
    if not project.dependencies or len(project.dependencies) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run analysis - project has no dependencies. Upload project files first."
        )
    
    # Validate analysis type
    valid_types = [
        "impact_scoring",
        "compatibility_prediction",
        "dependency_consolidation",
        "health_monitoring",
        "license_compliance",
        "performance_profiling"
    ]
    
    if analysis_req.analysis_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid analysis type. Valid types: {', '.join(valid_types)}"
        )
    
    # Create analysis record
    analysis = Analysis(
        id=uuid.uuid4(),
        project_id=project_id,
        analysis_type=analysis_req.analysis_type,
        status="pending",
        config=analysis_req.config or {}
    )
    
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    # Start appropriate background task
    if analysis_req.analysis_type == "impact_scoring":
        background_tasks.add_task(run_impact_scoring, project_id, str(analysis.id), db)
    
    elif analysis_req.analysis_type == "compatibility_prediction":
        # Get time horizon from config or use default
        time_horizon = analysis_req.config.get("time_horizon", 180) if analysis_req.config else 180
        background_tasks.add_task(run_compatibility_prediction, project_id, str(analysis.id), db, time_horizon)
    
    elif analysis_req.analysis_type == "dependency_consolidation":
        background_tasks.add_task(run_dependency_consolidation, project_id, str(analysis.id), db)
    
    elif analysis_req.analysis_type == "health_monitoring":
        background_tasks.add_task(run_health_monitoring, project_id, str(analysis.id), db)
    
    elif analysis_req.analysis_type == "license_compliance":
        # Get target license from config or use default
        target_license = analysis_req.config.get("target_license", "mit") if analysis_req.config else "mit"
        background_tasks.add_task(run_license_compliance, project_id, str(analysis.id), db, target_license)
    
    elif analysis_req.analysis_type == "performance_profiling":
        # Get profile type from config or use default
        profile_type = analysis_req.config.get("profile_type", "bundle_size") if analysis_req.config else "bundle_size"
        background_tasks.add_task(run_performance_profiling, project_id, str(analysis.id), db, profile_type)
    
    return analysis


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get analysis by ID.
    """
    # Get analysis and check if it belongs to a project owned by the user
    analysis = db.query(Analysis).join(Project).filter(
        Analysis.id == analysis_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or you don't have access to it"
        )
    
    return analysis


@router.get("/analyses/{analysis_id}/details", response_model=Dict[str, Any])
async def get_analysis_details(
    analysis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed results of an analysis.
    """
    # Get analysis and check if it belongs to a project owned by the user
    analysis = db.query(Analysis).join(Project).filter(
        Analysis.id == analysis_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or you don't have access to it"
        )
    
    # Check if analysis is completed
    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis is not yet completed. Current status: {analysis.status}"
        )
    
    # Based on analysis type, retrieve the detailed results
    project_id = str(analysis.project_id)
    
    try:
        if analysis.analysis_type == "impact_scoring":
            # Get all dependencies for the project
            project = db.query(Project).filter(Project.id == project_id).first()
            deps = project.dependencies
            
            # Get impact scores for this analysis
            from backend.core.models import ImpactScore
            scores = db.query(ImpactScore).filter(
                ImpactScore.analysis_id == analysis_id
            ).all()
            
            scores_data = []
            for score in scores:
                scores_data.append({
                    "dependency_name": score.dependency_name,
                    "version": score.version,
                    "business_value_score": score.business_value_score,
                    "usage_score": score.usage_score,
                    "complexity_score": score.complexity_score,
                    "health_score": score.health_score,
                    "overall_score": score.overall_score,
                    "used_features": score.used_features,
                    "unused_features": score.unused_features
                })
            
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result,
                "detailed_scores": scores_data
            }
            
        elif analysis.analysis_type == "compatibility_prediction":
            # To get detailed timeline, we would need to re-run the prediction or store it
            # For now, just return the summary
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result
            }
            
        elif analysis.analysis_type == "dependency_consolidation":
            # Get all dependencies for the project
            project = db.query(Project).filter(Project.id == project_id).first()
            
            # Convert to DependencyInfo objects
            from backend.analysis.dependency_parser import DependencyInfo
            dep_infos = []
            for dep in project.dependencies:
                dep_info = DependencyInfo(
                    name=dep.name,
                    version=dep.latest_version or "latest",
                    ecosystem=dep.ecosystem,
                    is_direct=True,  # Assume all are direct for now
                    repository_url=dep.repository_url
                )
                dep_infos.append(dep_info)
            
            # Re-run analysis to get detailed recommendations
            dependency_consolidator = get_dependency_consolidator(db)
            recommendations, metrics = await dependency_consolidator.analyze_dependencies(
                dep_infos, project_id
            )
            
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result,
                "recommendations": recommendations,
                "metrics": metrics
            }
            
        elif analysis.analysis_type == "health_monitoring":
            # Get all dependencies for the project
            project = db.query(Project).filter(Project.id == project_id).first()
            
            # Convert to DependencyInfo objects
            from backend.analysis.dependency_parser import DependencyInfo
            dep_infos = []
            for dep in project.dependencies:
                dep_info = DependencyInfo(
                    name=dep.name,
                    version=dep.latest_version or "latest",
                    ecosystem=dep.ecosystem,
                    is_direct=True,  # Assume all are direct for now
                    repository_url=dep.repository_url
                )
                dep_infos.append(dep_info)
            
            # Get health recommendations
            health_monitor = get_health_monitor(db)
            recommendations = await health_monitor.get_update_recommendations(
                dep_infos, project_id
            )
            
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result,
                "recommendations": recommendations
            }
            
        elif analysis.analysis_type == "license_compliance":
            # Get all dependencies for the project
            project = db.query(Project).filter(Project.id == project_id).first()
            
            # Convert to DependencyInfo objects
            from backend.analysis.dependency_parser import DependencyInfo
            dep_infos = []
            for dep in project.dependencies:
                dep_info = DependencyInfo(
                    name=dep.name,
                    version=dep.latest_version or "latest",
                    ecosystem=dep.ecosystem,
                    is_direct=True,  # Assume all are direct for now
                    repository_url=dep.repository_url
                )
                dep_infos.append(dep_info)
            
            # Re-run analysis to get detailed reports
            license_manager = get_license_manager(db)
            target_license = analysis.config.get("target_license", "mit") if analysis.config else "mit"
            summary, reports = await license_manager.analyze_licenses(
                dep_infos, project_id, target_license
            )
            
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result,
                "license_reports": reports
            }
            
        elif analysis.analysis_type == "performance_profiling":
            # Get all dependencies for the project
            project = db.query(Project).filter(Project.id == project_id).first()
            
            # Convert to DependencyInfo objects
            from backend.analysis.dependency_parser import DependencyInfo
            dep_infos = []
            for dep in project.dependencies:
                dep_info = DependencyInfo(
                    name=dep.name,
                    version=dep.latest_version or "latest",
                    ecosystem=dep.ecosystem,
                    is_direct=True,  # Assume all are direct for now
                    repository_url=dep.repository_url
                )
                dep_infos.append(dep_info)
            
            # Re-run analysis to get detailed reports
            performance_profiler = get_performance_profiler(db)
            profile_type = analysis.config.get("profile_type", "bundle_size") if analysis.config else "bundle_size"
            
            if profile_type == "bundle_size":
                result = await performance_profiler.analyze_bundle_size(
                    dep_infos, project_id
                )
            else:  # Runtime performance
                result = await performance_profiler.analyze_runtime_performance(
                    dep_infos, project_id
                )
            
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result,
                "detailed_results": result
            }
        
        else:
            return {
                "analysis_id": analysis_id,
                "analysis_type": analysis.analysis_type,
                "result_summary": analysis.result
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving detailed analysis results: {str(e)}"
        )