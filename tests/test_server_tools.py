"""Tests for server initialization and catalog wrapper functions."""

import pytest
from unittest.mock import Mock, patch

from poetry_mcp.server import get_catalog
from poetry_mcp.catalog.catalog import Catalog
from poetry_mcp.models.results import SyncResult, CatalogStats


@pytest.fixture
def test_vault(tmp_path):
    """Create a test vault with poems."""
    vault_root = tmp_path / "vault"
    catalog_dir = vault_root / "catalog"
    completed_dir = catalog_dir / "completed"
    completed_dir.mkdir(parents=True)

    # Create test poems
    (completed_dir / "poem1.md").write_text(
        """---
state: completed
form: free_verse
tags:
  - water
  - nature
---

# Test Poem One

Water flows through the valley
Clear and pure and cold"""
    )

    (completed_dir / "poem2.md").write_text(
        """---
state: completed
form: american_sentence
tags:
  - fire
  - nature
---

# Test Poem Two

Fire burns bright in the darkness of the winter night alone"""
    )

    return vault_root


class TestGetCatalog:
    """Test get_catalog() function."""

    def test_get_catalog_creates_instance(self, test_vault):
        """Test that get_catalog creates and caches catalog instance."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            # Reset global catalog
            import poetry_mcp.server as server_module

            server_module.catalog = None

            # First call should create catalog
            catalog1 = get_catalog()
            assert catalog1 is not None
            assert isinstance(catalog1, Catalog)

            # Second call should return same instance
            catalog2 = get_catalog()
            assert catalog2 is catalog1

    def test_get_catalog_with_custom_config(self, test_vault):
        """Test get_catalog with custom states and exclusions."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(
                    path=test_vault,
                    exclude_catalog_dirs=["archive"],
                    custom_states=["experimental"],
                )
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            assert catalog.vault_root == test_vault


class TestCatalogSync:
    """Test catalog sync operations through get_catalog."""

    def test_catalog_sync_success(self, test_vault):
        """Test successful catalog sync via get_catalog."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            result = catalog.sync(force_rescan=False)

            assert isinstance(result, SyncResult)
            assert result.total_poems == 2
            assert result.new_poems == 2

    def test_catalog_sync_force_rescan(self, test_vault):
        """Test sync with force_rescan=True."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            # First sync
            catalog.sync(force_rescan=False)

            # Force rescan
            result = catalog.sync(force_rescan=True)
            assert result.total_poems == 2
            assert result.new_poems == 2  # All counted as new


class TestCatalogGetPoem:
    """Test poem retrieval operations through get_catalog."""

    def test_get_poem_by_id(self, test_vault):
        """Test getting poem by ID."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poem = catalog.index.get_by_id("poem1")

            assert poem is not None
            assert poem.id == "poem1"
            assert poem.title == "Test Poem One"

    def test_get_poem_by_title(self, test_vault):
        """Test getting poem by title."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poem = catalog.index.get_by_title("Test Poem One")

            assert poem is not None
            assert poem.id == "poem1"

    def test_get_poem_not_found(self, test_vault):
        """Test getting nonexistent poem returns None."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poem = catalog.index.get_by_id("nonexistent")

            assert poem is None

    def test_poem_has_content(self, test_vault):
        """Test poem contains content after sync."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poem = catalog.index.get_by_id("poem1")

            assert poem is not None
            assert poem.id == "poem1"
            assert "Water flows" in poem.content


class TestCatalogSearch:
    """Test catalog search operations."""

    def test_search_poems_by_query(self, test_vault):
        """Test searching poems by text query."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.search_content("water")

            assert len(poems) == 1
            assert poems[0].id == "poem1"

    def test_search_poems_by_state(self, test_vault):
        """Test searching poems by state."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.get_by_state("completed")

            assert len(poems) == 2

    def test_search_poems_by_form(self, test_vault):
        """Test searching poems by form."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.get_by_form("american_sentence")

            assert len(poems) == 1
            assert poems[0].id == "poem2"

    def test_search_all_poems(self, test_vault):
        """Test accessing all poems."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.all_poems

            assert len(poems) == 2


class TestCatalogTagOperations:
    """Test catalog tag-based operations."""

    def test_find_by_single_tag(self, test_vault):
        """Test finding poems with single tag."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.get_by_tag("water")

            assert len(poems) == 1
            assert poems[0].id == "poem1"

    def test_find_by_multiple_tags_any(self, test_vault):
        """Test finding poems with any of multiple tags."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.get_by_tags(tags=["water", "fire"], match_mode="any")

            assert len(poems) == 2

    def test_find_by_multiple_tags_all(self, test_vault):
        """Test finding poems with all specified tags."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            poems = catalog.index.get_by_tags(tags=["water", "nature"], match_mode="all")

            assert len(poems) == 1
            assert poems[0].id == "poem1"


class TestCatalogStats:
    """Test catalog statistics operations."""

    def test_get_catalog_stats(self, test_vault):
        """Test getting catalog statistics."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            catalog.sync()
            stats = catalog.get_stats()

            assert isinstance(stats, CatalogStats)
            assert stats.total_poems == 2
            assert stats.by_state["completed"] == 2

    def test_catalog_has_vault_root(self, test_vault):
        """Test catalog exposes vault root for server info."""
        with patch("poetry_mcp.server.load_config") as mock_config:
            mock_config.return_value = Mock(
                vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
            )

            import poetry_mcp.server as server_module

            server_module.catalog = None

            catalog = get_catalog()
            assert catalog.vault_root == test_vault
