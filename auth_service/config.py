from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageBackend(StrEnum):
    SQLITE = "sqlite"
    REDIS = "redis"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    pepper: SecretStr = Field(
        ...,
        validation_alias="PEPPER",
        description="Server-side secret for HMAC token hashing",
    )
    admin_user: str = Field(
        ...,
        min_length=1,
        validation_alias="ADMIN_USER",
        description="Admin UI basic-auth username",
    )
    admin_pass: SecretStr = Field(
        ...,
        validation_alias="ADMIN_PASS",
        description="Admin UI basic-auth password",
    )

    storage_backend: StorageBackend = StorageBackend.SQLITE
    sqlite_path: Path = Path("/data/tokens.db")

    redis_host: str = "localhost"
    redis_port: int = Field(6379, ge=1, le=65535)
    redis_db: int = Field(0, ge=0)
    redis_username: str | None = None
    redis_password: str | None = None
    redis_tls: bool = False
    redis_tls_skip_verify: bool = False
    redis_ca_certs: str | None = None
    redis_socket_timeout: float = Field(5.0, gt=0)
    redis_socket_connect_timeout: float = Field(2.0, gt=0)
    redis_max_connections: int = Field(20, ge=1)
    redis_health_check_interval: int = Field(30, ge=1)
    redis_retry_count: int = Field(3, ge=0)
    redis_client_name: str = "wicket"

    token_ttl_seconds: int = Field(0, ge=0)

    auth_failure_window_seconds: int = Field(60, ge=1)
    auth_max_failures: int = Field(10, ge=1)

    @field_validator(
        "redis_username", "redis_password", "redis_ca_certs", mode="before"
    )
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("sqlite_path", mode="before")
    @classmethod
    def _coerce_path(cls, v: object) -> object:
        if isinstance(v, str) and v.strip():
            return Path(v)
        return v

    @model_validator(mode="after")
    def _check_secrets_not_default(self) -> Config:
        if self.pepper.get_secret_value() in ("", "change-me", "change-me-pepper"):
            raise ValueError("PEPPER must not be empty or the example placeholder")
        if self.admin_pass.get_secret_value() in ("", "admin", "change-me"):
            raise ValueError("ADMIN_PASS must not be empty or a trivial default")
        if self.admin_user in ("", "admin", "change-me"):
            raise ValueError("ADMIN_USER must not be empty or a trivial default")
        return self

    @model_validator(mode="after")
    def _check_redis_when_needed(self) -> Config:
        if self.storage_backend is not StorageBackend.REDIS:
            return self
        if not self.redis_host.strip():
            raise ValueError("storage_backend=redis but REDIS_HOST is empty")
        return self

    @model_validator(mode="after")
    def _check_sqlite_parent_is_dir(self) -> Config:
        if self.storage_backend is not StorageBackend.SQLITE:
            return self
        parent = self.sqlite_path.parent
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"SQLITE_PATH parent is not a directory: {parent}")
        return self
