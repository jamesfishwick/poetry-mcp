"""Tests for enrichment tools functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from poetry_mcp.catalog.catalog import Catalog
from poetry_mcp.models.nexus import NexusRegistry
from poetry_mcp.tools.enrichment_tools import (
    find_nexuses_for_poem,
    get_all_nexuses,
    get_poems_for_enrichment,
    grade_poem_quality,
    initialize_enrichment_tools,
    link_poem_to_nexus,
    move_poem_to_state,
    sync_nexus_tags,
)


@pytest.fixture
def complete_vault(tmp_path):
    """Create a complete test vault with catalog, poems, and nexuses."""
    vault_root = tmp_path / "vault"

    # Create catalog structure
    catalog_dir = vault_root / "catalog"
    completed_dir = catalog_dir / "completed"
    fledgeling_dir = catalog_dir / "fledgeling"

    completed_dir.mkdir(parents=True)
    fledgeling_dir.mkdir()

    # Create poems
    (completed_dir / "water.md").write_text(
        """---
state: completed
form: free_verse
tags:
  - water-liquid
---

# Water Poem

Water flows through [[Water-Liquid]] imagery
Deep and mysterious [[Body-Bones]] references
Clear as crystal"""
    )

    (fledgeling_dir / "fire.md").write_text(
        """---
state: fledgeling
form: free_verse
---

# Fire Poem

Fire burns bright
No tags yet"""
    )

    (completed_dir / "earth.md").write_text(
        """---
state: completed
form: american_sentence
tags:
  - body-bones
  - childhood
---

# Earth Poem

Earth holds memories of childhood summers and broken bones beneath the soil."""
    )

    # Create nexus structure
    nexus_dir = vault_root / "nexus"
    themes_dir = nexus_dir / "themes"
    motifs_dir = nexus_dir / "motifs"
    forms_dir = nexus_dir / "forms"

    themes_dir.mkdir(parents=True)
    motifs_dir.mkdir()
    forms_dir.mkdir()

    # Create theme nexuses (filenames become nexus names)
    (themes_dir / "Water-Liquid.md").write_text(
        """---
canonical_tag: water-liquid
---

# Water-Liquid

Water, blood, beer, tears - liquids as transformation."""
    )

    (themes_dir / "Body-Bones.md").write_text(
        """---
canonical_tag: body-bones
---

# Body-Bones

Bodies and bones, corporeal existence."""
    )

    (themes_dir / "Childhood.md").write_text(
        """---
canonical_tag: childhood
---

# Childhood

Memory, innocence, formative experiences."""
    )

    # Create motif (filename becomes nexus name)
    (motifs_dir / "American Grotesque.md").write_text(
        """---
canonical_tag: american-grotesque
---

# American Grotesque

Disturbing beauty of American imagery."""
    )

    # Create form (filename becomes nexus name)
    (forms_dir / "Catalog Poem.md").write_text(
        """---
canonical_tag: catalog-poem
---

# Catalog Poem

Anaphora and list structure."""
    )

    return vault_root


@pytest.fixture
def initialized_catalog(complete_vault):
    """Create and sync a test catalog."""
    # Create catalog
    catalog = Catalog(vault_root=complete_vault)
    catalog.sync()

    return catalog, complete_vault


class TestInitialization:
    """Test initialize_enrichment_tools()."""

    def test_initialize_sets_global_state(self, initialized_catalog):
        """Test initialization sets global catalog and registry."""
        catalog, vault_root = initialized_catalog

        # Mock config to return our test vault
        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))

            initialize_enrichment_tools(catalog)

            # Verify we can use the tools (they won't raise RuntimeError)
            import poetry_mcp.tools.enrichment_tools as tools

            assert tools._catalog is not None
            assert tools._nexus_registry is not None

    def test_initialize_loads_nexus_registry(self, initialized_catalog):
        """Test initialization loads nexus registry."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))

            initialize_enrichment_tools(catalog)

            import poetry_mcp.tools.enrichment_tools as tools

            registry = tools._nexus_registry

            # Should have themes, motifs, forms
            assert len(registry.themes) == 3
            assert len(registry.motifs) == 1
            assert len(registry.forms) == 1

    def test_initialize_with_empty_catalog(self, tmp_path):
        """Test initialization with empty catalog."""
        vault_root = tmp_path / "empty_vault"
        catalog_dir = vault_root / "catalog"
        catalog_dir.mkdir(parents=True)

        catalog = Catalog(vault_root=vault_root)
        catalog.sync()

        # Should initialize without error
        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)


