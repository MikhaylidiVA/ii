"""
Celery задачи для обработки проектов
"""
import logging
from datetime import datetime
from typing import Optional
import hashlib
import json

from celery import Task
from app.core.celery_app import celery_app
from app.core.database import get_db_context
from app.core.minio_client import get_file_bytes, delete_files
from app.models.database import Project, ProjectFile, Issue, ReviewStatus
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Базовый класс для задач с доступом к БД"""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = next(get_db_context())
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=DatabaseTask, bind=True, queue='parsing')
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def parse_project_file(self, file_id: str) -> dict:
    """
    Парсинг загруженного файла (PDF или DWG)
    
    Args:
        file_id: UUID файла в базе данных
    
    Returns:
        Результат парсинга с извлеченными данными
    """
    from app.services.parsers.pdf_parser import PDFParser
    from app.services.parsers.dwg_parser import DWGParser
    
    db = self.db
    
    # Получение информации о файле
    project_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not project_file:
        raise ValueError(f"File {file_id} not found")
    
    # Обновление статуса
    project_file.status = "parsing"
    db.commit()
    
    logger.info(f"Starting parsing of file {project_file.filename}")
    
    try:
        # Получение файла из S3
        file_bytes = get_file_bytes(project_file.s3_key)
        if not file_bytes:
            raise ValueError("Failed to retrieve file from storage")
        
        # Выбор парсера в зависимости от типа файла
        if project_file.file_type.lower() in ['pdf']:
            parser = PDFParser()
            extracted_data = parser.parse(file_bytes)
        elif project_file.file_type.lower() in ['dwg', 'dxf']:
            parser = DWGParser()
            extracted_data = parser.parse(file_bytes)
        else:
            raise ValueError(f"Unsupported file type: {project_file.file_type}")
        
        # Сохранение извлеченных данных
        project_file.extracted_data = extracted_data
        project_file.status = "parsed"
        project_file.parsed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Successfully parsed file {file_id}")
        
        # Запуск следующей задачи - AI анализ
        analyze_project_issues.delay(str(project_file.project_id))
        
        return {
            "success": True,
            "file_id": file_id,
            "entities_count": len(extracted_data.get('entities', [])),
            "text_blocks_count": len(extracted_data.get('text_blocks', [])),
        }
        
    except Exception as e:
        logger.error(f"Error parsing file {file_id}: {e}", exc_info=True)
        project_file.status = "failed"
        project_file.extracted_data = {"error": str(e)}
        db.commit()
        raise


@celery_app.task(base=DatabaseTask, bind=True, queue='ai_analysis')
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30)
)
def analyze_project_issues(self, project_id: str) -> dict:
    """
    AI анализ проекта на соответствие нормам
    
    Args:
        project_id: UUID проекта
    
    Returns:
        Результаты анализа с количеством найденных замечаний
    """
    from app.services.analysis.norm_checker import NormChecker
    from app.services.analysis.geometry_validator import GeometryValidator
    
    db = self.db
    
    # Получение проекта
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project {project_id} not found")
    
    # Обновление статуса проекта
    project.status = "processing"
    project.processing_started_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Starting AI analysis for project {project_id}")
    
    try:
        # Получение всех файлов проекта
        files = db.query(ProjectFile).filter(
            ProjectFile.project_id == project_id,
            ProjectFile.status == "parsed"
        ).all()
        
        if not files:
            raise ValueError("No parsed files found for project")
        
        # Инициализация сервисов
        norm_checker = NormChecker(db)
        geometry_validator = GeometryValidator()
        
        all_issues = []
        
        # Анализ каждого файла
        for project_file in files:
            logger.info(f"Analyzing file {project_file.filename}")
            
            # Извлечение данных
            extracted_data = project_file.extracted_data
            if not extracted_data:
                continue
            
            # RAG поиск релевантных норм и генерация замечаний
            issues = norm_checker.check_compliance(
                entities=extracted_data.get('entities', []),
                text_blocks=extracted_data.get('text_blocks', []),
                layers=extracted_data.get('layers', []),
            )
            
            # Геометрическая валидация
            geo_issues = geometry_validator.validate(
                entities=extracted_data.get('entities', []),
                dimensions=extracted_data.get('dimensions', []),
            )
            
            # Объединение результатов
            file_issues = issues + geo_issues
            
            # Добавление информации о файле
            for issue in file_issues:
                issue['file_id'] = str(project_file.id)
            
            all_issues.extend(file_issues)
        
        # Сохранение замечаний в БД
        saved_count = 0
        for issue_data in all_issues:
            issue = Issue(
                project_id=project_id,
                file_id=issue_data.get('file_id'),
                title=issue_data['title'],
                description=issue_data['description'],
                suggestion=issue_data.get('suggestion'),
                priority=issue_data['priority'],
                category=issue_data['category'],
                confidence_score=issue_data['confidence_score'],
                regulation_reference=issue_data['regulation_reference'],
                location_geometry=issue_data.get('location_geometry'),
                bounding_box=issue_data.get('bounding_box'),
                affected_entities=issue_data.get('affected_entities'),
                ai_trace=issue_data.get('ai_trace'),
            )
            db.add(issue)
            saved_count += 1
        
        db.commit()
        
        # Обновление статуса проекта
        project.status = "completed"
        project.processing_completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Analysis completed for project {project_id}. Found {saved_count} issues.")
        
        return {
            "success": True,
            "project_id": project_id,
            "issues_found": saved_count,
            "files_analyzed": len(files),
        }
        
    except Exception as e:
        logger.error(f"Error analyzing project {project_id}: {e}", exc_info=True)
        project.status = "failed"
        project.error_message = str(e)
        db.commit()
        raise


@celery_app.task(base=DatabaseTask, bind=True, queue='default')
def process_project_upload(self, project_id: str, file_ids: list[str]) -> dict:
    """
    Основная задача обработки загруженного проекта
    Запускает цепочку задач: парсинг -> анализ
    
    Args:
        project_id: UUID проекта
        file_ids: Список UUID файлов
    
    Returns:
        Статус запуска обработки
    """
    db = self.db
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project {project_id} not found")
    
    logger.info(f"Starting processing pipeline for project {project_id}")
    
    # Запуск парсинга для каждого файла
    for file_id in file_ids:
        parse_project_file.delay(file_id)
    
    return {
        "success": True,
        "project_id": project_id,
        "message": f"Processing started for {len(file_ids)} files",
    }


@celery_app.task(base=DatabaseTask, bind=True, queue='cleanup')
def cleanup_old_projects(self, days_to_keep: int = 7) -> dict:
    """
    Очистка старых проектов по TTL
    
    Args:
        days_to_keep: Количество дней хранения
    
    Returns:
        Количество удаленных проектов
    """
    from sqlalchemy import text
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    # Подсчет проектов для удаления
    projects_to_delete = self.db.query(Project).filter(
        Project.created_at < cutoff_date
    ).all()
    
    deleted_count = len(projects_to_delete)
    deleted_s3_keys = []
    
    # Сбор ключей файлов для удаления из S3
    for project in projects_to_delete:
        for file in project.files:
            deleted_s3_keys.append(file.s3_key)
    
    # Удаление проектов (каскадно удалит файлы и замечания)
    for project in projects_to_delete:
        self.db.delete(project)
    
    self.db.commit()
    
    # Удаление файлов из S3
    if deleted_s3_keys:
        delete_files(deleted_s3_keys)
    
    logger.info(f"Cleaned up {deleted_count} projects older than {days_to_keep} days")
    
    return {
        "success": True,
        "deleted_projects": deleted_count,
        "deleted_files": len(deleted_s3_keys),
    }


@celery_app.task(base=DatabaseTask, bind=True, queue='ai_analysis')
def index_norm_document(self, document_id: str, content_chunks: list[dict]) -> dict:
    """
    Индексация нормативного документа в векторной БД
    
    Args:
        document_id: ID документа
        content_chunks: Список чанков с содержанием
    
    Returns:
        Количество проиндексированных чанков
    """
    from app.services.embeddings.embedding_service import EmbeddingService
    
    embedding_service = EmbeddingService()
    
    indexed_count = 0
    
    for chunk in content_chunks:
        try:
            # Генерация эмбеддинга
            vector = embedding_service.embed_text(chunk['content'])
            
            # Подготовка payload
            payload = {
                "document_id": chunk.get('document_id', document_id),
                "document_name": chunk.get('document_name'),
                "document_type": chunk.get('document_type'),
                "section_number": chunk['section_number'],
                "section_title": chunk.get('section_title'),
                "content": chunk['content'],
                "keywords": chunk.get('keywords', []),
                "status": chunk.get('status', 'active'),
            }
            
            # Загрузка в Qdrant
            from app.core.qdrant_client import norms_search
            import uuid
            
            chunk_uuid = str(uuid.uuid4())
            norms_search.upload_norm_chunk(chunk_uuid, vector, payload)
            
            indexed_count += 1
            
        except Exception as e:
            logger.error(f"Error indexing chunk: {e}")
            continue
    
    logger.info(f"Indexed {indexed_count} chunks for document {document_id}")
    
    return {
        "success": True,
        "document_id": document_id,
        "chunks_indexed": indexed_count,
    }
