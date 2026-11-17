# State Sandbox

> State Sandbox is an experimental game for socioeconomic simulation. It uses Large Language Models to simulate the world and complex policy impacts. fork

[Blog Post](https://blog.sshh.io/p/socioeconomic-modeling-with-reasoning)

<img width="800" alt="chrome_GiI1Dyai3B" src="https://github.com/user-attachments/assets/6f2be284-c10e-4d5f-b3fa-5b62a575c47c" />

## Features

- 🌍 High dimensional game play (people, economy, media, crime, environment, etc).
- 🎯 Make arbitrary policy decisions and see the impact.
- 🌪️ Realistic randomized events and natural disasters.
- 🧠 Player-funded AI through Puter or personal provider keys.
- 🏆 Leaderboard for comparing your nation to others.

## Setup

### Environment Configuration

See `backend/config.py` for the environment variables that are used to configure the app.

### Development

- `cd frontend && npm install && npm run dev`
- `cd backend && pip install -r requirements.txt && python main.py`

### Deployment

Vercel (Next.js + Python serverless functions + external PostgreSQL). See below.

<img width="200" alt="chrome_Uv1nhxJ2po" src="https://github.com/user-attachments/assets/b68be3b1-86d5-4b0c-9f0c-13778b60ede1" />

## Serverless deployment (Vercel)

The application now uses two small projects from this repository. No Docker,
Nginx, Redis, cron worker, or permanently running Python service is required.
Existing `/api/auth`, `/api/states`, streaming responses, and Stripe webhook
paths are preserved. Data stays in external PostgreSQL; this is not a migration
to a new database or a replacement of the game's model logic.

### 1. Python API project

- Import the repository into Vercel with **Root Directory `backend`**.
- Use **Other** framework preset; no frontend build command or output directory.
  `backend/vercel.json` routes `/api/*` to the Python ASGI function.

- Python is pinned by `backend/.python-version` to **3.12**. That file is at the
  root of the API project's configured directory. Vercel's current Python runtime
  documentation lists 3.12 as the default, with 3.13 and 3.14 also supported. If
  this deployment reports 3.14, inspect the actual build log and confirm the API
  project's Root Directory is `backend` and the deployed commit contains this file.
  Redeploy with a cleared build cache after correcting the project configuration;
  do not change dependencies until the resolved interpreter is confirmed.
- Set `DATABASE_URL`, a stable `JWT_SECRET_KEY`, and
  `FRONTEND_URL`. See `backend/.env.example` for all settings.
- Use PostgreSQL with TLS, preferably the provider's transaction pooler (for
  example Supabase port 6543). SQLAlchemy uses `NullPool` so warm instances do
  not each retain a large pool. No Supabase-specific SDK is required.
- For an existing database, retain the URL and **the existing JWT secret** so
  users keep their sessions. Before rollout, add the AI relay/rate-limit tables using the command below.
- For a new database only, initialize tables once from a trusted environment:
  `cd backend && python -c 'from db import models; from db.database import init_db; init_db()'`.
  Do not create tables on each cold start. Export the environment variables first.
- Check `https://YOUR-API.vercel.app/api/health` after deployment.
- Optional: configure Postmark for login emails and Stripe keys/webhook signing
  secret for purchases. Stripe webhook URL remains
  `https://YOUR-API.vercel.app/api/stripe/stripe-hook`.

### 2. Next.js project

- Import the same repository as another Vercel project, **Root Directory
  `frontend`**, Next.js preset, install `npm ci`, build `npm run build`.
- Set **`API_ORIGIN=https://YOUR-API.vercel.app`** before building, without `/api`.
  It is a server-side variable, not a public secret. Redeploy after changing it.
- Leave `NEXT_PUBLIC_API_URL` unset: the browser calls relative `/api/*`, and
  Next.js rewrites requests to Python. This avoids browser localhost URLs and
  cross-origin configuration. If deliberately using a public API origin instead,
  set `CORS_ORIGINS` on the API to the exact frontend origins (comma separated).
- Set backend `FRONTEND_URL` to the frontend's production URL for email links.

### Runtime limits and recovery

