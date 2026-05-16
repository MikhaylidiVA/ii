"""
Модели базы данных
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, GEOMETRY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
import enum
import uuid


Base = declarative_base()


class IssuePriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    RECOMMENDATION = "RECOMMENDATION"


class IssueCategory(str, enum.Enum):
    ROAD_SAFETY = "ROAD_SAFETY"
    ACCESSIBILITY = "ACCESSIBILITY"
    LANDSCAPING = "LANDSCAPING"
    PARKING = "PARKING"
    DRAINAGE = "DRAINAGE"
    LIGHTING = "LIGHTING"
    SIGNAGE = "SIGNAGE"
    DIMENSIONS = "DIMENSIONS"
    CONFLICTS = "CONFLICTS"
    MISSING_ELEMENTS = "MISSING_ELEMENTS"


class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class Project(Base):
    """Проект с загруженными файлами"""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)  # User ID
    
    # Статус обработки
    status = Column(String(50), default="uploaded")  # uploaded, processing, completed, failed
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Связи
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    
    # Метаданные
    metadata_json = Column(JSON, nullable=True)


class ProjectFile(Base):
    """Загруженный файл проекта"""
    __tablename__ = "project_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, dwg, dxf
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA-256
    
    # S3 пути
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(512), nullable=False)
    
    # Статус обработки
    status = Column(String(50), default="uploaded")  # uploaded, parsing, parsed, failed
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    parsed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Извлеченные данные (кэширование)
    extracted_data = Column(JSON, nullable=True)  # Текст, геометрия, слои
    
    # Связи
    project = relationship("Project", back_populates="files")
    issues = relationship("Issue", back_populates="file", cascade="all, delete-orphan")


class Issue(Base):
    """Замечание к проекту"""
    __tablename__ = "issues"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("project_files.id"), nullable=True)
    
    # Основная информация
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=True)
    
    # Классификация
    priority = Column(SQLEnum(IssuePriority), nullable=False)
    category = Column(SQLEnum(IssueCategory), nullable=False)
    
    # Оценка уверенности ИИ
    confidence_score = Column(Float, nullable=False)
    
    # Нормативная ссылка
    regulation_reference = Column(JSON, nullable=False)
    # Структура: {document_id, document_name, document_type, section, full_text, url}
    
    # Геометрия (PostGIS)
    location_geometry = Column(GEOMETRY, nullable=True)  # Point, LineString, Polygon
    bounding_box = Column(JSON, nullable=True)  # [min_x, min_y, max_x, max_y]
    
    # Затронутые сущности из файла
    affected_entities = Column(JSON, nullable=True)  # IDs сущностей из DWG/PDF
    
    # Статус проверки
    review_status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING)
    reviewer_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)  # User ID
    
    # Аудит
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Трассировка принятия решений ИИ
    ai_trace = Column(JSON, nullable=True)
    # {retrieved_norms, llm_prompt_hash, geometric_checks, confidence_breakdown, model_versions}
    
    # Связи
    project = relationship("Project", back_populates="issues")
    file = relationship("ProjectFile", back_populates="issues")


class NormDocument(Base):
    """Нормативный документ (для RAG)"""
    __tablename__ = "norm_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(100), unique=True, nullable=False)  # gost_r_52289_2014
    document_name = Column(String(512), nullable=False)  # ГОСТ Р 52289-2014
    document_type = Column(String(50), nullable=False)  # ГОСТ, СП, СНиП, ПДД
    year = Column(Integer, nullable=True)
    status = Column(String(50), default="active")  # active, archived, superseded
    
    # Кэширование векторов (опционально)
    # Основные векторы хранятся в Qdrant
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    chunks = relationship("NormChunk", back_populates="document", cascade="all, delete-orphan")


class NormChunk(Base):
    """Чанк нормативного документа для RAG"""
    __tablename__ = "norm_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("norm_documents.id"), nullable=False)
    
    # Содержание
    section_number = Column(String(50), nullable=False)  # 5.2.3
    section_title = Column(String(512), nullable=True)
    content = Column(Text, nullable=False)
    
    # Метаданные для поиска
    keywords = Column(JSON, nullable=True)  # ["дорожные знаки", "видимость"]
    
    # Иерархия
    parent_section = Column(String(50), nullable=True)
    child_sections = Column(JSON, nullable=True)  # ["5.2.3.1", "5.2.3.2"]
    related_norms = Column(JSON, nullable=True)  # ["gost_33150_2019:4.1.2"]
    
    # Векторное представление (ID в Qdrant)
    qdrant_point_id = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    document = relationship("NormDocument", back_populates="chunks")


class User(Base):
    """Пользователь системы"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Роли
    role = Column(String(50), default="viewer")  # admin, expert, viewer
    
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    projects = relationship("Project", backref="owner")
    reviewed_issues = relationship("Issue", backref="reviewer")
