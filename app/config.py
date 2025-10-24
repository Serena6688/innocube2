import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///innocube.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 64 * 1024 * 1024))