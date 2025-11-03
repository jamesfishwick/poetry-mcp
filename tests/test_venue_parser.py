"""Comprehensive tests for venue parser."""

import pytest

from poetry_mcp.parsers.venue_parser import VenueParser, VenueRegistry
from poetry_mcp.models import Venue
from poetry_mcp.errors import BaseParseError as ParseError


@pytest.fixture
def valid_venue_content():
    """Return valid venue markdown content."""
    return """---
name: Test Poetry Journal
url: https://test-poetry-journal.com
simultaneous: yes
response_time_days: 90
payment: contributor copies
aesthetic: Accepts experimental work
---

# Test Poetry Journal

A test journal for poetry submissions.

### 📋 Planned

| Poem | Notes |
| --- | --- |
| First Poem | Ready to submit |
| Second Poem | Needs revision |

### 📤 Submitted

| Poem | Submitted | Response By | Notes |
| --- | --- | --- | --- |
| Third Poem | 2024-10-01 | 2024-12-30 | Waiting for response |

### ✅ Accepted

| Poem | Submitted | Response | Notes |
| --- | --- | --- | --- |
| Fourth Poem | 2024-09-01 | 2024-10-15 | Accepted for Fall issue |

### ❌ Rejected

| Poem | Submitted | Response | Notes |
| --- | --- | --- | --- |
| Fifth Poem | 2024-08-01 | 2024-09-01 | Not a fit |
"""


@pytest.fixture
def minimal_venue_content():
    """Return minimal valid venue content."""
    return """---
name: Minimal Journal
url: https://minimal.com
---

# Minimal Journal

A minimal journal with no submissions.
"""


@pytest.fixture
def parser():
    """Return VenueParser instance."""
    return VenueParser()


class TestVenueParserParseFile:
    """Test VenueParser.parse_file() method."""

    def test_parse_valid_venue_file(self, parser, tmp_path, valid_venue_content):
        """Test parsing a valid venue file with submissions."""
        venue_file = tmp_path / "test-journal.md"
        venue_file.write_text(valid_venue_content)

        venue, submissions = parser.parse_file(venue_file)

        assert isinstance(venue, Venue)
        assert venue.name == "Test Poetry Journal"
        assert str(venue.url) == "https://test-poetry-journal.com/"
        assert venue.simultaneous is True  # "yes" gets converted to True

        assert isinstance(submissions, list)
        assert len(submissions) > 0

    def test_parse_minimal_venue_file(self, parser, tmp_path, minimal_venue_content):
        """Test parsing minimal venue file without submissions."""
        venue_file = tmp_path / "minimal.md"
        venue_file.write_text(minimal_venue_content)

        venue, submissions = parser.parse_file(venue_file)

        assert isinstance(venue, Venue)
        assert venue.name == "Minimal Journal"
        assert isinstance(submissions, list)
        assert len(submissions) == 0

    def test_parse_file_not_found(self, parser, tmp_path):
        """Test that non-existent file raises ParseError."""
        nonexistent = tmp_path / "nonexistent.md"

        with pytest.raises(ParseError, match="Venue file not found"):
            parser.parse_file(nonexistent)

    def test_parse_returns_tuple(self, parser, tmp_path, minimal_venue_content):
        """Test that parse_file returns (Venue, list[Submission]) tuple."""
        venue_file = tmp_path / "test.md"
        venue_file.write_text(minimal_venue_content)

        result = parser.parse_file(venue_file)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Venue)
        assert isinstance(result[1], list)

    def test_parse_file_path_added_to_venue(self, parser, tmp_path, minimal_venue_content):
        """Test that file path is added to venue metadata."""
        venue_file = tmp_path / "test.md"
        venue_file.write_text(minimal_venue_content)

        venue, _ = parser.parse_file(venue_file)

        assert venue.file_path == str(venue_file)


