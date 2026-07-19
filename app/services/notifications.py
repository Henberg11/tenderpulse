"""
Sends alerts. Deliberately minimal and deliberately rare -- only fires when
something needs a human, not on every crawl cycle.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from loguru import logger

from app.config import settings


async def send_alert(subject: str, message: str) -> None:
    if settings.alert_email_to and settings.smtp_host:
        _send_email(subject, message)
    if settings.slack_webhook_url:
        await _send_slack(subject, message)
    if not settings.alert_email_to and not settings.slack_webhook_url:
        logger.warning(f"[alert] no notification channel configured -- would have sent: {subject}")


def send_html_email(subject: str, html_body: str, plain_fallback: str) -> None:
    """Separate from send_alert on purpose -- alerts are rare system-health
    pings (plain text is fine), the digest is a richer, regular email meant
    to actually be pleasant to read each morning."""
    if not (settings.alert_email_to and settings.smtp_host):
        logger.warning(f"[digest] no email configured -- would have sent: {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = settings.alert_email_to
        msg.attach(MIMEText(plain_fallback, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info(f"[digest] sent: {subject}")
    except Exception:
        logger.exception("[digest] failed to send digest email")


def _send_email(subject: str, message: str) -> None:
    try:
        msg = MIMEText(message)
        msg["Subject"] = f"[TenderPulse] {subject}"
        msg["From"] = settings.smtp_user
        msg["To"] = settings.alert_email_to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception:
        logger.exception("[alert] failed to send email alert")


async def _send_slack(subject: str, message: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.slack_webhook_url, json={"text": f"*[TenderPulse] {subject}*\n{message}"})
    except Exception:
        logger.exception("[alert] failed to send Slack alert")
