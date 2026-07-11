"""Regression test for the sync_submissions venue auto-regen step.

sync_submissions read `sub_cat.all_submissions`, but SubmissionCatalog has no
such attribute (it lives on the index; the public accessor is get_all()). The
tool therefore raised AttributeError at the venue-regeneration step for every
call. This drives the real tool against a temp vault and asserts it completes.
"""

import asyncio
from unittest.mock import Mock, patch

import poetry_mcp.server as server_module


def test_sync_submissions_completes_without_attribute_error(tmp_path):
    vault = tmp_path / "vault"
    (vault / "submissions").mkdir(parents=True)
    (vault / "venues").mkdir()
    (vault / "submissions" / "2025-01-01_Poem_TestVenue.md").write_text(
        "---\n"
        "venue_name: TestVenue\n"
        "status: submitted\n"
        "submitted_date: 2025-01-01\n"
        "---\n\n"
        "## Poems\n"
        "[[My Poem]]\n"
    )
    cfg = Mock(vault=Mock(path=vault, submissions_dir="submissions", venues_dir="venues"))

    with patch.object(server_module, "load_config", return_value=cfg):
        # Point the module-global catalogs at the temp vault, and reset after
        # so this test never leaks a temp catalog into others.
        server_module.submission_catalog = None
        server_module.venue_catalog = None
        try:
            result = asyncio.run(server_module.sync_submissions.fn())
        finally:
            server_module.submission_catalog = None
            server_module.venue_catalog = None

    # Before the fix this raised AttributeError before returning.
    assert result.success is True
    assert result.total_submissions == 1
