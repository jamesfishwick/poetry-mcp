"""
Submission catalog with indexing and fast lookup.

Scans submissions/ directory and provides indexed access to submission data.
"""

import logging
import time
from collections import defaultdict
from pathlib import Path

from poetry_mcp.errors import BaseParseError as ParseError
from poetry_mcp.models.submission import Submission, SubmissionStatus, SubmissionSummary
from poetry_mcp.parsers.submission_parser import SubmissionParser

logger = logging.getLogger(__name__)


class SubmissionIndex:
    """Fast lookup indices for submissions."""

    def __init__(self):
        self.all_submissions: list[Submission] = []
        self.by_venue: dict[str, list[Submission]] = defaultdict(list)
        self.by_status: dict[SubmissionStatus, list[Submission]] = defaultdict(list)
        self.by_poem: dict[str, list[Submission]] = defaultdict(list)
        self.by_file: dict[str, Submission] = {}

    def add(self, submission: Submission) -> None:
        """Add submission to all indices."""
        self.all_submissions.append(submission)

        # Index by venue
        venue_key = submission.venue_name.lower()
        self.by_venue[venue_key].append(submission)

        # Index by status
        self.by_status[submission.status].append(submission)

        # Index by poems
        for poem in submission.poems:
            poem_key = poem.lower()
            self.by_poem[poem_key].append(submission)

        # Index by source file
        if submission.source_file:
            self.by_file[submission.source_file] = submission

    def clear(self) -> None:
        """Clear all indices."""
        self.all_submissions.clear()
        self.by_venue.clear()
        self.by_status.clear()
        self.by_poem.clear()
        self.by_file.clear()

    def get_by_venue(self, venue_name: str) -> list[Submission]:
        """Get all submissions for a venue."""
        return self.by_venue.get(venue_name.lower(), [])

    def get_by_status(self, status: SubmissionStatus) -> list[Submission]:
        """Get all submissions with a given status."""
        return self.by_status.get(status, [])

    def get_by_poem(self, poem_title: str) -> list[Submission]:
        """Get all submissions containing a poem."""
        return self.by_poem.get(poem_title.lower(), [])

    def get_summary(self) -> SubmissionSummary:
        """Generate submission statistics."""
        total = len(self.all_submissions)

        # Count by status
        by_status = {status: len(submissions) for status, submissions in self.by_status.items()}

        # Active submissions (submitted and pending)
        active = len(self.by_status.get("submitted", []))

        # Total poems submitted
        total_poems = sum(len(sub.poems) for sub in self.all_submissions)

        # Acceptance rate (accepted / completed submissions)
        completed = (
            len(self.by_status.get("accepted", []))
            + len(self.by_status.get("rejected", []))
            + len(self.by_status.get("withdrawn", []))
        )
        acceptance_rate = None
        if completed > 0:
            accepted = len(self.by_status.get("accepted", []))
            acceptance_rate = round((accepted / completed) * 100, 1)

        return SubmissionSummary(
            total_submissions=total,
            by_status=by_status,
            active_submissions=active,
            total_poems_submitted=total_poems,
            acceptance_rate=acceptance_rate,
        )


class SubmissionCatalog:
    """
    Submission catalog with scanning and indexing.

    Scans submissions/ directory, parses all submission files,
    and maintains fast lookup indices.
    """

    def __init__(self, submissions_dir: Path):
        """
        Initialize catalog.

        Args:
            submissions_dir: Path to submissions/ directory
        """
        self.submissions_dir = Path(submissions_dir)
        self.parser = SubmissionParser()
        self.index = SubmissionIndex()
        self._last_scan_time: float | None = None

    def sync(self, force_rescan: bool = False) -> dict:
        """
        Scan submissions directory and rebuild index.

        Args:
            force_rescan: If True, rescan all files even if already loaded

        Returns:
            Dictionary with sync statistics
        """
        start_time = time.perf_counter()

        if force_rescan or self._last_scan_time is None:
            self.index.clear()

        if not self.submissions_dir.exists():
            logger.warning(f"Submissions directory not found: {self.submissions_dir}")
            return {
                "total_submissions": 0,
                "new_submissions": 0,
                "errors": [],
                "duration_seconds": time.perf_counter() - start_time,
            }

        # Find all .md files (excluding .base files)
        submission_files = [
            f for f in self.submissions_dir.glob("*.md") if not f.name.endswith(".base")
        ]

        new_count = 0
        errors = []

        for file_path in submission_files:
            # Skip if already indexed (unless force_rescan)
            if not force_rescan and str(file_path) in self.index.by_file:
                continue

            try:
                submission = self.parser.parse_file(file_path)
                self.index.add(submission)
                new_count += 1
            except ParseError as e:
                logger.warning(f"Failed to parse {file_path.name}: {e}")
                errors.append(f"{file_path.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error parsing {file_path.name}: {e}")
                errors.append(f"{file_path.name}: {e}")

        self._last_scan_time = time.perf_counter()
        duration = self._last_scan_time - start_time

        logger.info(
            f"Submission sync complete: {len(self.index.all_submissions)} total, "
            f"{new_count} new, {len(errors)} errors in {duration:.3f}s"
        )

        return {
            "total_submissions": len(self.index.all_submissions),
            "new_submissions": new_count,
            "errors": errors,
            "duration_seconds": duration,
        }

    def get_by_venue(self, venue_name: str) -> list[Submission]:
        """Get all submissions for a venue."""
        return self.index.get_by_venue(venue_name)

    def get_by_status(self, status: SubmissionStatus) -> list[Submission]:
        """Get all submissions with a given status."""
        return self.index.get_by_status(status)

    def get_by_poem(self, poem_title: str) -> list[Submission]:
        """Get all submissions containing a poem."""
        return self.index.get_by_poem(poem_title)

    def get_all(self) -> list[Submission]:
        """Get all submissions."""
        return self.index.all_submissions.copy()

    def get_summary(self) -> SubmissionSummary:
        """Get submission statistics."""
        return self.index.get_summary()

    def filter_submissions(
        self,
        venue: str | None = None,
        status: SubmissionStatus | None = None,
        poem: str | None = None,
    ) -> list[Submission]:
        """
        Filter submissions by multiple criteria.

        Args:
            venue: Filter by venue name
            status: Filter by submission status
            poem: Filter by poem title

        Returns:
            List of matching submissions
        """
        # Intersect on object identity rather than the objects themselves:
        # Submission is a Pydantic BaseModel and is unhashable, so it cannot go
        # in a set(). The index stores the same instances across every lookup,
        # so id() is a stable, field-independent key for AND-combining filters.
        results = list(self.index.all_submissions)

        # Apply filters
        if venue:
            allowed = {id(s) for s in self.index.get_by_venue(venue)}
            results = [s for s in results if id(s) in allowed]

        if status:
            allowed = {id(s) for s in self.index.get_by_status(status)}
            results = [s for s in results if id(s) in allowed]

        if poem:
            allowed = {id(s) for s in self.index.get_by_poem(poem)}
            results = [s for s in results if id(s) in allowed]

        # Sort by submission date (most recent first). Stringify the key so
        # real date objects (ISO, e.g. "2024-08-01") and fuzzy string dates
        # (e.g. "2014-XX-XX") compare without a str-vs-date TypeError.
        sorted_results = sorted(
            results,
            key=lambda s: str(s.submitted_date) if s.submitted_date else "",
            reverse=True,
        )

        return sorted_results