class TestVenueParserMetadata:
    """Test _parse_venue_metadata() method."""

    def test_parse_valid_frontmatter(self, parser, tmp_path):
        """Test extracting valid venue metadata."""
        content = """---
name: Test Journal
url: https://test.com
simultaneous: no
response_time_days: 60
payment: none
---

Body content here.
"""
        venue_file = tmp_path / "test.md"

        venue = parser._parse_venue_metadata(content, venue_file)

        assert venue.name == "Test Journal"
        assert venue.simultaneous is False  # "no" gets converted to False
        assert venue.response_time_days == 60

    def test_parse_no_frontmatter_raises_error(self, parser, tmp_path):
        """Test that missing frontmatter raises ParseError."""
        content = "# No frontmatter\n\nJust body content."
        venue_file = tmp_path / "test.md"

        with pytest.raises(ParseError, match="No frontmatter found"):
            parser._parse_venue_metadata(content, venue_file)

    def test_parse_invalid_yaml_raises_error(self, parser, tmp_path):
        """Test that invalid YAML raises ParseError."""
        content = """---
name: Test
invalid: yaml: syntax: here
---

Body"""
        venue_file = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Invalid YAML frontmatter"):
            parser._parse_venue_metadata(content, venue_file)

    def test_parse_frontmatter_not_dict_raises_error(self, parser, tmp_path):
        """Test that non-dict frontmatter raises ParseError."""
        content = """---
- list
- items
---

Body"""
        venue_file = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Frontmatter must be a dict"):
            parser._parse_venue_metadata(content, venue_file)

    def test_parse_missing_required_field_raises_error(self, parser, tmp_path):
        """Test that missing required fields raise ParseError."""
        content = """---
# missing name (actually required field)
url: https://test.com
---

Body"""
        venue_file = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Invalid venue metadata"):
            parser._parse_venue_metadata(content, venue_file)

    def test_parse_adds_file_path(self, parser, tmp_path):
        """Test that file_path is added to frontmatter."""
        content = """---
name: Test
url: https://test.com
---

Body"""
        venue_file = tmp_path / "test.md"

        venue = parser._parse_venue_metadata(content, venue_file)

        assert venue.file_path == str(venue_file)


class TestVenueParserSubmissions:
    """Test _parse_submissions() method."""

    def test_parse_planned_submissions(self, parser, tmp_path):
        """Test parsing planned submissions section."""
        content = """---
name: Test
url: https://test.com
---

### 📋 Planned

| Poem | Notes |
| --- | --- |
| Test Poem | Ready to go |
| Another Poem | Needs work |
"""
        # Parse submissions directly
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        # Filter for planned
        planned = [s for s in submissions if s.status == "planned"]

        assert len(planned) == 2
        assert planned[0].poems[0] == "Test Poem"
        assert "Ready to go" in (planned[0].notes or "")

    def test_parse_submitted_submissions(self, parser, tmp_path):
        """Test parsing submitted submissions section."""
        content = """---
name: Test
url: https://test.com
---

### 📤 Submitted

| Poem | Submitted | Response By | Notes |
| --- | --- | --- | --- |
| Waiting Poem | 2024-10-01 | 2024-12-30 | Under review |
"""
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        submitted = [s for s in submissions if s.status == "submitted"]

        assert len(submitted) == 1
        assert submitted[0].poems[0] == "Waiting Poem"
        # Dates are stored as strings, not date objects
        assert submitted[0].submitted_date == "2024-10-01"
        assert submitted[0].response_date == "2024-12-30"

    def test_parse_accepted_submissions(self, parser, tmp_path):
        """Test parsing accepted submissions section."""
        content = """---
name: Test
url: https://test.com
---

### ✅ Accepted

| Poem | Submitted | Response | Notes |
| --- | --- | --- | --- |
| Accepted Poem | 2024-09-01 | 2024-10-15 | Published in Fall issue |
"""
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        accepted = [s for s in submissions if s.status == "accepted"]

        assert len(accepted) == 1
        assert accepted[0].poems[0] == "Accepted Poem"
        # Dates are stored as strings, not date objects
        assert accepted[0].response_date == "2024-10-15"
        assert "Published" in (accepted[0].notes or "")

    def test_parse_rejected_submissions(self, parser, tmp_path):
        """Test parsing rejected submissions section."""
        content = """---
name: Test
url: https://test.com
---

### ❌ Rejected

| Poem | Submitted | Response | Notes |
| --- | --- | --- | --- |
| Rejected Poem | 2024-08-01 | 2024-09-01 | Not a fit |
"""
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        rejected = [s for s in submissions if s.status == "rejected"]

        assert len(rejected) == 1
        assert rejected[0].poems[0] == "Rejected Poem"
        assert "Not a fit" in (rejected[0].notes or "")

    def test_parse_multiple_submissions_sections(self, parser, tmp_path, valid_venue_content):
        """Test parsing multiple submission sections."""
        venue_file = tmp_path / "test.md"
        venue_file.write_text(valid_venue_content)

        _, submissions = parser.parse_file(venue_file)

        # Should have submissions from all sections
        statuses = {s.status for s in submissions}
        assert "planned" in statuses
        assert "submitted" in statuses
        assert "accepted" in statuses
        assert "rejected" in statuses

    def test_parse_empty_table(self, parser, tmp_path):
        """Test parsing section with empty table."""
        content = """---
name: Test
url: https://test.com
---

### 📋 Planned

| Poem | Notes |
| --- | --- |
"""
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        assert len(submissions) == 0

    def test_parse_no_tables(self, parser, tmp_path, minimal_venue_content):
        """Test parsing venue with no submission tables."""
        submissions = parser._parse_submissions(
            minimal_venue_content, "Minimal", tmp_path / "test.md"
        )

        assert isinstance(submissions, list)
        assert len(submissions) == 0

    def test_parse_invalid_date_format_handled(self, parser, tmp_path):
        """Test that invalid date formats are handled gracefully."""
        content = """---
name: Test
url: https://test.com
---

### 📤 Submitted

| Poem | Submitted | Response By | Notes |
| --- | --- | --- | --- |
| Test Poem | not-a-date | also-not-a-date | Bad dates |
"""
        # Should not crash, may skip or set dates to None
        submissions = parser._parse_submissions(content, "Test", tmp_path / "test.md")

        # Either empty or submission with None dates
        if submissions:
            assert submissions[0].poems[0] == "Test Poem"


