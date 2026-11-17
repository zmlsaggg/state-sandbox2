import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from routers import auth, states, stripe, ai

# Optional first-deployment bootstrap; avoid schema DDL on every cold start.
# Production deployments should run the documented migration command once.
if os.getenv("INIT_DB_ON_STARTUP", "false").lower() == "true":
    from db.database import init_db
    from scripts.init_ai_tables import init_ai_tables

    init_db()
    init_ai_tables()

# ASGI serverless runtimes need not run lifespan hooks. Cache is only an
# optimization local to this instance; no correctness depends on its contents.
FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(states.router)
app.include_router(stripe.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
