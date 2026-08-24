"""Tests for create_submission_impl.

Covers the write path that was missing entirely before: creating a new
submission record from scratch, the collision guard, overwrite+backup, the
non-fatal warnings for unknown venue / unknown poem, and round-trip parseability
of the generated file.
"""

import asyncio
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
    catalog = Mock(spec=["get_all"])
    catalog.get_all.return_value = [Mock(title="Some Other Poem", id="some-other-poem")]

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
    catalog = Mock(spec=["get_all"])
    catalog.get_all.return_value = [Mock(title="Careful Circles", id="26-careful-circles")]

    result = _run(
        create_submission_impl(
            venue_name="Rattle",
            poems=["careful circles"],  # case-insensitive match
            submitted_date="2026-08-23",
            sub_cat=sub_cat,
            catalog=catalog,
        ),
        cfg,
    )
    assert result.success is True
    assert result.warnings == []


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
