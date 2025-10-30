"""Exchange / Office365 SMTP sender implementation."""
from __future__ import annotations

import smtplib

from .base_sender import EmailSender
from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

class ExchangeSender(EmailSender):
    def send(self, subject: str, body: str, to, attachments=None) -> None:  # noqa: D401
        cfg = get_settings().email
        if not cfg.exchange_user or not cfg.exchange_password:
            raise ValueError("EXCHANGE_USER or EXCHANGE_PASSWORD missing")
        msg = self.build_message(subject, body, cfg.exchange_user, to, attachments)
        with smtplib.SMTP(cfg.exchange_server, cfg.exchange_port) as smtp:
            smtp.starttls()
            smtp.login(cfg.exchange_user, cfg.exchange_password)
            smtp.send_message(msg)
        logger.info("Email sent via Exchange to %s", to)
