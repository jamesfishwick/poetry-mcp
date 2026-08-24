"""Submission tool implementations.

Extracted from server.py. Catalogs are passed in (keyword-only) by the server
wrappers, which supply get_submission_catalog()/get_venue_catalog().
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..config import load_config
from ..models.results import (
    CreateSubmissionResult,
    SubmissionListResult,
    SubmissionStatusChange,
    SyncSubmissionsResult,
    UpdateSubmissionStatusResult,
)
from ..models.submission import Submission, SubmissionStatus, SubmissionSummary
from ..parsers.frontmatter_parser import extract_frontmatter
from ..parsers.submission_parser import SubmissionParser
from ..utils import slugify_filename
from ..writers.frontmatter_writer import create_backup
from ..writers.submission_writer import SubmissionWriter
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


async def create_submission_impl(
    venue_name: str,
    poems: list[str],
    status: SubmissionStatus = "submitted",
    submitted_date: str | None = None,
    due_date: str | None = None,
    response_date: str | None = None,
    cost: str | None = None,
    notes: str | None = None,
    details: str | None = None,
    overwrite: bool = False,
    sync: bool = True,
    *,
    sub_cat: Any,
    ven_cat: Any | None = None,
    catalog: Any | None = None,
) -> CreateSubmissionResult:
    """Create a new submission record on disk. See the server wrapper for docs."""
    warnings: list[str] = []

    # Build and validate the submission via the model so an invalid status or an
    # empty poem list fails here with a clear message rather than producing a
    # malformed file.
    try:
        submission = Submission(
            venue_name=venue_name,
            poems=poems,
            status=status,
            submitted_date=submitted_date,
            due_date=due_date,
            response_date=response_date,
            cost=cost,
            notes=notes,
        )
    except ValidationError as e:
        return CreateSubmissionResult(
            success=False,
            warnings=warnings,
            error=f"Invalid submission data: {e}",
        )

    # Non-fatal advisories: an unknown venue is expected (submit first, add venue
    # metadata later), and a poem title absent from the catalog is worth flagging
    # in case of a typo, but neither should block writing the record.
    if ven_cat is not None and ven_cat.get_by_name(venue_name) is None:
        warnings.append(
            f"Venue '{venue_name}' is not in the venue catalog. The submission was "
            f"still created; add venue metadata separately if you want it tracked."
        )

    if catalog is not None:
        for poem_title in poems:
            if not _poem_in_catalog(catalog, poem_title):
                warnings.append(
                    f"Poem '{poem_title}' was not found in the poem catalog "
                    f"(check the title matches the poem's H1/filename)."
                )

    # Resolve the destination path. Filenames are canonical; a name collision
    # means a same-day submission of the same lead poem to the same venue already
    # exists, so refuse rather than silently clobber it (mirrors the noclobber
    # rule the rest of the writers follow).
    config = load_config()
    submissions_dir = config.vault.path / config.vault.submissions_dir
    submissions_dir.mkdir(parents=True, exist_ok=True)

    parser = SubmissionParser()
    filename = parser.generate_filename(venue_name, poems, submitted_date)
    target = submissions_dir / filename

    if target.exists() and not overwrite:
        return CreateSubmissionResult(
            success=False,
            file_path=str(target),
            warnings=warnings,
            error=(
                f"Submission file already exists: {target.name}. Pass overwrite=True "
                f"to replace it, or update the existing record instead."
            ),
        )

    content = SubmissionWriter().generate_content(submission, details=details)

    # Validate before committing: write to a temp file in the same directory,
    # parse it back through the real parser, and only move it into place if it
    # round-trips. This guarantees we never leave an unparseable submission on
    # disk. If a valid file is being overwritten, back it up first.
    backup_created = None
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=submissions_dir, prefix=".tmp_submission_", suffix=".md"
    )
    tmp_path = Path(tmp_name)
    try:
        with open(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)

        try:
            parser.parse_file(tmp_path)
        except Exception as e:
            return CreateSubmissionResult(
                success=False,
                warnings=warnings,
                error=f"Generated submission did not parse; not written: {e}",
            )

        if target.exists():
            backup_created = create_backup(target)

        tmp_path.replace(target)
    finally:
        # Clean up the temp file if it was not renamed into place.
        if tmp_path.exists():
            tmp_path.unlink()

    # Re-parse from the final location so source_file points at the real path.
    parsed = parser.parse_file(target)

    logger.info(f"Created submission: {target.name} ({status}, {len(poems)} poem(s))")
    if backup_created:
        logger.info(f"Backed up prior file to {backup_created}")

    synced = False
    if sync:
        sub_cat.sync(force_rescan=True)
        synced = True

    return CreateSubmissionResult(
        success=True,
        file_path=str(target),
        submission=parsed,
        warnings=warnings,
        synced=synced,
    )


def _poem_in_catalog(catalog: Any, title: str) -> bool:
    """Best-effort check that a poem title exists in the catalog.

    Catalog shape varies (title index vs. list scan), so try the common
    accessors and fall back to a case-insensitive title/id scan. Returns True on
    any match; a False only feeds a non-fatal warning, never blocks creation.
    """
    needle = title.strip().lower()

    getter = getattr(catalog, "get_by_title", None)
    if callable(getter):
        try:
            if getter(title):
                return True
        except Exception:
            pass

    get_all = getattr(catalog, "get_all", None)
    poems = None
    if callable(get_all):
        try:
            poems = get_all()
        except Exception:
            poems = None
    if poems is None:
        poems = getattr(catalog, "poems", None)

    if poems:
        for poem in poems:
            ptitle = str(getattr(poem, "title", "")).strip().lower()
            pid = str(getattr(poem, "id", "")).strip().lower()
            if needle in (ptitle, pid):
                return True

    return False


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
