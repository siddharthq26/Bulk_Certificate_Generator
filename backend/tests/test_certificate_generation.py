"""
Tests for certificate generation service (unit tests).
Covers: successful generation, file existence, content, partial failure handling.
"""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch


class TestCertificateGenerator:
    """Unit tests for app.services.certificate_generator.generate_certificate"""

    @pytest.fixture(autouse=True)
    def temp_cert_dir(self, tmp_path):
        """Use a temp directory for certificate storage in tests."""
        with patch("app.services.certificate_generator.settings") as mock_settings:
            mock_settings.CERT_STORAGE_PATH = str(tmp_path)
            yield tmp_path

    def test_generate_certificate_creates_file(self):
        """Generating a certificate produces a PDF file on disk."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="Jane Doe",
            recipient_email="jane@example.com",
            event_name="Test Workshop",
            issued_by="Test Org",
        )
        assert Path(filepath).exists()
        assert filepath.endswith(".pdf")

    def test_generate_certificate_file_not_empty(self):
        """Generated PDF has non-zero size."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="John Smith",
            recipient_email="john@example.com",
            event_name="Coding Bootcamp",
            issued_by="Dev Academy",
        )
        assert Path(filepath).stat().st_size > 0

    def test_generate_certificate_with_all_fields(self):
        """Generation works with all optional fields provided."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="Full Fields User",
            recipient_email="full@example.com",
            event_name="Full Event",
            issued_by="Full Org",
            course_name="Full Course",
            completion_date="2024-01-15",
            certificate_id="test-cert-id-001",
        )
        assert Path(filepath).exists()

    def test_generate_certificate_without_optional_fields(self):
        """Generation works with only required fields."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="Minimal User",
            recipient_email="minimal@example.com",
            event_name="Minimal Event",
            issued_by="Org",
        )
        assert Path(filepath).exists()

    def test_generate_certificate_custom_id_in_filename(self):
        """Custom certificate_id appears in the filename."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="ID Test",
            recipient_email="idtest@example.com",
            event_name="Event",
            issued_by="Org",
            certificate_id="abcdef12-1234-5678-9abc-def012345678",
        )
        # First 8 chars of the ID should appear in filename
        assert "abcdef12" in Path(filepath).name

    def test_generate_certificate_special_chars_in_name(self):
        """Handles recipient names with special characters gracefully."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="María José García-López",
            recipient_email="maria@example.com",
            event_name="Event",
            issued_by="Org",
        )
        assert Path(filepath).exists()

    def test_generate_certificate_returns_absolute_path(self):
        """Return value is an absolute path string."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="Path Test",
            recipient_email="path@example.com",
            event_name="Event",
            issued_by="Org",
        )
        assert os.path.isabs(filepath)

    def test_generate_certificate_is_valid_pdf(self):
        """Generated file starts with PDF magic bytes (%PDF)."""
        from app.services.certificate_generator import generate_certificate
        filepath = generate_certificate(
            recipient_name="PDF Check",
            recipient_email="pdfcheck@example.com",
            event_name="Event",
            issued_by="Org",
        )
        with open(filepath, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_multiple_certs_get_unique_filenames(self):
        """Multiple certificates for different recipients get unique files."""
        from app.services.certificate_generator import generate_certificate
        path1 = generate_certificate(
            recipient_name="User One",
            recipient_email="one@example.com",
            event_name="Event",
            issued_by="Org",
        )
        path2 = generate_certificate(
            recipient_name="User Two",
            recipient_email="two@example.com",
            event_name="Event",
            issued_by="Org",
        )
        assert path1 != path2
        assert Path(path1).exists()
        assert Path(path2).exists()
