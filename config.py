import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # SECRET_KEY: must be fixed for sessions to persist
    SECRET_KEY = os.environ.get("SECRET_KEY", "super_secure_random_key_12345")

    # SQLAlchemy DB URI: change username/password/dbname as per your Postgres setup
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:ahati21+@localhost:5432/student_exit_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload folder
    UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max

    # SMTP email (replace with real credentials)
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "your-email@gmail.com")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "your-email-password")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USERNAME)
