import logging
import os
import smtplib
from email.message import EmailMessage


logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, reset_url: str) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        if os.getenv("ENVIRONMENT", "development").lower() in {"development", "dev"}:
            logger.warning("Development password reset link for %s: %s", email, reset_url)
            return
        raise RuntimeError("SMTP_HOST is required to send password reset emails")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username or "")
    if not sender:
        raise RuntimeError("SMTP_FROM or SMTP_USERNAME is required")

    message = EmailMessage()
    message["Subject"] = "Reset your Solvane ERP password"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "We received a request to reset your Solvane ERP password.\n\n"
        f"Use this link within 30 minutes: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as client:
            if username:
                client.login(username, password or "")
            client.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as client:
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            client.starttls()
        if username:
            client.login(username, password or "")
        client.send_message(message)
