"""
API роутеры для проектов
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db_session
from app.models.database import Project, ProjectFile, Issue, ReviewStatus, IssuePriority, IssueCategory
from pydantic import BaseModel, Field


router = APIRouter()


# Pydantic схемы
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    status: str
    created_at: str
    processing_completed_at: Optional[str]
    files_count: int = 0
    issues_count: int = 0
    
    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """Список всех проектов с фильтрацией"""
    query = db.query(Project)
    
    if status_filter:
        query = query.filter(Project.status == status_filter)
    
    projects = query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    
    # Добавляем счетчики
    result = []
    for project in projects:
        project_dict = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "created_at": project.created_at.isoformat(),
            "processing_completed_at": project.processing_completed_at.isoformat() if project.processing_completed_at else None,
            "files_count": len(project.files),
            "issues_count": len(project.issues),
        }
        result.append(project_dict)
    
    return result


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db_session),
):
    """Создание нового проекта"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        status="uploaded",
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "processing_completed_at": None,
        "files_count": 0,
        "issues_count": 0,
    }


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Получение информации о проекте"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "processing_completed_at": project.processing_completed_at.isoformat() if project.processing_completed_at else None,
        "files_count": len(project.files),
        "issues_count": len(project.issues),
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Удаление проекта"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    
    return None


@router.get("/{project_id}/issues")
def get_project_issues(
    project_id: UUID,
    priority: Optional[IssuePriority] = None,
    category: Optional[IssueCategory] = None,
    review_status: Optional[ReviewStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """Список замечаний проекта с фильтрацией"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = db.query(Issue).filter(Issue.project_id == project_id)
    
    if priority:
        query = query.filter(Issue.priority == priority)
    
    if category:
        query = query.filter(Issue.category == category)
    
    if review_status:
        query = query.filter(Issue.review_status == review_status)
    
    issues = query.order_by(Issue.priority.desc(), Issue.confidence_score.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "priority": issue.priority.value,
            "category": issue.category.value,
            "confidence_score": issue.confidence_score,
            "review_status": issue.review_status.value,
            "location_geometry": issue.location_geometry,
            "bounding_box": issue.bounding_box,
            "regulation_reference": issue.regulation_reference,
            "created_at": issue.created_at.isoformat(),
        }
        for issue in issues
    ]


@router.get("/{project_id}/statistics")
def get_project_statistics(
    project_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Статистика по проекту"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Подсчет по приоритетам
    priority_counts = db.query(
        Issue.priority,
        func.count(Issue.id).label('count')
    ).filter(
        Issue.project_id == project_id
    ).group_by(Issue.priority).all()
    
    # Подсчет по категориям
    category_counts = db.query(
        Issue.category,
        func.count(Issue.id).label('count')
    ).filter(
        Issue.project_id == project_id
    ).group_by(Issue.category).all()
    
    # Статусы проверки
    review_counts = db.query(
        Issue.review_status,
        func.count(Issue.id).label('count')
    ).filter(
        Issue.project_id == project_id
    ).group_by(Issue.review_status).all()
    
    from sqlalchemy import func
    
    return {
        "project_id": str(project_id),
        "total_issues": len(project.issues),
        "by_priority": {p.value: c for p, c in priority_counts},
        "by_category": {c.value: cnt for c, cnt in category_counts},
        "by_review_status": {s.value: cnt for s, cnt in review_counts},
        "avg_confidence": sum(i.confidence_score for i in project.issues) / len(project.issues) if project.issues else 0,
        "files_count": len(project.files),
    }
