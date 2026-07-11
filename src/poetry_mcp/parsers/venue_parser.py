"""
Venue file parser.

Parses venue markdown files to extract:
1. Venue metadata from frontmatter
2. Submission records from tables in the body
"""

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from poetry_mcp.errors import BaseParseError as ParseError
from poetry_mcp.models import Submission, Venue


class VenueParser:
    """
    Parser for venue markdown files.

    Extracts Venue metadata and Submission records from a single venue file.
    """

    def parse_file(self, file_path: Path) -> tuple[Venue, list[Submission]]:
        """
        Parse a venue markdown file.

        Args:
            file_path: Path to the venue markdown file

        Returns:
            Tuple of (Venue, list of Submissions)

        Raises:
            ParseError: If file is malformed or required fields are missing
        """
        if not file_path.exists():
            raise ParseError(f"Venue file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Extract venue metadata from frontmatter
        venue = self._parse_venue_metadata(content, file_path)

        # Extract submissions from body
        submissions = self._parse_submissions(content, venue.name, file_path)

        return venue, submissions

    def _parse_venue_metadata(self, content: str, file_path: Path) -> Venue:
        """Extract Venue model from frontmatter."""
        # Extract YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            raise ParseError(f"No frontmatter found in {file_path}")

        try:
            frontmatter = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML frontmatter in {file_path}: {e}")

        if not isinstance(frontmatter, dict):
            raise ParseError(f"Frontmatter must be a dict in {file_path}")

        # Add file path for roundtrip editing
        frontmatter["file_path"] = str(file_path)

        try:
            return Venue(**frontmatter)
        except ValidationError as e:
            raise ParseError(f"Invalid venue metadata in {file_path}: {e}")

    def _parse_submissions(
        self, content: str, venue_name: str, file_path: Path
    ) -> list[Submission]:
        """Extract Submission records from markdown tables."""
        submissions = []

        # Find all tables and their section headers
        lines = content.split("\n")
        current_section = None
        in_table = False
        table_headers = []

        for line in lines:
            line_stripped = line.strip()

            # Detect section headers
            if line_stripped.startswith("### 📋 Planned"):
                current_section = "planned"
                in_table = False
                continue
            elif line_stripped.startswith("### 📤 Submitted"):
                current_section = "submitted"
                in_table = False
                continue
            elif line_stripped.startswith("### ✅ Accepted"):
                current_section = "accepted"
                in_table = False
                continue
            elif line_stripped.startswith("### ❌ Rejected"):
                current_section = "rejected"
                in_table = False
                continue
            elif line_stripped.startswith("###") or line_stripped.startswith("##"):
                current_section = None
                in_table = False
                continue

            # Detect table start
            if current_section and line_stripped.startswith("|"):
                if not in_table:
                    # First row is headers
                    table_headers = [h.strip() for h in line_stripped.split("|")[1:-1]]
                    in_table = True
                elif "---" in line_stripped:
                    # Separator row, skip
                    continue
                else:
                    # Data row
                    cols = [c.strip() for c in line_stripped.split("|")[1:-1]]
                    if len(cols) >= 2 and cols[0] not in ("-", ""):
                        submission = self._parse_table_row(
                            cols, table_headers, current_section, venue_name, file_path
                        )
                        if submission:
                            submissions.append(submission)

        return submissions

    def _parse_table_row(
        self, cols: list[str], headers: list[str], status: str, venue_name: str, file_path: Path
    ) -> Submission | None:
        """Parse a single table row into a Submission."""
        # Create dict mapping headers to values
        row_data = {h.lower(): v for h, v in zip(headers, cols, strict=False)}

        # Extract poems (first column, comma-separated)
        poems_str = cols[0] if cols else ""
        if not poems_str or poems_str == "-":
            return None

        poems = [p.strip() for p in poems_str.split(",") if p.strip()]
        if not poems:
            return None

        # Build submission data based on status
        submission_data = {
            "venue_name": venue_name,
            "poems": poems,
            "status": status,
            "submitted": status in ("submitted", "accepted", "rejected"),
            "source_file": str(file_path),
        }

        # Map common column names to fields
        date_field = row_data.get("submitted", row_data.get("submitted date"))
        if date_field and date_field != "-":
            submission_data["submitted_date"] = date_field

        due_field = row_data.get("due date")
        if due_field and due_field != "-":
            submission_data["due_date"] = due_field

        response_field = row_data.get(
            "expected response",
            row_data.get("response", row_data.get("response by", row_data.get("accepted"))),
        )
        if response_field and response_field != "-":
            submission_data["response_date"] = response_field

        cost_field = row_data.get("cost")
        if cost_field and cost_field != "-":
            submission_data["cost"] = cost_field

        notes_field = row_data.get("notes")
        if notes_field and notes_field != "-":
            submission_data["notes"] = notes_field

        try:
            return Submission(**submission_data)
        except ValidationError as e:
            # Log warning but don't fail the entire parse
            print(f"Warning: Failed to parse submission row in {file_path}: {e}")
            return None


class VenueRegistry:
    """
    Registry for managing venues and their submissions.

    Provides methods to load, query, and manage venue data.
    """

    def __init__(self, venues_dir: Path):
        """
        Initialize venue registry.

        Args:
            venues_dir: Path to directory containing venue markdown files
        """
        self.venues_dir = venues_dir
        self.parser = VenueParser()
        self.venues: dict[str, Venue] = {}
        self.submissions: list[Submission] = []

    def load_all(self) -> None:
        """Load all venue files from the venues directory."""
        if not self.venues_dir.exists():
            raise ParseError(f"Venues directory not found: {self.venues_dir}")

        self.venues.clear()
        self.submissions.clear()

        for md_file in self.venues_dir.glob("*.md"):
            try:
                venue, submissions = self.parser.parse_file(md_file)
                self.venues[venue.name] = venue
                self.submissions.extend(submissions)
            except ParseError as e:
                print(f"Warning: Skipping {md_file.name}: {e}")

    def get_venue(self, name: str) -> Venue | None:
        """Get venue by name."""
        return self.venues.get(name)

    def get_submissions_for_venue(self, venue_name: str) -> list[Submission]:
        """Get all submissions for a specific venue."""
        return [s for s in self.submissions if s.venue_name == venue_name]

    def get_active_submissions(self) -> list[Submission]:
        """Get all submissions currently pending response."""
        return [s for s in self.submissions if s.is_active]

    def get_planned_submissions(self) -> list[Submission]:
        """Get all planned (not yet submitted) submissions."""
        return [s for s in self.submissions if s.status == "planned"]
