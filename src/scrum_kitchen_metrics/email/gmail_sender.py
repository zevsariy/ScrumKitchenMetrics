"""Gmail sender implementation using SMTP with app password."""
from __future__ import annotations

import smtplib
from pathlib import Path

from .base_sender import EmailSender
from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

class GmailSender(EmailSender):
    def send(self, subject: str, body: str, to, attachments=None) -> None:  # noqa: D401
        cfg = get_settings().email
        if not cfg.gmail_user or not cfg.gmail_app_password:
            raise ValueError("GMAIL_USER or GMAIL_APP_PASSWORD missing")
        msg = self.build_message(subject, body, cfg.gmail_user, to, attachments)
        with smtplib.SMTP(cfg.gmail_server, cfg.gmail_port) as smtp:
            smtp.starttls()
            smtp.login(cfg.gmail_user, cfg.gmail_app_password)
            smtp.send_message(msg)
        logger.info("Email sent via Gmail to %s", to)
