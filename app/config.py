from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Task Manager API"
    debug: bool = False

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/taskmanager"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Artificial delay/errors for load testing
    simulate_delay_ms: int = 0
    simulate_error_rate: float = 0.0  # 0.0 to 1.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
