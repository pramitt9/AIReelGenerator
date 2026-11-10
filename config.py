import os
from dotenv import load_dotenv

load_dotenv()
class Config:
    SECRET_KEY=os.getenv("SECRET_KEY","temporary-dev-key")
    DEBUG=os.getenv("FLASK_DEBUG","False").lower()=="true"

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

    SQLALCHEMY_DATABASE_URI=os.getenv(
        "DATABASE_URL",
        "sqlite:///reelgenerator.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS= False