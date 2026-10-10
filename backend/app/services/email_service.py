"""
Email delivery service for sending generated certificates to recipients.

Supports:
- SMTP (e.g., Gmail, SendGrid, Amazon SES, Mailgun, Mailtrap)
- Development/Mock mode: logs email dispatch without crashing when SMTP is not configured.
"""
import smtplib
import logging
from email.message import EmailMessage
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_certificate_email(
    recipient_name: str,
    recipient_email: str,
    event_name: str,
    pdf_file_path: str,
    issued_by: str,
) -> bool:
    """
    Send an email with the generated certificate PDF attached.

    If SMTP credentials are not provided in environment variables,
    it runs in simulation/dev mode and logs the action.
    """
    smtp_host = getattr(settings, "SMTP_HOST", "")
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USER", "")
    smtp_password = getattr(settings, "SMTP_PASSWORD", "")
    sender_email = getattr(settings, "SMTP_FROM_EMAIL", "certificates@certifyhub.com")

    # If no SMTP configured, log simulation mode
    if not smtp_host or not smtp_user:
        logger.info(
            f"[EMAIL DISPATCH SIMULATION] Certificate successfully prepared for {recipient_email} "
            f"({recipient_name}) for '{event_name}' (Attachment: {pdf_file_path})"
        )
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = f"Your Certificate of Completion for {event_name}"
        msg["From"] = sender_email
        msg["To"] = recipient_email

        msg.set_content(
            f"Hello {recipient_name},\n\n"
            f"Congratulations on successfully completing {event_name}!\n\n"
            f"Your certificate of completion issued by {issued_by} is attached to this email.\n\n"
            f"Best regards,\n"
            f"{issued_by}"
        )

        # Attach PDF
        pdf_path = Path(pdf_file_path)
        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename=f"Certificate_{recipient_name.replace(' ', '_')}.pdf"
            )

        # Send via SMTP
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"✓ Certificate email sent to {recipient_email}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to email certificate to {recipient_email}: {e}")
        return False
