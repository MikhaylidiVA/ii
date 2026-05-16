"""
Norms API endpoints.
Search and manage regulatory documents (GOST, SP, SNiP).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import NormDocument, NormSection, User
from app.api.auth import get_current_user

router = APIRouter()


@router.get("/search")
async def search_norms(
    query_text: str = Query(..., min_length=2),
    doc_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search regulatory documents by text.
    
    - **query_text**: Search query (full-text search)
    - **doc_type**: Filter by document type (GOST, SP, SNiP, etc.)
    - **limit**: Maximum number of results
    """
    # Full-text search using PostgreSQL tsvector
    from sqlalchemy import text
    
    search_query = f"SELECT id, doc_name, doc_type, doc_number, 
                     ts_rank(to_tsvector('russian', doc_name || ' ' || COALESCE(doc_number, '')), plainto_tsquery('russian', :query)) as rank
                     FROM norm_documents
                     WHERE to_tsvector('russian', doc_name || ' ' || COALESCE(doc_number, '')) @@ plainto_tsquery('russian', :query)"
    
    if doc_type:
        search_query += " AND doc_type = :doc_type"
    
    search_query += " ORDER BY rank DESC LIMIT :limit"
    
    result = db.execute(
        text(search_query),
        {"query": query_text, "doc_type": doc_type, "limit": limit}
    )
    
    docs = []
    for row in result:
        docs.append({
            "id": str(row.id),
            "doc_name": row.doc_name,
            "doc_type": row.doc_type,
            "doc_number": row.doc_number,
            "rank": float(row.rank) if row.rank else 0.0
        })
    
    return {
        "query": query_text,
        "results": docs,
        "total": len(docs)
    }


@router.get("/{norm_id}")
async def get_norm(
    norm_id: str,
    include_sections: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a regulatory document."""
    try:
        norm_uuid = uuid.UUID(norm_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid norm ID format")
    
    norm = db.query(NormDocument).filter(NormDocument.id == norm_uuid).first()
    
    if not norm:
        raise HTTPException(status_code=404, detail="Document not found")
    
    response = {
        "id": str(norm.id),
        "doc_name": norm.doc_name,
        "doc_type": norm.doc_type,
        "doc_number": norm.doc_number,
        "approval_date": norm.approval_date.isoformat() if norm.approval_date else None,
        "effective_date": norm.effective_date.isoformat() if norm.effective_date else None,
        "status": norm.status,
        "metadata": norm.metadata,
        "created_at": norm.created_at.isoformat() if norm.created_at else None
    }
    
    if include_sections:
        sections = db.query(NormSection).filter(
            NormSection.document_id == norm_uuid
        ).order_by(NormSection.level, NormSection.section_number).all()
        
        response["sections"] = [
            {
                "id": str(s.id),
                "section_number": s.section_number,
                "section_title": s.section_title,
                "content": s.content,
                "level": s.level
            }
            for s in sections
        ]
    
    return response


@router.get("/section/{section_id}")
async def get_norm_section(
    section_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific section of a regulatory document."""
    try:
        section_uuid = uuid.UUID(section_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid section ID format")
    
    section = db.query(NormSection).filter(NormSection.id == section_uuid).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    return {
        "id": str(section.id),
        "document_id": str(section.document_id),
        "section_number": section.section_number,
        "section_title": section.section_title,
        "content": section.content,
        "level": section.level,
        "metadata": section.metadata
    }
