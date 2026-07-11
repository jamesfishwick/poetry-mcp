"""
Test SubmissionCatalog API to prevent AttributeError regressions.

This test suite ensures the public API of SubmissionCatalog remains stable
and that internal implementation details aren't accidentally exposed or accessed.
"""

from pathlib import Path

import pytest

from poetry_mcp.catalog.submission_catalog import SubmissionCatalog


def test_direct_attribute_access_raises_error(tmp_path):
    """
    Verify that accessing internal attributes raises AttributeError.

    This is a regression test for the bug where sync_submissions tried to access
    sub_cat.all_submissions directly, which doesn't exist on the public API.
    """
    catalog = SubmissionCatalog(submissions_dir=tmp_path)

    # Attempting to access internal attributes should raise AttributeError
    with pytest.raises(
        AttributeError, match="'SubmissionCatalog' object has no attribute 'all_submissions'"
    ):
        _ = catalog.all_submissions


def test_get_all_method_works(tmp_path):
    """
    Verify get_all() is the correct way to retrieve all submissions.

    This is the public API that should be used instead of direct attribute access.
    """
    catalog = SubmissionCatalog(submissions_dir=tmp_path)
    catalog.sync()

    # get_all() should work and return a list
    all_submissions = catalog.get_all()
    assert isinstance(all_submissions, list)


def test_get_all_returns_copy(tmp_path):
    """
    Verify get_all() returns a copy, not a reference to internal data.

    This ensures encapsulation - modifications to the returned list
    shouldn't affect the catalog's internal state.
    """
    catalog = SubmissionCatalog(submissions_dir=tmp_path)
    catalog.sync()

    # Get the list twice
    list1 = catalog.get_all()
    list2 = catalog.get_all()

    # Should be equal in content
    assert list1 == list2

    # But not the same object (copy, not reference)
    assert list1 is not list2


def test_sync_submissions_pattern(tmp_path, monkeypatch):
    """
    Test the exact pattern used in sync_submissions tool.

    This simulates what happens in server.py line 973 to ensure
    the fix prevents the AttributeError from occurring.
    """
    catalog = SubmissionCatalog(submissions_dir=tmp_path)
    catalog.sync()

    # This is the CORRECT pattern (post-fix)
    all_submissions = catalog.get_all()
    venue_names = set(sub.venue_name for sub in all_submissions)

    # Should complete without errors
    assert isinstance(venue_names, set)

    # The OLD pattern should fail (pre-fix) - uncomment to verify:
    # with pytest.raises(AttributeError):
    #     all_submissions = catalog.all_submissions  # This was the bug
    #     venue_names = set(sub.venue_name for sub in all_submissions)


def test_public_api_surface():
    """
    Document the stable public API of SubmissionCatalog.

    Any changes to these methods should be considered breaking changes
    and require careful review.
    """
    catalog = SubmissionCatalog(submissions_dir=Path("/tmp"))

    # These public methods must always exist
    assert hasattr(catalog, "sync")
    assert hasattr(catalog, "get_all")
    assert hasattr(catalog, "get_by_venue")
    assert hasattr(catalog, "get_by_status")
    assert hasattr(catalog, "get_by_poem")
    assert hasattr(catalog, "filter_submissions")
    assert hasattr(catalog, "get_summary")

    # These should be callable
    assert callable(catalog.sync)
    assert callable(catalog.get_all)
    assert callable(catalog.get_by_venue)
    assert callable(catalog.get_by_status)
    assert callable(catalog.get_by_poem)
    assert callable(catalog.filter_submissions)
    assert callable(catalog.get_summary)
