"""Pytest configuration and shared fixtures."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from poetry_mcp.config import PoetryMCPConfig, VaultConfig

# Every module that does `from ..config import load_config` binds its own name,
# so patching one module's name leaves the others reading the real config on
# the machine. A test that patches only poetry_mcp.server.load_config passes
# wherever ~/.config/poetry-mcp/config.yaml exists and fails on CI.
LOAD_CONFIG_SITES = (
    "poetry_mcp.server.load_config",
    "poetry_mcp.tools.catalog_tools.load_config",
    "poetry_mcp.tools.enrichment_tools.load_config",
    "poetry_mcp.tools.nexus_tools.load_config",
    "poetry_mcp.tools.submission_tools.load_config",
    "poetry_mcp.tools.venue_tools.load_config",
)

# Module-level singletons on poetry_mcp.server that get_* lazily populate.
SERVER_GLOBALS = ("catalog", "submission_catalog", "venue_catalog", "nexus_manager")


def make_config(vault_path: Path, **vault_overrides) -> PoetryMCPConfig:
    """Build a real config rooted at vault_path.

    A real PoetryMCPConfig fails loudly when production reads a field the
    test never thought about, where a Mock would answer with another Mock.
    Pass VaultConfig fields as keywords to set a non-default.
    """
    return PoetryMCPConfig(vault=VaultConfig(path=vault_path, **vault_overrides))


@contextmanager
def patched_config(config: PoetryMCPConfig) -> Iterator[PoetryMCPConfig]:
    """Make every load_config site return config for the duration of the block."""
    with ExitStack() as stack:
        for site in LOAD_CONFIG_SITES:
            stack.enter_context(patch(site, return_value=config))
        yield config


def _reset_server_globals() -> None:
    import poetry_mcp.server as server_module

    for name in SERVER_GLOBALS:
        setattr(server_module, name, None)


@pytest.fixture
def reset_server_globals() -> Iterator[None]:
    """Clear the server singletons before and after a test.

    The teardown half runs on failure too, so a test that dies mid-way cannot
    leak its temp-vault catalog into the next test.
    """
    _reset_server_globals()
    yield
    _reset_server_globals()


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def base_files_dir(fixtures_dir: Path) -> Path:
    """Return path to BASE files fixtures."""
    return fixtures_dir / "base_files"


@pytest.fixture
def markdown_dir(fixtures_dir: Path) -> Path:
    """Return path to markdown fixtures."""
    return fixtures_dir / "markdown"
