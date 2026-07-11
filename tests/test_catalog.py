"""Tests for catalog functionality."""

from datetime import datetime

import pytest

from poetry_mcp.catalog.catalog import Catalog, CatalogIndex
from poetry_mcp.models.poem import Poem
from poetry_mcp.models.results import CatalogStats, SyncResult


class TestCatalogIndex:
    """Test CatalogIndex class."""

    @pytest.fixture
    def sample_poems(self):
        """Create sample poems for testing."""
        return [
            Poem(
                id="poem1",
                title="Water Poem",
                content="Water flows",
                state="completed",
                form="free_verse",
                tags=["water", "nature"],
                word_count=2,
                line_count=1,
                stanza_count=1,
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 1),
                file_path="/vault/catalog/completed/water.md",
            ),
            Poem(
                id="poem2",
                title="Fire Poem",
                content="Fire burns",
                state="completed",
                form="american_sentence",
                tags=["fire", "nature"],
                word_count=2,
                line_count=1,
                stanza_count=1,
                created_at=datetime(2024, 1, 2),
                updated_at=datetime(2024, 1, 2),
                file_path="/vault/catalog/completed/fire.md",
            ),
            Poem(
                id="poem3",
                title="Draft Poem",
                content="Unfinished work",
                state="fledgeling",
                form="free_verse",
                tags=["draft"],
                word_count=2,
                line_count=1,
                stanza_count=1,
                created_at=datetime(2024, 1, 3),
                updated_at=datetime(2024, 1, 3),
                file_path="/vault/catalog/fledgeling/draft.md",
            ),
        ]

    def test_add_poem_and_get_by_id(self, sample_poems):
        """Test adding poems and lookup by ID."""
        index = CatalogIndex()

        for poem in sample_poems:
            index.add_poem(poem)

        assert index.get_by_id("poem1") == sample_poems[0]
        assert index.get_by_id("poem2") == sample_poems[1]
        assert index.get_by_id("nonexistent") is None

    def test_get_by_title_case_insensitive(self, sample_poems):
        """Test title lookup is case-insensitive."""
        index = CatalogIndex()
        index.add_poem(sample_poems[0])

        assert index.get_by_title("Water Poem") == sample_poems[0]
        assert index.get_by_title("water poem") == sample_poems[0]
        assert index.get_by_title("WATER POEM") == sample_poems[0]
        assert index.get_by_title("Fire Poem") is None

    def test_get_by_state(self, sample_poems):
        """Test filtering by state."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        completed = index.get_by_state("completed")
        assert len(completed) == 2
        assert all(p.state == "completed" for p in completed)

        fledgeling = index.get_by_state("fledgeling")
        assert len(fledgeling) == 1
        assert fledgeling[0].id == "poem3"

    def test_get_by_form(self, sample_poems):
        """Test filtering by form."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        free_verse = index.get_by_form("free_verse")
        assert len(free_verse) == 2

        american_sentence = index.get_by_form("american_sentence")
        assert len(american_sentence) == 1
        assert american_sentence[0].id == "poem2"

    def test_get_by_tag_single(self, sample_poems):
        """Test getting poems by single tag."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        nature_poems = index.get_by_tag("nature")
        assert len(nature_poems) == 2
        assert all("nature" in p.tags for p in nature_poems)

        water_poems = index.get_by_tag("water")
        assert len(water_poems) == 1
        assert water_poems[0].id == "poem1"

    def test_get_by_tags_all_mode(self, sample_poems):
        """Test getting poems with ALL specified tags."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        # Both water AND nature
        result = index.get_by_tags(["water", "nature"], match_mode="all")
        assert len(result) == 1
        assert result[0].id == "poem1"

        # Both fire AND nature
        result = index.get_by_tags(["fire", "nature"], match_mode="all")
        assert len(result) == 1
        assert result[0].id == "poem2"

        # Water AND fire (no poems have both)
        result = index.get_by_tags(["water", "fire"], match_mode="all")
        assert len(result) == 0

    def test_get_by_tags_any_mode(self, sample_poems):
        """Test getting poems with ANY specified tags."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        # Water OR fire
        result = index.get_by_tags(["water", "fire"], match_mode="any")
        assert len(result) == 2

        # Nature OR draft
        result = index.get_by_tags(["nature", "draft"], match_mode="any")
        assert len(result) == 3

    def test_get_by_tags_empty_list(self):
        """Test that empty tag list returns empty results."""
        index = CatalogIndex()
        result = index.get_by_tags([], match_mode="all")
        assert result == []
        result = index.get_by_tags([], match_mode="any")
        assert result == []

    def test_search_content_case_insensitive(self, sample_poems):
        """Test content search is case-insensitive by default."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        # Search in content
        result = index.search_content("water")
        assert len(result) == 1
        assert result[0].id == "poem1"

        # Search in title
        result = index.search_content("fire poem")
        assert len(result) == 1
        assert result[0].id == "poem2"

        # Case variations
        result = index.search_content("WATER")
        assert len(result) == 1

    def test_search_content_case_sensitive(self, sample_poems):
        """Test case-sensitive content search."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        # Title is "Water Poem" with capital W
        result = index.search_content("Water", case_sensitive=True)
        assert len(result) == 1

        # Content is "Water flows" with capital W
        result = index.search_content("flows", case_sensitive=True)
        assert len(result) == 1

        result = index.search_content("FLOWS", case_sensitive=True)
        assert len(result) == 0

    def test_search_content_empty_query(self):
        """Test that empty query returns empty results."""
        index = CatalogIndex()
        result = index.search_content("")
        assert result == []

    def test_get_all_poems(self, sample_poems):
        """Test get_all_poems returns full list."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        assert len(index.all_poems) == 3
        assert index.all_poems == sample_poems

    def test_get_stats(self, sample_poems):
        """Test statistics generation."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        stats = index.get_stats()

        assert stats["total_poems"] == 3
        assert stats["by_state"]["completed"] == 2
        assert stats["by_state"]["fledgeling"] == 1
        assert stats["by_form"]["free_verse"] == 2
        assert stats["by_form"]["american_sentence"] == 1
        assert stats["poems_without_tags"] == 0
        assert stats["total_word_count"] == 6
        assert stats["avg_word_count"] == 2.0
        assert stats["oldest_poem"] == "Water Poem"
        assert stats["newest_poem"] == "Draft Poem"

    def test_get_stats_empty_catalog(self):
        """Test statistics for empty catalog."""
        index = CatalogIndex()
        stats = index.get_stats()

        assert stats["total_poems"] == 0
        assert stats["avg_word_count"] == 0
        assert stats["oldest_poem"] == ""
        assert stats["newest_poem"] == ""

    def test_clear_index(self, sample_poems):
        """Test clearing all indices."""
        index = CatalogIndex()
        for poem in sample_poems:
            index.add_poem(poem)

        assert len(index.all_poems) == 3

        index.clear()

        assert len(index.all_poems) == 0
        assert len(index.by_id) == 0
        assert len(index.by_title) == 0
        assert len(index.by_state) == 0
        assert len(index.by_form) == 0
        assert len(index.by_tag) == 0


class TestCatalog:
    """Test Catalog class."""

    @pytest.fixture
    def vault_with_poems(self, tmp_path):
        """Create a temporary vault with sample poems."""
        vault_root = tmp_path / "vault"
        catalog_dir = vault_root / "catalog"

        # Create directory structure
        completed_dir = catalog_dir / "completed"
        completed_dir.mkdir(parents=True)

        fledgeling_dir = catalog_dir / "fledgeling"
        fledgeling_dir.mkdir()

        # Create sample poem files
        (completed_dir / "water.md").write_text(
            """---
