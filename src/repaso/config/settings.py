from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REPASO_", env_file=".env", extra="ignore", case_sensitive=False
    )

    aws_region: str | None = None
    local_mode: bool | None = None
    local_data_dir: Path = Path(".local_data")
    cassette_path: Path | None = None
    record_cassette_path: Path | None = None

    ddb_table: str = "repaso"
    media_bucket: str = ""
    curriculum_bucket: str = ""
    event_bus: str = "repaso"
    scheduler_group: str = "repaso"
    telegram_secret_name: str = "repaso/telegram"
    judge_code_secret_name: str = "repaso/judge"
    invite_codes_secret_name: str = "repaso/pilot-invite-codes"

    guardrail_id: str = ""
    guardrail_version: str = ""

    pilot_invite_codes: str = ""

    holiday_dates: list[date] = []

    cohort_min_families: int = Field(default=3, ge=2)
    grader_confidence_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    escalation_min_samples: int = Field(default=9, ge=1)
    legibility_blur_floor: float = Field(default=300.0, gt=0.0)
    daily_llm_budget_calls: int = Field(default=40, ge=1)
    rework_max_iterations: int = Field(default=2, ge=0)
    item_regen_max_rounds: int = Field(default=2, ge=0)

    live_tests: bool = False

    @field_validator("cassette_path", "record_cassette_path", mode="before")
    @classmethod
    def blank_is_no_cassette(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def derive_local_mode(self) -> "Settings":
        if self.local_mode is None:
            self.local_mode = not bool(self.aws_region)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
