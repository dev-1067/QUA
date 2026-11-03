# RecoverIQ

**One case. One trail. Full visibility.** An AI-powered debt collections platform for banks and NBFCs, built for QUASAR 5.0, problem statement PS-01 (Fintech).

RecoverIQ scores every overdue account with reasons, sends it to the right channel (field visit, tele-call or digital self-cure), lets field agents work offline, marks a case paid only when the payment gateway confirms it, and records every action in a tamper-evident audit trail.

> All borrower data in this prototype is synthetic. Payments run in test mode only; no real money moves.

---

## Run it

Requirements: Python 3.11+ and Node.js 18+ (Node is only needed once, to build the web app).

```bash
python run.py
```

Or double-click `start.bat` on Windows. The launcher installs missing Python packages, builds the web app if needed, seeds a demo portfolio on first start (about 20 s), and prints the URL. If port 8000 is busy it picks the next free port.

| Open | URL |
|---|---|
| Manager console | http://localhost:8000 |
| Field agent app (phone layout) | http://localhost:8000/agent |
| API docs (OpenAPI) | http://localhost:8000/api/docs |

Options: `--port 9000`, `--reset` (wipe and re-seed the demo database), `--rebuild` (rebuild the web app).

### Demo accounts (password `Demo@1234` for all)

| Role | Email |
|---|---|
| Field agent (Mumbai) | agent@recoveriq.in |
| Branch manager (L2, Mumbai) | l2.mumbai@recoveriq.in |
| Regional manager (L1, West) | l1.west@recoveriq.in |
| Executive (HQ) | exec@recoveriq.in |
| Administrator | admin@recoveriq.in |

The login page has one-click buttons for each.

### Using a phone

The launcher also starts an **https** listener for phones (it prints the address, e.g. `https://192.168.1.5:8443/agent`). The sidebar's **Phone QR** button and every payment QR point there. The certificate is self-signed for your laptop, so the phone shows a warning once: tap **Advanced → Proceed**. After that, device GPS check-ins and voice notes work on the phone (browsers only allow them over https). Use `--no-https` to turn it off.

### Public link (optional, you run it)

To share the demo over the internet without deploying, open a second terminal while the server runs and start a free tunnel (no account needed):

```bash
ssh -R 80:localhost:8000 nokey@localhost.run
```

It prints a public `https://….lhr.life` address. Anyone with the link can use the demo accounts, so stop it (Ctrl-C) after judging.

---

## What's built: 18 of 18 essential requirements

| # | Requirement | Where to see it |
|---|---|---|
| 1 | Case intake, one case per account | **Case intake**: upload `Sample CSV` twice, the second upload creates 0 cases |
| 2 | Risk scoring with reasons | Any case: scorecard points + self-cure model with exact attributions |
| 3 | Channel decision | **Rules → Channel decision**: move a threshold, publish, cases re-route |
| 4 | Allocation by pincode + DPD bucket, workload balance | **Allocation**: Allocate / Rebalance; case page: Reassign shows each agent's fit |
| 5 | Agent mobile app | `/agent`: ranked worklist, history, call and visit logs |
| 6 | Visit tracking with GPS + time | Check-in: within 300 m = verified; far / low accuracy / impossible speed = flagged. **Live field map** |
| 7 | Digital nudges, caps, quiet hours | Case page → Digital nudge; **Message outbox** shows every message and every blocked attempt |
| 8 | Payment collection + instant receipt | Create link → UPI QR → borrower pay page → PDF receipt |
| 9 | Paid only after gateway confirmation, no double posting | **Payments**: Replay webhook (duplicate ignored), Forged webhook (401), Reconciliation |
| 10 | Promise-to-pay & escalation | Demo clock +3 days → promises break → field visit, then escalation to L2 |
| 11 | Manager & executive dashboards | **Dashboard**: KPIs, ageing, channel mix, cost per ₹100, live activity |
| 12 | Offline capability | Agent app menu → *Simulate no network* → check in, note, promise → reconnect → synced once |
| 13 | Permissions + masked data | Exec sees `98XXXXX321`; *Reveal* needs a written reason and is audited |
| 14 | Audit & compliance | **Audit trail**: Verify chain; admin can *Simulate insider tampering* → exact row flagged. **Compliance** report |
| 15 | Default classification rule | **Rules → Default classification**: safe expression editor + Test |
| 16 | City & state sentiment | **Sentiment map**: India map → state → cities → borrowers |
| 17 | Borrower notes, typed or voice, multilingual | Agent app → Voice note (Hindi / Marathi / English) |
| 18 | Single shared case record | Open the same case in two windows; changes appear in both over WebSocket |
| + | Learning loop | **Learning loop**: Retrain → shadow comparison → Approve → rollback |
| + | Verified leaderboard | **Leaderboard**: tap an agent to see the payments and visits behind every point |

### Demo clock

Rules read a business clock, not the computer clock. The clock button in the top bar (managers) can jump to 11:00 or 8:30 PM, or forward by days, so quiet hours and broken promises can be shown in seconds. It is labelled *simulated* while shifted, every change is audited, and *Reset to real time* puts it back.

---

## Architecture

```
web/      React 18 + TypeScript + Vite + Tailwind  (manager console, agent PWA, borrower pay page, sandbox checkout)
backend/  FastAPI + SQLAlchemy 2                   (REST API, WebSocket hub, webhook receiver, scheduler)
```

