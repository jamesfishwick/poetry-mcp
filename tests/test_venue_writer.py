"""Tests for VenueWriter class.

This module tests the venue markdown file generation functionality,
including frontmatter generation, submission tables, and notes preservation.
"""

from datetime import date
from pathlib import Path

import pytest

from poetry_mcp.models.submission import Submission
from poetry_mcp.models.venue import Venue
from poetry_mcp.writers.venue_writer import VenueWriter


class TestVenueWriter:
    """Test suite for VenueWriter."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        """Create a VenueWriter instance."""
        return VenueWriter()

    @pytest.fixture
    def sample_venue(self) -> Venue:
        """Create a sample venue for testing."""
        return Venue(
            name="Test Magazine",
            payment="$50/poem",
            response_time_days=90,
            simultaneous=True,
            aesthetic="Contemporary poetry with strong imagery",
            url="https://testmagazine.com",
            submission_format="Up to 5 poems, max 10 pages",
            submission_frequency="Year-round",
        )

    @pytest.fixture
    def minimal_venue(self) -> Venue:
        """Create a minimal venue with only required fields."""
        return Venue(name="Minimal Venue")

    @pytest.fixture
    def sample_submissions(self) -> list[Submission]:
        """Create sample submissions with various statuses."""
        return [
            Submission(
                venue_name="Test Magazine",
                poems=["Poem A", "Poem B"],
                status="planned",
                submitted=False,
                due_date=date(2025, 12, 1),
                cost="$3",
                notes="First batch",
            ),
            Submission(
                venue_name="Test Magazine",
                poems=["Poem C"],
                status="submitted",
                submitted=True,
                submitted_date=date(2025, 10, 15),
                response_date=date(2026, 1, 15),
                cost="free",
            ),
            Submission(
                venue_name="Test Magazine",
                poems=["Poem D", "Poem E"],
                status="accepted",
                submitted=True,
                submitted_date=date(2025, 8, 1),
                response_date=date(2025, 9, 15),
            ),
            Submission(
                venue_name="Test Magazine",
                poems=["Poem F"],
                status="rejected",
                submitted=True,
                submitted_date=date(2025, 7, 1),
                response_date=date(2025, 10, 1),
                notes="Form rejection",
            ),
            Submission(
                venue_name="Test Magazine",
                poems=["Poem G"],
                status="withdrawn",
                submitted=True,
                submitted_date=date(2025, 6, 1),
                response_date=date(2025, 6, 15),
            ),
        ]


class TestGenerateFrontmatter:
    """Test frontmatter generation."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_full_frontmatter(self, writer: VenueWriter) -> None:
        """Test frontmatter with all fields populated."""
        venue = Venue(
            name="Palette Poetry",
            payment="$50/poem",
            response_time_days=90,
            simultaneous="yes",
            aesthetic="Innovative poetry, marginalized voices",
            url="https://palettepoetry.com",
            submission_format="Up to 5 poems",
            submission_frequency="Year-round",
        )

        frontmatter = writer._generate_frontmatter(venue)

        assert frontmatter.startswith("---\n")
        assert frontmatter.endswith("---")
        assert "name: Palette Poetry" in frontmatter
        assert "payment: $50/poem" in frontmatter
        assert "response_time_days: 90" in frontmatter
        assert "simultaneous: 'yes'" in frontmatter or "simultaneous: yes" in frontmatter
        assert "aesthetic:" in frontmatter
        assert "url: https://palettepoetry.com" in frontmatter
        assert "submission_format:" in frontmatter
        assert "submission_frequency:" in frontmatter

    def test_minimal_frontmatter(self, writer: VenueWriter) -> None:
        """Test frontmatter with only required fields."""
        venue = Venue(name="Simple Venue")

        frontmatter = writer._generate_frontmatter(venue)

        assert "---\n" in frontmatter
        assert "name: Simple Venue" in frontmatter
        # Optional fields should not appear
        assert "payment:" not in frontmatter
        assert "response_time_days:" not in frontmatter
        assert "simultaneous:" not in frontmatter

    def test_boolean_simultaneous(self, writer: VenueWriter) -> None:
        """Test frontmatter with boolean simultaneous value."""
        venue = Venue(name="Bool Venue", simultaneous=False)

        frontmatter = writer._generate_frontmatter(venue)

        assert "simultaneous: false" in frontmatter


