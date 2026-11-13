"""Environment-based configuration; importing this module has no side effects."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, legacy: str = "", default: str = "") -> str:
    return os.getenv(name, os.getenv(legacy, default) if legacy else default)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", default=str(ROOT / "data"))))
    menu_path: Path = field(default_factory=lambda: Path(_env("MENU_PATH", default=str(ROOT / "instruction.json"))))
    static_dir: Path = field(default_factory=lambda: Path(_env("STATIC_DIR", default=str(ROOT / "frontend" / "dist"))))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", "tg_key"))
    admin_token: str = field(default_factory=lambda: _env("ADMIN_TOKEN", "admin_token"))
    admin_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x.strip())
            for x in _env(
                "ADMIN_IDS", default="6178875035,1189846903,5621436121,1644073645,1423155014,8367484968"
            ).split(",")
            if x.strip()
        )
    )
    webapp_url: str = field(default_factory=lambda: _env("WEBAPP_URL", default="https://pastamoalboal.shop"))
    manager_contact: str = field(default_factory=lambda: _env("MANAGER_CONTACT", default="@Philsbrands"))
    redis_url: str = field(
        default_factory=lambda: _env("REDIS_URL", default=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:6379/0")
    )
    deepseek_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY", "deepseek_key"))
    deepseek_model: str = field(default_factory=lambda: _env("DEEPSEEK_MODEL", default="deepseek-chat"))
    qdrant_url: str = field(default_factory=lambda: _env("QDRANT_URL", "qdrant_url", "http://localhost:6333"))
    qdrant_key: str = field(default_factory=lambda: _env("QDRANT_API_KEY", "qdrant_key"))
    qdrant_collection: str = field(default_factory=lambda: _env("QDRANT_COLLECTION", default="pastabar_menu_v2"))
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", default="ai-forever/ru-en-RoSBERTa"))
    model_cache_dir: Path = field(
        default_factory=lambda: Path(_env("MODEL_CACHE_DIR", default=str(ROOT / "model_weights")))
    )
    rag_enabled: bool = field(default_factory=lambda: _env("RAG_ENABLED", default="false").lower() == "true")
    telegram_enabled: bool = field(default_factory=lambda: _env("TELEGRAM_ENABLED", default="false").lower() == "true")

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite+aiosqlite:///{self.data_dir / 'pastabar.db'}"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls()

    def validate(self) -> None:
        if self.telegram_enabled and not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required when TELEGRAM_ENABLED=true")
        if self.telegram_enabled and not self.admin_ids:
            raise ValueError("ADMIN_IDS must contain an order recipient")
        if self.admin_token and len(self.admin_token) < 16:
            raise ValueError("ADMIN_TOKEN must be at least 16 characters")
