"""Tests for create_submission_impl.

Covers the write path that was missing entirely before: creating a new
submission record from scratch, the collision guard, overwrite+backup, the
non-fatal warnings for unknown venue / unknown poem, and round-trip parseability
of the generated file.
"""

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import poetry_mcp.tools.submission_tools as submission_tools_module
from poetry_mcp.catalog.submission_catalog import SubmissionCatalog
from poetry_mcp.parsers.submission_parser import SubmissionParser
from poetry_mcp.tools.submission_tools import create_submission_impl


def _make_vault(tmp_path):
    """Create a temp vault and a config Mock pointing the impl at it."""
    vault = tmp_path / "vault"
    (vault / "submissions").mkdir(parents=True)
    (vault / "venues").mkdir()
    cfg = Mock(vault=Mock(path=vault, submissions_dir="submissions", venues_dir="venues"))
    return vault, cfg


def _run(coro, cfg):
    with patch.object(submission_tools_module, "load_config", return_value=cfg):
        return asyncio.run(coro)


def test_creates_parseable_submission(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["No one really likes their hog"],
            submitted_date="2026-08-23",
            response_date="2026-10-01",
            cost="free",
            notes="Free challenge; finalist publication Jan 2027.",
            sub_cat=sub_cat,
        ),
        cfg,
    )

    assert result.success is True
    assert result.error is None
    assert result.synced is True
    assert result.submission is not None
    assert result.submission.venue_name == "Glossy Planet"
    assert result.submission.poems == ["No one really likes their hog"]
    assert result.submission.status == "submitted"
    assert result.submission.cost == "free"

    # Canonical filename and on-disk round-trip through the real parser.
    written = vault / "submissions" / "2026-08-23_No-one-really-likes-their-hog_Glossy-Planet.md"
    assert result.file_path == str(written)
    assert written.exists()
    reparsed = SubmissionParser().parse_file(written)
    assert reparsed.venue_name == "Glossy Planet"
    assert reparsed.poems == ["No one really likes their hog"]

    # And it shows up in the resynced catalog.
    assert len(sub_cat.get_by_venue("Glossy Planet")) == 1


def test_frontmatter_dates_are_unquoted_iso(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Dead Deer"],
            submitted_date="2026-01-02",
            sub_cat=sub_cat,
        ),
        cfg,
    )

    text = (vault / "submissions" / result.file_path.split("/")[-1]).read_text()
    # ISO dates emitted unquoted (date object), matching hand-authored files.
    assert "submitted_date: 2026-01-02" in text
    assert "status: submitted" in text


