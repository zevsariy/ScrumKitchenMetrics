"""Base email sender abstraction."""
from __future__ import annotations

import abc
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

class EmailSender(abc.ABC):
    @abc.abstractmethod
    def send(self, subject: str, body: str, to: Iterable[str], attachments: list[Path] | None = None) -> None:
        ...

    @staticmethod
    def build_message(subject: str, body: str, sender: str, to: Iterable[str], attachments: list[Path] | None = None) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(to)
        msg.set_content(body)
        for path in attachments or []:
            with open(path, 'rb') as f:
                data = f.read()
            maintype, subtype = _guess_mime(path)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        return msg

def _guess_mime(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == '.pdf':
        return 'application', 'pdf'
    if path.suffix.lower() in {'.xls', '.xlsx'}:
        return 'application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return 'application', 'octet-stream'
