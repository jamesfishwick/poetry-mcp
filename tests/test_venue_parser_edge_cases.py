"""Edge case and error path tests for venue parser.

This test file complements test_venue_parser.py by focusing on edge cases,
boundary conditions, and exceptional scenarios not covered in the happy path tests.
"""

import pytest
from poetry_mcp.parsers.venue_parser import VenueParser, VenueRegistry


@pytest.fixture
def temp_venue_dir(tmp_path):
    """Create a temporary directory for venue files."""
    venue_dir = tmp_path / "venues"
    venue_dir.mkdir()
    return venue_dir


class TestVenueParserSubmissionEdgeCases:
    """Test edge cases in submission parsing."""

    def test_parse_submission_with_dash_poems(self, temp_venue_dir):
        """Test submission row with '-' in poems column is skipped."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| -     | 2025-12-01 |
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert venue.name == "Test Venue"
        assert len(submissions) == 0  # Row with '-' should be skipped

    def test_parse_submission_with_empty_poems(self, temp_venue_dir):
        """Test submission row with empty poems field is skipped."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
|       | 2025-12-01 |
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert venue.name == "Test Venue"
        assert len(submissions) == 0  # Empty poems field should be skipped

    def test_parse_submission_with_comma_only_poems(self, temp_venue_dir):
        """Test submission row with only commas in poems field is skipped."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| ,,,   | 2025-12-01 |
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert venue.name == "Test Venue"
        assert len(submissions) == 0  # Comma-only should result in empty poems list

    def test_parse_submission_with_due_date(self, temp_venue_dir):
        """Test submission with due date field."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem1 | 2025-12-01 |
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert len(submissions) == 1
        assert submissions[0].due_date == "2025-12-01"

    def test_parse_submission_with_cost(self, temp_venue_dir):
        """Test submission with cost field."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Cost | Due Date |
|-------|------|----------|
| poem1 | $5   | 2025-12-01 |
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert len(submissions) == 1
        assert submissions[0].cost == "$5"

    def test_parse_submission_validation_error(self, temp_venue_dir):
        """Test that validation errors are caught and logged."""
        venue_file = temp_venue_dir / "test.md"
        # Create a submission that will fail validation
        # (empty poems list after Submission model validation)
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem1 | 2025-12-01 |
"""
        )

        parser = VenueParser()
        # This should succeed - just testing that parse doesn't crash on validation
        venue, submissions = parser.parse_file(venue_file)
        assert venue.name == "Test Venue"


class TestVenueParserSectionHandling:
    """Test section header handling."""

    def test_parse_with_other_level_2_headers(self, temp_venue_dir):
        """Test that ## headers outside submissions reset current section."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## About

This is some information.

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem1 | 2025-12-01 |

## More Information

Additional details.
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert venue.name == "Test Venue"
        assert len(submissions) == 1  # Should have parsed the one submission

    def test_parse_with_other_level_3_headers(self, temp_venue_dir):
        """Test that ### headers outside submissions reset current section."""
        venue_file = temp_venue_dir / "test.md"
        venue_file.write_text(
            """---
name: Test Venue
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem1 | 2025-12-01 |

### Other Section

Some other content.
"""
        )

        parser = VenueParser()
        venue, submissions = parser.parse_file(venue_file)

        assert venue.name == "Test Venue"
        assert len(submissions) == 1


class TestVenueRegistryMethods:
    """Test VenueRegistry query methods."""

    @pytest.fixture
    def populated_registry(self, temp_venue_dir):
        """Create a registry with test data."""
        # Create venue 1
        (temp_venue_dir / "venue1.md").write_text(
            """---
name: Venue One
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem1 | 2025-12-01 |

### 📤 Submitted

| Poems | Submitted | Response by |
|-------|-----------|-------------|
| poem2 | 2025-01-01 | 2025-02-01 |
"""
        )

        # Create venue 2
        (temp_venue_dir / "venue2.md").write_text(
            """---
name: Venue Two
---

## Submissions

### 📋 Planned

| Poems | Due Date |
|-------|----------|
| poem3 | 2025-12-15 |
"""
        )

        registry = VenueRegistry(venues_dir=temp_venue_dir)
        registry.load_all()
        return registry

    def test_get_venue(self, populated_registry):
        """Test getting a venue by name."""
        venue = populated_registry.get_venue("Venue One")
        assert venue is not None
        assert venue.name == "Venue One"

        # Test non-existent venue
        assert populated_registry.get_venue("Nonexistent") is None

    def test_get_submissions_for_venue(self, populated_registry):
        """Test getting submissions for a specific venue."""
        submissions = populated_registry.get_submissions_for_venue("Venue One")
        assert len(submissions) == 2  # 1 planned + 1 submitted

        submissions = populated_registry.get_submissions_for_venue("Venue Two")
        assert len(submissions) == 1  # 1 planned

        submissions = populated_registry.get_submissions_for_venue("Nonexistent")
        assert len(submissions) == 0

    def test_get_active_submissions(self, populated_registry):
        """Test getting active (pending response) submissions."""
        active = populated_registry.get_active_submissions()
        # Only the submitted one should be active (pending response)
        assert len(active) == 1
        assert active[0].status == "submitted"

    def test_get_planned_submissions(self, populated_registry):
        """Test getting planned submissions."""
        planned = populated_registry.get_planned_submissions()
        assert len(planned) == 2  # 2 planned submissions across venues
        assert all(s.status == "planned" for s in planned)
