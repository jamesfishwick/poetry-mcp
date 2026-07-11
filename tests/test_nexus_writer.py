"""Tests for NexusWriter class.

This module tests the nexus markdown file generation functionality,
including frontmatter generation, template creation, and filename generation.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from poetry_mcp.models.nexus import Nexus
from poetry_mcp.writers.nexus_writer import NexusWriter


class TestNexusWriter:
    """Test suite for NexusWriter."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        """Create a NexusWriter instance."""
        return NexusWriter()

    @pytest.fixture
    def theme_nexus(self) -> Nexus:
        """Create a sample theme nexus for testing."""
        return Nexus(
            name="Water-Liquid Imagery",
            category="theme",
            description="Water, blood, beer, tears - liquids as transformation",
            canonical_tag="water",
        )

    @pytest.fixture
    def motif_nexus(self) -> Nexus:
        """Create a sample motif nexus for testing."""
        return Nexus(
            name="American Grotesque",
            category="motif",
            description="Bodies consuming beyond capacity, spiritual hunger and material satiation",
            canonical_tag="american-grotesque",
        )

    @pytest.fixture
    def form_nexus(self) -> Nexus:
        """Create a sample form nexus for testing."""
        return Nexus(
            name="American Sentence",
            category="form",
            description="One line, exactly 17 syllables - Ginsberg's American answer to haiku",
            canonical_tag="american-sentence",
        )


class TestGenerateFrontmatter:
    """Test frontmatter generation."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_frontmatter_with_canonical_tag(self, writer: NexusWriter) -> None:
        """Test frontmatter includes canonical tag."""
        nexus = Nexus(
            name="Water-Liquid Imagery",
            category="theme",
            description="Water imagery theme",
            canonical_tag="water",
        )

        frontmatter = writer._generate_frontmatter(nexus)

        assert frontmatter.startswith("---\n")
        assert frontmatter.endswith("---")
        assert "canonical_tag: water" in frontmatter

    def test_frontmatter_without_canonical_tag(self, writer: NexusWriter) -> None:
        """Test frontmatter when no canonical tag is set."""
        nexus = Nexus(
            name="Test Theme",
            category="theme",
            description="Test description",
            canonical_tag=None,
        )

        frontmatter = writer._generate_frontmatter(nexus)

        # Should still have canonical_tag key even if None
        assert "canonical_tag:" in frontmatter


class TestGenerateDefaultTemplate:
    """Test default template generation."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_theme_template(self, writer: NexusWriter) -> None:
        """Test default template for theme category."""
        nexus = Nexus(
            name="Water-Liquid Imagery",
            category="theme",
            description="Water, blood, tears - liquids as transformation",
            canonical_tag="water",
        )

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            template = writer._generate_default_template(nexus)

        assert "# Water-Liquid Imagery" in template
        assert "## Overview" in template
        assert "Water, blood, tears - liquids as transformation" in template
        assert "## Key Appearances" in template
        assert "### Connection to Other Themes" in template  # Uses "Theme" for theme category
        assert "#theme" in template
        assert "Created: 2025-01-26" in template

    def test_motif_template(self, writer: NexusWriter) -> None:
        """Test default template for motif category."""
        nexus = Nexus(
            name="American Grotesque",
            category="motif",
            description="Bodies consuming beyond capacity",
            canonical_tag="american-grotesque",
        )

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            template = writer._generate_default_template(nexus)

        assert "# American Grotesque" in template
        assert "Bodies consuming beyond capacity" in template
        assert "### Connection to Other Motifs" in template  # Uses "Motif" for motif category
        assert "#motif" in template

    def test_form_template(self, writer: NexusWriter) -> None:
        """Test default template for form category."""
        nexus = Nexus(
            name="American Sentence",
            category="form",
            description="One line, exactly 17 syllables",
            canonical_tag="american-sentence",
        )

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            template = writer._generate_default_template(nexus)

        assert "# American Sentence" in template
        assert "One line, exactly 17 syllables" in template
        assert "### Connection to Other Forms" in template  # Uses "Form" for form category
        assert "#form" in template


class TestGetTodayIso:
    """Test ISO date generation."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_returns_iso_format(self, writer: NexusWriter) -> None:
        """Test that date is in ISO format."""
        result = writer._get_today_iso()

        # Should be a string in ISO format (YYYY-MM-DD)
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD
        # Verify it matches ISO date pattern
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # Year
        assert len(parts[1]) == 2  # Month
        assert len(parts[2]) == 2  # Day


