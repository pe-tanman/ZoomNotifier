# ZoomNotifier

Calls your phone when someone joins your Zoom **Personal Meeting Room** (PMI).

```
Someone joins your PMI ──► Zoom webhook ──► this server ──► Twilio ──► your phone rings
```

It reacts to people who:
- join the meeting (`meeting.participant_joined`)
- land in your waiting room (`meeting.participant_joined_waiting_room`)
- wait for you to start the meeting (`meeting.participant_jbh_waiting`)
- join before you, the host (`meeting.participant_jbh_joined`)

Your own join is ignored, and a cooldown (5 minutes by default) stops a group of people from ringing your phone over and over.

---

## A note about UT Zoom accounts

`utexas.zoom.us` is an organization account run by UT's IT team. Zoom webhooks need a **Zoom Marketplace app**, and organization admins can block regular users from making one. So there are two ways to run this:

| | Option A: Webhook (recommended) | Option B: Email fallback |
|---|---|---|
| Needs | Permission to create a Zoom app | Only a Zoom setting and an email inbox |
| Speed | About 1–2 seconds | About 20–60 seconds (email delay) |
| Catches waiting room / admitted joins | Yes | No, only "joined before host" |

Try Option A first. If the Marketplace says you need admin approval, use Option B (or ask UT ITS to approve the app).

---

## 1. Twilio setup (both options)

1. Sign up at <https://www.twilio.com/try-twilio>. A free trial is fine, but trial calls start with a short Twilio message and can only call numbers you have verified.
2. Buy or claim a phone number (Console → Phone Numbers).
3. Note your **Account SID** and **Auth Token** from the console dashboard.
4. On a trial account, verify your own cell number (Console → Verified Caller IDs).

## 2. Configure

```bash
cp .env.example .env    # then fill it in
```

Find your PMI at <https://utexas.zoom.us/profile> ("Personal Meeting ID"), and put it in `ZOOM_PMI` as digits only.

---

## Option A: Zoom webhook

### A1. Deploy the server (it needs a public HTTPS URL)

**Render (free):** push this repo to GitHub, then go to Render → New → Blueprint and pick the repo. `render.yaml` sets everything up, and you enter the env vars in the dashboard. Your URL will look like `https://zoomnotifier-xxxx.onrender.com`.
> Free Render services go to sleep when idle, and waking one can take longer than Zoom's 3-second timeout. To avoid this, use a paid instance, Fly.io or Railway, or ping `/` every 10 minutes with a free uptime monitor such as UptimeRobot.

**Docker anywhere:** `docker build -t zoomnotifier . && docker run --env-file .env -p 8000:8000 zoomnotifier`

**Local testing with ngrok:**
```bash
pip install -r requirements.txt
python -m zoomnotifier.webhook          # listens on :8000
ngrok http 8000                         # gives you https://xxxx.ngrok-free.app
```

Your webhook URL is `https://<your-host>/zoom/webhook`.

### A2. Create the Zoom app

1. Go to <https://marketplace.zoom.us/> and sign in with your UT account (SSO).
2. Click **Develop → Build App**. Choose **General App** (user-managed), or **Webhook Only** if it is offered.
3. **Basic Information:** give it a name. The OAuth redirect URL can be your server's URL.
4. **Features → Access:** copy the **Secret Token** into `ZOOM_WEBHOOK_SECRET_TOKEN` and redeploy/restart.
5. **Event Subscription:** turn it on and add a subscription:
   - Endpoint URL: `https://<your-host>/zoom/webhook`, then click **Validate** (the server answers Zoom's check automatically)
   - Events → **Meeting**: check *Participant/Host joined meeting*, *Participant joined waiting room*, *Participant waiting for host*, and *Participant joined before host*
6. **Scopes:** add the meeting read scope the event picker asks for (e.g. `meeting:read:meeting`).
7. **Local Test → Add App Now** to install it on your own account.

If step 2 or 7 says the app needs admin approval, UT has blocked user-built apps. Switch to Option B.

### A3. Test it

Open your PMI link in a private browser window or on another device where you are not signed in. Your phone should ring within a couple of seconds.

---

## Option B: Email fallback (no Zoom app needed)

1. In <https://utexas.zoom.us/profile/setting>, turn on:
   - **Allow participants to join before host**
   - **Notify host when participants join the meeting before host** (Zoom then emails you)

   If waiting room is on for your PMI, people wait there instead of joining, and Zoom sends no email. In that case you would need to turn the waiting room off for your PMI, which is less secure, so consider a passcode instead.
2. Your UT mailbox (Microsoft 365) does not allow simple IMAP logins. So **forward Zoom emails to a Gmail account**: in Outlook, add a rule *From contains `zoom.us`* → *Forward to you@gmail.com*.
3. In that Gmail account, enable 2-Step Verification and create an **App Password** (<https://myaccount.google.com/apppasswords>).
4. Set `IMAP_USER` and `IMAP_PASSWORD` in `.env`, then run it on any always-on machine (a laptop, Raspberry Pi or small VPS):
   ```bash
   pip install -r requirements.txt
   python -m zoomnotifier.email_watcher
   ```
5. Test it: join your PMI from another device while you are signed out. If nothing happens, look at the subject of Zoom's email and adjust `ZOOM_EMAIL_SUBJECT_PATTERN` (a regex, default `join`).

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
