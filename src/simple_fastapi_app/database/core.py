import psycopg
from psycopg.rows import dict_row

from simple_fastapi_app.config import DATABASE_URL


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)