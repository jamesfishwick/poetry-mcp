"""Submission tool implementations.

Extracted from server.py. Catalogs are passed in (keyword-only) by the server
wrappers, which supply get_submission_catalog()/get_venue_catalog().
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from ..config import load_config
from ..models.results import (
    SubmissionListResult,
    SubmissionStatusChange,
    SyncSubmissionsResult,
    UpdateSubmissionStatusResult,
)
from ..models.submission import SubmissionStatus, SubmissionSummary
from ..parsers.frontmatter_parser import extract_frontmatter
from ..utils import slugify_filename
from ..writers.frontmatter_writer import create_backup
from ..writers.venue_writer import VenueWriter

logger = logging.getLogger(__name__)


async def sync_submissions_impl(
    force_rescan: bool = False, *, sub_cat: Any, ven_cat: Any
) -> SyncSubmissionsResult:
    """Scan submissions and auto-regenerate venue files."""
    logger.info(f"Syncing submissions (force_rescan={force_rescan})...")
    result = sub_cat.sync(force_rescan=force_rescan)
    logger.info(f"Submission sync complete: {result['total_submissions']} submissions")

    logger.info("Auto-regenerating venue files...")
    config = load_config()
    venues_dir = config.vault.path / config.vault.venues_dir

    all_submissions = sub_cat.get_all()
    venue_names = {sub.venue_name for sub in all_submissions}

    regenerated_count = 0
    for venue_name in venue_names:
        venue = ven_cat.get_by_name(venue_name)
        if venue:
            submissions = sub_cat.get_by_venue(venue_name)
            output_path = venues_dir / f"{slugify_filename(venue_name)}.md"

            writer = VenueWriter()
            writer.generate_venue_file(venue, submissions, output_path)
            regenerated_count += 1
            logger.debug(f"Regenerated venue file: {venue_name}")

    logger.info(f"Regenerated {regenerated_count} venue files")

    return SyncSubmissionsResult(
        success=True,
        total_submissions=result["total_submissions"],
        new_submissions=result["new_submissions"],
        errors=result["errors"],
        duration_seconds=result["duration_seconds"],
    )


async def list_submissions_impl(
    venue: str | None = None,
    status: SubmissionStatus | None = None,
    poem: str | None = None,
    limit: int | None = 50,
    *,
    sub_cat: Any,
) -> SubmissionListResult:
    """List submissions with optional filtering."""
    submissions = sub_cat.filter_submissions(venue=venue, status=status, poem=poem)

    total = len(submissions)
    if limit:
        submissions = submissions[:limit]

    return SubmissionListResult(
        success=True,
        submissions=submissions,
        total_count=total,
        filters_applied={
            "venue": venue,
            "status": status,
            "poem": poem,
            "limit": limit,
        },
    )


async def update_submission_status_impl(
    new_status: SubmissionStatus,
    venue: str | None = None,
    poem: str | None = None,
    current_status: SubmissionStatus | None = None,
    dry_run: bool = True,
    *,
    sub_cat: Any,
) -> UpdateSubmissionStatusResult:
    """Bulk-update submission status for a scoped selection. See server wrapper."""
    if not (venue or poem or current_status):
        return UpdateSubmissionStatusResult(
            success=False,
            dry_run=dry_run,
            new_status=new_status,
            matched_count=0,
            filters_applied={"venue": venue, "poem": poem, "current_status": current_status},
            error=(
                "Refusing to update all submissions: provide at least one of "
                "venue, poem, or current_status to scope the change."
            ),
        )

    matches = sub_cat.filter_submissions(venue=venue, status=current_status, poem=poem)

    submitted_states = {"submitted", "accepted", "rejected", "withdrawn"}
    changes: list[SubmissionStatusChange] = []
    backups: list[str] = []

    for sub in matches:
        if sub.status == new_status:
            continue

        change = SubmissionStatusChange(
            source_file=sub.source_file or "",
            venue_name=sub.venue_name,
            poems=sub.poems,
            old_status=sub.status,
            new_status=new_status,
        )
        changes.append(change)

        if dry_run:
            continue

        if not sub.source_file:
            return UpdateSubmissionStatusResult(
                success=False,
                dry_run=False,
                new_status=new_status,
                matched_count=len(matches),
                changes=changes,
                backups=backups,
                filters_applied={"venue": venue, "poem": poem, "current_status": current_status},
                error=f"Submission for {sub.venue_name} has no source_file; cannot write.",
            )

        file_path = Path(sub.source_file)
        content = file_path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(content, file_path)

        frontmatter["status"] = new_status
        if "submitted" in frontmatter:
            frontmatter["submitted"] = new_status in submitted_states

        body = re.sub(
            r"^(\*\*Status\*\*:).*$",
            rf"\1 {new_status.title()}",
            body,
            count=1,
            flags=re.MULTILINE,
        )

        fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        new_content = f"---\n{fm_yaml}---\n{body}"

        backups.append(str(create_backup(file_path)))
        file_path.write_text(new_content, encoding="utf-8")

    if not dry_run and changes:
        sub_cat.sync(force_rescan=True)
        logger.info(f"Updated {len(changes)} submissions to status '{new_status}'")

    return UpdateSubmissionStatusResult(
        success=True,
        dry_run=dry_run,
        new_status=new_status,
        matched_count=len(matches),
        changes=changes,
        backups=backups,
        filters_applied={"venue": venue, "poem": poem, "current_status": current_status},
    )


async def get_submission_stats_impl(*, sub_cat: Any) -> SubmissionSummary:
    """Submission statistics and metrics."""
    return sub_cat.get_summary()
