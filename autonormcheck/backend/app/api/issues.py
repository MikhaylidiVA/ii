"""
API роутеры для замечаний
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db_session
from app.models.database import Issue, ReviewStatus


router = APIRouter()


@router.get("/{issue_id}")
def get_issue(
    issue_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Получение информации о замечании"""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    return {
        "id": str(issue.id),
        "project_id": str(issue.project_id),
        "title": issue.title,
        "description": issue.description,
        "suggestion": issue.suggestion,
        "priority": issue.priority.value,
        "category": issue.category.value,
        "confidence_score": issue.confidence_score,
        "regulation_reference": issue.regulation_reference,
        "location_geometry": issue.location_geometry,
        "bounding_box": issue.bounding_box,
        "affected_entities": issue.affected_entities,
        "review_status": issue.review_status.value,
        "reviewer_comment": issue.reviewer_comment,
        "reviewed_at": issue.reviewed_at.isoformat() if issue.reviewed_at else None,
        "created_at": issue.created_at.isoformat(),
    }


@router.patch("/{issue_id}/review")
def review_issue(
    issue_id: UUID,
    review_status: ReviewStatus,
    comment: Optional[str] = None,
    db: Session = Depends(get_db_session),
    user_id: Optional[UUID] = None,  # В production из токена
):
    """Проверка замечания экспертом (подтверждение/отклонение)"""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Обновление статуса проверки
    issue.review_status = review_status
    issue.reviewer_comment = comment
    issue.reviewed_at = datetime.utcnow()
    issue.reviewed_by = user_id
    
    db.commit()
    db.refresh(issue)
    
    return {
        "id": str(issue.id),
        "review_status": issue.review_status.value,
        "reviewer_comment": issue.reviewer_comment,
        "reviewed_at": issue.reviewed_at.isoformat(),
    }


@router.get("/statistics/summary")
def get_issues_summary(
    project_id: Optional[UUID] = None,
    db: Session = Depends(get_db_session),
):
    """Сводная статистика по замечаниям"""
    from sqlalchemy import func
    
    query = db.query(
        Issue.priority,
        Issue.review_status,
        func.count(Issue.id).label('count'),
        func.avg(Issue.confidence_score).label('avg_confidence'),
    )
    
    if project_id:
        query = query.filter(Issue.project_id == project_id)
    
    results = query.group_by(Issue.priority, Issue.review_status).all()
    
    summary = {
        "total": sum(r.count for r in results),
        "by_priority": {},
        "by_review_status": {},
    }
    
    for result in results:
        priority = result.priority.value
        status = result.review_status.value
        
        if priority not in summary["by_priority"]:
            summary["by_priority"][priority] = {"count": 0, "confirmed": 0}
        
        summary["by_priority"][priority]["count"] += result.count
        summary["by_priority"][priority]["avg_confidence"] = float(result.avg_confidence) if result.avg_confidence else 0
        
        if status == "CONFIRMED":
            summary["by_priority"][priority]["confirmed"] += result.count
        
        if status not in summary["by_review_status"]:
            summary["by_review_status"][status] = 0
        summary["by_review_status"][status] += result.count
    
    return summary
