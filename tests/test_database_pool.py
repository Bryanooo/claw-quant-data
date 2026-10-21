import pytest
from psycopg2.pool import PoolError

from service.data_service.database import Database


class FakeConnection:
    def __init__(self):
        self.closed = 0
        self.rollbacks = 0
        self.commits = 0
        self.sessions = []

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def set_session(self, **options):
        self.sessions.append(options)


class FakePool:
    def __init__(self, connection=None, *, exhausted=False):
        self.connection = connection
        self.exhausted = exhausted
        self.returned = []

    def getconn(self):
        if self.exhausted:
            raise PoolError("connection pool exhausted")
        return self.connection

    def putconn(self, connection, close=False):
        self.returned.append((connection, close))


def database_with_pool(pool, *, timeout=0.0):
    database = object.__new__(Database)
    database._pool = pool
    database._acquire_timeout_seconds = timeout
    return database


def test_pool_acquire_timeout_is_bounded():
    database = database_with_pool(FakePool(exhausted=True))

    with pytest.raises(PoolError, match="exhausted"):
        database._acquire()


def test_writable_connection_commits_and_restores_pool():
    connection = FakeConnection()
    pool = FakePool(connection)
    database = database_with_pool(pool)

    with database.writable_connection() as yielded:
        assert yielded is connection

    assert connection.rollbacks == 1
    assert connection.commits == 1
    assert connection.sessions == [{"readonly": False, "autocommit": False}]
    assert pool.returned == [(connection, False)]


def test_writable_connection_rolls_back_on_error():
    connection = FakeConnection()
    pool = FakePool(connection)
    database = database_with_pool(pool)

    with pytest.raises(RuntimeError, match="boom"):
        with database.writable_connection():
            raise RuntimeError("boom")

    assert connection.commits == 0
    assert connection.rollbacks == 2
    assert pool.returned == [(connection, False)]
