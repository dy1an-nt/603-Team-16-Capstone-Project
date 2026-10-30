"""Database connections.

Queries live in app.repositories, never in routers (NFR-12). In a router:

    from typing import Annotated

    import psycopg
    from fastapi import Depends

    from app.db import get_db
    from app.repositories import ResumeRepository

    @router.get("/{resume_id}")
    def get_resume(resume_id: int, conn: Annotated[psycopg.Connection, Depends(get_db)]):
        resume = ResumeRepository(conn).get(user_id, resume_id)  # user_id from auth
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


def get_db() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one connection per request.

    Commits when the endpoint returns and rolls back when it raises, including
    HTTPException, so a request that fails partway saves nothing.
    """
    with get_conn() as conn:
        yield conn
