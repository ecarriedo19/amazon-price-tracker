"""Where alerts go: the console, or WhatsApp via Twilio."""

from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)

TWILIO_ENV_VARS = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "WHATSAPP_TO")


class Notifier(Protocol):
    def send(self, message: str) -> None: ...


class ConsoleNotifier:
    """Prints alerts. Used for --dry-run and --demo."""

    def send(self, message: str) -> None:
        print(f"{'-' * 60}\n{message}\n{'-' * 60}", flush=True)


class TwilioWhatsAppNotifier:
    """Sends alerts as WhatsApp messages through the Twilio API."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str, to_number: str) -> None:
        try:
            from twilio.rest import Client
        except ImportError as exc:
            raise RuntimeError(
                "Twilio is not installed. Run: pip install -e '.[whatsapp]'"
            ) from exc
        self._client = Client(account_sid, auth_token)
        self._from = f"whatsapp:{from_number}"
        self._to = f"whatsapp:{to_number}"

    @classmethod
    def from_env(cls) -> TwilioWhatsAppNotifier:
        missing = [name for name in TWILIO_ENV_VARS if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                f"Missing environment variables: {', '.join(missing)}. "
                "Set them (see .env.example) or use --dry-run."
            )
        return cls(*(os.environ[name] for name in TWILIO_ENV_VARS))

    def send(self, message: str) -> None:
        self._client.messages.create(body=message, from_=self._from, to=self._to)
        logger.info("WhatsApp alert sent")
