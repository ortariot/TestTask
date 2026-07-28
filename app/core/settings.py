from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Coordinate calculation"
    version: str = "0.0.1"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    is_dev: bool = True

    fast_mode_limit: int = 5000

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"  # noqa: S105
    postgres_db: str = "app_db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_dsl: URL | None = None

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_namesapace: str = "0"
    redis_login: str = "default"
    redis_password: str = "pass"  # noqa: S105
    redis_dsl: URL | None = None

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_db: str = "sat"
    clickhouse_user: str = "default"
    clickhouse_password: str = "password"  # noqa: S105

    taskq_timeout: int = 3600

    @model_validator(mode="after")
    def set_dsl(self) -> Any:
        self.db_dsl = URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

        self.redis_dsl = URL.create(
            "redis",
            username=self.redis_login,
            password=self.redis_password,
            host=self.redis_host,
            port=self.redis_port,
            database=self.redis_namesapace,
        )
        return self


settings = ApiConfig()
