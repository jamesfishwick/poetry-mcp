"""Configuration management for Poetry MCP.

Handles loading and validation of configuration from environment variables
and default paths.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class VaultConfig(BaseModel):
    """Vault configuration with path validation."""

    path: Path = Field(
        ...,
        description="Absolute path to Poetry vault root"
    )

    catalog_dir: str = Field(
        default="catalog",
        description="Catalog subdirectory name"
    )

    nexus_dir: str = Field(
        default="nexus",
        description="Nexus subdirectory name"
    )

    qualities_dir: str = Field(
        default="Qualities",
        description="Qualities subdirectory name"
    )

    venues_dir: str = Field(
        default="venues",
        description="Venues subdirectory name"
    )

    influences_dir: str = Field(
        default="influences",
        description="Influences subdirectory name"
    )

    @field_validator('path')
    @classmethod
    def validate_vault_path(cls, v: Path) -> Path:
        """Validate vault path exists and is a directory."""
        v = Path(v).expanduser().resolve()

        if not v.exists():
            raise ValueError(f"Vault path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Vault path is not a directory: {v}")

        return v


class PoetryMCPConfig(BaseModel):
    """Complete Poetry MCP configuration."""

    vault: VaultConfig

    # Search settings
    search_default_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Default result limit for search queries"
    )

    search_case_sensitive: bool = Field(
        default=False,
        description="Whether text search is case-sensitive"
    )


def load_config() -> PoetryMCPConfig:
    """
    Load configuration from environment variables.

    Environment variables:
    - POETRY_VAULT_PATH: Path to Poetry vault (required)

    Returns:
        PoetryMCPConfig instance

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    # Get vault path from environment
    vault_path = os.getenv('POETRY_VAULT_PATH')

    if not vault_path:
        # Default to common Poetry vault location
        default_path = Path.home() / ".local/share/obsidian/art/Poetry"
        if default_path.exists():
            vault_path = str(default_path)
        else:
            raise ValueError(
                "POETRY_VAULT_PATH environment variable not set. "
                "Please set it to your Poetry vault location."
            )

    # Build configuration
    config = PoetryMCPConfig(
        vault=VaultConfig(path=vault_path)
    )

    return config


def get_config() -> PoetryMCPConfig:
    """
    Get cached configuration instance.

    Returns:
        PoetryMCPConfig instance
    """
    # For now, just load fresh each time
    # Could add caching later if needed
    return load_config()
