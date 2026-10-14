"""Runtime settings. Values are read lazily so tests can override them."""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_path: str
    notifications_enabled: bool


def get_settings() -> Settings:
    return Settings(
        database_path=os.environ.get("DATABASE_PATH", "shoplite.db"),
        notifications_enabled=os.getenv("NOTIFICATIONS_ENABLED", "1") == "1",
    )
