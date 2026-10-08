from zoomnotifier.email_watcher import check_once, is_zoom_join_email


def test_matches_zoom_join_email():
    assert is_zoom_join_email("Zoom <no-reply@zoom.us>", "Alice has joined your meeting", "join")
    assert not is_zoom_join_email("Zoom <no-reply@zoom.us>", "Your cloud recording is ready", "join")
    assert not is_zoom_join_email("spam@example.com", "someone joined", "join")


class FakeImap:
    def __init__(self, messages):
        self.messages = messages
        self.seen = []

    def select(self, box):
        return "OK", [b""]

    def search(self, charset, criteria):
        return "OK", [b" ".join(self.messages)]

    def fetch(self, num, spec):
        return "OK", [(b"hdr", self.messages[num])]

    def store(self, num, flags, value):
        self.seen.append(num)


class FakeNotifier:
    def __init__(self):
        self.alerts = []

    def alert(self, key, name):
        self.alerts.append((key, name))


def test_check_once_alerts_only_on_join_emails():
    imap = FakeImap({
        b"1": b"From: no-reply@zoom.us\r\nSubject: Participants have joined your meeting\r\n\r\n",
        b"2": b"From: no-reply@zoom.us\r\nSubject: Cloud recording available\r\n\r\n",
    })
    notifier = FakeNotifier()
    assert check_once(imap, notifier, "join") == 1
    assert imap.seen == [b"1"]
    assert notifier.alerts == [("email", "Someone")]