state: completed
form: free_verse
tags:
  - water
  - nature
---

# Water Poem

Water flows gently
Through the valley"""
        )

        (completed_dir / "fire.md").write_text(
            """---
state: completed
form: american_sentence
tags:
  - fire
---

# Fire Poem

Fire burns bright in the darkness of night"""
        )

        (fledgeling_dir / "draft.md").write_text(
            """---
state: fledgeling
form: free_verse
---

# Draft Poem

Unfinished work"""
        )

        return vault_root

    def test_catalog_initialization(self, vault_with_poems):
        """Test catalog initializes with vault root."""
        catalog = Catalog(vault_root=vault_with_poems)

        assert catalog.vault_root == vault_with_poems
        assert catalog.catalog_dir == vault_with_poems / "catalog"
        assert isinstance(catalog.index, CatalogIndex)
        assert catalog.last_sync is None

    def test_sync_loads_all_poems(self, vault_with_poems):
        """Test sync() loads all poems from filesystem."""
        catalog = Catalog(vault_root=vault_with_poems)
        result = catalog.sync()

        assert isinstance(result, SyncResult)
        assert result.total_poems == 3
        assert result.new_poems == 3
        assert result.skipped_poems == 0
        assert len(result.warnings) == 0
        assert catalog.last_sync is not None

    def test_sync_respects_exclude_dirs(self, vault_with_poems):
        """Test sync() excludes specified directories."""
        catalog = Catalog(vault_root=vault_with_poems, exclude_dirs=["fledgeling"])
        result = catalog.sync()

        # Should only load completed poems, not fledgeling
        assert result.total_poems == 2
        assert len(catalog.index.get_by_state("completed")) == 2
        assert len(catalog.index.get_by_state("fledgeling")) == 0

    def test_sync_handles_missing_catalog_dir(self, tmp_path):
        """Test sync() raises error for nonexistent catalog directory."""
        vault_root = tmp_path / "vault"
        vault_root.mkdir()
        # Don't create catalog directory

        catalog = Catalog(vault_root=vault_root)

        with pytest.raises(FileNotFoundError, match="Catalog directory not found"):
            catalog.sync()

    def test_sync_skips_malformed_files(self, vault_with_poems):
        """Test sync() skips files with parse errors."""
        # Create file with invalid YAML frontmatter
        catalog_dir = vault_with_poems / "catalog" / "completed"
        (catalog_dir / "bad.md").write_text(
            """---
