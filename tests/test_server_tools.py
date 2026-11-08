"""Tests for server initialization and catalog wrapper functions."""

import pytest

from poetry_mcp.catalog.catalog import Catalog
from poetry_mcp.models.results import CatalogStats, SyncResult
from poetry_mcp.server import get_catalog
from tests.conftest import make_config, patched_config

# Every test here drives get_catalog(), which caches on a module global, so
# each one starts and ends with the server singletons cleared.
pytestmark = pytest.mark.usefixtures("reset_server_globals")

# The test vault below holds exactly these two poems, both completed.
VAULT_POEM_COUNT = 2
WATER_POEM_ID = "poem1"
FIRE_POEM_ID = "poem2"
WATER_POEM_TITLE = "Test Poem One"


@pytest.fixture
def test_vault(tmp_path):
    """Create a test vault with poems."""
    vault_root = tmp_path / "vault"
    catalog_dir = vault_root / "catalog"
    completed_dir = catalog_dir / "completed"
    completed_dir.mkdir(parents=True)

    # Create test poems
    (completed_dir / f"{WATER_POEM_ID}.md").write_text(
        f"""---
state: completed
form: free_verse
tags:
  - water
  - nature
---

# {WATER_POEM_TITLE}

Water flows through the valley
Clear and pure and cold"""
    )

    (completed_dir / f"{FIRE_POEM_ID}.md").write_text(
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


@pytest.fixture
def synced_catalog(test_vault, reset_server_globals):
    """The server's catalog, built from a real config over test_vault and synced.

    Depends on reset_server_globals explicitly so the clear runs before the
    build and the teardown clear runs after the patch is lifted.
    """
    with patched_config(make_config(test_vault)):
        catalog = get_catalog()
        catalog.sync()
        yield catalog


class TestGetCatalog:
    """Test get_catalog() function."""

    def test_get_catalog_creates_instance(self, test_vault):
        """Test that get_catalog creates and caches catalog instance."""
        with patched_config(make_config(test_vault)):
            # First call should create catalog
            catalog1 = get_catalog()
            assert catalog1 is not None
            assert isinstance(catalog1, Catalog)

            # Second call should return same instance
            catalog2 = get_catalog()
            assert catalog2 is catalog1, "get_catalog() must cache on the module global"

    def test_get_catalog_with_custom_config(self, test_vault):
        """Test get_catalog with custom states and exclusions."""
        config = make_config(
            test_vault,
            exclude_catalog_dirs=["archive"],
            custom_states=["experimental"],
            custom_forms=["pantoum"],
        )

        with patched_config(config):
            catalog = get_catalog()

        assert catalog.vault_root == test_vault


class TestCatalogSync:
    """Test catalog sync operations through get_catalog."""

    def test_catalog_sync_success(self, test_vault):
        """Test successful catalog sync via get_catalog."""
        with patched_config(make_config(test_vault)):
            catalog = get_catalog()
            result = catalog.sync(force_rescan=False)

        assert isinstance(result, SyncResult)
        assert result.total_poems == VAULT_POEM_COUNT
        assert result.new_poems == VAULT_POEM_COUNT

    def test_catalog_sync_force_rescan(self, test_vault):
        """Test sync with force_rescan=True."""
        with patched_config(make_config(test_vault)):
            catalog = get_catalog()
            catalog.sync(force_rescan=False)

            result = catalog.sync(force_rescan=True)

        assert result.total_poems == VAULT_POEM_COUNT
        assert result.new_poems == VAULT_POEM_COUNT, "a forced rescan counts every poem as new"


class TestCatalogGetPoem:
    """Test poem retrieval operations through get_catalog."""

    def test_get_poem_by_id(self, synced_catalog):
        """Test getting poem by ID."""
        poem = synced_catalog.index.get_by_id(WATER_POEM_ID)

        assert poem is not None
        assert poem.id == WATER_POEM_ID
        assert poem.title == WATER_POEM_TITLE

    def test_get_poem_by_title(self, synced_catalog):
        """Test getting poem by title."""
        poem = synced_catalog.index.get_by_title(WATER_POEM_TITLE)

        assert poem is not None
        assert poem.id == WATER_POEM_ID

    def test_get_poem_not_found(self, synced_catalog):
        """Test getting nonexistent poem returns None."""
        poem = synced_catalog.index.get_by_id("nonexistent")

        assert poem is None

    def test_poem_has_content(self, synced_catalog):
        """Test poem contains content after sync."""
        poem = synced_catalog.index.get_by_id(WATER_POEM_ID)

        assert poem is not None
        assert poem.id == WATER_POEM_ID
        assert "Water flows" in poem.content


class TestCatalogSearch:
    """Test catalog search operations."""

    def test_search_poems_by_query(self, synced_catalog):
        """Test searching poems by text query."""
        poems = synced_catalog.index.search_content("water")

        assert [p.id for p in poems] == [WATER_POEM_ID]

    def test_search_poems_by_state(self, synced_catalog):
        """Test searching poems by state."""
        poems = synced_catalog.index.get_by_state("completed")

        assert len(poems) == VAULT_POEM_COUNT, f"got {[p.id for p in poems]}"

    def test_search_poems_by_form(self, synced_catalog):
        """Test searching poems by form."""
        poems = synced_catalog.index.get_by_form("american_sentence")

        assert [p.id for p in poems] == [FIRE_POEM_ID]

    def test_search_all_poems(self, synced_catalog):
        """Test accessing all poems."""
        poems = synced_catalog.index.all_poems

        assert len(poems) == VAULT_POEM_COUNT, f"got {[p.id for p in poems]}"


class TestCatalogTagOperations:
    """Test catalog tag-based operations."""

    def test_find_by_single_tag(self, synced_catalog):
        """Test finding poems with single tag."""
        poems = synced_catalog.index.get_by_tag("water")

        assert [p.id for p in poems] == [WATER_POEM_ID]

    def test_find_by_multiple_tags_any(self, synced_catalog):
        """Test finding poems with any of multiple tags."""
        poems = synced_catalog.index.get_by_tags(tags=["water", "fire"], match_mode="any")

        assert len(poems) == VAULT_POEM_COUNT, f"got {[p.id for p in poems]}"

    def test_find_by_multiple_tags_all(self, synced_catalog):
        """Test finding poems with all specified tags."""
        poems = synced_catalog.index.get_by_tags(tags=["water", "nature"], match_mode="all")

        assert [p.id for p in poems] == [WATER_POEM_ID]


class TestCatalogStats:
    """Test catalog statistics operations."""

    def test_get_catalog_stats(self, synced_catalog):
        """Test getting catalog statistics."""
        stats = synced_catalog.get_stats()

        assert isinstance(stats, CatalogStats)
        assert stats.total_poems == VAULT_POEM_COUNT
        assert stats.by_state["completed"] == VAULT_POEM_COUNT

    def test_catalog_has_vault_root(self, test_vault):
        """Test catalog exposes vault root for server info."""
        with patched_config(make_config(test_vault)):
            catalog = get_catalog()

        assert catalog.vault_root == test_vault
