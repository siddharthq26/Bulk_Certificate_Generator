"""
Celery tasks for background certificate generation.

Design Decision — Background Processing:
  We use Celery with Redis as the broker for background processing because:
  1. Bulk jobs can contain thousands of recipients; processing them synchronously
     in the HTTP request would block the connection for too long (timeouts).
  2. Celery allows us to track progress, retry failed tasks, and scale workers
     independently of the API.
  3. Each individual certificate is processed inside the same task so that a
     failure in one certificate does NOT prevent others from being generated.
  4. The Flower dashboard provides real-time visibility into task progress.
"""
import logging
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.database import SyncSessionLocal
from app.models.models import GenerationJob, Certificate, JobStatus, CertificateStatus
from app.services.certificate_generator import generate_certificate
from app.services.email_service import send_certificate_email

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task class that provides a managed database session."""

    _session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None or not self._session.is_active:
            self._session = SyncSessionLocal()
        return self._session

    def after_return(self, *args, **kwargs):
        if self._session is not None:
            self._session.close()
            self._session = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="generate_certificates_for_job",
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=3600,   # 1 hour soft limit
    time_limit=3660,         # Hard kill after 1 hour + 60s
)
def generate_certificates_for_job(self, job_id: str) -> dict:
    """
    Generate all certificates for a given job.

    Processes each recipient independently so a failure in one certificate
    does not block the others. Updates the job and certificate statuses
    in the database as it progresses.

    Args:
        job_id: UUID string of the GenerationJob to process.

    Returns:
        A summary dict with counts of completed and failed certificates.
    """
    logger.info(f"Starting certificate generation for job {job_id}")
    db: Session = self.session

    try:
        # ── 1. Fetch the job ───────────────────────────────────────────────
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"error": "Job not found"}

        # ── 2. Mark job as processing ──────────────────────────────────────
        job.status = JobStatus.PROCESSING
        db.commit()

        # ── 3. Fetch all pending certificates ─────────────────────────────
        certificates = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .all()
        )

        completed = 0
        failed = 0

        # ── 4. Generate each certificate independently ─────────────────────
        for cert in certificates:
            try:
                cert.status = CertificateStatus.GENERATING
                db.commit()

                file_path = generate_certificate(
                    recipient_name=cert.recipient_name,
                    recipient_email=cert.recipient_email,
                    event_name=job.event_name,
                    issued_by=job.issued_by,
                    course_name=cert.course_name,
                    completion_date=cert.completion_date,
                    certificate_id=str(cert.id),
                )

                cert.status = CertificateStatus.COMPLETED
                cert.file_path = file_path
                job.completed_count += 1
                completed += 1
                logger.info(f"  ✓ Certificate generated for {cert.recipient_email}")

                # Dispatch email notification / attachment
                send_certificate_email(
                    recipient_name=cert.recipient_name,
                    recipient_email=cert.recipient_email,
                    event_name=job.event_name,
                    pdf_file_path=file_path,
                    issued_by=job.issued_by,
                )

            except Exception as exc:
                # ── Individual failure: log, mark, continue ────────────────
                error_msg = f"{type(exc).__name__}: {str(exc)}"
                logger.warning(
                    f"  ✗ Failed to generate certificate for {cert.recipient_email}: {error_msg}"
                )
                cert.status = CertificateStatus.FAILED
                cert.error_message = error_msg
                job.failed_count += 1
                failed += 1

            finally:
                db.commit()

        # ── 5. Finalize job status ─────────────────────────────────────────
        if failed == 0:
            job.status = JobStatus.COMPLETED
        elif completed == 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.PARTIALLY_COMPLETED

        db.commit()

        summary = {
            "job_id": job_id,
            "status": job.status.value,
            "total": job.total_count,
            "completed": completed,
            "failed": failed,
        }
        logger.info(f"Job {job_id} finished: {summary}")
        return summary

    except Exception as exc:
        # Unexpected failure — mark job as failed and re-raise for Celery retry
        logger.exception(f"Unexpected error processing job {job_id}: {exc}")
        try:
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
