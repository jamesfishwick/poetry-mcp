"""
Submission file parser.

Parses individual submission markdown files from submissions/ directory.
Each file represents a single submission event.
"""

import re
from pathlib import Path
from typing import Optional
from datetime import date, datetime
import yaml
from pydantic import ValidationError

from poetry_mcp.models.submission import Submission, SubmissionStatus
from poetry_mcp.errors import BaseParseError as ParseError


class SubmissionParser:
    """
    Parser for individual submission markdown files.

    Files follow naming convention: YYYY-MM-DD_Poem-Title_Venue-Name.md
    """

    def parse_file(self, file_path: Path) -> Submission:
        """
        Parse a submission markdown file.

        Args:
            file_path: Path to submission file

        Returns:
            Submission model instance

        Raises:
            ParseError: If file is malformed or required fields missing
        """
        if not file_path.exists():
            raise ParseError(f"Submission file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Extract frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
        if not match:
            raise ParseError(f"No frontmatter found in {file_path}")

        try:
            frontmatter = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML frontmatter in {file_path}: {e}")

        if not isinstance(frontmatter, dict):
            raise ParseError(f"Frontmatter must be a dict in {file_path}")

        # Extract body content
        body = match.group(2)

        # Parse submission data
        submission_data = self._normalize_submission_data(frontmatter, body, file_path)

        # Add source file tracking
        submission_data["source_file"] = str(file_path)

        try:
            return Submission(**submission_data)
        except ValidationError as e:
            raise ParseError(f"Invalid submission data in {file_path}: {e}")

    def _normalize_submission_data(self, frontmatter: dict, body: str, file_path: Path) -> dict:
        """Normalize frontmatter and body into Submission model format."""
        data = {}

        # Venue name (required)
        data["venue_name"] = frontmatter.get("venue_name")
        if not data["venue_name"]:
            raise ParseError(f"Missing venue_name in {file_path}")

        # Poems - extract from ## Poems section wikilinks
        poems = self._extract_poems_from_body(body, file_path)
        if not poems:
            raise ParseError(f"No poems found in ## Poems section in {file_path}")
        data["poems"] = poems

        # Status - normalize aliases
        status = frontmatter.get("status", "planned")

        # Handle status aliases and legacy values
        status_map = {
            "pending": "submitted",  # alias
            "unknown": "planned",  # legacy default
        }
        status = status_map.get(status, status)

        if status not in ["planned", "submitted", "accepted", "rejected", "withdrawn"]:
            raise ParseError(f"Invalid status '{status}' in {file_path}")
        data["status"] = status

        # Submitted flag - infer from status if not explicit
        if "submitted" in frontmatter:
            data["submitted"] = frontmatter["submitted"]
        else:
            data["submitted"] = status in ["submitted", "accepted", "rejected", "withdrawn"]

        # Dates
        if "submitted_date" in frontmatter:
            data["submitted_date"] = self._parse_date_field(
                frontmatter["submitted_date"], file_path
            )

        if "due_date" in frontmatter:
            data["due_date"] = self._parse_date_field(frontmatter["due_date"], file_path)

        if "response_date" in frontmatter:
            data["response_date"] = self._parse_date_field(frontmatter["response_date"], file_path)
        elif "expected_response_date" in frontmatter:
            data["response_date"] = self._parse_date_field(
                frontmatter["expected_response_date"], file_path
            )

        # Financial
        if "cost" in frontmatter:
            data["cost"] = str(frontmatter["cost"])

        # Notes
        if "notes" in frontmatter:
            data["notes"] = frontmatter["notes"]

        return data

    def _parse_date_field(self, value: any, file_path: Path) -> Optional[date | str]:
        """Parse a date field, supporting multiple formats."""
        if value is None:
            return None

        # Already a date object
        if isinstance(value, date):
            return value

        # String format
        if isinstance(value, str):
            # Try ISO format first (YYYY-MM-DD)
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                pass

            # Return as-is for fuzzy dates like "2025-August"
            return value

        raise ParseError(f"Invalid date format in {file_path}: {value}")

    def _extract_poems_from_body(self, body: str, file_path: Path) -> list[str]:
        """
        Extract poem titles from [[wikilinks]] in ## Poems section.
        
        Args:
            body: Markdown body content after frontmatter
            file_path: Path to file (for error reporting)
            
        Returns:
            List of poem titles extracted from wikilinks
            
        Raises:
            ParseError: If ## Poems section not found or no wikilinks present
        """
        # Find ## Poems section
        poems_match = re.search(r'^##\s+Poems\s*$', body, re.MULTILINE)
        if not poems_match:
            raise ParseError(f"No ## Poems section found in {file_path}")
        
        # Extract content from ## Poems to next ## heading or end of file
        start_pos = poems_match.end()
        next_section = re.search(r'^##\s+', body[start_pos:], re.MULTILINE)
        
        if next_section:
            poems_content = body[start_pos:start_pos + next_section.start()]
        else:
            poems_content = body[start_pos:]
        
        # Extract all [[wikilinks]] from poems section
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', poems_content)
        
        if not wikilinks:
            raise ParseError(f"No [[wikilinks]] found in ## Poems section in {file_path}")
        
        return wikilinks

    def generate_filename(
        self,
        venue_name: str,
        poems: list[str],
        submitted_date: Optional[date | str] = None,
    ) -> str:
        """
        Generate canonical filename for a submission.

        Format: YYYY-MM-DD_First-Poem-Title_Venue-Name.md

        Args:
            venue_name: Name of venue
            poems: List of poem titles
            submitted_date: Submission date (or None for planned)

        Returns:
            Filename string
        """
        # Date component
        if submitted_date:
            if isinstance(submitted_date, date):
                date_str = submitted_date.strftime("%Y-%m-%d")
            elif isinstance(submitted_date, str) and re.match(r"\d{4}-\d{2}-\d{2}", submitted_date):
                date_str = submitted_date
            else:
                date_str = "XXXX-XX-XX"
        else:
            date_str = "XXXX-XX-XX"

        # Poem component (use first poem title)
        poem_title = poems[0] if poems else "Untitled"
        poem_slug = re.sub(r"[^\w\s-]", "", poem_title)
        poem_slug = re.sub(r"[-\s]+", "-", poem_slug).strip("-")

        # Venue component
        venue_slug = re.sub(r"[^\w\s-]", "", venue_name)
        venue_slug = re.sub(r"[-\s]+", "-", venue_slug).strip("-")

        return f"{date_str}_{poem_slug}_{venue_slug}.md"
