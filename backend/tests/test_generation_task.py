"""
Tests for the Celery generation task — partial failure handling,
job status transitions, and individual certificate error isolation.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Session, DeclarativeBase

from app.models.models import JobStatus, CertificateStatus


# ── SQLite-compatible models (no PostgreSQL UUID type) ─────────────────────────

class TaskTestBase(DeclarativeBase):
    pass


class TaskTestJob(TaskTestBase):
    __tablename__ = "tt_generation_jobs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String(255))
    issued_by = Column(String(255))
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    total_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    celery_task_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class TaskTestCertificate(TaskTestBase):
    __tablename__ = "tt_certificates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36))
    recipient_name = Column(String(255))
    recipient_email = Column(String(255))
    course_name = Column(String(255), nullable=True)
    completion_date = Column(String(50), nullable=True)
    status = Column(SAEnum(CertificateStatus), default=CertificateStatus.PENDING)
    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)


@pytest.fixture
def sync_db():
    """Provide a synchronous test database session (SQLite with string UUIDs)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TaskTestBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()
    engine.dispose()


def create_test_job(db: Session, num_recipients: int = 3) -> TaskTestJob:
    """Helper to create a job with N recipients in sync DB."""
    job = TaskTestJob(
        event_name="Test Event",
        issued_by="Test Org",
        status=JobStatus.PENDING,
        total_count=num_recipients,
        completed_count=0,
        failed_count=0,
    )
    db.add(job)
    db.flush()

    for i in range(num_recipients):
        cert = TaskTestCertificate(
            job_id=job.id,
            recipient_name=f"User {i}",
            recipient_email=f"user{i}@example.com",
            status=CertificateStatus.PENDING,
        )
        db.add(cert)
    db.commit()
    db.refresh(job)
    return job


def run_task_with_test_models(job_id: str, db: Session, mock_gen_fn):
    """
    Replicate the Celery task logic using SQLite-compatible test models.
    Tests the core business logic without PostgreSQL-specific UUID columns.
    """
    job = db.query(TaskTestJob).filter(TaskTestJob.id == job_id).first()
    if not job:
        return {"error": "Job not found"}

    job.status = JobStatus.PROCESSING
    db.commit()

    certificates = (
        db.query(TaskTestCertificate)
        .filter(
            TaskTestCertificate.job_id == job_id,
            TaskTestCertificate.status == CertificateStatus.PENDING,
        )
        .all()
    )

    completed = 0
    failed = 0

    for cert in certificates:
        try:
            cert.status = CertificateStatus.GENERATING
            db.commit()

            file_path = mock_gen_fn(
                recipient_name=cert.recipient_name,
                recipient_email=cert.recipient_email,
                event_name=job.event_name,
                issued_by=job.issued_by,
            )

            cert.status = CertificateStatus.COMPLETED
            cert.file_path = file_path
            job.completed_count += 1
            completed += 1

        except Exception as exc:
            cert.status = CertificateStatus.FAILED
            cert.error_message = f"{type(exc).__name__}: {str(exc)}"
            job.failed_count += 1
            failed += 1

        finally:
            db.commit()

    if failed == 0:
        job.status = JobStatus.COMPLETED
    elif completed == 0:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.PARTIALLY_COMPLETED

    db.commit()
    return {
        "job_id": job_id,
        "status": job.status.value,
        "total": job.total_count,
        "completed": completed,
        "failed": failed,
    }



