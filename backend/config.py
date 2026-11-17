import os


def _int_env(key, default: int = 0):
    return int(os.getenv(key, str(default)))


# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Serverless instances must share a stable signing key and external database.
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
TURN_LOCK_SECONDS = _int_env("TURN_LOCK_SECONDS", 900)

JWT_EXPIRATION_DAYS = _int_env(
    "JWT_EXPIRATION_DAYS", 10_000
)  # We don't have a sign back in feature

# Cache configuration
CACHE_TTL_STATES_LEADERBOARD = _int_env("CACHE_TTL_STATES_LEADERBOARD", 60 * 60 * 6)

# Misc configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://state.sshh.io")

# Credits config
CREDITS_DEFAULT = _int_env("CREDITS_DEFAULT", 10)

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Email configuration
POSTMARK_API_KEY = os.environ.get("POSTMARK_API_KEY")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "no-reply@state.sshh.io")
EMAIL_LOGIN_JWT_EXPIRATION_DAYS = _int_env("EMAIL_LOGIN_JWT_EXPIRATION_DAYS", 1)
