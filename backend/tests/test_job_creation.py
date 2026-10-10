"""
Tests for job creation endpoint.
Covers: creating a job, input validation, duplicate emails, edge cases.
"""
import pytest
from uuid import UUID


class TestCreateJob:
    """Tests for POST /api/v1/jobs/"""

    @pytest.mark.asyncio
    async def test_create_job_success(self, client, valid_job_payload):
        """Successfully create a job with valid payload."""
        ac, mock_task = client
        response = await ac.post("/api/v1/jobs/", json=valid_job_payload)

        assert response.status_code == 202
        data = response.json()

        assert "id" in data
        assert data["event_name"] == "Python Mastery Workshop"
        assert data["issued_by"] == "Tech Academy"
        assert data["status"] == "pending"
        assert data["total_count"] == 2
        assert "message" in data

        # Verify UUID is valid
        UUID(data["id"])

        # Verify Celery task was dispatched
        mock_task.delay.assert_called_once_with(data["id"])

    @pytest.mark.asyncio
    async def test_create_job_dispatches_celery_task(self, client, valid_job_payload):
        """Verify that creating a job dispatches exactly one Celery task."""
        ac, mock_task = client
        await ac.post("/api/v1/jobs/", json=valid_job_payload)
        assert mock_task.delay.call_count == 1

    @pytest.mark.asyncio
    async def test_create_job_single_recipient(self, client, single_recipient_payload):
        """Create a job with a single recipient."""
        ac, _ = client
        response = await ac.post("/api/v1/jobs/", json=single_recipient_payload)
        assert response.status_code == 202
        assert response.json()["total_count"] == 1

    @pytest.mark.asyncio
    async def test_create_job_large_batch(self, client):
        """Create a job with 50 recipients."""
        ac, _ = client
        recipients = [
            {"name": f"User {i}", "email": f"user{i}@example.com"}
            for i in range(50)
        ]
        payload = {
            "event_name": "Large Workshop",
            "issued_by": "Big Corp",
            "recipients": recipients,
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 202
        assert response.json()["total_count"] == 50

    @pytest.mark.asyncio
    async def test_create_job_without_optional_fields(self, client):
        """Create a job where recipients have no optional fields."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [
                {"name": "Min User", "email": "min@example.com"}
            ],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 202


class TestCreateJobValidation:
    """Validation tests for POST /api/v1/jobs/"""

    @pytest.mark.asyncio
    async def test_missing_event_name(self, client):
        """Reject payload with missing event_name."""
        ac, _ = client
        payload = {
            "issued_by": "Org",
            "recipients": [{"name": "Alice", "email": "alice@example.com"}],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_recipients_list(self, client):
        """Reject payload with empty recipients list."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email(self, client):
        """Reject recipient with invalid email format."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [
                {"name": "Bad Email", "email": "not-an-email"}
            ],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_blank_recipient_name(self, client):
        """Reject recipient with blank/whitespace-only name."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [
                {"name": "   ", "email": "valid@example.com"}
            ],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, client):
        """Reject recipient with non-ISO completion_date."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [
                {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "completion_date": "15-06-2024",  # wrong format
                }
            ],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_emails_rejected(self, client):
        """Reject payload with duplicate recipient emails."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "issued_by": "Org",
            "recipients": [
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Alice Again", "email": "alice@example.com"},
            ],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422
        # The error detail should mention duplicates somewhere in the response
        response_text = str(response.json()).lower()
        assert "duplicate" in response_text

    @pytest.mark.asyncio
    async def test_missing_issued_by(self, client):
        """Reject payload missing issued_by."""
        ac, _ = client
        payload = {
            "event_name": "Workshop",
            "recipients": [{"name": "Alice", "email": "alice@example.com"}],
        }
        response = await ac.post("/api/v1/jobs/", json=payload)
        assert response.status_code == 422
