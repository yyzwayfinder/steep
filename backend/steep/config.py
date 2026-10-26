"""Runtime settings, read from environment variables once at startup."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    data_dir: Path
    password: str | None
    secret_key: str
    trust_proxy_header: str | None
    fetch_concurrency: int
    default_refresh_minutes: int
    min_refresh_minutes: int
    fetch_timeout: int
    static_dir: Path | None
    pushover_user: str | None
    pushover_token: str | None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "steep.db"


def _load_secret(data_dir: Path) -> str:
    """Use STEEP_SECRET_KEY, else a random key persisted under the data dir."""
    env = os.environ.get("STEEP_SECRET_KEY")
    if env:
        return env
    path = data_dir / ".secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    path.chmod(0o600)
    return key


def _load_password(data_dir: Path) -> str:
    """Use STEEP_PASSWORD, else generate one on first run and save it for the user."""
    env = os.environ.get("STEEP_PASSWORD")
    if env:
        return env
    path = data_dir / "initial_password.txt"
    if path.exists():
        return path.read_text().strip()
    pw = secrets.token_urlsafe(12)
    path.write_text(pw + "\n")
    path.chmod(0o600)
    return pw


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("STEEP_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    static = os.environ.get("STEEP_STATIC_DIR")
    return Settings(
        data_dir=data_dir,
        password=_load_password(data_dir),
        secret_key=_load_secret(data_dir),
        trust_proxy_header=os.environ.get("STEEP_TRUST_PROXY_HEADER") or None,
        fetch_concurrency=max(1, _int("FETCH_CONCURRENCY", 8)),
        default_refresh_minutes=max(5, _int("STEEP_REFRESH_MINUTES", 30)),
        min_refresh_minutes=5,
        fetch_timeout=_int("STEEP_FETCH_TIMEOUT", 20),
        static_dir=Path(static) if static else None,
        pushover_user=os.environ.get("PUSHOVER_USER") or None,
        pushover_token=os.environ.get("PUSHOVER_TOKEN") or None,
    )


settings: Settings | None = None


def get_settings() -> Settings:
    global settings
    if settings is None:
        settings = load_settings()
    return settings
