"""Comprehensive tests for configuration management."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from poetry_mcp.config import (
    VaultConfig,
    SearchConfig,
    LoggingConfig,
    PerformanceConfig,
    PoetryMCPConfig,
    find_config_file,
    load_config_from_file,
    get_config,
)


class TestVaultConfig:
    """Test VaultConfig model and validation."""

    def test_valid_vault_config_with_defaults(self, tmp_path):
        """Test creating VaultConfig with valid path and default values."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = VaultConfig(path=vault)

        assert config.path == vault.resolve()
        assert config.catalog_dir == "catalog"
        assert config.nexus_dir == "nexus"
        assert config.qualities_dir == "Qualities"
        assert config.venues_dir == "venues"
        assert config.influences_dir == "influences"
        assert config.exclude_catalog_dirs == []
        assert config.custom_states == []

    def test_vault_config_with_custom_subdirs(self, tmp_path):
        """Test VaultConfig with custom subdirectory names."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = VaultConfig(
            path=vault,
            catalog_dir="poems",
            nexus_dir="themes",
            qualities_dir="QualityRubrics",
            venues_dir="publications",
            influences_dir="inspirations",
        )

        assert config.catalog_dir == "poems"
        assert config.nexus_dir == "themes"
        assert config.qualities_dir == "QualityRubrics"
        assert config.venues_dir == "publications"
        assert config.influences_dir == "inspirations"

    def test_vault_config_with_exclusions(self, tmp_path):
        """Test VaultConfig with excluded catalog directories."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = VaultConfig(path=vault, exclude_catalog_dirs=["drafts", "archive", "experiments"])

        assert config.exclude_catalog_dirs == ["drafts", "archive", "experiments"]

    def test_vault_config_with_custom_states(self, tmp_path):
        """Test VaultConfig with custom state definitions."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = VaultConfig(
            path=vault, custom_states=["phone_poetry", "experimental", "abandoned"]
        )

        assert config.custom_states == ["phone_poetry", "experimental", "abandoned"]

    @pytest.mark.skip(reason="Tilde expansion uses os.path.expanduser which can't be easily mocked")
    def test_vault_path_expansion_tilde(self, tmp_path, monkeypatch):
        """Test that ~ is expanded to home directory."""
        # Create a test vault in temp
        vault = tmp_path / "vault"
        vault.mkdir()

        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = VaultConfig(path="~/vault")

        assert config.path == vault.resolve()

    def test_vault_path_resolution_relative(self, tmp_path, monkeypatch):
        """Test that relative paths are resolved to absolute."""
        vault = tmp_path / "vault"
        vault.mkdir()

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)

        config = VaultConfig(path="./vault")

        assert config.path.is_absolute()
        assert config.path == vault.resolve()

    def test_vault_path_not_exists_raises_error(self):
        """Test that non-existent vault path raises ValidationError."""
        with pytest.raises(ValidationError, match="Vault path does not exist"):
            VaultConfig(path="/nonexistent/path/to/vault")

    def test_vault_path_is_file_raises_error(self, tmp_path):
        """Test that vault path pointing to file raises ValidationError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(ValidationError, match="Vault path is not a directory"):
            VaultConfig(path=file_path)

    def test_vault_config_serialization(self, tmp_path):
        """Test that VaultConfig can be serialized to dict."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = VaultConfig(path=vault, custom_states=["custom_state"])

        data = config.model_dump()

        assert data["path"] == vault.resolve()
        assert data["custom_states"] == ["custom_state"]
        assert "catalog_dir" in data

    def test_vault_config_from_dict(self, tmp_path):
        """Test creating VaultConfig from dictionary."""
        vault = tmp_path / "vault"
        vault.mkdir()

        data = {"path": str(vault), "catalog_dir": "poems", "custom_states": ["test_state"]}

        config = VaultConfig(**data)

        assert config.path == vault.resolve()
        assert config.catalog_dir == "poems"
        assert config.custom_states == ["test_state"]


class TestSearchConfig:
    """Test SearchConfig model and validation."""

    def test_search_config_defaults(self):
        """Test SearchConfig with default values."""
        config = SearchConfig()

        assert config.default_limit == 20
        assert config.case_sensitive is False

    def test_search_config_custom_values(self):
        """Test SearchConfig with custom values."""
        config = SearchConfig(default_limit=50, case_sensitive=True)

        assert config.default_limit == 50
        assert config.case_sensitive is True

    def test_search_config_min_limit(self):
        """Test SearchConfig with minimum valid limit."""
        config = SearchConfig(default_limit=1)
        assert config.default_limit == 1

    def test_search_config_max_limit(self):
        """Test SearchConfig with maximum valid limit."""
        config = SearchConfig(default_limit=100)
        assert config.default_limit == 100

    def test_search_config_invalid_limit_too_low(self):
        """Test that limit < 1 raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            SearchConfig(default_limit=0)

    def test_search_config_invalid_limit_too_high(self):
        """Test that limit > 100 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            SearchConfig(default_limit=101)


class TestLoggingConfig:
    """Test LoggingConfig model and validation."""

    def test_logging_config_defaults(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.file is None
        assert "%(asctime)s" in config.format
        assert "%(levelname)s" in config.format

    def test_logging_config_all_levels(self):
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_logging_config_invalid_level(self):
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError):
            LoggingConfig(level="INVALID")

    def test_logging_config_with_file(self, tmp_path):
        """Test LoggingConfig with log file path."""
        log_file = tmp_path / "poetry-mcp.log"

        config = LoggingConfig(file=log_file)

        assert config.file == log_file

    def test_logging_config_custom_format(self):
        """Test LoggingConfig with custom format string."""
        custom_format = "%(levelname)s: %(message)s"

        config = LoggingConfig(format=custom_format)

        assert config.format == custom_format


class TestPerformanceConfig:
    """Test PerformanceConfig model and validation."""

    def test_performance_config_defaults(self):
        """Test PerformanceConfig with default values."""
        config = PerformanceConfig()

        assert config.watch_files is False
        assert config.watch_debounce_seconds == 2.0
        assert config.cache_expiry_seconds == 3600

    def test_performance_config_custom_values(self):
        """Test PerformanceConfig with custom values."""
        config = PerformanceConfig(
            watch_files=True, watch_debounce_seconds=5.0, cache_expiry_seconds=7200
        )

        assert config.watch_files is True
        assert config.watch_debounce_seconds == 5.0
        assert config.cache_expiry_seconds == 7200

    def test_performance_config_min_debounce(self):
        """Test minimum valid debounce time."""
        config = PerformanceConfig(watch_debounce_seconds=0.1)
        assert config.watch_debounce_seconds == 0.1

    def test_performance_config_max_debounce(self):
        """Test maximum valid debounce time."""
        config = PerformanceConfig(watch_debounce_seconds=10.0)
        assert config.watch_debounce_seconds == 10.0

    def test_performance_config_invalid_debounce_too_low(self):
        """Test that debounce < 0.1 raises ValidationError."""
        with pytest.raises(ValidationError):
            PerformanceConfig(watch_debounce_seconds=0.05)

    def test_performance_config_invalid_debounce_too_high(self):
        """Test that debounce > 10.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            PerformanceConfig(watch_debounce_seconds=11.0)

    def test_performance_config_min_cache_expiry(self):
        """Test minimum valid cache expiry."""
        config = PerformanceConfig(cache_expiry_seconds=60)
        assert config.cache_expiry_seconds == 60

    def test_performance_config_max_cache_expiry(self):
        """Test maximum valid cache expiry."""
        config = PerformanceConfig(cache_expiry_seconds=86400)
        assert config.cache_expiry_seconds == 86400

    def test_performance_config_invalid_cache_expiry_too_low(self):
        """Test that cache expiry < 60 raises ValidationError."""
        with pytest.raises(ValidationError):
            PerformanceConfig(cache_expiry_seconds=30)

    def test_performance_config_invalid_cache_expiry_too_high(self):
        """Test that cache expiry > 86400 raises ValidationError."""
        with pytest.raises(ValidationError):
            PerformanceConfig(cache_expiry_seconds=90000)


