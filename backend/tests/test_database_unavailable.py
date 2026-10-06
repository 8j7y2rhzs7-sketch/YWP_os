from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import DEV_JWT_SECRET, settings
from app.services.database_guard import (
    DATABASE_UNAVAILABLE_MESSAGE,
    enforce_production_secrets,
    is_database_unavailable,
    last_prepare_failure,
    sanitize_database_error,
    try_prepare_database,
)


def test_sqlite_programming_errors_are_not_an_outage() -> None:
    missing = OperationalError("SELECT 1", {}, Exception("no such table: users"))
    assert not is_database_unavailable(missing)
    assert not is_database_unavailable(RuntimeError("no such table: users"))


def test_unreachable_host_is_an_outage() -> None:
    exc = OperationalError(
        "SELECT 1",
        {},
        Exception("failed to resolve host 'dpg-secret-host'"),
    )
    assert is_database_unavailable(exc)


def test_sanitize_database_error_strips_credentials() -> None:
    text = sanitize_database_error(
        "could not connect postgresql://ywp:super-secret@db.internal:5432/ywp"
    )
    assert "super-secret" not in text
    assert "postgresql://***@" in text


def test_production_refuses_the_published_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "jwt_secret", DEV_JWT_SECRET)
    with pytest.raises(RuntimeError, match="development default"):
        enforce_production_secrets()


def test_health_stays_up_when_the_database_host_is_gone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self, *args, **kwargs):
        del self, args, kwargs
        raise OperationalError(
            "SELECT 1",
            {},
            Exception("failed to resolve host 'dpg-secret-host'"),
        )

    monkeypatch.setattr(Session, "_execute_internal", boom)
    response = client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert body["message"] == DATABASE_UNAVAILABLE_MESSAGE
    assert body["version"] == "3.3.70"
    assert "dpg-" not in response.text
    assert "super-secret" not in response.text


def test_login_explains_a_database_outage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self, *args, **kwargs):
        del self, args, kwargs
        raise OperationalError(
            "SELECT 1",
            {},
            Exception("failed to resolve host 'dpg-secret-host'"),
        )

    monkeypatch.setattr(Session, "_execute_internal", boom)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@ywp-os.com", "password": "StrongYwp!2026"},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == DATABASE_UNAVAILABLE_MESSAGE
    assert "dpg-" not in response.text


def test_health_reports_a_failed_migration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YWP_DB_BOOT_FAILED", "1")
    response = client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "ok"
    assert "migration" in body["message"].lower()


def test_unreachable_database_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="failed to resolve host 'dpg-example'",
        )

    monkeypatch.setattr("app.services.database_guard.subprocess.run", fake_run)
    assert try_prepare_database() is False
    assert last_prepare_failure() == "unavailable"


def test_prepare_database_seeds_after_a_clean_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(args, **kwargs):
        del kwargs
        seen.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.database_guard.subprocess.run", fake_run)
    assert try_prepare_database() is True
    assert last_prepare_failure() is None
    assert any(cmd[-2:] == ["upgrade", "head"] for cmd in seen)
    assert any(cmd[-2:] == ["-m", "app.seed"] for cmd in seen)


def test_alembic_upgrade_head_on_empty_sqlite(tmp_path) -> None:
    database = tmp_path / "empty.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database}"
    env["YWP_ENV"] = "development"
    env["YWP_JWT_SECRET"] = "test-secret-that-is-longer-than-thirty-two-bytes"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    first = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    second = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert heads.returncode == 0, heads.stderr
    lines = [line for line in heads.stdout.splitlines() if "(head)" in line]
    assert len(lines) == 1
