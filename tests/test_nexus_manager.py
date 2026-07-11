"""Tests for NexusManager (previously ~21% covered, zero direct tests).

Covers create/delete/update, and specifically guards the update_nexus fixes:
new_description is now honored (was silently ignored), and a canonical_tag
value appearing in the body no longer corrupts the frontmatter edit (the old
string-replace approach was fragile).
"""

from pathlib import Path

import pytest

from poetry_mcp.catalog.nexus_manager import NexusManager
from poetry_mcp.errors import BaseParseError as ParseError


def _manager(tmp_path) -> NexusManager:
    return NexusManager(nexus_root=tmp_path / "nexus")


def test_create_nexus_writes_file(tmp_path):
    mgr = _manager(tmp_path)
    nexus = mgr.create_nexus("Water", "theme", "water", "Water imagery")
    assert nexus.canonical_tag == "water"
    content = Path(nexus.file_path).read_text()
    assert "canonical_tag: water" in content
    assert "Water imagery" in content  # description lands in the body


def test_create_nexus_duplicate_raises(tmp_path):
    mgr = _manager(tmp_path)
    mgr.create_nexus("Water", "theme", "water", "desc")
    with pytest.raises(ParseError, match="already exists"):
        mgr.create_nexus("Water", "theme", "water", "desc")


def test_delete_nexus_removes_file(tmp_path):
    mgr = _manager(tmp_path)
    nexus = mgr.create_nexus("Fire", "theme", "fire", "Fire imagery")
    assert Path(nexus.file_path).exists()
    result = mgr.delete_nexus("Fire", "theme", force=True)
    assert result["status"] == "success"
    assert not Path(nexus.file_path).exists()


def test_delete_nexus_not_found_raises(tmp_path):
    mgr = _manager(tmp_path)
    with pytest.raises(ParseError, match="not found"):
        mgr.delete_nexus("Ghost", "theme")


def test_update_nexus_changes_canonical_tag(tmp_path):
    mgr = _manager(tmp_path)
    mgr.create_nexus("Water", "theme", "water", "Water imagery")
    updated = mgr.update_nexus("Water", "theme", new_canonical_tag="liquid")
    assert updated.canonical_tag == "liquid"
    content = Path(updated.file_path).read_text()
    assert "canonical_tag: liquid" in content
    assert "canonical_tag: water" not in content


def test_update_nexus_honors_new_description(tmp_path):
    # Regression: new_description used to be silently ignored.
    mgr = _manager(tmp_path)
    mgr.create_nexus("Water", "theme", "water", "Old description")
    updated = mgr.update_nexus("Water", "theme", new_description="Fresh description")
    assert updated.description == "Fresh description"
    content = Path(updated.file_path).read_text()
    assert "Fresh description" in content
    assert "Old description" not in content
    # canonical_tag untouched when only description changes
    assert "canonical_tag: water" in content


def test_update_nexus_tag_value_in_body_no_corruption(tmp_path):
    # Regression: the old string-replace corrupted edits when the tag value
    # appeared in the body prose.
    mgr = _manager(tmp_path)
    mgr.create_nexus("Water", "theme", "water", "poems about water and rivers")
    updated = mgr.update_nexus("Water", "theme", new_canonical_tag="liquid")
    content = Path(updated.file_path).read_text()
    assert "canonical_tag: liquid" in content
    assert "poems about water and rivers" in content  # body prose preserved


def test_update_nexus_not_found_raises(tmp_path):
    mgr = _manager(tmp_path)
    with pytest.raises(ParseError, match="not found"):
        mgr.update_nexus("Ghost", "theme", new_canonical_tag="x")
