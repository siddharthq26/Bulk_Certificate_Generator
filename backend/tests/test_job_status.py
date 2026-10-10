"""
Tests for job status and detail endpoints.
Covers: status tracking, progress calculation, certificates listing.
"""
import pytest
from uuid import UUID, uuid4


class TestJobStatus:
    """Tests for GET /api/v1/jobs/{job_id}"""

    @pytest.mark.asyncio
    async def test_get_job_status_after_creation(self, client, valid_job_payload):
        """Verify that a newly created job has pending status."""
        ac, _ = client
        create_resp = await ac.post("/api/v1/jobs/", json=valid_job_payload)
        job_id = create_resp.json()["id"]

        status_resp = await ac.get(f"/api/v1/jobs/{job_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()

        assert data["id"] == job_id
        assert data["event_name"] == "Python Mastery Workshop"
        assert data["issued_by"] == "Tech Academy"
        assert data["status"] == "pending"
        assert data["total_count"] == 2
        assert data["completed_count"] == 0
        assert data["failed_count"] == 0
        assert data["progress_percentage"] == 0.0
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, client):
        """Return 404 for a non-existent job ID."""
        ac, _ = client
        fake_id = str(uuid4())
        response = await ac.get(f"/api/v1/jobs/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_job_status_invalid_uuid(self, client):
        """Return 422 for a non-UUID job ID."""
        ac, _ = client
        response = await ac.get("/api/v1/jobs/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_celery_task_id_recorded(self, client, single_recipient_payload):
        """Verify that the celery task ID is stored on the job."""
        ac, mock_task = client
        mock_task.delay.return_value.id = "celery-task-xyz"

        create_resp = await ac.post("/api/v1/jobs/", json=single_recipient_payload)
        job_id = create_resp.json()["id"]

        status_resp = await ac.get(f"/api/v1/jobs/{job_id}")
        data = status_resp.json()
        assert data["celery_task_id"] == "celery-task-xyz"


class TestJobDetail:
    """Tests for GET /api/v1/jobs/{job_id}/detail"""

    @pytest.mark.asyncio
    async def test_get_job_detail_includes_certificates(self, client, valid_job_payload):
        """Detail endpoint includes certificate records."""
        ac, _ = client
        create_resp = await ac.post("/api/v1/jobs/", json=valid_job_payload)
        job_id = create_resp.json()["id"]

        detail_resp = await ac.get(f"/api/v1/jobs/{job_id}/detail")
        assert detail_resp.status_code == 200
        data = detail_resp.json()

        assert "certificates" in data
        assert len(data["certificates"]) == 2

        # Check certificate fields
        cert = data["certificates"][0]
        assert "id" in cert
        assert "recipient_name" in cert
        assert "recipient_email" in cert
        assert cert["status"] == "pending"

    @pytest.mark.asyncio
    async def test_job_detail_not_found(self, client):
        """Return 404 for non-existent job in detail endpoint."""
        ac, _ = client
        response = await ac.get(f"/api/v1/jobs/{uuid4()}/detail")
        assert response.status_code == 404


class TestListCertificates:
    """Tests for GET /api/v1/jobs/{job_id}/certificates"""

    @pytest.mark.asyncio
    async def test_list_certificates_for_job(self, client, valid_job_payload):
        """List all certificates for a job."""
        ac, _ = client
        create_resp = await ac.post("/api/v1/jobs/", json=valid_job_payload)
        job_id = create_resp.json()["id"]

        list_resp = await ac.get(f"/api/v1/jobs/{job_id}/certificates")
        assert list_resp.status_code == 200
        certs = list_resp.json()
        assert isinstance(certs, list)
        assert len(certs) == 2

    @pytest.mark.asyncio
    async def test_list_certificates_recipient_data_correct(self, client, valid_job_payload):
        """Verify recipient data is stored correctly."""
        ac, _ = client
        create_resp = await ac.post("/api/v1/jobs/", json=valid_job_payload)
        job_id = create_resp.json()["id"]

        list_resp = await ac.get(f"/api/v1/jobs/{job_id}/certificates")
        certs = list_resp.json()

        emails = {c["recipient_email"] for c in certs}
        assert "alice@example.com" in emails
        assert "bob@example.com" in emails

    @pytest.mark.asyncio
    async def test_list_certificates_job_not_found(self, client):
        """Return 404 when job does not exist."""
        ac, _ = client
        response = await ac.get(f"/api/v1/jobs/{uuid4()}/certificates")
        assert response.status_code == 404