state: completed: invalid: yaml
---

Content"""
        )

        catalog = Catalog(vault_root=vault_with_poems)
        result = catalog.sync()

        # Should load 3 good poems and skip 1 bad
        assert result.total_poems == 3
        assert result.skipped_poems == 1
        assert len(result.warnings) == 1
        assert "bad.md" in result.warnings[0]

    def test_sync_force_rescan(self, vault_with_poems):
        """Test force_rescan clears existing index."""
        catalog = Catalog(vault_root=vault_with_poems)

        # Initial sync
        result1 = catalog.sync()
        assert result1.total_poems == 3
        assert result1.new_poems == 3

        # Sync with force_rescan
        result2 = catalog.sync(force_rescan=True)
        assert result2.total_poems == 3
        assert result2.new_poems == 3  # All counted as new after clear
        assert result2.updated_poems == 0

    def test_get_stats_returns_catalog_stats(self, vault_with_poems):
        """Test get_stats() returns CatalogStats model."""
        catalog = Catalog(vault_root=vault_with_poems)
        catalog.sync()

        stats = catalog.get_stats()

        assert isinstance(stats, CatalogStats)
        assert stats.total_poems == 3
        assert stats.by_state["completed"] == 2
        assert stats.by_state["fledgeling"] == 1
        assert stats.by_form["free_verse"] == 2
        assert stats.by_form["american_sentence"] == 1
        assert stats.total_word_count == 16  # actual word count from content
        assert stats.last_sync is not None

    def test_catalog_with_custom_states(self, vault_with_poems):
        """Test catalog accepts custom states."""
        # Create poem with custom state
        custom_dir = vault_with_poems / "catalog" / "archived"
        custom_dir.mkdir()

        (custom_dir / "old.md").write_text(
            """---
state: archived
form: free_verse
---

# Old Poem

Very old poem"""
        )

        catalog = Catalog(vault_root=vault_with_poems, custom_states=["archived"])
        result = catalog.sync()

        # Should load all 4 poems including custom state
        assert result.total_poems == 4
        archived = catalog.index.get_by_state("archived")
        assert len(archived) == 1
        assert archived[0].title == "Old Poem"

    def test_sync_performance_with_many_poems(self, tmp_path):
        """Test sync performance with 50+ poems."""
        vault_root = tmp_path / "vault"
        catalog_dir = vault_root / "catalog" / "completed"
        catalog_dir.mkdir(parents=True)

        # Create 50 poem files
        for i in range(50):
            (catalog_dir / f"poem{i}.md").write_text(
                f"""---
state: completed
form: free_verse
---

# poem{i}

Content {i}"""
            )

        catalog = Catalog(vault_root=vault_root)
        result = catalog.sync()

        assert result.total_poems == 50
        assert result.duration_seconds < 5.0  # Should be fast

        # Test index lookups are fast
        poem = catalog.index.get_by_id("poem25")
        assert poem is not None
        assert poem.title == "poem25"  # Title from heading

    def test_sync_updates_existing_poems(self, vault_with_poems):
        """Test sync updates existing poems when re-run."""
        catalog = Catalog(vault_root=vault_with_poems)

        # Initial sync
        result1 = catalog.sync()
        assert result1.total_poems == 3

        # Modify a file
        water_file = vault_with_poems / "catalog" / "completed" / "water.md"
        content = water_file.read_text()
        water_file.write_text(content.replace("Water Poem", "Updated Water Poem"))

        # Sync with force_rescan to reload
        result2 = catalog.sync(force_rescan=True)

        # Should reload all poems
        assert result2.total_poems == 3
        assert result2.new_poems == 3  # All counted as new after clear

        # Verify update
        poem = catalog.index.get_by_id("water")  # ID from filename
        assert poem.title == "Updated Water Poem"

    def test_combined_filters(self, vault_with_poems):
        """Test combining state, form, and tag filters."""
        catalog = Catalog(vault_root=vault_with_poems)
        catalog.sync()

        # Get completed free verse poems
        completed = catalog.index.get_by_state("completed")
        free_verse = catalog.index.get_by_form("free_verse")

        # Intersection
        completed_free_verse = [p for p in completed if p in free_verse]
        assert len(completed_free_verse) == 1
        assert completed_free_verse[0].id == "water"  # ID from filename

        # Get completed poems with water tag
        water_poems = catalog.index.get_by_tag("water")
        completed_water = [p for p in completed if p in water_poems]
        assert len(completed_water) == 1
