"""Edge case and error handling tests for frontmatter parser."""

from pathlib import Path

import pytest

from poetry_mcp.errors import FrontmatterParseError
from poetry_mcp.parsers.frontmatter_parser import (
    estimate_syllables,
    extract_frontmatter,
    parse_poem_file,
)


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault structure."""
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


class TestFileErrors:
    """Test file reading error cases."""

    def test_file_not_found(self, temp_vault):
        """Test FileNotFoundError when file doesn't exist."""
        nonexistent = temp_vault / "nonexistent.md"

        with pytest.raises(FileNotFoundError, match="Poem file not found"):
            parse_poem_file(nonexistent, temp_vault)

    def test_file_read_error(self, temp_vault):
        """Test read error handling with invalid encoding."""
        # Create a file with invalid UTF-8 bytes
        bad_file = temp_vault / "bad_encoding.md"
        bad_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        with pytest.raises(FrontmatterParseError, match="Failed to read"):
            parse_poem_file(bad_file, temp_vault)


class TestPathHandling:
    """Test path handling edge cases."""

    def test_file_outside_vault(self, tmp_path):
        """Test handling when file is outside vault root."""
        vault = tmp_path / "vault"
        vault.mkdir()

        outside_file = tmp_path / "outside.md"
        outside_file.write_text(
            """---
state: completed
form: free_verse
---

# Outside Poem

Content here"""
        )

        # File outside vault should use absolute path
        poem = parse_poem_file(outside_file, vault)
        assert poem.file_path == str(outside_file)

    def test_file_relative_to_vault(self, temp_vault):
        """Test relative path when file is inside vault."""
        catalog = temp_vault / "catalog"
        catalog.mkdir()

        poem_file = catalog / "poem.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
---

# Inside Poem

Content here"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.file_path == "catalog/poem.md"


class TestLegacyTagFormats:
    """Test legacy comma-separated tag handling."""

    def test_comma_separated_tags(self, temp_vault):
        """Test parsing legacy comma-separated tags."""
        poem_file = temp_vault / "legacy.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags: water, fire, nature
---

# Legacy Tags

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.tags == ["water", "fire", "nature"]

    def test_comma_separated_tags_with_spaces(self, temp_vault):
        """Test parsing tags with extra spaces."""
        poem_file = temp_vault / "spaces.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags:  water ,  fire  , nature
---

