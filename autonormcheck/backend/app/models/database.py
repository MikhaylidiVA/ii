"""
SQLAlchemy models for AutoNormCheck database.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, BigInteger, 
    DateTime, ForeignKey, Enum as SQLEnum, Real, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


# Enum types
class IssuePriority(str):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    RECOMMENDATION = "RECOMMENDATION"


class IssueStatus(str):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class FileType(str):
    PDF = "PDF"
    DWG = "DWG"
    DXF = "DXF"


class ProcessingStatus(str):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Models
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    reviewed_issues = relationship("Issue", back_populates="reviewer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="projects")
    files = relationship("File", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(SQLEnum(FileType), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="files")
    issues = relationship("Issue", back_populates="file")
    tasks = relationship("ProcessingTask", back_populates="file", cascade="all, delete-orphan")


class NormDocument(Base):
    __tablename__ = "norm_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approval_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    sections = relationship("NormSection", back_populates="document", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="regulation_document")


class NormSection(Base):
    __tablename__ = "norm_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("norm_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("norm_sections.id"), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    document = relationship("NormDocument", back_populates="sections")
    embeddings = relationship("NormEmbedding", back_populates="section", cascade="all, delete-orphan")


class NormEmbedding(Base):
    __tablename__ = "norm_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("norm_sections.id", ondelete="CASCADE"), nullable=False
    )
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    section = relationship("NormSection", back_populates="embeddings")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True
    )
    priority: Mapped[str] = mapped_column(SQLEnum(IssuePriority), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        SQLEnum(IssueStatus), default=IssueStatus.PENDING, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Real, default=0.0)
    
    # Regulation reference
    regulation_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("norm_documents.id"), nullable=True, index=True
    )
    regulation_section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    regulation_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Location data (GeoJSON)
    location_geojson: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(50), default="WCS")
    
    # Review data
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project", back_populates="issues")
    file = relationship("File", back_populates="issues")
    regulation_document = relationship("NormDocument", back_populates="issues")
    reviewer = relationship("User", back_populates="reviewed_issues")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    file = relationship("File", back_populates="tasks")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
