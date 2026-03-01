"""Configuration management for Poetry MCP.

Handles loading and validation of configuration from YAML files,
environment variables, and interactive setup.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Literal
import yaml
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


class VaultConfig(BaseModel):
    """Vault configuration with path validation."""

    path: Path = Field(..., description="Absolute path to Poetry vault root")

    catalog_dir: str = Field(default="catalog", description="Catalog subdirectory name")

    nexus_dir: str = Field(default="nexus", description="Nexus subdirectory name")

    qualities_dir: str = Field(default="Qualities", description="Qualities subdirectory name")

    venues_dir: str = Field(default="venues", description="Venues subdirectory name")

    submissions_dir: str = Field(default="submissions", description="Submissions subdirectory name")

    influences_dir: str = Field(default="influences", description="Influences subdirectory name")

    exclude_catalog_dirs: list[str] = Field(
        default_factory=list,
        description="Catalog subdirectories to exclude from scanning (e.g., ['drafts', 'archive'])",
    )

    custom_states: list[str] = Field(
        default_factory=list,
        description="Additional custom states beyond the standard ones (e.g., ['phone_poetry'])",
    )

    @field_validator("path")
    @classmethod
    def validate_vault_path(cls, v: Path) -> Path:
        """Validate vault path exists and is a directory."""
        v = Path(v).expanduser().resolve()

        if not v.exists():
            raise ValueError(f"Vault path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Vault path is not a directory: {v}")

        return v


class SearchConfig(BaseModel):
    """Search behavior configuration."""

    default_limit: int = Field(
        default=50, ge=1, le=100, description="Default result limit for search queries"
    )

    case_sensitive: bool = Field(default=False, description="Whether text search is case-sensitive")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Log level"
    )

    file: Optional[Path] = Field(default=None, description="Log file path (None = console only)")

    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )


class PerformanceConfig(BaseModel):
    """Performance tuning configuration."""

    watch_files: bool = Field(
        default=False, description="Enable file watching for auto-reload (requires watchdog)"
    )

    watch_debounce_seconds: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Debounce time for file watching"
    )

    cache_expiry_seconds: int = Field(
        default=3600, ge=60, le=86400, description="Cache expiry time in seconds"
    )


class PoetryMCPConfig(BaseModel):
    """Complete Poetry MCP configuration."""

    vault: VaultConfig
    search: SearchConfig = Field(default_factory=SearchConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)


def find_config_file() -> Optional[Path]:
    """
    Find configuration file in standard locations.

    Search order:
    1. $POETRY_MCP_CONFIG environment variable
    2. ~/.config/poetry-mcp/config.yaml
    3. ~/.poetry-mcp/config.yaml

    Returns:
        Path to config file if found, None otherwise
    """
    # Check environment variable
    env_config = os.getenv("POETRY_MCP_CONFIG")
    if env_config:
        config_path = Path(env_config).expanduser().resolve()
        if config_path.exists():
            logger.debug(f"Found config from POETRY_MCP_CONFIG: {config_path}")
            return config_path
        else:
            logger.warning(f"POETRY_MCP_CONFIG points to non-existent file: {config_path}")

    # Check XDG config directory
    xdg_config = Path.home() / ".config" / "poetry-mcp" / "config.yaml"
    if xdg_config.exists():
        logger.debug(f"Found config at XDG location: {xdg_config}")
        return xdg_config

    # Check home directory
    home_config = Path.home() / ".poetry-mcp" / "config.yaml"
    if home_config.exists():
        logger.debug(f"Found config in home directory: {home_config}")
        return home_config

    logger.debug("No config file found in standard locations")
    return None


def load_config_from_file(config_path: Path) -> PoetryMCPConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml file

    Returns:
        PoetryMCPConfig instance

    Raises:
        ValueError: If config file is invalid
    """
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Config file is empty: {config_path}")

        # Build config from YAML data
        config = PoetryMCPConfig(**data)
        logger.info(f"Loaded config from {config_path}")
        return config

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load config from {config_path}: {e}")