The Python function is configured for **300 seconds**. Confirm that your Vercel
plan/runtime supports this limit. Streaming sends heartbeats, but **does not
bypass the platform timeout**. Generation runs inside the request, not in a
background task. The app cancels generation at 280 seconds by default and closes
stream tasks and database sessions. Adjust `STREAM_TIMEOUT_SECONDS` below the
platform limit if changing the function duration.

Turns use an atomic database lock instead of an always-running reset loop.
After an abrupt process termination, a subsequent attempt can reclaim a lock
older than `TURN_LOCK_SECONDS` (default 900 seconds; keep it above the platform
limit). Do not lower this below the maximum invocation duration. The leaderboard
cache is per-instance, best-effort only, and may differ across cold starts.
For simulations that reliably exceed the invocation limit, a durable job queue
and polling/resume protocol are needed; that is not silently emulated here.

### Local development and checks

Environment example files are templates; variables must be exported or supplied
through your environment manager (they are not loaded automatically).

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
# Export DATABASE_URL and JWT_SECRET_KEY first.
(cd backend && ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000)
# In another terminal; /api proxies to the local Python process by default:
cd frontend && npm ci && npm run dev -- --hostname 0.0.0.0
```

Offline API/stream smoke tests (isolated SQLite database, no paid API calls):

```bash
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
API_ORIGIN=https://YOUR-API.vercel.app npm run build --prefix frontend
```

Frontend fonts are bundled from npm, so builds do not require Google Fonts
network access. The lockfile pins Next.js 15.5.29; keep it updated with security
patches rather than relying on a caret alone to update `npm ci` deployments.


## Player-funded AI: Puter + personal keys

The game no longer uses a shared `OPENAI_API_KEY` or owner-funded fallback.
All generation paths (country creation, next year, advice, and their internal
model calls) use a request-local player AI session. Game credits are no longer
checked/deducted for those actions. Existing credit balances and historical
Stripe webhook handling are retained for compatibility, but the purchase UI is
removed. Review/disable old public payment links separately in your Stripe account.

### Required rollout step

After deploying code but **before accepting game traffic**, run against the
existing database from a trusted environment with `DATABASE_URL` and
`JWT_SECRET_KEY` exported:

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/init_ai_tables.py
```

This idempotently creates only `ai_budgets` and `ai_results`, leaving existing
users/states/snapshots unchanged. On PostgreSQL it enables RLS with no public
policies for these internal tables. The backend must connect as table owner or a
trusted BYPASSRLS role. Do not expose database credentials to the browser. For a
fresh DB, initialize the game tables as above first, then run this script too.
No external database was modified by this code change.

### Player setup (Account → Your AI provider)

- **Puter:** explicitly connect your own Puter account, choose an available model,
  then keep the game tab open during generation. `puter.ai.chat` runs in the
  browser; neither the Puter token nor a developer Puter key is sent to Python.
  The SDK is loaded only after clicking Enable Puter SDK on the account settings page, not globally on every page.
- **Personal key:** choose OpenAI, Groq, or OpenRouter and enter your own key and
  a model you can access. Keys are stored only in the current tab's JS memory,
  not in app localStorage/sessionStorage, URLs, or the database. Reloading requires
  entering the key again. Requests send `X-AI-Key` over HTTPS to the trusted game
  API, which calls a fixed allowlisted provider URL. Arbitrary upstream URLs are
  not accepted. No retry/fallback ever spends a developer key.
- Model names are configurable, but capabilities and availability are not
  guaranteed. Use long-context, strong Markdown/structured-output models; small
  models may produce invalid states. Errors do not leak upstream response bodies
  or credentials. Prompts/model output are no longer printed by game actions.
- Puter and providers can require payment, enforce quotas, or change availability.
  This is **not unlimited free AI**. You still pay any hosting/database charges.
  Set spending caps at your provider; this app cannot guarantee provider prices.

### Browser relay and trust boundaries

Python still constructs prompts, orchestrates all game stages, parses model
output, and commits snapshots. For Puter it emits `ai_request` NDJSON events.
The browser runs `puter.ai.chat` and POSTs each result to
`/api/ai/results/{request_id}` using the game login token. This callback must NOT
be blocked by the one-active-action limiter: it completes the already admitted
action. Multiple internal requests can run concurrently, bounded by
`AI_MAX_PARALLEL_CALLS` (default 3). Responses are size-limited, owner-bound,
expiring and single-use. Short-lived result mailboxes contain output only (not
keys or prompts), are deleted on completion/cancellation, and stale mailboxes
are cleaned on subsequent action admission after expiry. PostgreSQL rather than
process-local memory supports callbacks landing on another serverless instance.