- **One source of truth.** A `cases` row plus append-only `case_events`. Status changes only through the state machine in `backend/app/domain/state_machine.py`; `PAID` and `CLOSED` can only be set by the payment service.
- **Payment truth.** `backend/app/services.py::apply_payment` is the only code that records money. It runs from the HMAC-verified webhook or the reconciliation job. `UNIQUE(gateway_payment_id)` makes replays harmless.
- **Gateway.** With `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` set, links are created through Razorpay Payment Links (test mode). Without keys, a built-in sandbox gateway stands in: it keeps its own ledger and confirms payments only by POSTing a signed webhook to the same endpoint Razorpay would call. The Razorpay path is written to Razorpay's documented API but has not been exercised without real test keys.
- **Offline sync.** The agent app writes every action to an IndexedDB outbox with a client UUID; `POST /api/v1/sync/push` applies each one exactly once (`UNIQUE(client_id)`), each in its own savepoint.
- **Compliance as code.** `backend/app/domain/contact_policy.py` checks the contact window, daily/weekly caps, opt-outs, cured and disputed accounts before any SMS, WhatsApp, email or call.
- **Tamper-evident audit.** `audit_log` rows store `SHA256(prev_hash ‖ row)`; SQLite triggers reject UPDATE and DELETE.
- **Scoring.** Versioned rule scorecard (`domain/scoring.py`) + logistic self-cure model (`domain/ml.py`). For a linear model the SHAP value of a feature equals coefficient × deviation from the mean, so the attributions shown are exact. The model is trained on documented synthetic data plus outcomes recorded in the app.
- **Sentiment.** Offline multilingual lexicon for Hindi and Marathi (Devanagari), English and romanised Hinglish (`domain/sentiment.py`), plus an offline English gist (marked "≈") from a phrase glossary. If `ANTHROPIC_API_KEY` is set, Claude (`claude-haiku-5-5`) gives a full translation and a second opinion; failures fall back to the lexicon.
- **Messaging.** Every message lands in the in-app outbox. With Twilio or SMTP settings, a real copy is also sent, but only to the test recipient you configure, never to the (synthetic) borrower numbers.
- **Security.** JWT access (15 min) + refresh, Argon2id passwords, lockout after 5 failed logins, AES-GCM encryption of borrower name/phone/email/address, PII masked for managers, role + branch/region scoping on every query.

### Configuration (`backend/.env`, all optional)

```
DATABASE_URL=sqlite:///...        # default: backend/data/recoveriq.db
RAZORPAY_KEY_ID=rzp_test_...      # use Razorpay test mode instead of the sandbox gateway
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...       # must match the webhook secret set in the Razorpay dashboard
ANTHROPIC_API_KEY=...             # translation + richer sentiment for notes
DEMO_MODE=1                       # enables the demo clock and the audit tamper demo

# real message delivery (optional); copies go ONLY to these test recipients
DEMO_RECIPIENT_PHONE=+91XXXXXXXXXX  # your own phone, verified in Twilio
DEMO_RECIPIENT_EMAIL=you@example.com
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_SMS_FROM=+1...             # your Twilio number
TWILIO_WHATSAPP_FROM=+14155238886  # Twilio WhatsApp sandbox
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<app password>
SMTP_FROM=you@gmail.com
```

Secrets that are not supplied (JWT secret, PII key, webhook secret) are generated once and stored in `backend/data/`.

---

## Tests

```bash
cd backend && python -m pytest -q                      # 27 tests: domain, API, and Twilio/SMTP/Razorpay against mocked APIs
python backend/tests/smoke_live.py http://localhost:8000   # every endpoint as all 5 roles, fails on any 5xx
python backend/tests/e2e_ui.py http://localhost:8000       # Playwright walk-through, 34 steps, saves docs/screenshots
```

The browser test signs in, opens every screen, presses the main buttons (reveal PII, reassign, nudge, rebalance, forged webhook, tamper and restore, retrain, rule test), then runs the agent app offline and back online, and pays a link as a borrower through the gateway. It fails on any console or page error.

Note: the browser test changes demo data (payments, promises). Run `python run.py --reset` afterwards for a clean demo.

## Known limits (honest list)

- SQLite and an in-process scheduler keep the laptop demo self-contained. For a multi-instance deployment set `DATABASE_URL` to Postgres and move the scheduler to a worker; the code paths are the same.
- Without Twilio/SMTP settings, SMS / WhatsApp / email go only to the in-app **Message outbox**. With them, a copy goes to your test recipient. Sending to real borrowers in India would also need TRAI DLT registration.
- Voice transcription uses the browser's speech recognition (Chrome / Edge). Other browsers record audio and ask for a typed transcript.
- Without an API key, Hindi and Marathi notes get an offline English gist (key phrases), not a full translation.
- Map tiles come from OpenStreetMap and need internet; everything else works offline on the laptop.
- The service worker that lets the agent app reload with no network works on localhost and on a trusted https link; browsers refuse it on the self-signed LAN certificate (the app still works offline once open there).
- The Razorpay and Twilio paths are tested against mocked APIs; they need your own test keys to run against the real services.

See `CREDITS.md` for third-party libraries and data.
