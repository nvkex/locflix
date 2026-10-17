from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCFLIX_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    movies_dir: Path = Path(r"D:\TV\Movies")
    series_dir: Path = Path(r"D:\TV\Series")
    # Bind 0.0.0.0 so other LAN devices can reach this seeder.
    host: str = "0.0.0.0"
    port: int = 8787
    data_dir: Path = Path("./data")
    scan_on_start: bool = True
    # Comma list, or "*" to allow any browser origin (needed for LAN leechers).
    cors_origins: str = "*"
    lan_discovery_port: int = 8788
    # Free key from https://www.themoviedb.org/settings/api
    tmdb_api_key: str = ""
    fetch_posters_on_scan: bool = True
    # Free consumer key: https://www.opensubtitles.com/en/consumers
    opensubtitles_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return raw or ["*"]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "locflix.db"

    @property
    def posters_dir(self) -> Path:
        return self.data_dir / "posters"


@lru_cache
def get_settings() -> Settings:
    return Settings()
