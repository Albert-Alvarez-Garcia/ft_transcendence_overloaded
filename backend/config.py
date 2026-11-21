import os


def env(name, default=""):
    return (os.environ.get(name, default) or default).strip().strip('"\'')


JWT_SECRET = env("JWT_SECRET")
SESSION_TTL_HOURS = int(env("SESSION_TTL_HOURS", "24"))
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "https://localhost:8443").rstrip("/")

DB = dict(host=env("DB_HOST", "postgres_db"), port=int(env("DB_PORT", "5432")),
          dbname=env("DB_NAME"), user=env("DB_USER"), password=env("DB_PASSWORD"))

SMTP_HOST = env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
SMTP_FROM = env("SMTP_FROM") or SMTP_USER

FT_ID = env("FORTYTWO_CLIENT_ID")
FT_SECRET = env("FORTYTWO_CLIENT_SECRET")
