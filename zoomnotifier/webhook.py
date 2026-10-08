"""Zoom webhook receiver: calls you when someone enters your Personal Meeting Room.

Run locally:   python -m zoomnotifier.webhook
Production:    gunicorn "zoomnotifier.webhook:create_app()"
"""

import hashlib
import hmac
import logging
import os
import threading
import time

from flask import Flask, abort, jsonify, request

from .config import Settings
from .notifier import Notifier

log = logging.getLogger(__name__)

# Events that mean "someone is trying to get into / has entered the room".
ALERT_EVENTS = {
    "meeting.participant_joined",               # joined the meeting
    "meeting.participant_joined_waiting_room",  # sitting in your waiting room
    "meeting.participant_jbh_waiting",          # waiting for you (the host) to start
    "meeting.participant_jbh_joined",           # joined before host
}

# Reject requests whose timestamp is too old (replay protection).
MAX_CLOCK_SKEW_SECONDS = 300


def _hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_signature(secret: str, timestamp: str, raw_body: str, signature: str) -> bool:
    if not (secret and timestamp and signature):
        return False
    try:
        if abs(time.time() - int(timestamp)) > MAX_CLOCK_SKEW_SECONDS:
            return False
    except ValueError:
        return False
    expected = "v0=" + _hmac_hex(secret, f"v0:{timestamp}:{raw_body}")
    return hmac.compare_digest(expected, signature)


def is_ignored(settings: Settings, obj: dict, participant: dict) -> bool:
    # Your own join (logged-in host) has the same user id as the meeting host.
    host_id = obj.get("host_id")
    if host_id and participant.get("id") == host_id:
        return True
    email = (participant.get("email") or "").lower()
    name = (participant.get("user_name") or "").lower()
    return bool(email and email in settings.ignore_participants) or bool(
        name and name in settings.ignore_participants
    )


def create_app(settings: Settings | None = None, notifier: Notifier | None = None) -> Flask:
    settings = settings or Settings.from_env()
    if not settings.zoom_webhook_secret:
        raise RuntimeError("ZOOM_WEBHOOK_SECRET_TOKEN is required for webhook mode")
    notifier = notifier or Notifier(settings)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = Flask(__name__)

    @app.get("/")
    def health():
        return "ZoomNotifier is running"

    @app.post("/zoom/webhook")
    def zoom_webhook():
        raw = request.get_data(as_text=True)
        if not verify_signature(
            settings.zoom_webhook_secret,
            request.headers.get("x-zm-request-timestamp", ""),
            raw,
            request.headers.get("x-zm-signature", ""),
        ):
            abort(401)

        body = request.get_json(silent=True) or {}
        event = body.get("event", "")
        payload = body.get("payload", {})

        # Zoom validates the endpoint URL when you save it (and every 72h).
        if event == "endpoint.url_validation":
            plain = payload.get("plainToken", "")
            return jsonify(
                plainToken=plain,
                encryptedToken=_hmac_hex(settings.zoom_webhook_secret, plain),
            )

        if event not in ALERT_EVENTS:
            return "", 204

        obj = payload.get("object", {})
        participant = obj.get("participant", {})
        meeting_id = str(obj.get("id", ""))

        if settings.zoom_pmi and meeting_id != settings.zoom_pmi:
            return "", 204
        if is_ignored(settings, obj, participant):
            return "", 204

        name = participant.get("user_name") or "Someone"
        log.info("%s: %s in meeting %s", event, name, meeting_id)
        # Zoom expects a response within 3 seconds, so place the call in the background.
        threading.Thread(
            target=_safe_alert, args=(notifier, meeting_id, name), daemon=True
        ).start()
        return "", 200

    return app


def _safe_alert(notifier: Notifier, key: str, name: str) -> None:
    try:
        notifier.alert(key, name)
    except Exception:
        log.exception("Failed to place alert call")


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