class TestGenerateSubmissionTables:
    """Test submission table generation."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_tables_with_all_statuses(self, writer: VenueWriter) -> None:
        """Test generating tables with submissions in all status groups."""
        submissions = [
            Submission(venue_name="Test", poems=["A"], status="planned", due_date="2025-12-01"),
            Submission(venue_name="Test", poems=["B"], status="submitted", submitted=True, submitted_date="2025-10-01"),
            Submission(venue_name="Test", poems=["C"], status="accepted", submitted=True, submitted_date="2025-09-01", response_date="2025-11-01"),
            Submission(venue_name="Test", poems=["D"], status="rejected", submitted=True, submitted_date="2025-08-01", response_date="2025-10-01"),
            Submission(venue_name="Test", poems=["E"], status="withdrawn", submitted=True, submitted_date="2025-07-01", response_date="2025-07-15"),
        ]

        tables = writer._generate_submission_tables(submissions)

        assert "# Test" in tables
        assert "## Submissions" in tables
        # Section headers include emojis
        assert "Planned" in tables
        assert "Submitted (Pending Response)" in tables
        assert "Accepted" in tables
        assert "Rejected" in tables
        assert "Withdrawn" in tables
        assert "## Notes" in tables
        assert "[[A]]" in tables
        assert "[[B]]" in tables
        assert "[[C]]" in tables

    def test_tables_with_preserved_notes(self, writer: VenueWriter) -> None:
        """Test that preserved notes are included."""
        submissions = [
            Submission(venue_name="Test", poems=["A"], status="planned"),
        ]

        preserved_notes = "This is my custom notes content."
        tables = writer._generate_submission_tables(submissions, preserved_notes)

        assert "This is my custom notes content." in tables
        assert "_Add venue-specific observations" not in tables

    def test_tables_with_default_notes(self, writer: VenueWriter) -> None:
        """Test default notes message when no preserved notes."""
        submissions = [
            Submission(venue_name="Test", poems=["A"], status="planned"),
        ]

        tables = writer._generate_submission_tables(submissions)

        assert "_Add venue-specific observations, research, or strategy notes here_" in tables

    def test_empty_status_groups_not_shown(self, writer: VenueWriter) -> None:
        """Test that empty status groups are not rendered."""
        submissions = [
            Submission(venue_name="Test", poems=["A"], status="submitted", submitted=True),
        ]

        tables = writer._generate_submission_tables(submissions)

        assert "Submitted (Pending Response)" in tables
        # These should not appear since no submissions in these statuses
        assert "Planned" not in tables
        assert "Accepted" not in tables
        assert "Rejected" not in tables


class TestFormatSubmissionTable:
    """Test individual submission table formatting."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_planned_table_format(self, writer: VenueWriter) -> None:
        """Test table format for planned submissions."""
        submissions = [
            Submission(
                venue_name="Test",
                poems=["Poem A", "Poem B"],
                status="planned",
                due_date=date(2025, 12, 1),
                cost="$5",
                notes="Test notes",
            ),
        ]

        table = writer._format_submission_table(submissions, "planned")

        assert "| Poems | Due Date | Cost | Notes |" in table
        assert "[[Poem A]], [[Poem B]]" in table
        assert "2025-12-01" in table
        assert "$5" in table
        assert "Test notes" in table

    def test_submitted_table_format(self, writer: VenueWriter) -> None:
        """Test table format for submitted submissions."""
        submissions = [
            Submission(
                venue_name="Test",
                poems=["Poem C"],
                status="submitted",
                submitted=True,
                submitted_date=date(2025, 10, 15),
                response_date=date(2026, 1, 15),
                cost="free",
            ),
        ]

        table = writer._format_submission_table(submissions, "submitted")

        assert "| Poems | Submitted | Expected Response | Cost | Notes |" in table
        assert "[[Poem C]]" in table
        assert "2025-10-15" in table
        assert "2026-01-15" in table
        assert "free" in table

    def test_accepted_table_format(self, writer: VenueWriter) -> None:
        """Test table format for accepted submissions."""
        submissions = [
            Submission(
                venue_name="Test",
                poems=["Poem D"],
                status="accepted",
                submitted=True,
                submitted_date=date(2025, 8, 1),
                response_date=date(2025, 9, 15),
            ),
        ]

        table = writer._format_submission_table(submissions, "accepted")

        assert "| Poems | Submitted | Response Date | Cost | Notes |" in table
        assert "[[Poem D]]" in table
        assert "2025-08-01" in table
        assert "2025-09-15" in table

    def test_empty_submissions(self, writer: VenueWriter) -> None:
        """Test formatting empty submission list."""
        table = writer._format_submission_table([], "planned")

        assert "_No submissions_" in table