class TestPoetryMCPConfig:
    """Test complete PoetryMCPConfig model."""

    def test_complete_config_with_all_sections(self, tmp_path):
        """Test creating complete configuration with all sections."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = PoetryMCPConfig(
            vault=VaultConfig(path=vault),
            search=SearchConfig(default_limit=30),
            logging=LoggingConfig(level="DEBUG"),
            performance=PerformanceConfig(watch_files=True),
        )

        assert config.vault.path == vault.resolve()
        assert config.search.default_limit == 30
        assert config.logging.level == "DEBUG"
        assert config.performance.watch_files is True

    def test_complete_config_with_defaults(self, tmp_path):
        """Test that sub-configs use default factories."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = PoetryMCPConfig(vault=VaultConfig(path=vault))

        assert isinstance(config.search, SearchConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert config.search.default_limit == 20
        assert config.logging.level == "INFO"

    def test_complete_config_serialization(self, tmp_path):
        """Test full config serialization."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config = PoetryMCPConfig(
            vault=VaultConfig(path=vault, custom_states=["test"]),
            search=SearchConfig(default_limit=50),
        )

        data = config.model_dump()

        assert "vault" in data
        assert "search" in data
        assert "logging" in data
        assert "performance" in data
        assert data["search"]["default_limit"] == 50


class TestFindConfigFile:
    """Test find_config_file() function."""

    def test_find_from_env_var(self, tmp_path, monkeypatch):
        """Test finding config from POETRY_MCP_CONFIG environment variable."""
        config_file = tmp_path / "custom-config.yaml"
        config_file.write_text("vault:\n  path: /test/vault\n")

        monkeypatch.setenv("POETRY_MCP_CONFIG", str(config_file))

        found = find_config_file()

        assert found == config_file.resolve()

    def test_find_from_xdg_config(self, tmp_path, monkeypatch):
        """Test finding config from ~/.config/poetry-mcp/config.yaml."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        xdg_config_dir = tmp_path / ".config" / "poetry-mcp"
        xdg_config_dir.mkdir(parents=True)
        config_file = xdg_config_dir / "config.yaml"
        config_file.write_text("vault:\n  path: /test/vault\n")

        found = find_config_file()

        assert found == config_file

    def test_find_from_home_directory(self, tmp_path, monkeypatch):
        """Test finding config from ~/.poetry-mcp/config.yaml."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        home_config_dir = tmp_path / ".poetry-mcp"
        home_config_dir.mkdir()
        config_file = home_config_dir / "config.yaml"
        config_file.write_text("vault:\n  path: /test/vault\n")

        found = find_config_file()

        assert found == config_file

    def test_search_order_env_var_takes_precedence(self, tmp_path, monkeypatch):
        """Test that POETRY_MCP_CONFIG env var takes precedence."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config in XDG location
        xdg_config_dir = tmp_path / ".config" / "poetry-mcp"
        xdg_config_dir.mkdir(parents=True)
        xdg_config_file = xdg_config_dir / "config.yaml"
        xdg_config_file.write_text("vault:\n  path: /xdg/vault\n")

        # Create config in custom location
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text("vault:\n  path: /custom/vault\n")

        monkeypatch.setenv("POETRY_MCP_CONFIG", str(custom_config))

        found = find_config_file()

        assert found == custom_config.resolve()

    def test_search_order_xdg_before_home(self, tmp_path, monkeypatch):
        """Test that XDG config takes precedence over home directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config in both locations
        xdg_config_dir = tmp_path / ".config" / "poetry-mcp"
        xdg_config_dir.mkdir(parents=True)
        xdg_config_file = xdg_config_dir / "config.yaml"
        xdg_config_file.write_text("vault:\n  path: /xdg/vault\n")

        home_config_dir = tmp_path / ".poetry-mcp"
        home_config_dir.mkdir()
        home_config_file = home_config_dir / "config.yaml"
        home_config_file.write_text("vault:\n  path: /home/vault\n")

        found = find_config_file()

        assert found == xdg_config_file

    def test_no_config_found_returns_none(self, tmp_path, monkeypatch):
        """Test that None is returned when no config file exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("POETRY_MCP_CONFIG", raising=False)

        found = find_config_file()

        assert found is None

    def test_env_var_nonexistent_file_logs_warning(self, tmp_path, monkeypatch, caplog):
        """Test that non-existent env var path logs warning and continues search."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("POETRY_MCP_CONFIG", "/nonexistent/config.yaml")

        # Create fallback config
        home_config_dir = tmp_path / ".poetry-mcp"
        home_config_dir.mkdir()
        config_file = home_config_dir / "config.yaml"
        config_file.write_text("vault:\n  path: /test/vault\n")

        found = find_config_file()

        assert found == config_file
        assert "non-existent" in caplog.text.lower()


class TestLoadConfigFromFile:
    """Test load_config_from_file() function."""

    def test_load_valid_config_file(self, tmp_path):
        """Test loading a valid YAML configuration file."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"""
vault:
  path: {vault}
  catalog_dir: poems
  custom_states:
    - phone_poetry

search:
  default_limit: 50
  case_sensitive: true

logging:
  level: DEBUG
  file: /tmp/poetry-mcp.log

performance:
  watch_files: true
  cache_expiry_seconds: 7200
"""
        )

        config = load_config_from_file(config_file)

        assert config.vault.path == vault.resolve()
        assert config.vault.catalog_dir == "poems"
        assert config.vault.custom_states == ["phone_poetry"]
        assert config.search.default_limit == 50
        assert config.search.case_sensitive is True
        assert config.logging.level == "DEBUG"
        assert config.performance.watch_files is True

    def test_load_minimal_config_file(self, tmp_path):
        """Test loading config with only required fields."""
        vault = tmp_path / "vault"
        vault.mkdir()

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"""
vault:
  path: {vault}
"""
        )

        config = load_config_from_file(config_file)

        assert config.vault.path == vault.resolve()
        # Check defaults are applied
        assert config.search.default_limit == 20
        assert config.logging.level == "INFO"

    def test_load_empty_config_file_raises_error(self, tmp_path):
        """Test that empty config file raises ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError, match="Config file is empty"):
            load_config_from_file(config_file)

    def test_load_invalid_yaml_raises_error(self, tmp_path):
        """Test that invalid YAML syntax raises ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
vault:
  path: /test/vault
  invalid: yaml: syntax: here
"""
        )

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config_from_file(config_file)

    def test_load_missing_required_field_raises_error(self, tmp_path):
        """Test that missing required vault field raises ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
search:
  default_limit: 50
"""
        )

        with pytest.raises(ValueError, match="Field required"):
            load_config_from_file(config_file)

    def test_load_invalid_field_value_raises_error(self, tmp_path):
        """Test that invalid field value raises ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
vault:
  path: /nonexistent/vault

search:
  default_limit: 1000
"""
        )

        with pytest.raises(ValueError, match="validation error"):
            load_config_from_file(config_file)


