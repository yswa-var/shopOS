from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from shopos.config import database_url


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=4)
def _engine(url: str):
    return create_engine(url, pool_pre_ping=True)


def make_engine():
    return _engine(database_url())
