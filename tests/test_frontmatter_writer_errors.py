"""Error path and edge case tests for frontmatter writer.

This test file complements test_frontmatter_writer.py by focusing on error handling,
edge cases, and exceptional conditions not covered in the happy path tests.
"""

import pytest
from unittest.mock import patch

from poetry_mcp.writers.frontmatter_writer import (
    extract_frontmatter_and_content,
    update_poem_tags,
    update_poem_frontmatter,
    create_backup,
    rollback_from_backup,
    atomic_write,
    FrontmatterUpdateResult,
)
from poetry_mcp.errors import FrontmatterParseError


@pytest.fixture
def temp_poem(tmp_path):
    """Create a temporary poem file for testing."""
    poem_file = tmp_path / "test_poem.md"
    poem_file.write_text(
        """---
state: completed
form: free_verse
tags:
  - water
  - nature
---

# Test Poem

Content here"""
    )
    return poem_file


class TestExtractFrontmatterErrors:
    """Test error handling in frontmatter extraction."""

    def test_unclosed_frontmatter(self, tmp_path):
        """Test error when frontmatter is not closed."""
        file_path = tmp_path / "unclosed.md"
        content = """---
state: completed
# Missing closing ---

Content"""

        with pytest.raises(FrontmatterParseError, match="Unclosed frontmatter"):
            extract_frontmatter_and_content(content, file_path)

    def test_invalid_yaml_in_frontmatter(self, tmp_path):
        """Test error when YAML is malformed."""
        file_path = tmp_path / "invalid.md"
        content = """---
state: completed
invalid: {not: closed
---

Content"""

        with pytest.raises(FrontmatterParseError, match="Invalid YAML"):
            extract_frontmatter_and_content(content, file_path)

    def test_empty_frontmatter_section(self, tmp_path):
        """Test handling of empty frontmatter (just delimiters)."""
        file_path = tmp_path / "empty.md"
        content = """---
---

# Content"""

        frontmatter, body = extract_frontmatter_and_content(content, file_path)

        assert frontmatter == {}
        assert "# Content" in body


class TestAtomicWriteErrors:
    """Test error handling in atomic write operations."""

    def test_atomic_write_temp_file_cleanup_on_error(self, tmp_path):
        """Test that temp file is cleaned up when write fails."""
        file_path = tmp_path / "test.md"
        content = "test content"

        # Mock Path.replace to raise an error
        with patch("pathlib.Path.replace", side_effect=OSError("Replace failed")):
            with pytest.raises(OSError, match="Replace failed"):
                atomic_write(file_path, content)

            # Verify temp file was cleaned up
            temp_files = list(tmp_path.glob("*.tmp"))
            assert len(temp_files) == 0

    def test_atomic_write_cleanup_failure_silent(self, tmp_path):
        """Test that cleanup failure doesn't mask original error."""
        file_path = tmp_path / "test.md"
        content = "test content"

        # Mock both replace and unlink to fail
        with patch("pathlib.Path.replace", side_effect=OSError("Replace failed")):
            with patch("pathlib.Path.unlink", side_effect=OSError("Unlink failed")):
                # Should raise the replace error, not the cleanup error
                with pytest.raises(OSError, match="Replace failed"):
                    atomic_write(file_path, content)