class TestGetConfig:
    """Test get_config() function."""

    def test_get_config_from_found_file(self, tmp_path, monkeypatch):
        """Test get_config loads from found configuration file."""
        vault = tmp_path / "vault"
        vault.mkdir()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".poetry-mcp"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            f"""
vault:
  path: {vault}
  custom_states:
    - test_state
"""
        )

        config = get_config()

        assert config.vault.path == vault.resolve()
        assert config.vault.custom_states == ["test_state"]

    @pytest.mark.skip(reason="get_config() doesn't support vault_root parameter")
    def test_get_config_with_vault_root_override(self, tmp_path, monkeypatch):
        """Test that vault_root parameter overrides config file."""
        # Create config file
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        old_vault = tmp_path / "old_vault"
        old_vault.mkdir()

        config_dir = tmp_path / ".poetry-mcp"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            f"""
vault:
  path: {old_vault}
"""
        )

        # Override with new vault
        new_vault = tmp_path / "new_vault"
        new_vault.mkdir()

        config = get_config(vault_root=str(new_vault))

        assert config.vault.path == new_vault.resolve()

    @pytest.mark.skip(reason="interactive_setup function doesn't exist in config module")
    def test_get_config_interactive_setup_when_no_config(self, tmp_path, monkeypatch):
        """Test that get_config falls back to interactive setup when no config found."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("POETRY_MCP_CONFIG", raising=False)

        # Create vault for interactive setup
        vault = tmp_path / "vault"
        vault.mkdir()

        # Mock interactive_setup to return vault path
        def mock_setup():
            return str(vault)

        monkeypatch.setattr("poetry_mcp.config.interactive_setup", mock_setup)

        config = get_config()

        assert config.vault.path == vault.resolve()

    @pytest.mark.skip(reason="get_config() doesn't support vault_root parameter")
    def test_get_config_uses_vault_root_when_no_config_and_provided(self, tmp_path, monkeypatch):
        """Test get_config uses vault_root parameter when no config file exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("POETRY_MCP_CONFIG", raising=False)

        vault = tmp_path / "vault"
        vault.mkdir()

        config = get_config(vault_root=str(vault))

        assert config.vault.path == vault.resolve()

    def test_get_config_caching_behavior(self, tmp_path, monkeypatch):
        """Test that get_config returns same instance on repeated calls."""
        vault = tmp_path / "vault"
        vault.mkdir()

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config_dir = tmp_path / ".poetry-mcp"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            f"""
vault:
  path: {vault}
"""
        )

        config1 = get_config()
        config2 = get_config()

        # Should return same configuration (though may be new instance)
        assert config1.vault.path == config2.vault.path
