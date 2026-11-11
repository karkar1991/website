from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool: ConnectionPool | None = None


def init_pool(url: str, timezone: str = "UTC") -> ConnectionPool:
    global pool
    pool = ConnectionPool(url, min_size=1, max_size=10, open=True,
                          kwargs={"row_factory": dict_row, "options": f"-c timezone={timezone}"})
    return pool


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def get_conn():
    """FastAPI dependency: one connection + transaction per request.
    Commits when the request succeeds, rolls back on any error."""
    assert pool is not None, "database pool not initialised"
    with pool.connection() as conn:
        yield conn
