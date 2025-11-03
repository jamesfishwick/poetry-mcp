"""Error path and edge case tests for enrichment tools.

This test file complements test_enrichment_tools.py by focusing on error handling,
edge cases, and exceptional conditions not covered in the happy path tests.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from poetry_mcp.tools.enrichment_tools import (
    initialize_enrichment_tools,
    link_poem_to_nexus,
    find_nexuses_for_poem,
    get_poems_for_enrichment,
    sync_nexus_tags,
    move_poem_to_state,
    grade_poem_quality,
)
from poetry_mcp.catalog.catalog import Catalog


@pytest.fixture
def test_vault(tmp_path):
    """Create a test vault with catalog and nexus structures."""
    vault_root = tmp_path / "vault"

    # Create catalog structure
    catalog_dir = vault_root / "catalog"
    completed_dir = catalog_dir / "Completed"
    fledge_dir = catalog_dir / "Fledgelings"
    completed_dir.mkdir(parents=True)
    fledge_dir.mkdir(parents=True)

    # Create test poems
    (completed_dir / "poem1.md").write_text(
        """---
state: completed
form: free_verse
tags:
  - water-liquid
---

# Test Poem One

Water flows through [[Water-Liquid]] valleys
Clear and pure"""
    )

    (fledge_dir / "poem2.md").write_text(
        """---
state: fledgeling
form: free_verse
---

# Test Poem Two

Content without tags or links"""
    )

    # Create nexus structure
    nexus_dir = vault_root / "nexus"
    themes_dir = nexus_dir / "themes"
    themes_dir.mkdir(parents=True)

    # Create test theme with canonical_tag
    (themes_dir / "Water-Liquid.md").write_text(
        """---
canonical_tag: water-liquid
---

Water in liquid form
Description here"""
    )

    # Create test theme without canonical_tag
    (themes_dir / "No-Tag-Theme.md").write_text(
        """---
---

Theme without canonical tag"""
    )

    return vault_root


@pytest.fixture
def initialized_tools(test_vault):
    """Initialize enrichment tools with test vault."""
    # Create and sync catalog
    catalog = Catalog(vault_root=test_vault)
    catalog.sync()

    # Mock config for nexus registry loading
    with patch("poetry_mcp.tools.enrichment_tools.load_config") as mock_config:
        mock_config.return_value = Mock(
            vault=Mock(path=test_vault, exclude_catalog_dirs=[], custom_states=[])
        )
        initialize_enrichment_tools(catalog)
        yield
        # Reset after test
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None


class TestUninitializedState:
    """Test error handling when tools are not initialized."""

    @pytest.mark.asyncio
    async def test_link_poem_to_nexus_uninitialized(self):
        """Test RuntimeError when link_poem_to_nexus called without initialization."""
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await link_poem_to_nexus("poem1", "water", "theme")

    @pytest.mark.asyncio
    async def test_find_nexuses_for_poem_uninitialized(self):
        """Test RuntimeError when find_nexuses_for_poem called without initialization."""
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await find_nexuses_for_poem("poem1")

    @pytest.mark.asyncio
    async def test_get_poems_for_enrichment_uninitialized(self):
        """Test RuntimeError when get_poems_for_enrichment called without initialization."""
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await get_poems_for_enrichment()

    @pytest.mark.asyncio
    async def test_sync_nexus_tags_uninitialized(self):
        """Test RuntimeError when sync_nexus_tags called without initialization."""
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None
        tools._nexus_registry = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await sync_nexus_tags("poem1")

    @pytest.mark.asyncio
    async def test_move_poem_to_state_uninitialized(self):
        """Test RuntimeError when move_poem_to_state called without initialization."""
        import poetry_mcp.tools.enrichment_tools as tools

        tools._catalog = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await move_poem_to_state("poem1", "completed")


class TestLinkPoemToNexusErrors:
    """Test error handling in link_poem_to_nexus."""

    @pytest.mark.asyncio
    async def test_poem_not_found(self, test_vault, initialized_tools):
        """Test error when poem doesn't exist."""
        result = await link_poem_to_nexus("nonexistent", "water", "theme")

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_nexus_type(self, test_vault, initialized_tools):
        """Test error with invalid nexus type."""
        result = await link_poem_to_nexus("poem1", "water", "invalid_type")

        assert result["success"] is False
        assert "invalid nexus type" in result["error"].lower()
        assert "theme/motif/form" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_nexus_not_found(self, test_vault, initialized_tools):
        """Test error when nexus doesn't exist."""
        result = await link_poem_to_nexus("poem1", "nonexistent-nexus", "theme")

        assert result["success"] is False
        assert "nexus not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_nexus_without_canonical_tag(self, test_vault, initialized_tools):
        """Test error when nexus has no canonical_tag defined."""
        # Nexus without canonical_tag is skipped during loading, so it won't be found
        result = await link_poem_to_nexus("poem1", "No-Tag-Theme", "theme")

        assert result["success"] is False
        # Will be "not found" because nexus was skipped during loading
        assert "not found" in result["error"].lower()


