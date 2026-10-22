"""Runtime settings. Everything comes from the environment (or `.env`), nothing is hard-coded per company."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]  # repository root: apps/api/pulse/core/config.py → ../../../..


class Settings(BaseSettings):
    # Paths do not depend on the working directory: the server may be started from anywhere.
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore")

    crm_mode: Literal["emulator", "live"] = "emulator"
    b24_webhook_url: str = ""

    erp_mode: Literal["emulator", "live"] = "emulator"
    onec_odata_url: str = ""
    onec_user: str = ""
    onec_password: str = ""

    sync_interval_s: int = 180
    admin_key: str = ""

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek/deepseek-chat"
    llm_vision_model: str = "google/gemini-2.5-flash-lite"

    ai_daily_usd: float = 1.5
    ai_visitor_questions: int = 10
    ai_visitor_documents: int = 3

    hermes_api_url: str = ""
    hermes_api_key: str = ""

    telegram_bot_token: str = ""
    public_url: str = "http://127.0.0.1:8010"

    pulse_data_dir: Path = ROOT / "var"
    timezone: str = "Europe/Moscow"

    @property
    def db_path(self) -> Path:
        return self.pulse_data_dir / "pulse.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