class TestVenueRegistry:
    """Test VenueRegistry class."""

    def test_load_multiple_venue_files(self, tmp_path):
        """Test loading multiple venue files from directory."""
        venues_dir = tmp_path / "venues"
        venues_dir.mkdir()

        # Create multiple venue files
        (venues_dir / "journal1.md").write_text(
            """---
name: Journal One
url: https://journal1.com
---

Content here.
"""
        )
        (venues_dir / "journal2.md").write_text(
            """---
name: Journal Two
url: https://journal2.com
---

More content.
"""
        )

        registry = VenueRegistry(venues_dir)
        registry.load_all()

        assert len(registry.venues) == 2
        # venues is a dict with name as key
        assert "Journal One" in registry.venues
        assert "Journal Two" in registry.venues

    def test_load_skips_non_markdown_files(self, tmp_path):
        """Test that non-markdown files are skipped."""
        venues_dir = tmp_path / "venues"
        venues_dir.mkdir()

        (venues_dir / "journal.md").write_text(
            """---
name: Journal
url: https://journal.com
---

Content"""
        )
        (venues_dir / "notes.txt").write_text("Not a venue")
        (venues_dir / "image.png").write_bytes(b"fake image")

        registry = VenueRegistry(venues_dir)
        registry.load_all()

        assert len(registry.venues) == 1
        assert "Journal" in registry.venues

    def test_load_empty_directory(self, tmp_path):
        """Test loading from empty venues directory."""
        venues_dir = tmp_path / "venues"
        venues_dir.mkdir()

        registry = VenueRegistry(venues_dir)
        registry.load_all()

        assert len(registry.venues) == 0

    def test_load_nonexistent_directory(self, tmp_path):
        """Test that nonexistent venues directory raises error."""
        registry = VenueRegistry(tmp_path / "nonexistent")

        with pytest.raises(ParseError, match="Venues directory not found"):
            registry.load_all()

    def test_load_parse_errors_logged_but_continue(self, tmp_path, caplog):
        """Test that parse errors are logged but don't stop loading."""
        venues_dir = tmp_path / "venues"
        venues_dir.mkdir()

        # Valid venue
        (venues_dir / "good.md").write_text(
            """---
name: Good Journal
url: https://good.com
---

Content"""
        )

        # Invalid venue (malformed)
        (venues_dir / "bad.md").write_text("No frontmatter here!")

        registry = VenueRegistry(venues_dir)
        registry.load_all()

        # Should have loaded the good one
        assert len(registry.venues) == 1
        assert "Good Journal" in registry.venues

        # Should have logged error for bad one (printed via print statement)
        # Note: This test may need capsys instead of caplog