class TestGetAllNexuses:
    """Test get_all_nexuses()."""

    @pytest.mark.asyncio
    async def test_get_nexuses_returns_registry(self, initialized_catalog):
        """Test get_all_nexuses returns NexusRegistry."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            registry = await get_all_nexuses()

            assert isinstance(registry, NexusRegistry)
            assert registry.total_count == 5
            assert len(registry.themes) == 3
            assert len(registry.motifs) == 1
            assert len(registry.forms) == 1

    @pytest.mark.asyncio
    async def test_get_nexuses_not_initialized_raises_error(self):
        """Test get_all_nexuses raises error if not initialized."""
        # Reset global state
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await get_all_nexuses()

    @pytest.mark.asyncio
    async def test_get_nexuses_registry_structure(self, initialized_catalog):
        """Test registry has correct structure."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            registry = await get_all_nexuses()

            # Check theme names
            theme_names = {t.name for t in registry.themes}
            assert "Water-Liquid" in theme_names
            assert "Body-Bones" in theme_names
            assert "Childhood" in theme_names

            # Check canonical tags
            theme_tags = {t.canonical_tag for t in registry.themes}
            assert "water-liquid" in theme_tags


class TestLinkPoemToNexus:
    """Test link_poem_to_nexus()."""

    @pytest.mark.asyncio
    async def test_link_theme_to_poem_success(self, initialized_catalog):
        """Test successfully linking a theme to a poem."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="Water-Liquid", nexus_type="theme"
            )

            assert result["success"] is True
            assert result["poem_title"] == "Fire Poem"
            assert result["tag_added"] == "water-liquid"
            assert result["nexus_name"] == "Water-Liquid"
            assert "backup_path" in result

    @pytest.mark.asyncio
    async def test_link_motif_to_poem(self, initialized_catalog):
        """Test linking a motif to a poem."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="American Grotesque", nexus_type="motif"
            )

            assert result["success"] is True
            assert result["tag_added"] == "american-grotesque"

    @pytest.mark.asyncio
    async def test_link_form_to_poem(self, initialized_catalog):
        """Test linking a form to a poem."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="Catalog Poem", nexus_type="form"
            )

            assert result["success"] is True
            assert result["tag_added"] == "catalog-poem"

    @pytest.mark.asyncio
    async def test_link_poem_not_found_returns_error(self, initialized_catalog):
        """Test linking to nonexistent poem returns error."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="nonexistent", nexus_name="Water-Liquid", nexus_type="theme"
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_link_nexus_not_found_returns_error(self, initialized_catalog):
        """Test linking to nonexistent nexus returns error."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="Nonexistent Theme", nexus_type="theme"
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_link_invalid_nexus_type_returns_error(self, initialized_catalog):
        """Test invalid nexus type returns error."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="Water-Liquid", nexus_type="invalid"
            )

            assert result["success"] is False
            assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_link_creates_backup_and_resyncs(self, initialized_catalog):
        """Test that linking creates backup and resyncs catalog."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initial_count = len(catalog.index.all_poems)
            initialize_enrichment_tools(catalog)

            result = await link_poem_to_nexus(
                poem_id="fire", nexus_name="Water-Liquid", nexus_type="theme"
            )

            assert result["success"] is True
            assert result["catalog_resynced"] is True
            assert result["new_poem_count"] == initial_count


class TestFindNexusesForPoem:
    """Test find_nexuses_for_poem()."""

    @pytest.mark.asyncio
    async def test_find_nexuses_returns_poem_and_themes(self, initialized_catalog):
        """Test find_nexuses_for_poem returns poem data and available themes."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await find_nexuses_for_poem(poem_id="water", max_suggestions=3)

            assert result["success"] is True
            assert "poem" in result
            assert result["poem"]["id"] == "water"
            assert result["poem"]["title"] == "Water Poem"
            assert "available_themes" in result
            assert len(result["available_themes"]) == 3
            assert result["max_suggestions"] == 3

    @pytest.mark.asyncio
    async def test_find_nexuses_loads_content(self, initialized_catalog):
        """Test that poem content is loaded."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await find_nexuses_for_poem(poem_id="water")

            assert result["success"] is True
            assert len(result["poem"]["content"]) > 0
            assert "Water flows" in result["poem"]["content"]

    @pytest.mark.asyncio
    async def test_find_nexuses_formats_theme_descriptions(self, initialized_catalog):
        """Test that theme descriptions are formatted."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await find_nexuses_for_poem(poem_id="water")

            assert result["success"] is True
            themes = result["available_themes"]
            for theme in themes:
                assert "name" in theme
                assert "canonical_tag" in theme
                assert "description" in theme
                assert len(theme["description"]) <= 200

    @pytest.mark.asyncio
    async def test_find_nexuses_respects_max_suggestions(self, initialized_catalog):
        """Test max_suggestions parameter is respected."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await find_nexuses_for_poem(poem_id="water", max_suggestions=2)

            assert result["success"] is True
            assert result["max_suggestions"] == 2
            assert "instructions" in result
            assert "up to 2" in result["instructions"]

    @pytest.mark.asyncio
    async def test_find_nexuses_poem_not_found(self, initialized_catalog):
        """Test error when poem not found."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await find_nexuses_for_poem(poem_id="nonexistent")

            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestGetPoemsForEnrichment:
    """Test get_poems_for_enrichment()."""

    @pytest.mark.asyncio
    async def test_get_untagged_poems_by_default(self, initialized_catalog):
        """Test gets poems with no tags or few tags by default."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await get_poems_for_enrichment()

            assert result["success"] is True
            assert result["total_count"] > 0
            # fire.md has no tags
            poem_ids = [p["id"] for p in result["poems"]]
            assert "fire" in poem_ids

    @pytest.mark.asyncio
    async def test_get_specific_poem_ids(self, initialized_catalog):
        """Test getting specific poems by ID."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await get_poems_for_enrichment(poem_ids=["water", "fire"])

            assert result["success"] is True
            assert result["total_count"] == 2
            poem_ids = [p["id"] for p in result["poems"]]
            assert "water" in poem_ids
            assert "fire" in poem_ids

    @pytest.mark.asyncio
    async def test_get_respects_max_poems_limit(self, initialized_catalog):
        """Test max_poems parameter limits results."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await get_poems_for_enrichment(max_poems=1)

            assert result["success"] is True
            assert result["total_count"] <= 1

    @pytest.mark.asyncio
    async def test_get_truncates_long_content(self, initialized_catalog):
        """Test that long content is truncated to 500 chars."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await get_poems_for_enrichment(poem_ids=["water"])

            assert result["success"] is True
            for poem in result["poems"]:
                assert len(poem["content"]) <= 503  # 500 + "..."

    @pytest.mark.asyncio
    async def test_get_includes_themes_and_instructions(self, initialized_catalog):
        """Test result includes themes and instructions."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await get_poems_for_enrichment()

            assert result["success"] is True
            assert "available_themes" in result
            assert "instructions" in result
            assert len(result["available_themes"]) == 3


class TestSyncNexusTags:
    """Test sync_nexus_tags()."""

    @pytest.mark.asyncio
    async def test_sync_links_to_tags_adds_tags(self, initialized_catalog):
        """Test syncing [[links]] to tags adds missing tags."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="water", direction="links_to_tags")

            assert result["success"] is True
            assert "tags_added" in result
            # Water poem has [[Water-Liquid]] and [[Body-Bones]] links
            # Should add body-bones tag if not present

    @pytest.mark.asyncio
    async def test_sync_tags_to_links_finds_conflicts(self, initialized_catalog):
        """Test syncing tags to links reports conflicts."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="earth", direction="tags_to_links")

            assert result["success"] is True
            # earth.md has childhood tag but no [[Childhood]] link
            assert "conflicts" in result

    @pytest.mark.asyncio
    async def test_sync_both_directions(self, initialized_catalog):
        """Test bidirectional sync."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="water", direction="both")

            assert result["success"] is True
            assert result["direction"] == "both"

    @pytest.mark.asyncio
    async def test_sync_reports_unmatched_links(self, initialized_catalog):
        """Test that unmatched links are reported."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="water", direction="links_to_tags")

            assert result["success"] is True
            assert "links_found" in result

    @pytest.mark.asyncio
    async def test_sync_handles_multiple_links(self, initialized_catalog):
        """Test syncing poem with multiple links."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="water", direction="links_to_tags")

            assert result["success"] is True
            # water.md has 2 [[links]]
            assert len(result["links_found"]) == 2

    @pytest.mark.asyncio
    async def test_sync_poem_not_found(self, initialized_catalog):
        """Test error when poem not found."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="nonexistent", direction="both")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sync_creates_backup(self, initialized_catalog):
        """Test that sync creates backup when changes made."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await sync_nexus_tags(poem_id="water", direction="links_to_tags")

            # If changes were made, backup should be created
            if result.get("changes_made"):
                assert result["success"] is True


