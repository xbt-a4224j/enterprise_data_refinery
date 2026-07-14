import os

os.environ.setdefault("EDR_DATABASE_URL", "postgresql+psycopg://edr:edr@localhost:5432/edr")
os.environ.setdefault("EDR_LLM_PROVIDER", "fake")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import edr.models  # noqa: F401  register mappers
from edr.db import Base


@pytest.fixture
def db_session():
    eng = create_engine("sqlite://", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False, future=True)
    sess = Session()
    try:
        yield sess
    finally:
        sess.close()
