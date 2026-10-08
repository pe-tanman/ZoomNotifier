"""Places the phone call (and optional SMS) through Twilio's REST API."""

import base64
import logging
import threading
import time
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

from .config import Settings

log = logging.getLogger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/{resource}.json"


class Notifier:
    def __init__(self, settings: Settings, clock=time.monotonic):
        self.settings = settings
        self._clock = clock
        self._last_alert: dict[str, float] = {}
        self._lock = threading.Lock()

    def should_alert(self, key: str) -> bool:
        """Rate-limit so a burst of joins only rings your phone once."""
        now = self._clock()
        with self._lock:
            last = self._last_alert.get(key)
            if last is not None and now - last < self.settings.cooldown_seconds:
                return False
            self._last_alert[key] = now
            return True

    def alert(self, key: str, participant_name: str) -> bool:
        """Call (and optionally text) you. Returns False if suppressed by the cooldown."""
        if not self.should_alert(key):
            log.info("Suppressed alert for %s (cooldown)", key)
            return False

        message = self.settings.call_message.format(name=participant_name or "Someone")
        # Repeat the message once so you catch it after picking up.
        twiml = (
            "<Response>"
            f'<Say voice="alice">{escape(message)}</Say>'
            '<Pause length="1"/>'
            f'<Say voice="alice">{escape(message)}</Say>'
            "</Response>"
        )
        self._post("Calls", {"To": self.settings.my_phone_number,
                             "From": self.settings.twilio_from_number,
                             "Twiml": twiml})
        log.info("Calling %s: %s", self.settings.my_phone_number, message)

        if self.settings.send_sms:
            self._post("Messages", {"To": self.settings.my_phone_number,
                                    "From": self.settings.twilio_from_number,
                                    "Body": message})
        return True

    def _post(self, resource: str, data: dict) -> None:
        s = self.settings
        url = TWILIO_API.format(sid=s.twilio_account_sid, resource=resource)
        token = base64.b64encode(f"{s.twilio_account_sid}:{s.twilio_auth_token}".encode()).decode()
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Authorization": f"Basic {token}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
