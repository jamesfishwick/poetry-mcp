"""
Submission file writer.

Generates individual submission markdown files from submission metadata.
Unlike venue files (auto-generated views), a submission file is source-of-truth:
it is what SubmissionParser reads back, so the output here must round-trip
through that parser. See SubmissionWriter.generate_content.
"""

from datetime import date, datetime

import yaml

from poetry_mcp.models.submission import Submission


class SubmissionWriter:
    """Render a Submission to the on-disk markdown format the parser reads.

    The machine-readable contract is small: frontmatter with ``venue_name`` and
    ``status`` plus a ``## Poems`` section of ``[[wikilinks]]``. Everything else
    (details, notes) is prose the caller supplies. Keeping generation here, apart
    from file I/O, lets callers validate output by parsing it back before writing.
    """

    def generate_content(
        self,
        submission: Submission,
        details: str | None = None,
    ) -> str:
        """Build the full markdown text for a submission file.

        Args:
            submission: The submission to render.
            details: Optional freeform markdown inserted between the Poems and
                Notes sections (e.g. "## Terms", selection rationale). May carry
                its own ``##`` headings; written verbatim.

        Returns:
            Complete file content: frontmatter, title, Poems, optional details,
            and a Notes section.
        """
        frontmatter = self._generate_frontmatter(submission)
        body = self._generate_body(submission, details)
        return f"{frontmatter}\n{body}"

    def _generate_frontmatter(self, sub: Submission) -> str:
        """Serialize submission metadata to YAML frontmatter.

        Only non-empty fields are written, mirroring the existing hand-authored
        files. ``response_date`` is written as ``expected_response_date`` to
        match the convention those files use (the parser accepts either).
        """
        fm: dict = {"venue_name": sub.venue_name}

        if sub.submitted_date is not None:
            fm["submitted_date"] = self._yaml_date(sub.submitted_date)
        if sub.due_date is not None:
            fm["due_date"] = self._yaml_date(sub.due_date)
        if sub.response_date is not None:
            fm["expected_response_date"] = self._yaml_date(sub.response_date)

        fm["status"] = sub.status

        if sub.cost is not None:
            fm["cost"] = sub.cost

        # Emit notes into frontmatter, not only the body ## Notes section, so the
        # parser (which reads notes from frontmatter) round-trips it back into
        # CreateSubmissionResult.submission.notes. The body still renders the same
        # text for humans reading in Obsidian.
        if sub.notes is not None and sub.notes.strip():
            fm["notes"] = sub.notes

        yaml_str = yaml.dump(
            fm,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{yaml_str}---"

    def _generate_body(self, sub: Submission, details: str | None) -> str:
        """Build the markdown body: title, Poems wikilinks, details, Notes."""
        # Title mirrors existing files: single poem by name, else "N Poems".
        if len(sub.poems) == 1:
            subject = sub.poems[0]
        else:
            subject = f"{len(sub.poems)} Poems"

        sections = [f"\n# Submission: {subject} → {sub.venue_name}\n"]

        sections.append("## Poems")
        sections.extend(f"[[{poem}]]" for poem in sub.poems)
        sections.append("")

        if details and details.strip():
            sections.append(details.strip())
            sections.append("")

        sections.append("## Notes")
        sections.append(
            sub.notes.strip()
            if sub.notes and sub.notes.strip()
            else "_Add submission-specific notes here_"
        )
        sections.append("")

        return "\n".join(sections)

    def _yaml_date(self, value: date | str) -> date | str:
        """Normalize a date for YAML output.

        An ISO ``YYYY-MM-DD`` string is converted to a ``date`` so PyYAML emits
        it unquoted (``submitted_date: 2026-08-23``), matching existing files.
        Fuzzy strings ("2026-August") and real dates pass through unchanged.
        """
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return value
        return value