class TestGetNexusFilename:
    """Test filename generation."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_theme_adds_imagery_suffix(self, writer: NexusWriter) -> None:
        """Test that theme names get ' Imagery' suffix if not present."""
        result = writer.get_nexus_filename("Water-Liquid", "theme")
        assert result == "Water-Liquid Imagery.md"

    def test_theme_preserves_existing_imagery_suffix(self, writer: NexusWriter) -> None:
        """Test that theme names with ' Imagery' don't get double suffix."""
        result = writer.get_nexus_filename("Water-Liquid Imagery", "theme")
        assert result == "Water-Liquid Imagery.md"

    def test_motif_no_suffix(self, writer: NexusWriter) -> None:
        """Test that motif names don't get suffix."""
        result = writer.get_nexus_filename("American Grotesque", "motif")
        assert result == "American Grotesque.md"

    def test_form_no_suffix(self, writer: NexusWriter) -> None:
        """Test that form names don't get suffix."""
        result = writer.get_nexus_filename("American Sentence", "form")
        assert result == "American Sentence.md"


class TestGenerateNexusFile:
    """Test complete nexus file generation."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_generate_new_nexus_file(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test generating a new nexus file."""
        nexus = Nexus(
            name="Test Theme",
            category="theme",
            description="A test theme for unit testing",
            canonical_tag="test-theme",
        )
        output_path = tmp_path / "nexus" / "themes" / "test_theme.md"

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            writer.generate_nexus_file(nexus, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # Frontmatter
        assert "---\n" in content
        assert "canonical_tag: test-theme" in content

        # Content
        assert "# Test Theme" in content
        assert "A test theme for unit testing" in content
        assert "## Overview" in content
        assert "## Key Appearances" in content

    def test_generate_with_custom_template(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test generating nexus file with custom template."""
        nexus = Nexus(
            name="Custom Nexus",
            category="motif",
            description="Custom description",
            canonical_tag="custom",
        )
        output_path = tmp_path / "custom_nexus.md"

        custom_template = """# Custom Template

This is my custom content.

## My Custom Section

- Item 1
- Item 2
"""

        writer.generate_nexus_file(nexus, output_path, template=custom_template)

        content = output_path.read_text()

        # Should have frontmatter
        assert "canonical_tag: custom" in content

        # Should have custom template, not default
        assert "# Custom Template" in content
        assert "This is my custom content." in content
        assert "## My Custom Section" in content

        # Should NOT have default template sections
        assert "## Overview" not in content

    def test_generate_creates_parent_directories(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        nexus = Nexus(
            name="Deep Nexus",
            category="form",
            description="Deeply nested nexus",
            canonical_tag="deep",
        )
        output_path = tmp_path / "deep" / "nested" / "path" / "nexus.md"

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            writer.generate_nexus_file(nexus, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_generate_overwrites_existing_file(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test that generating overwrites existing file."""
        output_path = tmp_path / "existing.md"
        output_path.write_text("Old content that should be replaced")

        nexus = Nexus(
            name="New Nexus",
            category="theme",
            description="New content",
            canonical_tag="new",
        )

        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            writer.generate_nexus_file(nexus, output_path)

        content = output_path.read_text()

        assert "Old content" not in content
        assert "# New Nexus" in content
        assert "canonical_tag: new" in content


class TestNexusWriterIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def writer(self) -> NexusWriter:
        return NexusWriter()

    def test_complete_theme_workflow(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test creating a complete theme nexus file."""
        nexus = Nexus(
            name="Water-Liquid Imagery",
            category="theme",
            description="Water, blood, beer, tears - liquids as transformation and dissolution",
            canonical_tag="water",
        )

        # Generate filename
        filename = writer.get_nexus_filename(nexus.name, nexus.category)
        assert filename == "Water-Liquid Imagery.md"

        # Generate file
        output_path = tmp_path / "themes" / filename
        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            writer.generate_nexus_file(nexus, output_path)

        # Verify complete file
        assert output_path.exists()
        content = output_path.read_text()

        # Check all expected sections
        assert "---" in content  # Frontmatter delimiters
        assert "canonical_tag: water" in content
        assert "# Water-Liquid Imagery" in content
        assert "## Overview" in content
        assert "Water, blood, beer, tears" in content
        assert "## Key Appearances" in content
        assert "## Analysis" in content
        assert "### Connection to Other Themes" in content
        assert "#theme" in content
        assert "Created: 2025-01-26" in content

    def test_complete_form_workflow(self, writer: NexusWriter, tmp_path: Path) -> None:
        """Test creating a complete form nexus file."""
        nexus = Nexus(
            name="Sonnet",
            category="form",
            description="14-line poem with specific rhyme scheme and volta",
            canonical_tag="sonnet",
        )

        # Generate filename (forms don't get Imagery suffix)
        filename = writer.get_nexus_filename(nexus.name, nexus.category)
        assert filename == "Sonnet.md"

        # Generate file
        output_path = tmp_path / "forms" / filename
        with patch.object(writer, "_get_today_iso", return_value="2025-01-26"):
            writer.generate_nexus_file(nexus, output_path)

        content = output_path.read_text()

        assert "canonical_tag: sonnet" in content
        assert "# Sonnet" in content
        assert "14-line poem" in content
        assert "### Connection to Other Forms" in content
        assert "#form" in content
