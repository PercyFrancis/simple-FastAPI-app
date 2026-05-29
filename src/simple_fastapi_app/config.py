import os


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db",
)