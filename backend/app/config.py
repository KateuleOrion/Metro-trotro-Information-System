"""Settings, read from environment variables (or a .env file)."""
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/metro_trotro")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-to-a-long-random-string")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
DEFAULT_STATION_ID = int(os.getenv("DEFAULT_STATION_ID", "1"))

# Queue positions must stay between 1 and 999 (database rule); we keep the queue compact (1..n).
MAX_QUEUE = 400

# New staff accounts from the registration page wait for a station manager's approval.
# Set STAFF_SIGNUP_NEEDS_APPROVAL=false in .env to let new accounts sign in straight away.
STAFF_SIGNUP_NEEDS_APPROVAL = os.getenv("STAFF_SIGNUP_NEEDS_APPROVAL", "true").strip().lower() not in ("false", "0", "no")

# Login protection: this many wrong passwords for one email within the window locks sign-in briefly.
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 300

# Set APP_ENV=production in .env on the real server. The server then refuses to start with a weak secret.
APP_ENV = os.getenv("APP_ENV", "development").lower()
if JWT_SECRET == "change-this-to-a-long-random-string" or len(JWT_SECRET) < 32:
    if APP_ENV == "production":
        raise RuntimeError(
            "JWT_SECRET is missing, still the default, or shorter than 32 characters. Create one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"  and put it in .env'
        )
    warnings.warn("JWT_SECRET is the default value. Set a long random value in .env before deploying.")
