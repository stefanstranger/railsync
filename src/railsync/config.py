"""Configuration management for RailSync."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_int(v: str | int) -> int:
    """Coerce string to int for Literal validation."""
    if isinstance(v, str):
        return int(v)
    return v


# Type aliases for integer literals that can be loaded from env vars as strings
Visibility = Annotated[Literal[0, 1, 2, 3], BeforeValidator(_coerce_int)]
BusinessType = Annotated[Literal[0, 1, 2], BeforeValidator(_coerce_int)]


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Settings can be provided via:
    - Environment variables
    - .env file in the current directory
    - .env file in the project root

    Example:
        >>> settings = Settings()
        >>> print(settings.traewelling_client_id)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Träwelling OAuth2 settings
    traewelling_client_id: str = Field(
        ...,
        description="OAuth2 client ID from Träwelling",
    )
    traewelling_client_secret: str = Field(
        ...,
        description="OAuth2 client secret from Träwelling",
    )
    traewelling_redirect_uri: str = Field(
        default="http://localhost:8000/callback",
        description="OAuth2 redirect URI",
    )
    traewelling_api_base: str = Field(
        default="https://traewelling.de/api/v1",
        description="Träwelling API base URL",
    )

    # RailSync settings
    railsync_debug: bool = Field(
        default=False,
        description="Enable debug logging",
    )
    railsync_default_visibility: Visibility = Field(
        default=0,
        description="Default visibility (0=public, 1=unlisted, 2=followers, 3=private)",
    )
    railsync_default_business_type: BusinessType = Field(
        default=0,
        description="Default business type (0=private, 1=business, 2=commute)",
    )

    # File paths
    stations_file: Path = Field(
        default=Path("data/stations.json"),
        description="Path to NS stations JSON file",
    )
    cache_file: Path = Field(
        default=Path("data/station_cache.json"),
        description="Path to station mapping cache file",
    )
    token_file: Path = Field(
        default=Path(".railsync_token"),
        description="Path to store OAuth token",
    )


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Settings instance.

    Raises:
        ValidationError: If required settings are missing.
    """
    return Settings()
