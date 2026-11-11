import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    TestingSession = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture(autouse=True)
def enable_legacy_status_for_existing_tests(monkeypatch):
    """
    兼容早期状态机测试。
    正式服务默认关闭旧状态写接口。
    """
    monkeypatch.setenv(
        "TICKETFLOW_LEGACY_STATUS_WRITES", "1"
    )
