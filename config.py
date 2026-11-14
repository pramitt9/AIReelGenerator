import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    ENV = os.getenv("FLASK_ENV", "development").strip().lower()
    DEBUG = os.getenv("FLASK_DEBUG", "False").strip().lower() == "true"

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if ENV == "production":
            raise RuntimeError(
                "SECRET_KEY must be set in the environment when FLASK_ENV=production."
            )
        SECRET_KEY = "temporary-dev-key"

    # API credentials are optional at startup so the app can run without
    # every external integration configured.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///reelgenerator.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Safer defaults for session cookies. Secure cookies are enabled in
    # production and require HTTPS there.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENV == "production"
