import hashlib
import hmac
import json
import time

import pytest

from zoomnotifier.config import Settings
from zoomnotifier.notifier import Notifier
from zoomnotifier import webhook

SECRET = "test-secret"


class FakeNotifier(Notifier):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = []

    def _post(self, resource, data):
        self.calls.append((resource, data))


@pytest.fixture
def settings():
    return Settings(
        twilio_account_sid="AC123", twilio_auth_token="tok",
        twilio_from_number="+15550000000", my_phone_number="+15551111111",
        zoom_webhook_secret=SECRET, zoom_pmi="1234567890",
        ignore_participants=["me@utexas.edu"],
    )


@pytest.fixture
def client_and_notifier(settings, monkeypatch):
    notifier = FakeNotifier(settings)

    class SyncThread:  # run the alert inline so tests can assert on it
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(webhook.threading, "Thread", SyncThread)
    app = webhook.create_app(settings, notifier)
    return app.test_client(), notifier


def post(client, body, secret=SECRET, ts=None):
    raw = json.dumps(body)
    ts = str(ts if ts is not None else int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{raw}".encode(), hashlib.sha256).hexdigest()
    return client.post("/zoom/webhook", data=raw, content_type="application/json",
                       headers={"x-zm-request-timestamp": ts, "x-zm-signature": sig})


def join_event(event="meeting.participant_joined", meeting_id="1234567890", **participant):
    participant.setdefault("user_name", "Alice")
    return {"event": event, "payload": {"object": {
        "id": meeting_id, "host_id": "HOST", "participant": participant}}}


def test_url_validation(client_and_notifier):
    client, _ = client_and_notifier
    resp = post(client, {"event": "endpoint.url_validation", "payload": {"plainToken": "abc"}})
    assert resp.status_code == 200
    expected = hmac.new(SECRET.encode(), b"abc", hashlib.sha256).hexdigest()
    assert resp.get_json() == {"plainToken": "abc", "encryptedToken": expected}


def test_bad_signature_rejected(client_and_notifier):
    client, notifier = client_and_notifier
    assert post(client, join_event(), secret="wrong").status_code == 401
    assert notifier.calls == []


def test_stale_timestamp_rejected(client_and_notifier):
    client, _ = client_and_notifier
    assert post(client, join_event(), ts=int(time.time()) - 3600).status_code == 401


@pytest.mark.parametrize("event", sorted(webhook.ALERT_EVENTS))
def test_join_events_place_call(client_and_notifier, event):
    client, notifier = client_and_notifier
    assert post(client, join_event(event=event)).status_code == 200
    assert len(notifier.calls) == 1
    resource, data = notifier.calls[0]
    assert resource == "Calls"
    assert data["To"] == "+15551111111"
    assert "Alice" in data["Twiml"]


def test_other_meeting_ignored(client_and_notifier):
    client, notifier = client_and_notifier
    post(client, join_event(meeting_id="999"))
    assert notifier.calls == []


def test_host_and_ignored_participants_skipped(client_and_notifier):
    client, notifier = client_and_notifier
    post(client, join_event(id="HOST"))
    post(client, join_event(email="ME@utexas.edu"))
    assert notifier.calls == []


def test_cooldown_prevents_repeat_calls(client_and_notifier):
    client, notifier = client_and_notifier
    post(client, join_event(user_name="Alice"))
    post(client, join_event(user_name="Bob"))
    assert len(notifier.calls) == 1


def test_name_is_xml_escaped(client_and_notifier):
    client, notifier = client_and_notifier
    post(client, join_event(user_name="<Eve & co>"))
    assert "&lt;Eve &amp; co&gt;" in notifier.calls[0][1]["Twiml"]


def test_sms_sent_when_enabled(settings):
    settings.send_sms = True
    notifier = FakeNotifier(settings)
    notifier.alert("m", "Alice")
    assert [r for r, _ in notifier.calls] == ["Calls", "Messages"]


def test_cooldown_expires(settings):
    now = [0.0]
    notifier = Notifier(settings, clock=lambda: now[0])
    assert notifier.should_alert("m")
    now[0] = settings.cooldown_seconds - 1
    assert not notifier.should_alert("m")
    now[0] = settings.cooldown_seconds + 1
    assert notifier.should_alert("m")
