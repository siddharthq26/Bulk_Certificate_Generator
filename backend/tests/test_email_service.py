"""
Tests for email delivery service.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.email_service import send_certificate_email


class TestEmailService:
    def test_simulation_mode_when_no_smtp(self, tmp_path):
        """When SMTP credentials are not configured, runs in mock/simulation mode without error."""
        pdf_file = tmp_path / "cert.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test")

        success = send_certificate_email(
            recipient_name="Siddharth Sharma",
            recipient_email="siddharth@example.com",
            event_name="Cloud Computing",
            pdf_file_path=str(pdf_file),
            issued_by="Tech Academy",
        )
        assert success is True

    @patch("smtplib.SMTP")
    def test_smtp_send_success(self, mock_smtp_class, tmp_path):
        """When SMTP credentials are configured, sends email with attachment."""
        pdf_file = tmp_path / "cert.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test")

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.mailtrap.io"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user123"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM_EMAIL = "certs@test.com"

            success = send_certificate_email(
                recipient_name="Jane Doe",
                recipient_email="jane@example.com",
                event_name="AI Workshop",
                pdf_file_path=str(pdf_file),
                issued_by="AI Institute",
            )

            assert success is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user123", "pass")
            mock_server.send_message.assert_called_once()
