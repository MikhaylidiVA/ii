"""
Issues API endpoints.
Manage and review analysis findings.
"""
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Issue, Project, User, IssuePriority, IssueStatus
from app.api.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_issues(
    project_id: Optional[str] = None,
    priority: Optional[str] = None,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List issues with optional filters."""
    query = db.query(Issue).join(Project).filter(
        Project.user_id == current_user.id
    )
    
    if project_id:
        try:
            project_uuid = uuid.UUID(project_id)
            query = query.filter(Issue.project_id == project_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if priority:
        query = query.filter(Issue.priority == priority)
    
    if status_filter:
        query = query.filter(Issue.status == status_filter)
    
    if category:
        query = query.filter(Issue.category == category)
    
    total = query.count()
    issues = query.offset(skip).limit(limit).all()
    
    result = []
    for issue in issues:
        result.append({
            "id": str(issue.id),
            "project_id": str(issue.project_id),
            "file_id": str(issue.file_id) if issue.file_id else None,
            "priority": issue.priority,
            "status": issue.status,
            "category": issue.category,
            "title": issue.title,
            "description": issue.description,
            "suggestion": issue.suggestion,
            "confidence_score": issue.confidence_score,
            "regulation_reference": {
                "doc_name": issue.regulation_doc_id,
                "section": issue.regulation_section,
                "text": issue.regulation_text
            } if issue.regulation_doc_id else None,
            "location": issue.location_geojson,
            "bbox": issue.bbox,
            "review_comment": issue.review_comment,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "reviewed_at": issue.reviewed_at.isoformat() if issue.reviewed_at else None
        })
    
    return {
        "items": result,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{issue_id}")
async def get_issue(
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific issue."""
    try:
        issue_uuid = uuid.UUID(issue_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue ID format")
    
    issue = db.query(Issue).join(Project).filter(
        Issue.id == issue_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    return {
        "id": str(issue.id),
        "project_id": str(issue.project_id),
        "file_id": str(issue.file_id) if issue.file_id else None,
        "priority": issue.priority,
        "status": issue.status,
        "category": issue.category,
        "title": issue.title,
        "description": issue.description,
        "suggestion": issue.suggestion,
        "confidence_score": issue.confidence_score,
        "regulation_reference": {
            "doc_id": str(issue.regulation_doc_id) if issue.regulation_doc_id else None,
            "section": issue.regulation_section,
            "text": issue.regulation_text
        },
        "location": issue.location_geojson,
        "bbox": issue.bbox,
        "coordinate_system": issue.coordinate_system,
        "review_comment": issue.review_comment,
        "reviewed_by": str(issue.reviewed_by) if issue.reviewed_by else None,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        "reviewed_at": issue.reviewed_at.isoformat() if issue.reviewed_at else None
    }


@router.patch("/{issue_id}/review")
async def review_issue(
    issue_id: str,
    status_update: str,
    comment: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Review an issue (confirm or reject).
    
    - **status_update**: New status (CONFIRMED, REJECTED, RESOLVED)
    - **comment**: Optional review comment
    """
    try:
        issue_uuid = uuid.UUID(issue_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid issue ID format")
    
    if status_update not in ["CONFIRMED", "REJECTED", "RESOLVED"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid status. Must be CONFIRMED, REJECTED, or RESOLVED"
        )
    
    issue = db.query(Issue).join(Project).filter(
        Issue.id == issue_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    from datetime import datetime
    issue.status = status_update
    issue.reviewed_by = current_user.id
    issue.review_comment = comment
    issue.reviewed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(issue)
    
    return {
        "id": str(issue.id),
        "status": issue.status,
        "review_comment": issue.review_comment,
        "reviewed_by": str(issue.reviewed_by),
        "reviewed_at": issue.reviewed_at.isoformat() if issue.reviewed_at else None
    }


@router.get("/export")
async def export_issues(
    project_id: str,
    format: str = Query("json", regex="^(json|csv|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export issues to JSON, CSV, or PDF format."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    
    issues = db.query(Issue).join(Project).filter(
        Issue.project_id == project_uuid,
        Project.user_id == current_user.id
    ).all()
    
    if format == "json":
        return {
            "project_id": project_id,
            "total_issues": len(issues),
            "summary": {
                "critical": sum(1 for i in issues if i.priority == "CRITICAL"),
                "important": sum(1 for i in issues if i.priority == "IMPORTANT"),
                "recommendations": sum(1 for i in issues if i.priority == "RECOMMENDATION")
            },
            "issues": [
                {
                    "id": str(i.id),
                    "priority": i.priority,
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "suggestion": i.suggestion,
                    "regulation": i.regulation_text
                }
                for i in issues
            ]
        }
    
    # TODO: Implement CSV and PDF export
    raise HTTPException(status_code=501, detail=f"{format.upper()} export not yet implemented")
