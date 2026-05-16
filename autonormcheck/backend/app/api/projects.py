"""
Projects API endpoints.
CRUD operations for projects.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Project, User
from app.api.auth import get_current_user

router = APIRouter()


# Pydantic models (simplified for brevity)
class ProjectCreate:
    def __init__(self, name: str, description: Optional[str] = None):
        self.name = name
        self.description = description


class ProjectResponse:
    def __init__(self, id: str, name: str, description: Optional[str], 
                 status: str, created_at, updated_at, files_count: int = 0):
        self.id = id
        self.name = name
        self.description = description
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.files_count = files_count


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str,
    description: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project."""
    project = Project(
        user_id=current_user.id,
        name=name,
        description=description
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }


@router.get("/", response_model=list)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all projects for the current user."""
    query = db.query(Project).filter(Project.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(Project.status == status_filter)
    
    total = query.count()
    projects = query.offset(skip).limit(limit).all()
    
    result = []
    for project in projects:
        result.append({
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "files_count": len(project.files),
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None
        })
    
    return {
        "items": result,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project details by ID."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    project = db.query(Project).filter(
        Project.id == project_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "files": [
            {
                "id": str(f.id),
                "original_name": f.original_name,
                "file_type": f.file_type,
                "processing_status": f.processing_status,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in project.files
        ],
        "issues_count": len(project.issues),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update project details."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    project = db.query(Project).filter(
        Project.id == project_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if status is not None:
        project.status = status
    
    db.commit()
    db.refresh(project)
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a project and all associated data."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    project = db.query(Project).filter(
        Project.id == project_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    
    return None