class TestUpdatePoemTagsErrors:
    """Test error handling in tag update operations."""

    def test_file_not_found(self, tmp_path):
        """Test error when poem file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.md"

        result = update_poem_tags(nonexistent, tags_to_add=["test"])

        assert result.success is False
        assert "File not found" in result.error

    def test_yaml_validation_failure_on_write(self, temp_poem):
        """Test that YAML validation catches corruption before write."""
        # Mock serialize to produce invalid YAML
        with patch(
            "poetry_mcp.writers.frontmatter_writer.serialize_frontmatter_and_content",
            return_value="---\ninvalid: {not: closed\n---\nContent",
        ):
            result = update_poem_tags(temp_poem, tags_to_add=["test"])

            assert result.success is False
            assert "YAML validation failed" in result.error

    def test_general_exception_handling(self, temp_poem):
        """Test that unexpected exceptions are caught and reported."""
        # Mock extract_frontmatter_and_content to raise unexpected error
        with patch(
            "poetry_mcp.writers.frontmatter_writer.extract_frontmatter_and_content",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = update_poem_tags(temp_poem, tags_to_add=["test"])

            assert result.success is False
            assert "Unexpected error" in result.error

    def test_string_path_conversion(self, temp_poem):
        """Test that string paths are converted to Path objects."""
        result = update_poem_tags(str(temp_poem), tags_to_add=["test-tag"])

        assert result.success is True
        assert result.file_path == str(temp_poem)


class TestUpdatePoemFrontmatterErrors:
    """Test error handling in general frontmatter updates."""

    def test_file_not_found(self, tmp_path):
        """Test error when poem file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.md"

        result = update_poem_frontmatter(nonexistent, updates={"state": "fledgeling"})

        assert result.success is False
        assert "File not found" in result.error

    def test_yaml_validation_failure(self, temp_poem):
        """Test YAML validation catches corruption in general updates."""
        # Mock serialize to produce invalid YAML
        with patch(
            "poetry_mcp.writers.frontmatter_writer.serialize_frontmatter_and_content",
            return_value="---\ninvalid: {corrupt\n---\nContent",
        ):
            result = update_poem_frontmatter(temp_poem, updates={"state": "completed"})

            assert result.success is False
            assert "YAML validation failed" in result.error

    def test_general_exception_handling(self, temp_poem):
        """Test unexpected exception handling in frontmatter update."""
        with patch(
            "poetry_mcp.writers.frontmatter_writer.extract_frontmatter_and_content",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = update_poem_frontmatter(temp_poem, updates={"state": "completed"})

            assert result.success is False
            assert "Unexpected error" in result.error

    def test_string_path_conversion(self, temp_poem):
        """Test that string paths are converted to Path objects."""
        result = update_poem_frontmatter(str(temp_poem), updates={"state": "fledgeling"})

        assert result.success is True
        assert result.file_path == str(temp_poem)


class TestRollbackFromBackup:
    """Test rollback functionality edge cases."""

    def test_rollback_when_backup_missing(self, tmp_path):
        """Test rollback fails gracefully when no backup exists."""
        poem_file = tmp_path / "poem.md"
        poem_file.write_text("content")

        result = rollback_from_backup(poem_file)

        assert result is False

    def test_rollback_with_io_error(self, tmp_path):
        """Test rollback handles I/O errors gracefully."""
        poem_file = tmp_path / "poem.md"
        backup_file = poem_file.with_suffix(poem_file.suffix + ".bak")

        poem_file.write_text("current")
        backup_file.write_text("backup")

        # Mock shutil.copy2 to raise an error
        with patch("shutil.copy2", side_effect=IOError("Copy failed")):
            result = rollback_from_backup(poem_file)

            assert result is False


class TestFrontmatterUpdateResult:
    """Test FrontmatterUpdateResult model edge cases."""

    def test_updated_tags_property_with_final_tags(self):
        """Test updated_tags returns _final_tags when available."""
        result = FrontmatterUpdateResult(
            success=True,
            file_path="/test/path.md",
            tags_added=["added1"],
            tags_removed=["removed1"],
        )
        # Manually set _final_tags after construction
        result._final_tags = ["final1", "final2", "final3"]

        assert result.updated_tags == ["final1", "final2", "final3"]

    def test_updated_tags_property_fallback_to_added(self):
        """Test updated_tags falls back to tags_added when _final_tags is None."""
        result = FrontmatterUpdateResult(
            success=True,
            file_path="/test/path.md",
            tags_added=["added1", "added2"],
            tags_removed=["removed1"],
            _final_tags=None,
        )

        assert result.updated_tags == ["added1", "added2"]


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""

    def test_empty_tags_list_operations(self, temp_poem):
        """Test operations with empty tag lists."""
        result = update_poem_tags(temp_poem, tags_to_add=[], tags_to_remove=[])

        assert result.success is True
        assert result.tags_added == []
        assert result.tags_removed == []

    def test_none_tags_operations(self, temp_poem):
        """Test operations with None tag lists (should be converted to empty)."""
        result = update_poem_tags(temp_poem, tags_to_add=None, tags_to_remove=None)

        assert result.success is True
        assert result.tags_added == []
        assert result.tags_removed == []

    def test_poem_without_existing_tags(self, tmp_path):
        """Test adding tags to poem that has no tags field."""
        poem_file = tmp_path / "notags.md"
        poem_file.write_text(
            """---
state: fledgeling
form: free_verse
---

# Poem

Content"""
        )

        result = update_poem_tags(poem_file, tags_to_add=["first-tag"])

        assert result.success is True
        assert "first-tag" in result.tags_added
        assert "first-tag" in result.updated_tags

    def test_backup_creation_without_extension(self, tmp_path):
        """Test backup creation for files without typical extensions."""
        odd_file = tmp_path / "poem"  # No extension
        odd_file.write_text("content")

        backup = create_backup(odd_file)

        assert backup.exists()
        assert backup.name == "poem.bak"

    def test_frontmatter_only_document(self, tmp_path):
        """Test handling document with frontmatter but no content."""
        poem_file = tmp_path / "frontmatter_only.md"
        poem_file.write_text(
            """---
state: completed
tags:
  - test
---
"""
        )

        result = update_poem_tags(poem_file, tags_to_add=["another"])

        assert result.success is True
        assert "another" in result.tags_added