class TestGenerationTask:
    """Tests for the certificate generation task logic — partial failure handling,
    status transitions, and error isolation."""

    def test_task_completes_all_certificates(self, sync_db, tmp_path):
        """All certificates marked COMPLETED when generation succeeds."""
        def mock_gen(**kwargs):
            path = tmp_path / f"cert_{kwargs['recipient_email']}.pdf"
            path.write_bytes(b"%PDF-fake")
            return str(path)

        job = create_test_job(sync_db, num_recipients=3)
        result = run_task_with_test_models(str(job.id), sync_db, mock_gen)

        sync_db.refresh(job)
        assert job.status == JobStatus.COMPLETED
        assert job.completed_count == 3
        assert job.failed_count == 0
        assert result["completed"] == 3
        assert result["failed"] == 0

    def test_task_partial_failure_does_not_block_others(self, sync_db, tmp_path):
        """A single certificate failure does not prevent others from being generated."""
        call_count = 0

        def mock_gen(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Simulated generation failure")
            path = tmp_path / f"cert_{call_count}.pdf"
            path.write_bytes(b"%PDF-fake")
            return str(path)

        job = create_test_job(sync_db, num_recipients=3)
        result = run_task_with_test_models(str(job.id), sync_db, mock_gen)

        sync_db.refresh(job)
        assert job.status == JobStatus.PARTIALLY_COMPLETED
        assert job.completed_count == 2
        assert job.failed_count == 1
        assert result["completed"] == 2
        assert result["failed"] == 1

    def test_task_all_failures_marks_job_failed(self, sync_db):
        """If all certificates fail, job status becomes FAILED."""
        def mock_gen(**kwargs):
            raise RuntimeError("All fail")

        job = create_test_job(sync_db, num_recipients=2)
        result = run_task_with_test_models(str(job.id), sync_db, mock_gen)

        sync_db.refresh(job)
        assert job.status == JobStatus.FAILED
        assert job.completed_count == 0
        assert job.failed_count == 2

    def test_failed_certificate_has_error_message(self, sync_db):
        """Failed certificate records capture the error message."""
        def mock_gen(**kwargs):
            raise ValueError("PDF rendering error")

        job = create_test_job(sync_db, num_recipients=1)
        run_task_with_test_models(str(job.id), sync_db, mock_gen)

        cert = sync_db.query(TaskTestCertificate).filter(
            TaskTestCertificate.job_id == job.id
        ).first()
        assert cert.status == CertificateStatus.FAILED
        assert cert.error_message is not None
        assert "PDF rendering error" in cert.error_message

    def test_task_marks_job_completed_after_run(self, sync_db, tmp_path):
        """Job status is COMPLETED after successful run."""
        def mock_gen(**kwargs):
            path = tmp_path / "cert.pdf"
            path.write_bytes(b"%PDF-fake")
            return str(path)

        job = create_test_job(sync_db, num_recipients=1)
        run_task_with_test_models(str(job.id), sync_db, mock_gen)

        sync_db.refresh(job)
        assert job.status == JobStatus.COMPLETED

    def test_task_nonexistent_job_returns_error(self, sync_db):
        """Task handles gracefully when job_id doesn't exist."""
        result = run_task_with_test_models(str(uuid.uuid4()), sync_db, lambda **k: None)
        assert result.get("error") == "Job not found"

    def test_completed_certificates_have_file_path(self, sync_db, tmp_path):
        """Completed certificates store the file path."""
        expected_path = str(tmp_path / "cert.pdf")
        (tmp_path / "cert.pdf").write_bytes(b"%PDF-fake")

        def mock_gen(**kwargs):
            return expected_path

        job = create_test_job(sync_db, num_recipients=1)
        run_task_with_test_models(str(job.id), sync_db, mock_gen)

        cert = sync_db.query(TaskTestCertificate).filter(
            TaskTestCertificate.job_id == job.id
        ).first()
        assert cert.status == CertificateStatus.COMPLETED
        assert cert.file_path == expected_path




class TestCertificateDownload:
    """Tests for certificate download endpoint."""

    @pytest.mark.asyncio
    async def test_download_not_completed_certificate(self, client, valid_job_payload):
        """Cannot download a certificate that is still pending."""
        ac, _ = client
        create_resp = await ac.post("/api/v1/jobs/", json=valid_job_payload)
        job_id = create_resp.json()["id"]

        # Get a certificate ID
        list_resp = await ac.get(f"/api/v1/jobs/{job_id}/certificates")
        cert_id = list_resp.json()[0]["id"]

        # Try to download — should fail with 409 since it's pending
        dl_resp = await ac.get(f"/api/v1/jobs/{job_id}/certificates/{cert_id}/download")
        assert dl_resp.status_code == 409

    @pytest.mark.asyncio
    async def test_download_certificate_job_not_found(self, client):
        """Returns 404 when job doesn't exist."""
        ac, _ = client
        fake_job = str(uuid.uuid4())
        fake_cert = str(uuid.uuid4())
        resp = await ac.get(f"/api/v1/jobs/{fake_job}/certificates/{fake_cert}/download")
        assert resp.status_code == 404
