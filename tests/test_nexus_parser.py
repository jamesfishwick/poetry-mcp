"""Tests for nexus parser functionality."""

import pytest

from poetry_mcp.errors import FrontmatterParseError
from poetry_mcp.parsers.nexus_parser import (
    extract_canonical_tag,
    load_nexus_registry,
    parse_nexus_file,
    scan_nexus_directory,
)


class TestExtractCanonicalTag:
    """Test extract_canonical_tag() function."""

    def test_extract_valid_tag(self, tmp_path):
        """Test extracting canonical_tag from valid frontmatter."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
canonical_tag: water-liquid
---

Water imagery in poetry."""
        )

        tag, content = extract_canonical_tag(nexus_file)

        assert tag == "water-liquid"
        assert "Water imagery" in content

    def test_extract_tag_with_extra_fields(self, tmp_path):
        """Test extraction ignores extra frontmatter fields."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
canonical_tag: body-bones
description: Skeletal imagery
extra_field: ignored
---

Body content."""
        )

        tag, content = extract_canonical_tag(nexus_file)

        assert tag == "body-bones"

    def test_missing_frontmatter_raises_error(self, tmp_path):
        """Test that missing frontmatter raises error."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text("No frontmatter here!")

        with pytest.raises(FrontmatterParseError, match="Missing frontmatter"):
            extract_canonical_tag(nexus_file)

    def test_unclosed_frontmatter_raises_error(self, tmp_path):
        """Test that unclosed frontmatter raises error."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
canonical_tag: test
No closing delimiter"""
        )

        with pytest.raises(FrontmatterParseError, match="Unclosed frontmatter"):
            extract_canonical_tag(nexus_file)

    def test_invalid_yaml_raises_error(self, tmp_path):
        """Test that invalid YAML raises error."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
canonical_tag: test: invalid: yaml
---"""
        )

        with pytest.raises(FrontmatterParseError, match="Invalid YAML"):
            extract_canonical_tag(nexus_file)

    def test_missing_canonical_tag_field_raises_error(self, tmp_path):
        """Test that missing canonical_tag field raises error."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
name: Test
---"""
        )

        with pytest.raises(FrontmatterParseError, match="Missing 'canonical_tag'"):
            extract_canonical_tag(nexus_file)

    def test_empty_frontmatter_raises_error(self, tmp_path):
        """Test that empty frontmatter raises error."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
---"""
        )

        with pytest.raises(FrontmatterParseError, match="Missing 'canonical_tag'"):
            extract_canonical_tag(nexus_file)

    def test_tag_with_whitespace_preserved(self, tmp_path):
        """Test that canonical_tag whitespace is preserved."""
        nexus_file = tmp_path / "test.md"
        nexus_file.write_text(
            """---
canonical_tag: "  water-liquid  "
---"""
        )

        tag, _ = extract_canonical_tag(nexus_file)

        # YAML parser should preserve whitespace in quoted strings
        assert tag == "  water-liquid  "


class TestParseNexusFile:
    """Test parse_nexus_file() function."""

    def test_parse_valid_nexus_file(self, tmp_path):
        """Test parsing valid nexus file with all fields."""
        nexus_file = tmp_path / "Water-Liquid Imagery.md"
        nexus_file.write_text(
            """---
canonical_tag: water-liquid
---

Water, blood, beer, tears - liquids as transformation."""
        )

        nexus = parse_nexus_file(nexus_file, "theme")

        assert nexus.name == "Water-Liquid"  # " Imagery" suffix removed
        assert nexus.category == "theme"
        assert nexus.canonical_tag == "water-liquid"
        assert "transformation" in nexus.description
        assert nexus.file_path == str(nexus_file)

    def test_parse_nexus_without_imagery_suffix(self, tmp_path):
        """Test parsing nexus file without ' Imagery' suffix."""
        nexus_file = tmp_path / "Catalog Poem.md"
        nexus_file.write_text(
            """---
canonical_tag: catalog-poem
---

Anaphora and list structure."""
        )

        nexus = parse_nexus_file(nexus_file, "form")

        assert nexus.name == "Catalog Poem"
        assert nexus.category == "form"

    def test_parse_nexus_minimal_content(self, tmp_path):
        """Test parsing nexus with minimal content."""
        nexus_file = tmp_path / "Test.md"
        nexus_file.write_text(
            """---
canonical_tag: test-tag
---"""
        )

        nexus = parse_nexus_file(nexus_file, "theme")

        assert nexus.name == "Test"
        assert nexus.canonical_tag == "test-tag"
        assert nexus.description  # Should contain full content

    def test_parse_missing_canonical_tag_raises_error(self, tmp_path):
        """Test that missing canonical_tag raises error."""
        nexus_file = tmp_path / "Invalid.md"
        nexus_file.write_text(
            """---
name: Invalid
---"""
        )

        with pytest.raises(FrontmatterParseError, match="Missing 'canonical_tag'"):
            parse_nexus_file(nexus_file, "theme")

    def test_parse_nonexistent_file_raises_error(self, tmp_path):
        """Test that nonexistent file raises error."""
        nexus_file = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            parse_nexus_file(nexus_file, "theme")

    def test_parse_preserves_full_content_in_description(self, tmp_path):
        """Test that full file content is preserved in description."""
        nexus_file = tmp_path / "Test.md"
        content = """---
canonical_tag: test-tag
---

# Heading

Multiple paragraphs
with content."""
        nexus_file.write_text(content)

        nexus = parse_nexus_file(nexus_file, "theme")

        assert nexus.description == content


class TestScanNexusDirectory:
    """Test scan_nexus_directory() function."""

    def test_scan_multiple_nexus_files(self, tmp_path):
        """Test scanning directory with multiple nexus files."""
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()

        (themes_dir / "water.md").write_text(
            """---
