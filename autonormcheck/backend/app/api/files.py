"""
API роутеры для файлов
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import hashlib
from datetime import datetime

from app.core.database import get_db_session
from app.models.database import Project, ProjectFile
from app.core.minio_client import upload_file_bytes
from app.workers.tasks import process_project_upload


router = APIRouter()


@router.post("/{project_id}/upload", response_model=List[dict])
async def upload_files(
    project_id: UUID,
    files: List[UploadFile],
    db: Session = Depends(get_db_session),
):
    """Загрузка файлов в проект"""
    # Проверка существования проекта
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status != "uploaded":
        raise HTTPException(status_code=400, detail="Project is already being processed")
    
    uploaded_files = []
    file_ids = []
    
    for file in files:
        # Валидация расширения
        filename = file.filename.lower()
        if not (filename.endswith('.pdf') or filename.endswith('.dwg') or filename.endswith('.dxf')):
            continue
        
        # Определение типа файла
        if filename.endswith('.pdf'):
            file_type = 'pdf'
        elif filename.endswith('.dwg'):
            file_type = 'dwg'
        else:
            file_type = 'dxf'
        
        # Чтение содержимого
        content = await file.read()
        file_size = len(content)
        
        # Вычисление хэша
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Генерация S3 ключа
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"projects/{project_id}/{timestamp}_{file.filename}"
        
        # Загрузка в S3
        success = upload_file_bytes(
            file_bytes=content,
            object_name=s3_key,
            content_type=file.content_type or "application/octet-stream",
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}")
        
        # Создание записи в БД
        project_file = ProjectFile(
            project_id=project_id,
            filename=s3_key.split('/')[-1],
            original_filename=file.filename,
            file_type=file_type,
            file_size_bytes=file_size,
            file_hash=file_hash,
            s3_bucket="projects",
            s3_key=s3_key,
            status="uploaded",
        )
        
        db.add(project_file)
        uploaded_files.append(project_file)
        file_ids.append(str(project_file.id))
    
    db.commit()
    
    # Запуск обработки в фоне
    if file_ids:
        process_project_upload.delay(str(project_id), file_ids)
    
    return [
        {
            "id": str(f.id),
            "filename": f.original_filename,
            "file_type": f.file_type,
            "file_size_bytes": f.file_size_bytes,
            "status": f.status,
        }
        for f in uploaded_files
    ]


@router.get("/{file_id}")
def get_file_info(
    file_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Информация о файле"""
    file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "id": str(file.id),
        "project_id": str(file.project_id),
        "filename": file.original_filename,
        "file_type": file.file_type,
        "file_size_bytes": file.file_size_bytes,
        "status": file.status,
        "uploaded_at": file.uploaded_at.isoformat(),
        "parsed_at": file.parsed_at.isoformat() if file.parsed_at else None,
        "extracted_data_available": file.extracted_data is not None,
    }


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: UUID,
    db: Session = Depends(get_db_session),
):
    """Удаление файла"""
    file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Удаление из S3
    from app.core.minio_client import delete_file as s3_delete
    s3_delete(file.s3_key)
    
    # Удаление из БД
    db.delete(file)
    db.commit()
    
    return None
