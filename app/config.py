from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./app.db"
    admins: str = ""
    project_name: str = "meetup_bot"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_ids(self) -> set[int]:
        result: set[int] = set()

        for raw_id in self.admins.split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue

            try:
                result.add(int(raw_id))
            except ValueError:
                pass

        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()