"""
API routes for certificate generation jobs.
"""
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.models import (
    GenerationJob, Certificate, JobStatus, CertificateStatus
)
from app.schemas.schemas import (
    JobCreateRequest, JobCreateResponse, JobStatusResponse,
    JobDetailResponse, CertificateResponse, MessageResponse
)
from app.tasks.generation_tasks import generate_certificates_for_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Certificate Generation Jobs"])


# ─── POST /jobs — Create a new bulk generation job ────────────────────────────

@router.post(
    "/",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation request",
    description=(
        "Accepts a list of recipients and kicks off background generation. "
        "Returns a job ID that can be used to track progress."
    ),
)
async def create_job(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    # ── Create the job record ─────────────────────────────────────────────────
    job = GenerationJob(
        event_name=payload.event_name,
        issued_by=payload.issued_by,
        status=JobStatus.PENDING,
        total_count=len(payload.recipients),
    )
    db.add(job)
    await db.flush()  # get job.id without committing

    # ── Create individual certificate records ─────────────────────────────────
    certificates = []
    for recipient in payload.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=str(recipient.email),
            course_name=recipient.course_name,
            completion_date=recipient.completion_date,
            status=CertificateStatus.PENDING,
        )
        certificates.append(cert)

    db.add_all(certificates)
    await db.commit()
    await db.refresh(job)

    # ── Dispatch the Celery task ──────────────────────────────────────────────
    task = generate_certificates_for_job.delay(str(job.id))
    job.celery_task_id = task.id
    await db.commit()

    logger.info(f"Created job {job.id} with {job.total_count} recipients, task {task.id}")

    return JobCreateResponse(
        id=job.id,
        event_name=job.event_name,
        issued_by=job.issued_by,
        status=job.status.value,
        total_count=job.total_count,
        message=(
            f"Job created successfully. {job.total_count} certificates will be "
            f"generated in the background. Use GET /jobs/{job.id} to track progress."
        ),
    )


# ─── GET /jobs/{job_id} — Get job status ──────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job progress and status",
    description="Returns the current status, progress counts, and completion percentage for a job.",
)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobStatusResponse(
        id=job.id,
        event_name=job.event_name,
        issued_by=job.issued_by,
        status=job.status.value,
        total_count=job.total_count,
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        progress_percentage=job.progress_percentage,
        celery_task_id=job.celery_task_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ─── GET /jobs/{job_id}/detail — Full job detail with certificates ─────────────

@router.get(
    "/{job_id}/detail",
    response_model=JobDetailResponse,
    summary="Get full job detail including individual certificate statuses",
)
async def get_job_detail(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GenerationJob)
        .where(GenerationJob.id == job_id)
        .options(selectinload(GenerationJob.certificates))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    certs = [
        CertificateResponse(
            id=c.id,
            job_id=c.job_id,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            course_name=c.course_name,
            completion_date=c.completion_date,
            status=c.status.value,
            error_message=c.error_message,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in job.certificates
    ]

    return JobDetailResponse(
        id=job.id,
        event_name=job.event_name,
        issued_by=job.issued_by,
        status=job.status.value,
        total_count=job.total_count,
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        progress_percentage=job.progress_percentage,
        celery_task_id=job.celery_task_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        certificates=certs,
    )


# ─── GET /jobs/{job_id}/certificates — List certificates ──────────────────────

@router.get(
    "/{job_id}/certificates",
    response_model=list[CertificateResponse],
    summary="List all certificates for a job",
)
async def list_certificates(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    cert_result = await db.execute(
        select(Certificate).where(Certificate.job_id == job_id)
    )
    certs = cert_result.scalars().all()

    return [
        CertificateResponse(
            id=c.id,
            job_id=c.job_id,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            course_name=c.course_name,
            completion_date=c.completion_date,
            status=c.status.value,
            error_message=c.error_message,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in certs
    ]


# ─── GET /jobs/{job_id}/certificates/{cert_id}/download — Download PDF ────────

@router.get(
    "/{job_id}/certificates/{cert_id}/download",
    summary="Download a generated certificate PDF",
    description="Streams the PDF file for a completed certificate.",
    response_class=FileResponse,
)
async def download_certificate(
    job_id: UUID,
    cert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Certificate).where(
            Certificate.id == cert_id,
            Certificate.job_id == job_id,
        )
    )
    cert = result.scalar_one_or_none()

    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate {cert_id} not found in job {job_id}",
        )

    if cert.status != CertificateStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Certificate is not ready yet (status: {cert.status.value}). "
                   f"Error: {cert.error_message or 'N/A'}",
        )

    if not cert.file_path or not Path(cert.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file not found on disk. It may have been deleted.",
        )

    safe_name = "".join(
        c if c.isalnum() or c in " -_." else "_"
        for c in cert.recipient_name
    )
    filename = f"certificate_{safe_name}.pdf"

    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=filename,
    )
