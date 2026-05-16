"""
API роутеры для нормативных документов
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db_session
from app.models.database import NormDocument, NormChunk


router = APIRouter()


@router.get("", response_model=List[dict])
def list_norm_documents(
    document_type: Optional[str] = None,
    status: str = "active",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_session),
):
    """Список нормативных документов"""
    query = db.query(NormDocument).filter(NormDocument.status == status)
    
    if document_type:
        query = query.filter(NormDocument.document_type == document_type)
    
    documents = query.order_by(NormDocument.document_name).offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(doc.id),
            "document_id": doc.document_id,
            "document_name": doc.document_name,
            "document_type": doc.document_type,
            "year": doc.year,
            "status": doc.status,
            "chunks_count": len(doc.chunks),
        }
        for doc in documents
    ]


@router.get("/{document_id}")
def get_norm_document(
    document_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Информация о нормативном документе"""
    doc = db.query(NormDocument).filter(NormDocument.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": str(doc.id),
        "document_id": doc.document_id,
        "document_name": doc.document_name,
        "document_type": doc.document_type,
        "year": doc.year,
        "status": doc.status,
        "chunks": [
            {
                "id": str(chunk.id),
                "section_number": chunk.section_number,
                "section_title": chunk.section_title,
                "content": chunk.content,
            }
            for chunk in doc.chunks
        ],
    }


@router.post("/search")
def search_norms(
    query_text: str,
    document_type: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db_session),
):
    """Полнотекстовый поиск по нормативным документам"""
    from sqlalchemy import func
    
    # Полнотекстовый поиск через tsvector
    results = db.query(
        NormChunk,
        func.ts_rank_cd(NormChunk.content_tsv, func.plainto_tsquery('russian', query_text)).label('rank')
    ).filter(
        NormChunk.content_tsv.op('@@')(func.plainto_tsquery('russian', query_text))
    )
    
    if document_type:
        results = results.join(NormDocument).filter(NormDocument.document_type == document_type)
    
    results = results.order_by(func.ts_rank_cd(NormChunk.content_tsv, func.plainto_tsquery('russian', query_text)).desc())
    results = results.limit(limit).all()
    
    return [
        {
            "id": str(chunk.id),
            "document_id": chunk.document.document_id,
            "document_name": chunk.document.document_name,
            "section_number": chunk.section_number,
            "section_title": chunk.section_title,
            "content": chunk.content,
            "rank": rank,
        }
        for chunk, rank in results
    ]
