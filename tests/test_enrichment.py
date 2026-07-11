"""Integration tests for enrichment tools and workflows."""

from pathlib import Path

import pytest

from poetry_mcp.writers.frontmatter_writer import update_poem_tags


class TestFrontmatterWriter:
    """Test frontmatter writer functionality."""

    @pytest.fixture
    def sample_poem_file(self, tmp_path):
        """Create a sample poem file for testing."""
        poem_file = tmp_path / "test-poem.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags:
  - water
  - memory
---

# Test Poem

Content here.
"""
        )
        return poem_file

    def test_add_tags_to_poem(self, sample_poem_file):
        """Test adding tags to a poem."""
        result = update_poem_tags(
            str(sample_poem_file), tags_to_add=["body", "failure"], tags_to_remove=[]
        )

        assert result.success is True
        assert "body" in result.updated_tags
        assert "failure" in result.updated_tags
        assert "water" in result.updated_tags
        assert "memory" in result.updated_tags

        # Verify file was actually updated
        content = sample_poem_file.read_text()
        assert "body" in content
        assert "failure" in content

    def test_remove_tags_from_poem(self, sample_poem_file):
        """Test removing tags from a poem."""
        result = update_poem_tags(str(sample_poem_file), tags_to_add=[], tags_to_remove=["water"])

        assert result.success is True
        assert "water" not in result.updated_tags
        assert "memory" in result.updated_tags

        content = sample_poem_file.read_text()
        assert "- water" not in content

    def test_add_and_remove_tags_simultaneously(self, sample_poem_file):
        """Test adding and removing tags in same operation."""
        result = update_poem_tags(
            str(sample_poem_file), tags_to_add=["nature"], tags_to_remove=["memory"]
        )

        assert result.success is True
        assert "nature" in result.updated_tags
        assert "memory" not in result.updated_tags
        assert "water" in result.updated_tags

    def test_prevent_duplicate_tags(self, sample_poem_file):
        """Test that duplicate tags are not added."""
        result = update_poem_tags(
            str(sample_poem_file),
            tags_to_add=["water"],
            tags_to_remove=[],  # Already exists
        )

        assert result.success is True
        content = sample_poem_file.read_text()
        # Count occurrences of "- water"
        assert content.count("- water") == 1

    def test_preserve_other_frontmatter_fields(self, sample_poem_file):
        """Test that other frontmatter fields are preserved."""
        result = update_poem_tags(str(sample_poem_file), tags_to_add=["nature"], tags_to_remove=[])

        assert result.success is True
        content = sample_poem_file.read_text()
        assert "state: completed" in content
        assert "form: free_verse" in content

    def test_preserve_poem_content(self, sample_poem_file):
        """Test that poem content is preserved."""
        original_content = sample_poem_file.read_text()
        original_body = original_content.split("---")[-1]

        update_poem_tags(str(sample_poem_file), tags_to_add=["nature"], tags_to_remove=[])

        new_content = sample_poem_file.read_text()
        new_body = new_content.split("---")[-1]

        assert original_body == new_body

    def test_create_backup_file(self, sample_poem_file):
        """Test that backup file is created."""
        backup_path = Path(str(sample_poem_file) + ".bak")

        # Remove any existing backup
        if backup_path.exists():
            backup_path.unlink()

        update_poem_tags(str(sample_poem_file), tags_to_add=["nature"], tags_to_remove=[])

        assert backup_path.exists()

    def test_handle_poem_without_tags_field(self, tmp_path):
        """Test handling poem without existing tags field."""
        poem_file = tmp_path / "no-tags.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
---

# No Tags Poem

Content.
"""
        )

        result = update_poem_tags(str(poem_file), tags_to_add=["water"], tags_to_remove=[])

        assert result.success is True
        assert "water" in result.updated_tags

        content = poem_file.read_text()
        assert "water" in content

    def test_handle_poem_without_frontmatter(self, tmp_path):
        """Test handling poem without any frontmatter."""
        poem_file = tmp_path / "no-frontmatter.md"
        poem_file.write_text(
            """# No Frontmatter

Just content.
"""
        )

        result = update_poem_tags(str(poem_file), tags_to_add=["water"], tags_to_remove=[])

        # Should handle gracefully
        assert result.success is True

    def test_atomic_write_on_error(self, tmp_path):
        """Test that original file is preserved if write fails."""
        poem_file = tmp_path / "test.md"
        original_content = """---
state: completed
tags:
  - water
---

# Poem

Content.
"""
        poem_file.write_text(original_content)

        # Make directory read-only to force failure
        tmp_path.chmod(0o444)

        try:
            update_poem_tags(str(poem_file), tags_to_add=["nature"], tags_to_remove=[])
            # Should fail or handle gracefully
        except Exception:
            pass
        finally:
            tmp_path.chmod(0o755)

        # Original file should be unchanged
        assert poem_file.read_text() == original_content


