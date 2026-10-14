"""Database access.

Use parameterized queries only (NFR-12). Example:

    with get_conn() as conn:
        conn.execute("SELECT id FROM users WHERE email = %s", (email,))
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        yield conn
