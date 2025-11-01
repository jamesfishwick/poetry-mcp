"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


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
