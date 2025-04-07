import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import shutil
import os
import tempfile

from backend.core.db import get_db
from backend.core.models import User, Project, Analysis, Dependency
from backend.api.auth import get_current_active_user
from backend.analysis.dependency_parser import parse_project_dependencies, detect_project_ecosystems

router = APIRouter()


# Models
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    repository_url: Optional[str] = None
    ecosystem: str


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repository_url: Optional[str] = None
    ecosystem: Optional[str] = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    ecosystem: str
    description: Optional[str] = None
    dependency_count: int
    last_analysis: Optional[datetime] = None
    risk_level: Optional[str] = None
    
    class Config:
        orm_mode = True


# Endpoints
@router.get("/", response_model=List[ProjectSummary])
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all projects for the current user.
    """
    projects = db.query(Project).filter(Project.owner_id == current_user.id).offset(skip).limit(limit).all()
    
    # Enhance with summary data
    result = []
    for project in projects:
        # Get dependency count
        dependency_count = db.query(Dependency).join(
            "projects"
        ).filter(
            Project.id == project.id
        ).count()
        
        # Get last analysis
        last_analysis = db.query(Analysis).filter(
            Analysis.project_id == project.id
        ).order_by(
            Analysis.created_at.desc()
        ).first()
        
        # Determine risk level based on recent analyses
        risk_analyses = db.query(Analysis).filter(
            Analysis.project_id == project.id,
            Analysis.result.isnot(None)
        ).order_by(
            Analysis.created_at.desc()
        ).limit(5).all()
        
        risk_level = "unknown"
        for analysis in risk_analyses:
            result = analysis.result
            if isinstance(result, dict):
                if "risk_level" in result:
                    risk_level = result["risk_level"]
                    break
                elif "impact_level" in result:
                    risk_level = result["impact_level"]
                    break
                elif "overall_risk_level" in result:
                    risk_level = result["overall_risk_level"]
                    break
        
        # Create summary
        summary = ProjectSummary(
            id=str(project.id),
            name=project.name,
            ecosystem=project.ecosystem,
            description=project.description,
            dependency_count=dependency_count,
            last_analysis=last_analysis.created_at if last_analysis else None,
            risk_level=risk_level
        )
        
        result.append(summary)
    
    return result


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    """
    db_project = Project(
        id=uuid.uuid4(),
        name=project.name,
        description=project.description,
        repository_url=project.repository_url,
        ecosystem=project.ecosystem,
        owner_id=current_user.id
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return db_project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a project by ID.
    """
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return db_project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a project.
    """
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update fields
    update_data = project_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    db.commit()
    db.refresh(db_project)
    
    return db_project


@router.delete("/{project_id}", response_model=Dict[str, Any])
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a project.
    """
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Delete project
    db.delete(db_project)
    db.commit()
    
    return {"message": "Project deleted successfully"}


@router.post("/{project_id}/upload", response_model=Dict[str, Any])
async def upload_project_files(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload project files for dependency analysis.
    """
    # Check if project exists
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create a temporary directory to store uploaded files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save uploaded files
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        # Auto-detect ecosystems
        ecosystems = detect_project_ecosystems(temp_dir)
        
        # If no ecosystem detected from files, use the project's ecosystem
        if not ecosystems and db_project.ecosystem:
            ecosystems = [db_project.ecosystem]
        
        # If still no ecosystem, return error
        if not ecosystems:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not detect project ecosystem. Please specify manually."
            )
        
        # Parse dependencies
        dependencies_by_ecosystem = parse_project_dependencies(temp_dir)
        
        # Flatten the dependencies
        all_dependencies = []
        for eco, deps in dependencies_by_ecosystem.items():
            all_dependencies.extend(deps)
        
        # Store dependencies in database
        stored_deps = []
        for dep in all_dependencies:
            # Check if dependency already exists
            db_dep = db.query(Dependency).filter(
                Dependency.name == dep.name,
                Dependency.ecosystem == dep.ecosystem
            ).first()
            
            if not db_dep:
                # Create new dependency
                db_dep = Dependency(
                    id=uuid.uuid4(),
                    name=dep.name,
                    ecosystem=dep.ecosystem,
                    latest_version=dep.version,
                    description=getattr(dep, 'description', None),
                    repository_url=getattr(dep, 'repository_url', None),
                    homepage_url=None
                )
                db.add(db_dep)
            
            # Link to project if not already linked
            if db_dep not in db_project.dependencies:
                db_project.dependencies.append(db_dep)
            
            stored_deps.append(db_dep)
        
        # Update project ecosystem if not set
        if not db_project.ecosystem and ecosystems:
            db_project.ecosystem = ecosystems[0]
        
        db.commit()
    
    return {
        "message": f"Successfully processed {len(all_dependencies)} dependencies",
        "detected_ecosystems": ecosystems,
        "dependency_count": len(all_dependencies),
        "direct_dependencies": len([d for d in all_dependencies if d.is_direct])
    }


@router.get("/{project_id}/dependencies", response_model=List[Dict[str, Any]])
async def get_project_dependencies(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all dependencies for a project.
    """
    # Check if project exists
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get dependencies
    dependencies = db_project.dependencies
    
    # Format response
    result = []
    for dep in dependencies:
        dep_data = {
            "id": str(dep.id),
            "name": dep.name,
            "ecosystem": dep.ecosystem,
            "latest_version": dep.latest_version,
            "description": dep.description,
            "repository_url": dep.repository_url,
            "homepage_url": dep.homepage_url,
            "health_score": dep.health_score
        }
        
        # Add metadata if available
        if dep.metadata:
            dep_data["metadata"] = dep.metadata
        
        result.append(dep_data)
    
    return result


@router.get("/{project_id}/analyses", response_model=List[Dict[str, Any]])
async def get_project_analyses(
    project_id: str,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all analyses for a project.
    """
    # Check if project exists
    db_project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get analyses
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id
    ).order_by(
        Analysis.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # Format response
    result = []
    for analysis in analyses:
        analysis_data = {
            "id": str(analysis.id),
            "project_id": str(analysis.project_id),
            "analysis_type": analysis.analysis_type,
            "status": analysis.status,
            "created_at": analysis.created_at,
            "started_at": analysis.started_at,
            "completed_at": analysis.completed_at
        }
        
        # Add result summary if available
        if analysis.result:
            analysis_data["result_summary"] = analysis.result
        
        # Add error message if failed
        if analysis.error_message:
            analysis_data["error_message"] = analysis.error_message
        
        result.append(analysis_data)
    
    return result