class TestFormatSubmissionRow:
    """Test individual row formatting."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_planned_row_with_all_fields(self, writer: VenueWriter) -> None:
        """Test planned row with all fields populated."""
        sub = Submission(
            venue_name="Test",
            poems=["A", "B", "C"],
            status="planned",
            due_date=date(2025, 12, 1),
            cost="$3",
            notes="Good fit",
        )

        row = writer._format_submission_row(sub, "planned")

        assert "[[A]], [[B]], [[C]]" in row
        assert "2025-12-01" in row
        assert "$3" in row
        assert "Good fit" in row

    def test_row_with_missing_optional_fields(self, writer: VenueWriter) -> None:
        """Test row with missing optional fields shows dashes."""
        sub = Submission(
            venue_name="Test",
            poems=["Single"],
            status="planned",
        )

        row = writer._format_submission_row(sub, "planned")

        # Missing date, cost, notes should show as "-"
        assert "| - |" in row or "| - |" in row

    def test_submitted_row_format(self, writer: VenueWriter) -> None:
        """Test submitted row has expected response date column."""
        sub = Submission(
            venue_name="Test",
            poems=["Poem"],
            status="submitted",
            submitted=True,
            submitted_date=date(2025, 10, 1),
            response_date=date(2026, 1, 1),
            cost="free",
        )

        row = writer._format_submission_row(sub, "submitted")

        assert "2025-10-01" in row
        assert "2026-01-01" in row
        assert "free" in row


class TestFormatDate:
    """Test date formatting."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_date_object(self, writer: VenueWriter) -> None:
        """Test formatting a date object."""
        d = date(2025, 8, 15)
        result = writer._format_date(d)
        assert result == "2025-08-15"

    def test_string_date(self, writer: VenueWriter) -> None:
        """Test formatting a string date passthrough."""
        result = writer._format_date("2025-August")
        assert result == "2025-August"

    def test_none_date(self, writer: VenueWriter) -> None:
        """Test formatting None returns dash."""
        result = writer._format_date(None)
        assert result == "-"