def test_fuzzy_date_passthrough(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Dead Deer"],
            status="planned",
            due_date="2026-August",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is True
    text = (vault / "submissions" / result.file_path.split("/")[-1]).read_text()
    assert "2026-August" in text


def test_collision_refuses_without_overwrite(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    first = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["Hog"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert first.success is True

    second = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["Hog"],
            submitted_date="2026-08-23",
            notes="different note",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert second.success is False
    assert "already exists" in second.error
    # Original content untouched (no "different note" leaked in).
    assert (
        "different note" not in (vault / "submissions" / first.file_path.split("/")[-1]).read_text()
    )


def test_overwrite_replaces_and_backs_up(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    subs_dir = vault / "submissions"
    sub_cat = SubmissionCatalog(submissions_dir=subs_dir)

    first = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["Hog"],
            submitted_date="2026-08-23",
            notes="original",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    fname = first.file_path.split("/")[-1]

    second = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["Hog"],
            submitted_date="2026-08-23",
            notes="revised",
            overwrite=True,
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert second.success is True
    assert "revised" in (subs_dir / fname).read_text()
    # A .bak sibling captured the prior version.
    assert (subs_dir / (fname + ".bak")).exists()
    assert "original" in (subs_dir / (fname + ".bak")).read_text()


def test_unknown_venue_warns_but_creates(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")
    ven_cat = Mock()
    ven_cat.get_by_name.return_value = None

    result = _run(
        create_submission_impl(
            venue_name="Glossy Planet",
            poems=["Hog"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
            ven_cat=ven_cat,
        ),
        cfg,
    )
    assert result.success is True
    assert any("not in the venue catalog" in w for w in result.warnings)


def test_unknown_poem_warns_but_creates(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")
    # Lookups live on catalog.index (Catalog exposes CatalogIndex there), so shape
    # the mock the way the real object is shaped, not with a bare get_all.
    catalog = Mock()
    catalog.index.get_by_title.return_value = None
    catalog.index.all_poems = [Mock(title="Some Other Poem", id="some-other-poem")]

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["No one really likes their hog"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
            catalog=catalog,
        ),
        cfg,
    )
    assert result.success is True
    assert any("was not found in the poem catalog" in w for w in result.warnings)


def test_known_poem_no_warning(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")
    # get_by_title (the primary, case-insensitive accessor on the index) finds it.
    catalog = Mock()
    catalog.index.get_by_title.return_value = Mock(title="Careful Circles")
    catalog.index.all_poems = []

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Careful Circles"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
            catalog=catalog,
        ),
        cfg,
    )
    assert result.success is True
    assert result.warnings == []


def test_poem_lookup_against_real_catalog(tmp_path):
    """Regression for the lookup running against a real Catalog.

    _poem_in_catalog must reach the poem index via catalog.index (Catalog itself
    has no get_by_title/all_poems). A known poem must NOT warn; an unknown one
    must. A mock with the wrong shape hid this; a real Catalog catches it.
    """
    from poetry_mcp.catalog.catalog import Catalog

    vault, cfg = _make_vault(tmp_path)
    poem_dir = vault / "catalog" / "completed"
    poem_dir.mkdir(parents=True)
    (poem_dir / "hog.md").write_text(
        "---\nstate: completed\nform: free_verse\n---\n\n"
        "# No one really likes their hog\n\nA hog poem\n"
    )
    catalog = Catalog(vault_root=vault)
    catalog.sync()
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    known = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["No one really likes their hog"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
            catalog=catalog,
        ),
        cfg,
    )
    assert known.success is True
    assert not any("not found in the poem catalog" in w for w in known.warnings)

    unknown = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["A Poem That Does Not Exist"],
            submitted_date="2026-08-24",
            sub_cat=sub_cat,
            catalog=catalog,
        ),
        cfg,
    )
    assert unknown.success is True
    assert any("not found in the poem catalog" in w for w in unknown.warnings)


def test_details_block_inserted_between_poems_and_notes(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["A", "B"],
            submitted_date="2026-08-23",
            notes="a note",
            details="## Terms\n- Free entry\n- Two pages max",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    text = (vault / "submissions" / result.file_path.split("/")[-1]).read_text()
    assert text.index("## Poems") < text.index("## Terms") < text.index("## Notes")
    # Multi-poem title uses the count form.
    assert "# Submission: 2 Poems → Rattle" in text


def test_empty_poems_is_error(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=[],
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is False
    assert "Invalid submission data" in result.error
    # Nothing written.
    assert list((vault / "submissions").glob("*.md")) == []


def test_invalid_status_is_error(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["A"],
            status="bogus",  # type: ignore[arg-type]
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is False
    assert "Invalid submission data" in result.error


def test_sync_false_skips_resync(tmp_path):
    vault, cfg = _make_vault(tmp_path)
    sub_cat = Mock()

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["A"],
            submitted_date="2026-08-23",
            sync=False,
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is True
    assert result.synced is False
    sub_cat.sync.assert_not_called()


def test_unparseable_generation_writes_nothing(tmp_path):
    """The flagship safety claim: if the generated file does not parse, the tool
    returns success=False, writes nothing to the target, and leaves no temp."""
    vault, cfg = _make_vault(tmp_path)
    subs_dir = vault / "submissions"
    sub_cat = SubmissionCatalog(submissions_dir=subs_dir)

    with patch.object(
        submission_tools_module.SubmissionParser,
        "parse_file",
        side_effect=Exception("boom: unparseable"),
    ):
        result = _run(
            create_submission_impl(
                venue_name="Rattle",
                poems=["Hog"],
                submitted_date="2026-08-23",
                sub_cat=sub_cat,
                sync=False,
            ),
            cfg,
        )

    assert result.success is False
    assert "did not parse" in result.error
    # Nothing landed at the target, and no temp file leaked.
    assert list(subs_dir.glob("*.md")) == []
    assert list(subs_dir.glob(".tmp_submission_*")) == []


def test_post_write_resync_failure_still_reports_success(tmp_path):
    """If the file is written but the post-write resync throws, the tool must
    report success=True (the record IS on disk) with synced=False and a warning,
    not escape as an uncaught exception."""
    vault, cfg = _make_vault(tmp_path)
    sub_cat = Mock()
    sub_cat.sync.side_effect = RuntimeError("catalog blew up")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Hog"],
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
        ),
        cfg,
    )

    assert result.success is True  # file was written
    assert result.synced is False
    assert any("Run sync_submissions" in w for w in result.warnings)
    # The file really is on disk despite the resync failure.
    assert Path(result.file_path).exists()


def test_submitted_flag_consistent_with_status(tmp_path):
    """A status=submitted create must yield submitted=True (and is_active), not
    the model's default submitted=False."""
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Hog"],
            status="submitted",
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is True
    assert result.submission.submitted is True
    assert result.submission.is_active is True


def test_notes_round_trip_into_parsed_submission(tmp_path):
    """notes passed in must survive into the parsed-back submission, not vanish
    because it was written only to the body."""
    vault, cfg = _make_vault(tmp_path)
    sub_cat = SubmissionCatalog(submissions_dir=vault / "submissions")

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["Hog"],
            submitted_date="2026-08-23",
            notes="watch the reprint clause",
            sub_cat=sub_cat,
        ),
        cfg,
    )
    assert result.success is True
    assert result.submission.notes == "watch the reprint clause"
    # And it survives an independent re-parse from disk.
    reparsed = SubmissionParser().parse_file(Path(result.file_path))
    assert reparsed.notes == "watch the reprint clause"
