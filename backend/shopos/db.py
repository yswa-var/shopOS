from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from shopos.config import database_url


class Base(DeclarativeBase):
    pass


def make_engine():
    return create_engine(database_url(), pool_pre_ping=True)
