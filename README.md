# ZoomNotifier

Calls your phone when someone joins your Zoom **Personal Meeting Room** (PMI).

Two ways it can find out someone joined:

```
Email watcher (works on UT without approval):
  Someone joins your PMI ──► Zoom emails you ──► watcher reads the email ──► Twilio ──► your phone rings

Webhook (needs a Zoom app, which UT must approve):
  Someone joins your PMI ──► Zoom webhook ──► this server ──► Twilio ──► your phone rings
```

Your own join is ignored, and a cooldown (5 minutes by default) stops a group of people from ringing your phone over and over.

---

## Which setup to use (UT accounts)

`utexas.zoom.us` is run by UT's IT team, and **creating a Zoom Marketplace app needs admin approval**, so the webhook route is blocked by default. Your options:

| | **Email watcher (use this)** | Webhook | Personal (non-UT) Zoom account + webhook |
|---|---|---|---|
| Needs | A Zoom setting + an email inbox | UT ITS to approve your app | A separate free Zoom account |
| Speed | About 20–60 s | About 1–2 s | About 1–2 s |
| Detects | People who join before you | Joins, waiting room, waiting for host | Same as webhook |
| Catch | Waiting room must be **off** for your PMI | Approval may take a while or be denied | Not your UT room; free meetings stop after 40 min |

**Start with the email watcher.** If you also want instant alerts, ask UT ITS to approve your app ([UT Zoom help](https://zoom.utexas.edu/)) and switch to the webhook once it is approved. The code for both is in this repo.

---

## 1. Twilio setup (needed for every option)

1. Sign up at <https://www.twilio.com/try-twilio>. A free trial is fine, but trial calls start with a short Twilio message and can only call numbers you have verified.
2. Buy or claim a phone number (Console → Phone Numbers).
3. Note your **Account SID** and **Auth Token** from the console dashboard.
4. On a trial account, verify your own cell number (Console → Verified Caller IDs).

Then:

```bash
pip install -r requirements.txt
cp .env.example .env                              # fill in the TWILIO_* and MY_PHONE_NUMBER lines
python -m zoomnotifier.email_watcher --test-call  # your phone should ring now
```

---

## 2. Email watcher (recommended for UT)

Zoom can email you when someone joins your meeting before you do. The watcher reads those emails and calls you.

### 2a. Zoom settings

At <https://utexas.zoom.us/profile/setting> (and on your PMI's own settings at <https://utexas.zoom.us/meeting#/pmi>):

- Turn **on** *Allow participants to join before host*.
- Turn **on** *Notify host when participants join the meeting before host*. This is the email Zoom sends you.
- Turn **off** the *Waiting Room* for your PMI. People in a waiting room do not count as "joined", so Zoom sends no email. Keep a **passcode** on the PMI so strangers can't just walk in.

If UT has locked any of these settings (they show greyed out), the email watcher can't work. In that case, request app approval from ITS, or use a personal Zoom account.

### 2b. Get the emails somewhere the watcher can read them

UT's Microsoft 365 mailbox does not allow simple password (IMAP) logins, so send the Zoom emails to a Gmail account:

1. In Outlook on the web (<https://outlook.office.com>) go to Settings → Mail → Rules → **Add new rule**: *From* `no-reply@zoom.us` → *Forward to* `you@gmail.com`.
   - If UT blocks forwarding to outside addresses, use **Power Automate** instead (<https://make.powerautomate.com>, sign in with UT): *When a new email arrives (V3)*, From = `no-reply@zoom.us` → *Send an email (V2)* to your Gmail.
2. In Gmail, turn on 2-Step Verification and create an **App Password** (<https://myaccount.google.com/apppasswords>).
3. Put `IMAP_USER` (your Gmail) and `IMAP_PASSWORD` (the app password) in `.env`.

### 2c. Run it

On any computer that stays on (your laptop while you're working, a Raspberry Pi or a small cloud VM):

```bash
python -m zoomnotifier.email_watcher
```

### 2d. Test it

Sign out of Zoom on another device (or use a private browser window) and join your PMI link. Within a minute, the email should arrive and your phone should ring.

If the email arrives but no call comes, check its subject line. The watcher only reacts to Zoom emails whose subject matches `ZOOM_EMAIL_SUBJECT_PATTERN` (a regex, default `join`), so change it to match.

---

## 3. Webhook (once UT ITS approves your app, or with a personal Zoom account)

### 3a. Deploy the server (it needs a public HTTPS URL)

**Render (free):** push this repo to GitHub, then go to Render → New → Blueprint and pick the repo. `render.yaml` sets everything up, and you enter the env vars in the dashboard.
> Free Render services go to sleep when idle, and waking one can take longer than Zoom's 3-second timeout. To avoid this, use a paid instance, or ping `/` every 10 minutes with a free uptime monitor such as UptimeRobot.

**Docker anywhere:** `docker build -t zoomnotifier . && docker run --env-file .env -p 8000:8000 zoomnotifier`

**Local testing:** `python -m zoomnotifier.webhook` (port 8000), then `ngrok http 8000`.

Your webhook URL is `https://<your-host>/zoom/webhook`.

### 3b. Create the Zoom app

1. Go to <https://marketplace.zoom.us/> → **Develop → Build App** → **General App**.
2. **Features → Access:** copy the **Secret Token** into `ZOOM_WEBHOOK_SECRET_TOKEN` and restart the server.
3. **Event Subscription:** turn it on. Set Endpoint URL `https://<your-host>/zoom/webhook`, then click **Validate** (the server answers Zoom's check automatically). Add these Meeting events: *Participant/Host joined meeting*, *Participant joined waiting room*, *Participant waiting for host*, *Participant joined before host*.
4. **Scopes:** add the meeting read scope the event picker asks for.
5. Install the app on your account (on UT this is the step that waits for admin approval).

When asking ITS for approval, say that the app only *receives* meeting-join events for your own account and has no access to recordings, chat or other users.

---

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `ZOOM_PMI` | *(blank)* | Only alert for this meeting ID. Blank = any meeting you host |
| `IGNORE_PARTICIPANTS` | | Comma-separated emails or display names that never trigger a call |
| `COOLDOWN_SECONDS` | `300` | Minimum time between calls for the same meeting |
| `SEND_SMS` | `false` | Also send a text |
| `CALL_MESSAGE` | `Hey! {name} just joined…` | What the call says. `{name}` = participant's name |

## Development

```bash
pip install -r requirements-dev.txt
pytest
```
