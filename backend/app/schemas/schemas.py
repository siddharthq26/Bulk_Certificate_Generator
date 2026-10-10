from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ─── Recipient ────────────────────────────────────────────────────────────────

class RecipientIn(BaseModel):
    """A single recipient for certificate generation."""
    name: str = Field(..., min_length=1, max_length=255, description="Recipient's full name")
    email: EmailStr = Field(..., description="Recipient's email address")
    course_name: Optional[str] = Field(None, max_length=255, description="Name of the course/event")
    completion_date: Optional[str] = Field(None, max_length=50, description="Date of completion (YYYY-MM-DD)")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Recipient name cannot be blank or whitespace only")
        return v.strip()

    @field_validator("completion_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from datetime import date
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("completion_date must be in YYYY-MM-DD format")
        return v


# ─── Job Request ──────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    """Request body for creating a bulk certificate generation job."""
    event_name: str = Field(..., min_length=1, max_length=255, description="Event or course name")
    issued_by: str = Field(..., min_length=1, max_length=255, description="Issuing organization")
    recipients: List[RecipientIn] = Field(..., min_length=1, description="List of recipients")

    @field_validator("recipients")
    @classmethod
    def no_duplicate_emails(cls, v: List[RecipientIn]) -> List[RecipientIn]:
        emails = [r.email.lower() for r in v]
        duplicates = {e for e in emails if emails.count(e) > 1}
        if duplicates:
            raise ValueError(f"Duplicate email addresses found: {', '.join(sorted(duplicates))}")
        return v


# ─── Certificate Responses ────────────────────────────────────────────────────

class CertificateResponse(BaseModel):
    id: UUID
    job_id: UUID
    recipient_name: str
    recipient_email: str
    course_name: Optional[str]
    completion_date: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Job Responses ────────────────────────────────────────────────────────────

class JobCreateResponse(BaseModel):
    id: UUID
    event_name: str
    issued_by: str
    status: str
    total_count: int
    message: str

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: UUID
    event_name: str
    issued_by: str
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    progress_percentage: float
    celery_task_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(JobStatusResponse):
    certificates: List[CertificateResponse] = []

    model_config = {"from_attributes": True}


# ─── Generic ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    detail: str
    errors: Optional[List[ErrorDetail]] = None
