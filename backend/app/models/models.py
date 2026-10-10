import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey,
    Text, Enum as SAEnum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class CertificateStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationJob(Base):
    """Represents a bulk certificate generation request."""
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_name = Column(String(255), nullable=False)
    issued_by = Column(String(255), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)

    total_count = Column(Integer, default=0, nullable=False)
    completed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    # Celery task ID for tracking
    celery_task_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    certificates = relationship("Certificate", back_populates="job", cascade="all, delete-orphan")

    @property
    def progress_percentage(self) -> float:
        if self.total_count == 0:
            return 0.0
        return round(((self.completed_count + self.failed_count) / self.total_count) * 100, 2)

    def __repr__(self):
        return f"<GenerationJob id={self.id} status={self.status}>"


class Certificate(Base):
    """Represents an individual certificate within a generation job."""
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    course_name = Column(String(255), nullable=True)
    completion_date = Column(String(50), nullable=True)

    status = Column(SAEnum(CertificateStatus), default=CertificateStatus.PENDING, nullable=False, index=True)
    file_path = Column(String(500), nullable=True)  # Path to the generated PDF
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    job = relationship("GenerationJob", back_populates="certificates")

    def __repr__(self):
        return f"<Certificate id={self.id} recipient={self.recipient_name} status={self.status}>"
