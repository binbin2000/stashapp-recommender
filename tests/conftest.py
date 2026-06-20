from __future__ import annotations

import pytest

from stashai.core.database import Base, make_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def session(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    engine = make_engine(db_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()