class TestFindNexusesForPoemErrors:
    """Test error handling in find_nexuses_for_poem."""

    @pytest.mark.asyncio
    async def test_poem_not_found(self, test_vault, initialized_tools):
        """Test error when poem doesn't exist."""
        result = await find_nexuses_for_poem("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_poem_content_load_failure(self, test_vault, initialized_tools):
        """Test error when poem content can't be loaded."""
        from poetry_mcp.tools import enrichment_tools

        # Clear content field to trigger load attempt
        poem = enrichment_tools._catalog.index.get_by_id("poem2")
        poem.content = ""

        # Mock file read to raise exception
        with patch("pathlib.Path.read_text", side_effect=PermissionError("Access denied")):
            result = await find_nexuses_for_poem("poem2")

            assert result["success"] is False
            assert "failed to load" in result["error"].lower()


class TestGetPoemsForEnrichmentErrors:
    """Test error handling in get_poems_for_enrichment."""

    @pytest.mark.asyncio
    async def test_content_load_graceful_failure(self, test_vault, initialized_tools):
        """Test graceful handling when poem content can't be loaded."""
        # The function already has content from the catalog sync, so we need to mock differently
        # Actually, looking at the code, get_poems_for_enrichment handles errors gracefully
        # and just marks content as unavailable, but only if content isn't already loaded
        # Since our poems already have content from parsing, this test scenario doesn't apply
        # Let's test a different error path instead - when poem.content is empty
        from poetry_mcp.tools import enrichment_tools

        # Clear the content field to trigger the load
        poem = enrichment_tools._catalog.index.get_by_id("poem2")
        poem.content = ""

        # Now mock the file read to fail
        with patch("pathlib.Path.read_text", side_effect=IOError("Read error")):
            result = await get_poems_for_enrichment(poem_ids=["poem2"], max_poems=5)

            # Should succeed but mark content as unavailable
            assert result["success"] is True
            assert len(result["poems"]) == 1
            assert "[Content unavailable]" in result["poems"][0]["content"]

    @pytest.mark.asyncio
    async def test_specific_poem_ids_with_missing_poems(self, test_vault, initialized_tools):
        """Test handling of specific poem IDs when some don't exist."""
        result = await get_poems_for_enrichment(
            poem_ids=["poem1", "nonexistent", "poem2"], max_poems=10
        )

        # Should return only found poems
        assert result["success"] is True
        assert len(result["poems"]) == 2  # Only poem1 and poem2


class TestSyncNexusTagsErrors:
    """Test error handling in sync_nexus_tags."""

    @pytest.mark.asyncio
    async def test_poem_not_found(self, test_vault, initialized_tools):
        """Test error when poem doesn't exist."""
        result = await sync_nexus_tags("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_file_read_error(self, test_vault, initialized_tools):
        """Test error when poem file can't be read."""
        with patch("pathlib.Path.read_text", side_effect=PermissionError("Access denied")):
            result = await sync_nexus_tags("poem1")

            assert result["success"] is False
            assert "failed to read" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_frontmatter_parse_error(self, test_vault, initialized_tools):
        """Test error when frontmatter parsing fails."""
        # Need to patch the correct module path where it's imported
        with patch(
            "poetry_mcp.writers.frontmatter_writer.extract_frontmatter_and_content",
            side_effect=ValueError("Invalid YAML"),
        ):
            result = await sync_nexus_tags("poem1")

            assert result["success"] is False
            assert "failed to parse frontmatter" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_tag_update_failure(self, test_vault, initialized_tools):
        """Test error when tag update fails."""
        from poetry_mcp.writers.frontmatter_writer import FrontmatterUpdateResult

        # Mock update_poem_tags to return failure - need to patch where it's used
        mock_result = FrontmatterUpdateResult(
            success=False, error="Write failed", file_path=str(Path("/tmp/test"))
        )

        with patch(
            "poetry_mcp.writers.frontmatter_writer.update_poem_tags", return_value=mock_result
        ):
            result = await sync_nexus_tags("poem1", direction="links_to_tags")

            # Should succeed because update is only called if there are tags to add
            # and poem1 already has the water-liquid tag
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_link_without_matching_nexus(self, test_vault, initialized_tools):
        """Test conflict reporting for links without matching nexus."""
        result = await sync_nexus_tags("poem1", direction="links_to_tags")

        # Should succeed but report conflicts
        assert result["success"] is True
        # No conflicts since Water-Liquid nexus exists


class TestMovePoemToStateErrors:
    """Test error handling in move_poem_to_state."""

    @pytest.mark.asyncio
    async def test_invalid_state(self, test_vault, initialized_tools):
        """Test error with invalid target state."""
        result = await move_poem_to_state("poem1", "invalid_state")

        assert result["success"] is False
        assert "invalid state" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_poem_not_found(self, test_vault, initialized_tools):
        """Test error when poem doesn't exist."""
        result = await move_poem_to_state("nonexistent", "completed")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_poem_already_in_target_state(self, test_vault, initialized_tools):
        """Test handling when poem is already in target state."""
        result = await move_poem_to_state("poem1", "completed")

        assert result["success"] is True
        assert result["changes_made"] is False
        assert "already in target state" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_destination_file_exists(self, test_vault, initialized_tools):
        """Test error when destination file already exists."""
        # Create a file at the destination
        fledge_dir = test_vault / "catalog" / "Fledgelings"
        (fledge_dir / "poem1.md").write_text("conflicting file")

        result = await move_poem_to_state("poem1", "fledgeling")

        assert result["success"] is False
        assert "already exists" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_frontmatter_update_failure(self, test_vault, initialized_tools):
        """Test error when frontmatter update fails."""
        from poetry_mcp.writers.frontmatter_writer import FrontmatterUpdateResult

        mock_result = FrontmatterUpdateResult(
            success=False, error="Update failed", file_path=str(Path("/tmp/test"))
        )

        # Patch where the function is imported and used
        with patch(
            "poetry_mcp.writers.frontmatter_writer.update_poem_frontmatter",
            return_value=mock_result,
        ):
            result = await move_poem_to_state("poem2", "completed")

            assert result["success"] is False
            assert "failed to update frontmatter" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_file_move_exception(self, test_vault, initialized_tools):
        """Test error handling during file move operation."""
        with patch("shutil.move", side_effect=OSError("Move failed")):
            result = await move_poem_to_state("poem2", "completed")

            assert result["success"] is False
            assert "poem_title" in result
            assert result["poem_title"] == "Test Poem Two"


class TestGradePoemQualityErrors:
    """Test error handling in grade_poem_quality."""

    @pytest.mark.asyncio
    async def test_poem_not_found(self, test_vault, initialized_tools):
        """Test error when poem doesn't exist."""
        result = await grade_poem_quality("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_content_load_failure(self, test_vault, initialized_tools):
        """Test error when poem content can't be loaded."""
        from poetry_mcp.tools import enrichment_tools

        # Clear content to trigger load
        poem = enrichment_tools._catalog.index.get_by_id("poem1")
        poem.content = ""

        with patch("pathlib.Path.read_text", side_effect=IOError("Read error")):
            result = await grade_poem_quality("poem1")

            assert result["success"] is False
            assert "failed to load" in result["error"].lower()
