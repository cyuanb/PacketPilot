from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-flash"
    owner_username: str = "owner"
    owner_password: str = ""
    app_origin: str = "http://localhost:8010"
    data_dir: str = "data"
    cookie_secure: bool = False
    max_file_bytes: int = 20 * 1024 * 1024
    max_pages: int = 100
    model_timeout: int = 60
    ocr_enabled: bool = True
    ocr_min_score: float = 0.85
    ocr_max_pages: int = 30
    parse_timeout: int = 300

    @property
    def storage(self) -> Path:
        return (ROOT / self.data_dir).resolve()


settings = Settings()
