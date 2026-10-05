import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-deployment-secret")
from .settings import *  # noqa: F403

# PostgreSQL is used by default in the application and in CI.
# SQLite is an explicit fallback for isolated tests on machines without Docker.
if os.environ.get("TEST_POSTGRES") != "true":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
