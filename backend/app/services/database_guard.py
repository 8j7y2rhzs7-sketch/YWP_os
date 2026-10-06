"""Tell the truth when Postgres is unreachable, without leaking the connection.

Render suspends an expired free database and stops resolving its host. The
phone should see one plain sentence. Deploy logs can keep the driver error.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from app.core.config import DEV_JWT_SECRET, settings

logger = logging.getLogger(__name__)

DATABASE_UNAVAILABLE_MESSAGE = (
    "YWP OS is up, but the database is unavailable. "
    "Accounts, the sports board, and Markets cannot load until the database is restored. "
    "Try again in a few minutes."
)
MIGRATION_FAILED_MESSAGE = (
    "YWP OS is up, but the latest database migration did not finish. "
    "Check the deploy logs before using the board."
)

_UNAVAILABLE_MARKERS = (
    "could not connect",
    "connection refused",
    "could not translate host",
    "name or service not known",
    "failed to resolve host",
    "name resolution",
    "server closed the connection",
    "timeout expired",
    "connection timed out",
    "the database system is",
    "ssl connection has been closed",
    "remaining connection slots",
    "temporary failure in name resolution",
    "network is unreachable",
    "no route to host",
)

_lock = threading.Lock()
_failure: str | None = None
_recovery_started = False


def enforce_production_secrets() -> None:
    """Stop a production process that is still using the published dev secret."""
    if settings.env != "production":
        return
    if settings.jwt_secret == DEV_JWT_SECRET:
        raise RuntimeError("Refusing to start: YWP_JWT_SECRET is still the development default.")


def is_database_unavailable(exc: BaseException) -> bool:
    """True for a down or unreachable database. False for bad SQL and app bugs.

    Starlette wraps a sync endpoint error in an ExceptionGroup whose cause
    points back at the group. Walk that graph without calling str() on it.
    """
    return _walk_unavailable(exc, set())


def _walk_unavailable(exc: BaseException, seen: set[int]) -> bool:
    if id(exc) in seen:
        return False
    seen.add(id(exc))
    children = getattr(exc, "exceptions", None)
    if children:
        return any(
            isinstance(child, BaseException) and _walk_unavailable(child, seen)
            for child in children
        )
    if _text_is_unavailable(_safe_exception_bits(exc)):
        return True
    orig = getattr(exc, "orig", None)
    if isinstance(orig, BaseException) and _walk_unavailable(orig, seen):
        return True
    if orig is not None and not isinstance(orig, BaseException) and _text_is_unavailable(str(orig)):
        return True
    cause = exc.__cause__ or exc.__context__
    return isinstance(cause, BaseException) and _walk_unavailable(cause, seen)


def _safe_exception_bits(exc: BaseException) -> str:
    """Type name plus string arguments. Avoids Exception.__str__ cycles."""
    bits = [type(exc).__name__]
    for arg in exc.args:
        if isinstance(arg, str):
            bits.append(arg)
    return " ".join(bits)


def _text_is_unavailable(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _UNAVAILABLE_MARKERS)


def sanitize_database_error(text: str) -> str:
    """Drop credentials before a driver error is written to a log line."""
    cleaned = re.sub(r"://[^@\s/]+@", "://***@", text)
    return cleaned[:500]


def last_prepare_failure() -> str | None:
    return _failure


def backend_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "alembic.ini").is_file():
        return cwd
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "alembic.ini").is_file():
        return candidate
    return cwd


def try_prepare_database() -> bool:
    """Apply migrations and the production identity step.

    Returns True when both finished. A missing database is retryable. A
    migration that fails for any other reason is recorded and not retried.
    """
    global _failure
    root = backend_root()
    env = os.environ.copy()
    env.setdefault("PGCONNECT_TIMEOUT", "8")
    migrate = _run([sys.executable, "-m", "alembic", "upgrade", "head"], root, env)
    if migrate.returncode != 0:
        output = f"{migrate.stdout}\n{migrate.stderr}"
        logger.warning(
            "database migration failed: %s",
            sanitize_database_error(output),
        )
        with _lock:
            _failure = "unavailable" if _text_is_unavailable(output) else "migration"
        return False
    seed = _run([sys.executable, "-m", "app.seed"], root, env)
    if seed.returncode != 0:
        output = f"{seed.stdout}\n{seed.stderr}"
        logger.warning("database seed failed: %s", sanitize_database_error(output))
        with _lock:
            _failure = "unavailable" if _text_is_unavailable(output) else "migration"
        return False
    with _lock:
        _failure = None
    return True


def _run(args: list[str], root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def start_database_recovery() -> None:
    """Keep trying migrations after a boot where Postgres was still down."""
    global _recovery_started
    if settings.env == "test":
        return
    with _lock:
        if _recovery_started:
            return
        _recovery_started = True
    threading.Thread(target=_recover, name="ywp-db-recovery", daemon=True).start()


def _recover() -> None:
    import time

    while True:
        if try_prepare_database():
            logger.info("Database migrations are applied.")
            return
        if last_prepare_failure() != "unavailable":
            logger.error("Database migration failed and will not be retried automatically.")
            return
        time.sleep(30)