# Spaced Tags

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.tags == ["water", "fire", "nature"]

    def test_comma_separated_empty_tags(self, temp_vault):
        """Test handling empty tags in comma-separated list."""
        poem_file = temp_vault / "empty.md"
        poem_file.write_text(
            """---
state: completed
form: free_verse
tags: water,, , fire,
---

# Empty Tags

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.tags == ["water", "fire"]


class TestStateInference:
    """Test state inference from directory paths."""

    def test_infer_completed_state(self, temp_vault):
        """Test inferring 'completed' state from path."""
        completed_dir = temp_vault / "catalog" / "completed"
        completed_dir.mkdir(parents=True)

        poem_file = completed_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# No State Specified

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "completed"

    def test_infer_fledgeling_state(self, temp_vault):
        """Test inferring 'fledgeling' state from path."""
        fledge_dir = temp_vault / "catalog" / "fledgeling"
        fledge_dir.mkdir(parents=True)

        poem_file = fledge_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Fledgeling

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "fledgeling"

    def test_infer_still_cooking_state(self, temp_vault):
        """Test inferring 'still_cooking' state from path."""
        cooking_dir = temp_vault / "catalog" / "still cooking"
        cooking_dir.mkdir(parents=True)

        poem_file = cooking_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Still Cooking

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "still_cooking"

    def test_infer_still_cooking_hyphenated(self, temp_vault):
        """Test inferring 'still_cooking' from hyphenated path."""
        cooking_dir = temp_vault / "catalog" / "still-cooking"
        cooking_dir.mkdir(parents=True)

        poem_file = cooking_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Still Cooking Hyphenated

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "still_cooking"

    def test_infer_needs_research_state(self, temp_vault):
        """Test inferring 'needs_research' state from path."""
        research_dir = temp_vault / "catalog" / "needs research"
        research_dir.mkdir(parents=True)

        poem_file = research_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Needs Research

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "needs_research"

    def test_infer_risk_state(self, temp_vault):
        """Test inferring 'risk' state from path."""
        risk_dir = temp_vault / "catalog" / "risk"
        risk_dir.mkdir(parents=True)

        poem_file = risk_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Risk

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "risk"

    def test_infer_default_fledgeling(self, temp_vault):
        """Test default to 'fledgeling' for unknown directories."""
        unknown_dir = temp_vault / "catalog" / "unknown_state"
        unknown_dir.mkdir(parents=True)

        poem_file = unknown_dir / "poem.md"
        poem_file.write_text(
            """---
form: free_verse
---

# Unknown State

Content"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.state == "fledgeling"


class TestFormDetection:
    """Test heuristic form detection."""

    def test_detect_empty_content_as_free_verse(self, temp_vault):
        """Test empty content defaults to free_verse."""
        poem_file = temp_vault / "empty.md"
        poem_file.write_text(
            """---
state: completed
---

# Empty Poem
"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.form == "free_verse"

    def test_detect_american_sentence_17_syllables(self, temp_vault):
        """Test detecting american_sentence with ~17 syllables."""
        poem_file = temp_vault / "american.md"
        poem_file.write_text(
            """---
state: completed
---

# American Sentence

Just seventeen syllables exactly in this single long line here"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.form == "american_sentence"

    def test_detect_prose_poem_long_lines(self, temp_vault):
        """Test detecting prose_poem with long lines."""
        poem_file = temp_vault / "prose.md"
        poem_file.write_text(
            """---
state: completed
---

# Prose Poem

This is a very long prose line that goes on and on and on without any line breaks creating a paragraph-like structure that should be detected as a prose poem format.
Another very long prose line that continues the paragraph format with lots of words and no traditional line breaks like you would see in verse poetry."""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.form == "prose_poem"

    def test_detect_catalog_poem_anaphora(self, temp_vault):
        """Test detecting catalog_poem with repeated line starts."""
        poem_file = temp_vault / "catalog.md"
        poem_file.write_text(
            """---
state: completed
---

# Catalog Poem

Water in the river
Water in the rain
Water in the ocean
Water in my veins"""
        )

        poem = parse_poem_file(poem_file, temp_vault)
        assert poem.form == "catalog_poem"


class TestSyllableEstimation:
    """Test syllable estimation for american_sentence detection."""

    def test_estimate_syllables_simple(self):
        """Test syllable estimation for simple words."""
        assert estimate_syllables("water") == 2
        assert estimate_syllables("fire") == 1  # fi-re → silent e = 1
        assert estimate_syllables("nature") == 2

    def test_estimate_syllables_silent_e(self):
        """Test syllable estimation handles silent 'e'."""
        assert estimate_syllables("time") == 1  # ti-me → 2, minus silent e = 1
        assert estimate_syllables("love") == 1  # lo-ve → 2, minus silent e = 1

    def test_estimate_syllables_sentence(self):
        """Test syllable estimation for full sentence."""
        # "Just seventeen syllables here" = 7 syllables
        text = "Just seventeen syllables here"
        count = estimate_syllables(text)
        assert 6 <= count <= 8  # Allow some variance in estimation

    def test_estimate_syllables_punctuation(self):
        """Test syllable estimation removes punctuation."""
        assert estimate_syllables("water,") == 2
        assert estimate_syllables("fire!") == 1  # fi-re → silent e = 1
        assert estimate_syllables("nature.") == 2


class TestExtractFrontmatter:
    """Test frontmatter extraction edge cases."""

    def test_extract_no_frontmatter(self):
        """Test extracting from content with no frontmatter."""
        content = "# Just a heading\n\nSome content"
        frontmatter, poem_content = extract_frontmatter(content, Path("test.md"))

        assert frontmatter == {}
        assert "Just a heading" in poem_content

    def test_extract_empty_frontmatter(self):
        """Test extracting empty frontmatter."""
        content = """---
---

# Heading

Content"""
        frontmatter, poem_content = extract_frontmatter(content, Path("test.md"))

        assert frontmatter == {}
        assert "Heading" in poem_content

    def test_extract_frontmatter_with_content(self):
        """Test normal frontmatter extraction."""
        content = """---
state: completed
form: free_verse
---

# Poem

Content here"""
        frontmatter, poem_content = extract_frontmatter(content, Path("test.md"))

        assert frontmatter["state"] == "completed"
        assert frontmatter["form"] == "free_verse"
        assert "Content here" in poem_content