class TestExtractNotesSection:
    """Test notes section extraction from existing files."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_extract_notes_from_file(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test extracting notes from existing venue file."""
        file_content = """---
name: Test Venue
---

# Test Venue

## Submissions

| Poems | Status |
|-------|--------|
| Test  | Planned |

## Notes

My custom notes about this venue.
They span multiple lines.
"""
        venue_file = tmp_path / "test_venue.md"
        venue_file.write_text(file_content)

        notes = writer._extract_notes_section(venue_file)

        assert notes is not None
        assert "My custom notes about this venue." in notes
        assert "They span multiple lines." in notes

    def test_extract_notes_default_message_returns_none(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test that default notes message returns None."""
        file_content = """---
name: Test Venue
---

## Notes

_Add venue-specific observations, research, or strategy notes here_
"""
        venue_file = tmp_path / "test_venue.md"
        venue_file.write_text(file_content)

        notes = writer._extract_notes_section(venue_file)

        assert notes is None

    def test_extract_notes_no_notes_section(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test file without notes section returns None."""
        file_content = """---
name: Test Venue
---

# Test Venue

## Submissions

Some content here.
"""
        venue_file = tmp_path / "test_venue.md"
        venue_file.write_text(file_content)

        notes = writer._extract_notes_section(venue_file)

        assert notes is None

    def test_extract_notes_file_not_exists(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test non-existent file returns None."""
        nonexistent = tmp_path / "nonexistent.md"

        notes = writer._extract_notes_section(nonexistent)

        assert notes is None


class TestGenerateVenueFile:
    """Test complete venue file generation."""

    @pytest.fixture
    def writer(self) -> VenueWriter:
        return VenueWriter()

    def test_generate_new_venue_file(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test generating a new venue file from scratch."""
        venue = Venue(
            name="New Venue",
            payment="$100/poem",
            response_time_days=60,
        )
        submissions = [
            Submission(
                venue_name="New Venue",
                poems=["Test Poem"],
                status="planned",
            ),
        ]
        output_path = tmp_path / "venues" / "new_venue.md"

        writer.generate_venue_file(venue, submissions, output_path)

        assert output_path.exists()
        content = output_path.read_text()

        # Frontmatter
        assert "---\n" in content
        assert "name: New Venue" in content
        assert "payment: $100/poem" in content
        assert "response_time_days: 60" in content

        # Submissions
        assert "# New Venue" in content
        assert "## Submissions" in content
        assert "[[Test Poem]]" in content

        # Notes
        assert "## Notes" in content

    def test_generate_overwrites_existing(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test that generating overwrites existing file."""
        output_path = tmp_path / "existing.md"
        output_path.write_text("Old content that should be replaced")

        venue = Venue(name="Updated Venue")
        submissions = [
            Submission(venue_name="Updated Venue", poems=["New Poem"], status="submitted", submitted=True),
        ]

        writer.generate_venue_file(venue, submissions, output_path)

        content = output_path.read_text()
        assert "Old content" not in content
        assert "name: Updated Venue" in content
        assert "[[New Poem]]" in content

    def test_generate_preserves_existing_notes(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test that existing notes are preserved on regeneration."""
        output_path = tmp_path / "venue_with_notes.md"

        # Create existing file with custom notes
        existing_content = """---
name: Notes Venue
---

# Notes Venue

## Submissions

| Poems | Status |
|-------|--------|
| Old   | Planned |

## Notes

My carefully written notes that should be preserved.
With multiple paragraphs.
"""
        output_path.write_text(existing_content)

        # Regenerate with new data
        venue = Venue(name="Notes Venue", payment="$25/poem")
        submissions = [
            Submission(venue_name="Notes Venue", poems=["New Poem"], status="planned"),
        ]

        writer.generate_venue_file(venue, submissions, output_path)

        content = output_path.read_text()

        # New content
        assert "payment: $25/poem" in content
        assert "[[New Poem]]" in content

        # Preserved notes
        assert "My carefully written notes that should be preserved." in content
        assert "With multiple paragraphs." in content

    def test_generate_creates_parent_directories(self, writer: VenueWriter, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        output_path = tmp_path / "deep" / "nested" / "path" / "venue.md"

        venue = Venue(name="Deep Venue")
        submissions = [
            Submission(venue_name="Deep Venue", poems=["Poem"], status="planned"),
        ]

        writer.generate_venue_file(venue, submissions, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()
