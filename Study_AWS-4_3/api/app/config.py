from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///./local.db"
    log_level: str = "INFO"
    enable_debug_error_endpoint: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
