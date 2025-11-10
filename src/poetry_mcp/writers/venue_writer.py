"""
Venue file writer.

Generates venue markdown files from venue metadata and submission data.
Venue files are auto-generated views, not source-of-truth.
"""

import yaml
from pathlib import Path
from typing import Optional
from datetime import date

from poetry_mcp.models.venue import Venue
from poetry_mcp.models.submission import Submission


class VenueWriter:
    """
    Generates venue markdown files from metadata and submissions.

    Venue files contain:
    1. Frontmatter with venue metadata
    2. Tables of submissions grouped by status
    3. Notes section
    """

    def generate_venue_file(
        self,
        venue: Venue,
        submissions: list[Submission],
        output_path: Path,
    ) -> None:
        """
        Generate a complete venue markdown file.

        Args:
            venue: Venue metadata
            submissions: List of submissions for this venue
            output_path: Where to write the file
        """
        # Preserve existing notes if file exists
        preserved_notes = self._extract_notes_section(output_path) if output_path.exists() else None

        # Generate frontmatter
        frontmatter = self._generate_frontmatter(venue)

        # Generate submission tables
        tables = self._generate_submission_tables(submissions, preserved_notes)

        # Combine into full file
        content = f"{frontmatter}\n{tables}"

        # Write file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    def _generate_frontmatter(self, venue: Venue) -> str:
        """Generate YAML frontmatter from venue metadata."""
        frontmatter_dict = {}

        # Required fields
        frontmatter_dict["name"] = venue.name

        # Optional fields (only include if present)
        if venue.payment:
            frontmatter_dict["payment"] = venue.payment

        if venue.response_time_days:
            frontmatter_dict["response_time_days"] = venue.response_time_days

        if venue.simultaneous is not None:
            frontmatter_dict["simultaneous"] = venue.simultaneous

        if venue.aesthetic:
            frontmatter_dict["aesthetic"] = venue.aesthetic

        if venue.url:
            frontmatter_dict["url"] = str(venue.url)

        if venue.submission_format:
            frontmatter_dict["submission_format"] = venue.submission_format

        if venue.submission_frequency:
            frontmatter_dict["submission_frequency"] = venue.submission_frequency

        # Serialize to YAML
        yaml_str = yaml.dump(
            frontmatter_dict,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        return f"---\n{yaml_str}---"

    def _generate_submission_tables(self, submissions: list[Submission], preserved_notes: Optional[str] = None) -> str:
        """Generate submission tables grouped by status."""
        # Group submissions by status
        by_status = {
            "planned": [],
            "submitted": [],
            "accepted": [],
            "rejected": [],
            "withdrawn": [],
        }

        for sub in submissions:
            by_status[sub.status].append(sub)

        # Generate sections
        sections = []

        sections.append(f"\n# {submissions[0].venue_name if submissions else 'Venue'}\n")
        sections.append("## Submissions\n")

        # Planned
        if by_status["planned"]:
            sections.append("### 📋 Planned\n")
            sections.append(self._format_submission_table(by_status["planned"], "planned"))

        # Submitted (pending response)
        if by_status["submitted"]:
            sections.append("### 📤 Submitted (Pending Response)\n")
            sections.append(self._format_submission_table(by_status["submitted"], "submitted"))

        # Accepted
        if by_status["accepted"]:
            sections.append("### ✅ Accepted\n")
            sections.append(self._format_submission_table(by_status["accepted"], "accepted"))

        # Rejected
        if by_status["rejected"]:
            sections.append("### ❌ Rejected\n")
            sections.append(self._format_submission_table(by_status["rejected"], "rejected"))

        # Withdrawn
        if by_status["withdrawn"]:
            sections.append("### 🚫 Withdrawn\n")
            sections.append(self._format_submission_table(by_status["withdrawn"], "withdrawn"))

        # Notes section - preserve existing or use default
        sections.append("## Notes\n")
        if preserved_notes:
            sections.append(preserved_notes)
        else:
            sections.append("_Add venue-specific observations, research, or strategy notes here_\n")

        return "\n".join(sections)

    def _format_submission_table(self, submissions: list[Submission], status: str) -> str:
        """Format a list of submissions as a markdown table."""
        if not submissions:
            return "_No submissions_\n"

        # Table header
        if status == "planned":
            headers = ["Poems", "Due Date", "Cost", "Notes"]
        elif status == "submitted":
            headers = ["Poems", "Submitted", "Expected Response", "Cost", "Notes"]
        else:  # accepted, rejected, withdrawn
            headers = ["Poems", "Submitted", "Response Date", "Cost", "Notes"]

        # Format rows
        rows = []
        for sub in submissions:
            row = self._format_submission_row(sub, status)
            rows.append(row)

        # Build table
        header_row = "| " + " | ".join(headers) + " |"
        separator = "|" + "|".join(["-------" for _ in headers]) + "|"
        table_rows = "\n".join(rows)

        return f"{header_row}\n{separator}\n{table_rows}\n"

    def _format_submission_row(self, sub: Submission, status: str) -> str:
        """Format a single submission as a table row."""
        # Poems column - wrap in [[wikilinks]] for Obsidian graph
        poems_text = ", ".join(f"[[{poem}]]" for poem in sub.poems)

        # Date columns (vary by status)
        if status == "planned":
            date1 = self._format_date(sub.due_date) if sub.due_date else "-"
            date2 = None
        elif status == "submitted":
            date1 = self._format_date(sub.submitted_date) if sub.submitted_date else "-"
            date2 = self._format_date(sub.response_date) if sub.response_date else "-"
        else:  # accepted, rejected, withdrawn
            date1 = self._format_date(sub.submitted_date) if sub.submitted_date else "-"
            date2 = self._format_date(sub.response_date) if sub.response_date else "-"

        # Cost
        cost = sub.cost if sub.cost else "-"

        # Notes
        notes = sub.notes if sub.notes else "-"

        # Build row
        if status == "planned":
            return f"| {poems_text} | {date1} | {cost} | {notes} |"
        else:
            return f"| {poems_text} | {date1} | {date2} | {cost} | {notes} |"

    def _format_date(self, date_val: Optional[date | str]) -> str:
        """Format a date for display."""
        if date_val is None:
            return "-"
        if isinstance(date_val, date):
            return date_val.strftime("%Y-%m-%d")
        return str(date_val)

    def _extract_notes_section(self, file_path: Path) -> Optional[str]:
        """
        Extract existing ## Notes section content from venue file.
        
        Args:
            file_path: Path to existing venue file
            
        Returns:
            Notes section content (everything after ## Notes heading) or None
        """
        import re
        
        if not file_path.exists():
            return None
            
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Find ## Notes section
            notes_match = re.search(r'^##\s+Notes\s*$', content, re.MULTILINE)
            if not notes_match:
                return None
            
            # Extract content from ## Notes to end of file (no next ## heading for Notes)
            start_pos = notes_match.end()
            notes_content = content[start_pos:].strip()
            
            # Return preserved content (or None if it's just the default message)
            if notes_content and notes_content != "_Add venue-specific observations, research, or strategy notes here_":
                return notes_content + "\n"
            
            return None
            
        except Exception:
            # If we can't read the file, just return None
            return None