canonical_tag: water-liquid
---"""
        )
        (themes_dir / "body.md").write_text(
            """---
canonical_tag: body-bones
---"""
        )
        (themes_dir / "food.md").write_text(
            """---
canonical_tag: food-eating
---"""
        )

        nexuses = scan_nexus_directory(themes_dir, "theme")

        assert len(nexuses) == 3
        tags = {n.canonical_tag for n in nexuses}
        assert tags == {"water-liquid", "body-bones", "food-eating"}

    def test_scan_skips_non_markdown_files(self, tmp_path):
        """Test that non-markdown files are skipped."""
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()

        (themes_dir / "valid.md").write_text(
            """---
canonical_tag: valid-tag
---"""
        )
        (themes_dir / "notes.txt").write_text("Not a nexus")
        (themes_dir / "image.png").write_bytes(b"fake image")

        nexuses = scan_nexus_directory(themes_dir, "theme")

        assert len(nexuses) == 1
        assert nexuses[0].canonical_tag == "valid-tag"

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty directory returns empty list."""
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()

        nexuses = scan_nexus_directory(themes_dir, "theme")

        assert nexuses == []

    def test_scan_nonexistent_directory(self, tmp_path):
        """Test scanning nonexistent directory returns empty list."""
        nexuses = scan_nexus_directory(tmp_path / "nonexistent", "theme")

        assert nexuses == []

    def test_scan_parse_errors_logged_but_continue(self, tmp_path, capfd):
        """Test that parse errors are logged but don't stop scanning."""
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()

        # Valid file
        (themes_dir / "valid.md").write_text(
            """---
canonical_tag: valid-tag
---"""
        )

        # Invalid file (missing canonical_tag)
        (themes_dir / "invalid.md").write_text(
            """---
name: Invalid
---"""
        )

        # Another valid file
        (themes_dir / "valid2.md").write_text(
            """---
canonical_tag: valid-tag-2
---"""
        )

        nexuses = scan_nexus_directory(themes_dir, "theme")

        # Should have loaded 2 valid files
        assert len(nexuses) == 2
        tags = {n.canonical_tag for n in nexuses}
        assert tags == {"valid-tag", "valid-tag-2"}

        # Check warning was printed
        captured = capfd.readouterr()
        assert "Warning: Skipping" in captured.out
        assert "invalid.md" in captured.out


class TestLoadNexusRegistry:
    """Test load_nexus_registry() function."""

    def test_load_complete_registry(self, tmp_path):
        """Test loading complete registry with all categories."""
        # Create nexus directory structure
        nexus_dir = tmp_path / "nexus"
        themes_dir = nexus_dir / "themes"
        motifs_dir = nexus_dir / "motifs"
        forms_dir = nexus_dir / "forms"

        themes_dir.mkdir(parents=True)
        motifs_dir.mkdir()
        forms_dir.mkdir()

        # Create theme files
        (themes_dir / "water.md").write_text(
            """---
canonical_tag: water-liquid
---"""
        )
        (themes_dir / "body.md").write_text(
            """---
canonical_tag: body-bones
---"""
        )

        # Create motif files
        (motifs_dir / "grotesque.md").write_text(
            """---
canonical_tag: american-grotesque
---"""
        )

        # Create form files
        (forms_dir / "catalog.md").write_text(
            """---
canonical_tag: catalog-poem
---"""
        )
        (forms_dir / "prose.md").write_text(
            """---
canonical_tag: prose-poem
---"""
        )

        registry = load_nexus_registry(tmp_path)

        assert len(registry.themes) == 2
        assert len(registry.motifs) == 1
        assert len(registry.forms) == 2
        assert registry.total_count == 5

    def test_load_registry_categorization(self, tmp_path):
        """Test that nexuses are correctly categorized."""
        nexus_dir = tmp_path / "nexus"
        themes_dir = nexus_dir / "themes"
        themes_dir.mkdir(parents=True)

        (themes_dir / "test.md").write_text(
            """---
canonical_tag: test-theme
---"""
        )

        registry = load_nexus_registry(tmp_path)

        assert len(registry.themes) == 1
        assert registry.themes[0].category == "theme"
        assert registry.themes[0].canonical_tag == "test-theme"

    def test_load_registry_nonexistent_vault(self, tmp_path):
        """Test loading from nonexistent vault returns empty registry."""
        registry = load_nexus_registry(tmp_path / "nonexistent")

        assert registry.themes == []
        assert registry.motifs == []
        assert registry.forms == []
        assert registry.total_count == 0

    def test_load_registry_missing_subdirectories(self, tmp_path):
        """Test loading when some category directories don't exist."""
        nexus_dir = tmp_path / "nexus"
        themes_dir = nexus_dir / "themes"
        themes_dir.mkdir(parents=True)

        (themes_dir / "test.md").write_text(
            """---
canonical_tag: test-theme
---"""
        )

        # No motifs or forms directories
        registry = load_nexus_registry(tmp_path)

        assert len(registry.themes) == 1
        assert registry.motifs == []
        assert registry.forms == []
        assert registry.total_count == 1

    def test_load_registry_file_path_assignment(self, tmp_path):
        """Test that file_path is correctly assigned to each nexus."""
        nexus_dir = tmp_path / "nexus"
        themes_dir = nexus_dir / "themes"
        themes_dir.mkdir(parents=True)

        nexus_file = themes_dir / "water.md"
        nexus_file.write_text(
            """---
canonical_tag: water-liquid
---"""
        )

        registry = load_nexus_registry(tmp_path)

        assert registry.themes[0].file_path == str(nexus_file)
