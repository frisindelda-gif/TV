from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fm27si.api import create_app
from fm27si.db import Database
from fm27si.testdata import write_test_career

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db() -> Database:
    return Database("sqlite://")


@pytest.fixture
def session(db):
    with db.sessionmaker() as s:
        yield s


@pytest.fixture
def small_dump_path() -> Path:
    return FIXTURES / "fmss_dump_small.json"


@pytest.fixture
def small_dump(small_dump_path) -> dict:
    return json.loads(small_dump_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def career_dumps(tmp_path_factory) -> list[Path]:
    """Carreira de teste SINTÉTICA: 3 épocas, 400 jogadores iniciais."""
    return write_test_career(tmp_path_factory.mktemp("career"), players=400, seasons=3, seed=27)


@pytest.fixture
def client(db) -> TestClient:
    return TestClient(create_app(db))