**A browser is not a trusted model oracle.** A player can alter their own Puter
result, even though they cannot answer another player's request. Existing parsing
checks are not cryptographic model attestation; the public leaderboard must be
considered casual/unverified, not a cheat-proof competitive ranking. AI flags are
rendered as isolated SVG images rather than injecting untrusted SVG DOM into the
page. Other game output continues through the existing Markdown/state parsers.

The Puter SDK is third-party code with access to the page context; connecting it
is an explicit trust decision. Do not configure infrastructure/APM to record
`X-AI-Key`, authentication headers, or request bodies. The app itself does not
persist personal keys, but infrastructure log redaction remains your responsibility.

Puter's vendor-compatible endpoint is deliberately NOT used with a browser token:
[current upstream controller](https://github.com/HeyPuter/puter/blob/main/src/backend/controllers/puterai/PuterAIController.ts)
requires a delegated API token and paid subscription there; browser accounts use
[the JS chat implementation](https://github.com/HeyPuter/puter/blob/main/src/puter-js/src/modules/ai/chat.js).

### Gameplay-friendly distributed rate limits

Defaults, configured on the API project (see `backend/.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_RATE_ACTIONS` | 12 | Starts per account per fixed window |
| `AI_RATE_WINDOW_SECONDS` | 600 | Ten-minute window |
| `AI_COOLDOWN_SECONDS` | 8 | Minimum interval between starts |
| `AI_ACTION_LEASE_SECONDS` | 330 | One-active-action lease; must exceed platform hard timeout |
| `AI_MAX_PARALLEL_CALLS` | 3 | Internal model-call concurrency within one action |

A whole turn counts as **one** action, not one per AI request. Failed admitted
attempts count too, preventing invalid-key/error spam. Rejections are HTTP 429
with `Retry-After`, surfaced in the UI. The database performs conditional atomic
updates; normal completion releases the active lease, cooldown/window counts
remain, and abrupt termination is recoverable after lease expiry. Keep
`STREAM_TIMEOUT_SECONDS` below the platform timeout and the lease above it.
Callbacks are not charged a second action. Account farming/distributed bots are
not stopped by a per-account limiter; add signup CAPTCHA, edge/IP abuse controls,
and infrastructure budgets before a public launch. No free-hosting guarantee.

The advice endpoint now uses the same streaming transport as other AI actions;
the included client still returns `{ markdown_advice }` to the existing advisor UI.
Custom API consumers must handle NDJSON events and Puter callbacks too.

### Offline validation

```bash
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
npm test --prefix frontend
API_ORIGIN=https://YOUR-API.vercel.app npm run build --prefix frontend
```

Tests mock model calls. Real Puter login/popups, paid providers, production
PostgreSQL concurrency and Vercel streaming must also be smoke-tested after deployment;
no live model call or deployment is implied by the offline suite.

Puter requests already started in the browser may continue at the provider after
a tab closes or the server action is cancelled. The app stops accepting results
and cleans its server tasks, but cannot guarantee cancellation/refunds of the
third-party SDK request. Do not treat a game timeout as a provider spending cap.

New generated states are checked for all game dimensions and the country name
before saving; this rejects obviously incomplete output, but is not a full schema
or semantic validator for every metric. Strong structured-output models are still
recommended. Existing saved data is not rewritten or revalidated by the rollout.

The Account page reads effective limits, remaining starts, and active-action
status from authenticated `GET /api/ai/status` (non-cached, read-only). Use
"Refresh current limits" for a new snapshot; viewing the status never consumes
an action. Invalid limiter configuration fails at startup rather than silently
allowing a short lease or disabling limits. Puter SDK loading times out after
15 seconds and can be retried without reloading the page.

The existing main-branch auto-initialization change is preserved as an opt-in:
`INIT_DB_ON_STARTUP=true` creates missing game tables plus the AI tables/RLS at
import for a first deployment. It requires owner-level DDL privileges and should
be set back to `false` immediately afterwards. Prefer running the explicit
migration once; the default avoids schema DDL on every serverless cold start.
