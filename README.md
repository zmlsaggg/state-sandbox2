# State Sandbox

> State Sandbox is an experimental game for socioeconomic simulation. It uses Large Language Models to simulate the world and complex policy impacts. fork

[Blog Post](https://blog.sshh.io/p/socioeconomic-modeling-with-reasoning)

<img width="800" alt="chrome_GiI1Dyai3B" src="https://github.com/user-attachments/assets/6f2be284-c10e-4d5f-b3fa-5b62a575c47c" />

## Features

- 🌍 High dimensional game play (people, economy, media, crime, environment, etc).
- 🎯 Make arbitrary policy decisions and see the impact.
- 🌪️ Realistic randomized events and natural disasters.
- 🧠 Powered by powerful o1 reasoning models.
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
- Set `DATABASE_URL`, a stable `JWT_SECRET_KEY`, `OPENAI_API_KEY`, and
  `FRONTEND_URL`. See `backend/.env.example` for all settings.
- Use PostgreSQL with TLS, preferably the provider's transaction pooler (for
  example Supabase port 6543). SQLAlchemy uses `NullPool` so warm instances do
  not each retain a large pool. No Supabase-specific SDK is required.
- For an existing database, retain the URL and **the existing JWT secret** so
  users keep their sessions. There is no schema change in this migration.
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
# Export DATABASE_URL, JWT_SECRET_KEY and OPENAI_API_KEY first.
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
