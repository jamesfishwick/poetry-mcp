"""
Venue catalog with indexing and fast lookup.

Scans venues/ directory and provides indexed access to venue metadata.
Venue metadata is stored in frontmatter of venue markdown files.
"""

import logging
import time
from pathlib import Path

from poetry_mcp.errors import BaseParseError as ParseError
from poetry_mcp.models.venue import Venue
from poetry_mcp.parsers.venue_parser import VenueParser

logger = logging.getLogger(__name__)


class VenueIndex:
    """Fast lookup indices for venues."""

    def __init__(self):
        self.all_venues: list[Venue] = []
        self.by_name: dict[str, Venue] = {}
        self.by_file: dict[str, Venue] = {}

    def add(self, venue: Venue) -> None:
        """Add venue to all indices."""
        self.all_venues.append(venue)

        # Index by name (case-insensitive)
        name_key = venue.name.lower()
        self.by_name[name_key] = venue

        # Index by file path
        if venue.file_path:
            self.by_file[venue.file_path] = venue

    def clear(self) -> None:
        """Clear all indices."""
        self.all_venues.clear()
        self.by_name.clear()
        self.by_file.clear()

    def get_by_name(self, name: str) -> Venue | None:
        """Get venue by name (case-insensitive)."""
        return self.by_name.get(name.lower())


class VenueCatalog:
    """
    Venue catalog with scanning and indexing.

    Scans venues/ directory, parses venue frontmatter,
    and maintains fast lookup indices.
    """

    def __init__(self, venues_dir: Path):
        """
        Initialize catalog.

        Args:
            venues_dir: Path to venues/ directory
        """
        self.venues_dir = Path(venues_dir)
        self.parser = VenueParser()
        self.index = VenueIndex()
        self._last_scan_time: float | None = None

    def sync(self, force_rescan: bool = False) -> dict:
        """
        Scan venues directory and rebuild index.

        Args:
            force_rescan: If True, rescan all files even if already loaded

        Returns:
            Dictionary with sync statistics
        """
        start_time = time.perf_counter()

        if force_rescan or self._last_scan_time is None:
            self.index.clear()

        if not self.venues_dir.exists():
            logger.warning(f"Venues directory not found: {self.venues_dir}")
            return {
                "total_venues": 0,
                "new_venues": 0,
                "errors": [],
                "duration_seconds": time.perf_counter() - start_time,
            }

        # Find all .md files (excluding .base files)
        venue_files = [f for f in self.venues_dir.glob("*.md") if not f.name.endswith(".base")]

        new_count = 0
        errors = []

        for file_path in venue_files:
            # Skip if already indexed (unless force_rescan)
            if not force_rescan and str(file_path) in self.index.by_file:
                continue

            try:
                # Parse venue file (returns venue + submissions)
                venue, _ = self.parser.parse_file(file_path)
                self.index.add(venue)
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
            f"Venue sync complete: {len(self.index.all_venues)} total, "
            f"{new_count} new, {len(errors)} errors in {duration:.3f}s"
        )

        return {
            "total_venues": len(self.index.all_venues),
            "new_venues": new_count,
            "errors": errors,
            "duration_seconds": duration,
        }

    def get_by_name(self, name: str) -> Venue | None:
        """Get venue by name (case-insensitive)."""
        return self.index.get_by_name(name)

    def get_all(self) -> list[Venue]:
        """Get all venues."""
        return self.index.all_venues.copy()

    def filter_venues(
        self,
        payment_filter: str | None = None,
        simultaneous_filter: bool | None = None,
    ) -> list[Venue]:
        """
        Filter venues by criteria.

        Args:
            payment_filter: Filter by payment (e.g., "yes", "no", "$50")
            simultaneous_filter: Filter by simultaneous submissions acceptance

        Returns:
            List of matching venues
        """
        results = self.index.all_venues.copy()

        if payment_filter:
            results = [
                v for v in results if v.payment and payment_filter.lower() in v.payment.lower()
            ]

        if simultaneous_filter is not None:
            results = [
                v
                for v in results
                if v.simultaneous == simultaneous_filter
                or (
                    isinstance(v.simultaneous, str)
                    and v.simultaneous.lower() == "yes"
                    and simultaneous_filter
                )
                or (
                    isinstance(v.simultaneous, str)
                    and v.simultaneous.lower() == "no"
                    and not simultaneous_filter
                )
            ]

        # Sort by name
        results.sort(key=lambda v: v.name.lower())

        return results
