"""Venue tool implementations.

Extracted from server.py. Catalogs are passed in (keyword-only) by the server
wrappers, which supply get_venue_catalog()/get_submission_catalog().
"""

import logging
from typing import Any

from ..config import load_config
from ..models.results import (
    RegenerateVenueResult,
    SyncVenuesResult,
    VenueDetailResult,
    VenueListResult,
)
from ..utils import slugify_filename
from ..writers.venue_writer import VenueWriter

logger = logging.getLogger(__name__)


async def sync_venues_impl(force_rescan: bool = False, *, ven_cat: Any) -> SyncVenuesResult:
    """Scan the venues directory and index venue metadata."""
    logger.info(f"Syncing venues (force_rescan={force_rescan})...")
    result = ven_cat.sync(force_rescan=force_rescan)
    logger.info(f"Venue sync complete: {result['total_venues']} venues")

    return SyncVenuesResult(
        success=True,
        total_venues=result["total_venues"],
        new_venues=result["new_venues"],
        errors=result["errors"],
        duration_seconds=result["duration_seconds"],
    )


async def list_venues_impl(
    payment_filter: str | None = None,
    simultaneous_filter: bool | None = None,
    *,
    ven_cat: Any,
) -> VenueListResult:
    """List venues with optional payment/simultaneous filters."""
    venues = ven_cat.filter_venues(
        payment_filter=payment_filter,
        simultaneous_filter=simultaneous_filter,
    )

    return VenueListResult(
        success=True,
        venues=venues,
        total_count=len(venues),
        filters_applied={
            "payment": payment_filter,
            "simultaneous": simultaneous_filter,
        },
    )


async def get_venue_impl(venue_name: str, *, ven_cat: Any, sub_cat: Any) -> VenueDetailResult:
    """Venue metadata + its submission history."""
    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return VenueDetailResult(
            success=False,
            error=f"Venue not found: {venue_name}",
        )

    submissions = sub_cat.get_by_venue(venue_name)

    return VenueDetailResult(
        success=True,
        venue=venue,
        submissions=submissions,
    )


async def regenerate_venue_file_impl(
    venue_name: str, *, ven_cat: Any, sub_cat: Any
) -> RegenerateVenueResult:
    """Rebuild a venue's markdown file from metadata + submissions."""
    config = load_config()

    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return RegenerateVenueResult(
            success=False,
            venue_name=venue_name,
            file_path="",
            submissions_count=0,
            error=f"Venue not found: {venue_name}",
        )

    submissions = sub_cat.get_by_venue(venue_name)

    venues_dir = config.vault.path / config.vault.venues_dir
    output_path = venues_dir / f"{slugify_filename(venue_name)}.md"

    writer = VenueWriter()
    writer.generate_venue_file(venue, submissions, output_path)

    logger.info(f"Regenerated venue file: {output_path}")

    return RegenerateVenueResult(
        success=True,
        venue_name=venue_name,
        file_path=str(output_path),
        submissions_count=len(submissions),
    )
