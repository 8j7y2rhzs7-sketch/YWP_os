from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YWP OS API"
    app_version: str = "3.1.0"
    api_prefix: str = "/api/v1"
    env: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias="YWP_ENV"
    )
    demo_mode: bool = Field(default=True, validation_alias="YWP_DEMO_MODE")

    jwt_secret: str = Field(
        default="local-development-secret-change-before-production-12345",
        validation_alias="YWP_JWT_SECRET",
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ywp-os"
    jwt_audience: str = "ywp-app"
    access_token_minutes: int = Field(default=30, validation_alias="YWP_ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=30, validation_alias="YWP_REFRESH_TOKEN_DAYS")

    database_url: str = Field(default="sqlite:///./ywp.db", validation_alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    cors_origins_raw: str = Field(
        default="http://localhost:8081,http://localhost:19006,http://localhost:3000,https://whop.com",
        validation_alias="YWP_CORS_ORIGINS",
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    sports_data_api_key: str | None = Field(default=None, validation_alias="SPORTS_DATA_API_KEY")
    odds_api_key: str | None = Field(default=None, validation_alias="ODDS_API_KEY")
    weather_api_key: str | None = Field(default=None, validation_alias="WEATHER_API_KEY")

    whop_api_key: str | None = Field(default=None, validation_alias="WHOP_API_KEY")
    whop_webhook_secret: str | None = Field(default=None, validation_alias="WHOP_WEBHOOK_SECRET")
    whop_company_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WHOP_COMPANY_ID", "NEXT_PUBLIC_WHOP_COMPANY_ID"),
    )
    whop_product_id: str | None = Field(default=None, validation_alias="WHOP_PRODUCT_ID")
    whop_plan_id: str | None = Field(default=None, validation_alias="WHOP_PLAN_ID")
    whop_app_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WHOP_APP_ID", "NEXT_PUBLIC_WHOP_APP_ID"),
    )
    whop_checkout_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("WHOP_CHECKOUT_URL", "NEXT_PUBLIC_WHOP_CHECKOUT_URL"),
    )
    whop_api_version_date: str = Field(
        default="2026-09-02-2", validation_alias="WHOP_API_VERSION_DATE"
    )
    whop_subscription_required: bool = Field(
        default=False, validation_alias="WHOP_SUBSCRIPTION_REQUIRED"
    )

    lock_check_ttl_seconds: int = 300
    odds_warning_move_probability_points: float = 0.03
    odds_blocking_move_probability_points: float = 0.06
    minimum_data_quality: float = 0.65
    minimum_edge: float = 0.015
    model_version: str = "ywp-sports-v3.0.1"
    protocol_version: str = "2026.09.03"
    learning_min_sample_size: int = 30
    learning_min_repeated_pattern: int = 5
    learning_max_weight_delta: float = 0.03
    learning_micro_delta: float = 0.008
    learning_weight_floor: float = 0.02
    learning_weight_ceiling: float = 0.25
    learning_requires_human_approval: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value.encode()) < 32:
            raise ValueError("YWP_JWT_SECRET must be at least 32 bytes")
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://") and "+psycopg" not in value:
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @field_validator(
        "odds_api_key",
        "whop_api_key",
        "whop_webhook_secret",
        "whop_app_id",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def empty_secret_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip().strip('"').strip("'")
            if cleaned in {"", "-", "null", "None"}:
                return None
            return cleaned
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def checkout_url(self) -> str:
        return self.whop_checkout_url or "https://whop.com/checkout/plan_MwJ2qcFxmvqDY"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