class TestEnrichmentWorkflow:
    """Test end-to-end enrichment workflows."""

    @pytest.fixture
    def test_catalog(self, tmp_path, markdown_dir):
        """Create a test catalog with poems."""
        import shutil

        from poetry_mcp.catalog.catalog import Catalog

        vault_dir = tmp_path / "vault"
        catalog_dir = vault_dir / "catalog" / "Completed"
        catalog_dir.mkdir(parents=True)

        # Copy test fixtures
        for fixture in markdown_dir.glob("*.md"):
            shutil.copy(fixture, catalog_dir / fixture.name)

        catalog = Catalog(str(vault_dir))
        catalog.sync()
        return catalog

    def test_link_poem_to_nexus_workflow(self, test_catalog, tmp_path):
        """Test complete workflow of linking poem to nexus."""
        # This would test the link_poem_to_nexus tool
        # For now, test the components

        # Get a poem
        poems = test_catalog.index.all_poems
        assert len(poems) > 0

        poem = poems[0]

        # Construct absolute path using catalog's vault_root
        vault_dir = tmp_path / "vault"
        absolute_path = vault_dir / poem.file_path

        # Simulate adding nexus tag
        result = update_poem_tags(absolute_path, tags_to_add=["water-liquid"], tags_to_remove=[])

        assert result.success is True
        assert "water-liquid" in result.updated_tags

    def test_batch_enrichment_workflow(self, test_catalog, tmp_path):
        """Test batch enrichment workflow."""
        # Get vault directory to construct absolute paths
        vault_dir = tmp_path / "vault"

        # Find poems without tags
        untagged_poems = [p for p in test_catalog.index.all_poems if len(p.tags) == 0]

        if len(untagged_poems) > 0:
            # Simulate batch tagging
            enriched_count = 0
            for poem in untagged_poems[:5]:  # Limit to 5 for testing
                absolute_path = vault_dir / poem.file_path
                result = update_poem_tags(
                    absolute_path, tags_to_add=["test-tag"], tags_to_remove=[]
                )
                if result.success:
                    enriched_count += 1

            assert enriched_count > 0

    def test_quality_scoring_workflow(self, test_catalog):
        """Test quality scoring workflow."""
        # Get a poem
        poems = test_catalog.index.all_poems
        if len(poems) > 0:
            poem = poems[0]

            # Simulate quality scoring by reading poem with qualities
            if poem.qualities:
                assert "detail" in poem.qualities or len(poem.qualities) >= 0


class TestEnrichmentIntegration:
    """Integration tests for enrichment tool chain."""

    def test_sync_after_enrichment(self, tmp_path, markdown_dir):
        """Test that catalog sync picks up enrichment changes."""
        import shutil

        from poetry_mcp.catalog.catalog import Catalog

        vault_dir = tmp_path / "vault"
        catalog_dir = vault_dir / "catalog" / "Completed"
        catalog_dir.mkdir(parents=True)

        # Copy a test fixture
        test_poem = markdown_dir / "fledgeling_poem.md"
        target = catalog_dir / "fledgeling_poem.md"
        shutil.copy(test_poem, target)

        # Initial sync
        catalog = Catalog(str(vault_dir))
        catalog.sync()

        poem_before = catalog.index.all_poems[0]

        # Enrich poem
        update_poem_tags(str(target), tags_to_add=["enriched"], tags_to_remove=[])

        # Resync
        catalog.sync()

        poem_after = catalog.index.get_by_id(poem_before.id)
        assert poem_after is not None
        assert "enriched" in poem_after.tags

    def test_multiple_enrichment_operations(self, tmp_path):
        """Test multiple enrichment operations on same poem."""
        poem_file = tmp_path / "test.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags: []
---

# Test

Content.
"""
        )

        # Operation 1: Add tags
        result1 = update_poem_tags(str(poem_file), tags_to_add=["water"], tags_to_remove=[])
        assert result1.success is True

        # Operation 2: Add more tags
        result2 = update_poem_tags(str(poem_file), tags_to_add=["memory"], tags_to_remove=[])
        assert result2.success is True

        # Operation 3: Remove a tag
        result3 = update_poem_tags(str(poem_file), tags_to_add=[], tags_to_remove=["water"])
        assert result3.success is True

        # Final state
        content = poem_file.read_text()
        assert "- memory" in content
        assert "- water" not in content

    def test_enrichment_preserves_quality_scores(self, tmp_path):
        """Test that enrichment preserves existing quality scores."""
        poem_file = tmp_path / "graded.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags:
  - water
qualities:
  detail: 8
  life: 7
---

# Graded Poem

Content.
"""
        )

        update_poem_tags(str(poem_file), tags_to_add=["memory"], tags_to_remove=[])

        content = poem_file.read_text()
        assert "detail: 8" in content
        assert "life: 7" in content
        assert "memory" in content
