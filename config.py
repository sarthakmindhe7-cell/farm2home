import os

class Config:
    # Set these as environment variables in your hosting provider.
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-for-local-demo")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "farm2home")
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