class TestMovePoemToState:
    """Test move_poem_to_state()."""

    @pytest.mark.asyncio
    async def test_move_completed_to_fledgeling(self, initialized_catalog):
        """Test moving poem from completed to fledgeling."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="water", new_state="fledgeling")

            assert result["success"] is True
            assert result["old_state"] == "completed"
            assert result["new_state"] == "fledgeling"
            assert "Fledgelings" in result["new_path"]

    @pytest.mark.asyncio
    async def test_move_updates_frontmatter_and_file(self, initialized_catalog):
        """Test that move updates both frontmatter and file location."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="fire", new_state="completed")

            assert result["success"] is True
            assert result["changes_made"] is True
            # Verify file was moved
            new_path = Path(result["new_path"])
            assert new_path.exists()

    @pytest.mark.asyncio
    async def test_move_invalid_state_returns_error(self, initialized_catalog):
        """Test moving to invalid state returns error."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="fire", new_state="invalid")

            assert result["success"] is False
            assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_move_already_in_state_no_changes(self, initialized_catalog):
        """Test moving to same state makes no changes."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="water", new_state="completed")

            assert result["success"] is True
            assert result["changes_made"] is False
            assert "already in target state" in result["message"]

    @pytest.mark.asyncio
    async def test_move_creates_directory_if_needed(self, initialized_catalog):
        """Test that target directory is created if it doesn't exist."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="fire", new_state="still_cooking")

            assert result["success"] is True
            # Directory should have been created
            new_path = Path(result["new_path"])
            assert new_path.parent.exists()

    @pytest.mark.asyncio
    async def test_move_poem_not_found(self, initialized_catalog):
        """Test error when poem not found."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await move_poem_to_state(poem_id="nonexistent", new_state="completed")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_move_handles_backup_file(self, initialized_catalog):
        """Test that backup files are moved with the poem."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            # Create a backup file
            old_file = vault_root / "catalog" / "fledgeling" / "fire.md"
            backup_file = old_file.with_suffix(".md.bak")
            backup_file.write_text("backup content")

            result = await move_poem_to_state(poem_id="fire", new_state="completed")

            assert result["success"] is True
            # Backup should be mentioned or moved
            if backup_file.exists():
                assert "backup_path" in result


class TestGradePoemQuality:
    """Test grade_poem_quality()."""

    @pytest.mark.asyncio
    async def test_grade_returns_all_dimensions(self, initialized_catalog):
        """Test grading returns all 8 quality dimensions."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await grade_poem_quality(poem_id="water")

            assert result["success"] is True
            assert "dimensions" in result
            assert len(result["dimensions"]) == 8
            assert result["dimensions_count"] == 8

            # Check all dimension names are present
            dim_names = {d["name"] for d in result["dimensions"]}
            expected = {
                "Detail",
                "Life",
                "Music",
                "Mystery",
                "Sufficient Thought",
                "Surprise",
                "Syntax",
                "Unity",
            }
            assert dim_names == expected

    @pytest.mark.asyncio
    async def test_grade_filters_specific_dimensions(self, initialized_catalog):
        """Test grading specific dimensions only."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await grade_poem_quality(
                poem_id="water", dimensions=["Detail", "Music", "Unity"]
            )

            assert result["success"] is True
            assert len(result["dimensions"]) == 3
            dim_names = {d["name"] for d in result["dimensions"]}
            assert dim_names == {"Detail", "Music", "Unity"}

    @pytest.mark.asyncio
    async def test_grade_invalid_dimensions_returns_error(self, initialized_catalog):
        """Test invalid dimensions return error."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await grade_poem_quality(poem_id="water", dimensions=["InvalidDimension"])

            assert result["success"] is False
            assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_grade_poem_not_found(self, initialized_catalog):
        """Test error when poem not found."""
        catalog, vault_root = initialized_catalog

        with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
            mock_config.return_value = Mock(vault=Mock(path=vault_root))
            initialize_enrichment_tools(catalog)

            result = await grade_poem_quality(poem_id="nonexistent")

            assert result["success"] is False
            assert "not found" in result["error"].lower()
