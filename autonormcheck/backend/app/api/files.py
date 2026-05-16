"""
Files API endpoints.
Upload, download, and manage project files (PDF, DWG).
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.database import File, Project, FileType, ProcessingStatus
from app.api.auth import get_current_user
from app.api.projects import get_project

router = APIRouter()


def validate_file_extension(filename: str) -> str:
    """Validate file extension and return file type."""
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        return FileType.PDF
    elif ext in ("dwg", "dxf"):
        return FileType.DWG if ext == "dwg" else FileType.DXF
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: pdf, dwg, dxf"
        )


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    project_id: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Upload a new file to a project.
    
    - **file**: The file to upload (PDF, DWG, or DXF)
    - **project_id**: ID of the project to associate with
    """
    # Validate file size
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.FILE_UPLOAD_MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.FILE_UPLOAD_MAX_SIZE} bytes"
        )
    
    # Validate file type
    try:
        file_type = validate_file_extension(file.filename)
    except HTTPException as e:
        raise e
    
    # Verify project exists and belongs to user
    try:
        project_uuid = uuid.UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    project = db.query(Project).filter(
        Project.id == project_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create file record
    stored_name = f"{uuid.uuid4()}_{file.filename}"
    expires_at = datetime.utcnow() + timedelta(days=settings.DATA_RETENTION_DAYS)
    
    db_file = File(
        project_id=project_uuid,
        original_name=file.filename,
        stored_name=stored_name,
        file_type=file_type,
        file_size=file_size,
        mime_type=file.content_type,
        s3_bucket=settings.MINIO_BUCKET,
        s3_key=f"{project_id}/{stored_name}",
        processing_status=ProcessingStatus.PENDING,
        expires_at=expires_at
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    # TODO: Upload file to MinIO here
    # minio_client.put_object(...)
    
    # Trigger async processing
    # from app.workers.tasks import parse_file
    # parse_file.delay(str(db_file.id))
    
    return {
        "id": str(db_file.id),
        "project_id": str(db_file.project_id),
        "original_name": db_file.original_name,
        "file_type": db_file.file_type,
        "file_size": db_file.file_size,
        "processing_status": db_file.processing_status,
        "created_at": db_file.created_at.isoformat() if db_file.created_at else None
    }


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get file details by ID."""
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    db_file = db.query(File).join(Project).filter(
        File.id == file_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "id": str(db_file.id),
        "project_id": str(db_file.project_id),
        "original_name": db_file.original_name,
        "stored_name": db_file.stored_name,
        "file_type": db_file.file_type,
        "file_size": db_file.file_size,
        "mime_type": db_file.mime_type,
        "processing_status": db_file.processing_status,
        "error_message": db_file.error_message,
        "metadata": db_file.metadata,
        "created_at": db_file.created_at.isoformat() if db_file.created_at else None,
        "processed_at": db_file.processed_at.isoformat() if db_file.processed_at else None
    }


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a file and its associated data."""
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    db_file = db.query(File).join(Project).filter(
        File.id == file_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # TODO: Delete from MinIO
    # minio_client.remove_object(db_file.s3_bucket, db_file.s3_key)
    
    db.delete(db_file)
    db.commit()
    
    return None


@router.post("/{file_id}/analyze")
async def analyze_file(
    file_id: str,
    check_categories: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Trigger analysis for a specific file.
    
    - **check_categories**: Comma-separated list of categories to check
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    
    db_file = db.query(File).join(Project).filter(
        File.id == file_uuid,
        Project.user_id == current_user.id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if db_file.processing_status == ProcessingStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="File is already being processed")
    
    # Update status
    db_file.processing_status = ProcessingStatus.PROCESSING
    db.commit()
    
    # Parse categories
    categories = None
    if check_categories:
        categories = [c.strip() for c in check_categories.split(",")]
    
    # Trigger async analysis task
    # from app.workers.tasks import analyze_file
    # task = analyze_file.delay(str(db_file.id), categories)
    
    return {
        "message": "Analysis started",
        "file_id": str(db_file.id),
        "categories": categories
    }