def prompt_for_vault_path() -> Path:
    """
    Interactively prompt user for vault path.

    Returns:
        Validated vault path

    Raises:
        ValueError: If user provides invalid path
    """
    print("\n=== Poetry MCP Setup ===")
    print("No configuration found. Let's set up your Poetry vault path.\n")

    # Try to detect common locations
    common_locations = [
        Path.home() / ".local/share/obsidian/art/Poetry",
        Path.home() / "Documents" / "Obsidian" / "Poetry",
        Path.home() / "Obsidian" / "Poetry",
    ]

    detected = [p for p in common_locations if p.exists()]

    if detected:
        print("Detected possible vault locations:")
        for i, path in enumerate(detected, 1):
            print(f"  {i}. {path}")
        print(f"  {len(detected) + 1}. Enter custom path")
        print()

        while True:
            choice = input(f"Select option (1-{len(detected) + 1}): ").strip()
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(detected):
                    return detected[choice_num - 1]
                elif choice_num == len(detected) + 1:
                    break
                else:
                    print(f"Invalid choice. Please enter 1-{len(detected) + 1}")
            except ValueError:
                print("Invalid input. Please enter a number.")

    # Custom path entry
    while True:
        path_str = input("Enter path to your Poetry vault: ").strip()
        if not path_str:
            print("Path cannot be empty")
            continue

        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            print(f"Path does not exist: {path}")
            retry = input("Try again? (y/n): ").strip().lower()
            if retry != "y":
                raise ValueError("Setup cancelled by user")
            continue

        if not path.is_dir():
            print(f"Path is not a directory: {path}")
            continue

        # Check if it looks like a Poetry vault
        catalog_dir = path / "catalog"
        if not catalog_dir.exists():
            print(f"\nWarning: {path} does not contain a 'catalog' subdirectory.")
            print("This may not be a Poetry vault.")
            confirm = input("Use this path anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue

        return path


def create_default_config(vault_path: Path, config_path: Optional[Path] = None) -> Path:
    """
    Create default configuration file.

    Args:
        vault_path: Path to Poetry vault
        config_path: Where to save config (default: ~/.config/poetry-mcp/config.yaml)

    Returns:
        Path to created config file
    """
    if config_path is None:
        config_path = Path.home() / ".config" / "poetry-mcp" / "config.yaml"

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Build default config
    config_data = {
        "vault": {
            "path": str(vault_path),
            "catalog_dir": "catalog",
            "nexus_dir": "nexus",
            "qualities_dir": "Qualities",
            "venues_dir": "venues",
            "influences_dir": "influences",
            "exclude_catalog_dirs": [],
            "custom_states": [],
        },
        "search": {"default_limit": 20, "case_sensitive": False},
        "logging": {
            "level": "INFO",
            "file": None,
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "performance": {
            "watch_files": False,
            "watch_debounce_seconds": 2.0,
            "cache_expiry_seconds": 3600,
        },
    }

    # Write YAML file
    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Created default config at {config_path}")
    return config_path


def save_config(config: PoetryMCPConfig, config_path: Optional[Path] = None) -> Path:
    """
    Save configuration to YAML file.

    Args:
        config: Configuration to save
        config_path: Where to save (default: ~/.config/poetry-mcp/config.yaml)

    Returns:
        Path to saved config file
    """
    if config_path is None:
        config_path = Path.home() / ".config" / "poetry-mcp" / "config.yaml"

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict for YAML serialization
    config_dict = {
        "vault": {
            "path": str(config.vault.path),
            "catalog_dir": config.vault.catalog_dir,
            "nexus_dir": config.vault.nexus_dir,
            "qualities_dir": config.vault.qualities_dir,
            "venues_dir": config.vault.venues_dir,
            "influences_dir": config.vault.influences_dir,
            "exclude_catalog_dirs": config.vault.exclude_catalog_dirs,
            "custom_states": config.vault.custom_states,
        },
        "search": {
            "default_limit": config.search.default_limit,
            "case_sensitive": config.search.case_sensitive,
        },
        "logging": {
            "level": config.logging.level,
            "file": str(config.logging.file) if config.logging.file else None,
            "format": config.logging.format,
        },
        "performance": {
            "watch_files": config.performance.watch_files,
            "watch_debounce_seconds": config.performance.watch_debounce_seconds,
            "cache_expiry_seconds": config.performance.cache_expiry_seconds,
        },
    }

    # Write YAML file
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved config to {config_path}")
    return config_path


def load_config() -> PoetryMCPConfig:
    """
    Load configuration from multiple sources with fallback.

    Priority order:
    1. Config file (YAML)
    2. Environment variables (POETRY_VAULT_PATH)
    3. Interactive setup (if no config found)

    Returns:
        PoetryMCPConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    # Try loading from config file
    config_file = find_config_file()
    if config_file:
        try:
            return load_config_from_file(config_file)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            # Fall through to other methods

    # Try environment variable
    vault_path_env = os.getenv("POETRY_VAULT_PATH")
    if vault_path_env:
        vault_path = Path(vault_path_env).expanduser().resolve()
        logger.info(f"Using vault from POETRY_VAULT_PATH: {vault_path}")
        return PoetryMCPConfig(vault=VaultConfig(path=vault_path))

    # Try default location
    default_vault = Path.home() / ".local/share/obsidian/art/Poetry"
    if default_vault.exists():
        logger.info(f"Using default vault location: {default_vault}")
        return PoetryMCPConfig(vault=VaultConfig(path=default_vault))

    # Interactive setup (only in TTY)
    if sys.stdin.isatty():
        try:
            vault_path = prompt_for_vault_path()
            config_path = create_default_config(vault_path)
            print(f"\nConfiguration saved to: {config_path}")
            print("You can edit this file to customize settings.\n")
            return load_config_from_file(config_path)
        except Exception as e:
            raise ValueError(f"Setup failed: {e}")

    # No config found and not interactive
    raise ValueError(
        "No configuration found. Please either:\n"
        "  1. Set POETRY_VAULT_PATH environment variable\n"
        "  2. Create config file at ~/.config/poetry-mcp/config.yaml\n"
        "  3. Run interactively for setup wizard"
    )


# Cached config instance
_config_cache: Optional[PoetryMCPConfig] = None


def get_config(force_reload: bool = False) -> PoetryMCPConfig:
    """
    Get cached configuration instance.

    Args:
        force_reload: Force reload from disk

    Returns:
        PoetryMCPConfig instance
    """
    global _config_cache

    if force_reload or _config_cache is None:
        _config_cache = load_config()

    return _config_cache
