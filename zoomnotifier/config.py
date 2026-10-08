"""Settings loaded from environment variables (or a .env file)."""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass
class Settings:
    # Twilio (places the phone call)
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    my_phone_number: str

    # Zoom
    zoom_webhook_secret: str = ""
    # Your Personal Meeting ID, digits only. Empty = alert for every meeting you host.
    zoom_pmi: str = ""
    # Emails / display names that should never trigger a call (e.g. yourself).
    ignore_participants: list[str] = field(default_factory=list)

    # Minimum seconds between two calls for the same meeting.
    cooldown_seconds: int = 300
    # Also send an SMS alongside the call.
    send_sms: bool = False
    # What the call says. {name} is replaced with the participant's name.
    call_message: str = "Hey! {name} just joined your Zoom personal meeting room."

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            twilio_account_sid=_required("TWILIO_ACCOUNT_SID"),
            twilio_auth_token=_required("TWILIO_AUTH_TOKEN"),
            twilio_from_number=_required("TWILIO_FROM_NUMBER"),
            my_phone_number=_required("MY_PHONE_NUMBER"),
            zoom_webhook_secret=os.environ.get("ZOOM_WEBHOOK_SECRET_TOKEN", "").strip(),
            zoom_pmi=os.environ.get("ZOOM_PMI", "").replace(" ", "").replace("-", ""),
            ignore_participants=_list("IGNORE_PARTICIPANTS"),
            cooldown_seconds=int(os.environ.get("COOLDOWN_SECONDS", "300")),
            send_sms=os.environ.get("SEND_SMS", "false").lower() in ("1", "true", "yes"),
            call_message=os.environ.get("CALL_MESSAGE", cls.call_message),
        )
