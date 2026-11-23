"""PostgreSQL connection pool. Each request gets one connection and one transaction:
it is committed if the request succeeds and rolled back if anything fails."""
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

pool = ConnectionPool(
    config.DATABASE_URL,
    min_size=1,
    max_size=10,
    # client_encoding makes text come back as normal strings even if the database was created as SQL_ASCII
    kwargs={"row_factory": dict_row, "client_encoding": "UTF8"},
    open=False,
)


def open_pool():
    pool.open(wait=True, timeout=15)


def close_pool():
    pool.close()


def get_conn():
    with pool.connection() as conn:
        yield conn
