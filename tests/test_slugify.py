"""Tests for slugify_filename, which guards venue/submission file writes.

Venue files are written to `venues_dir / f"{venue_name}.md"` with venue_name
coming from frontmatter; without sanitizing, a name like "../../x" would escape
the vault. slugify_filename strips those characters.
"""

from poetry_mcp.utils import slugify_filename


def test_slugify_removes_path_separators():
    result = slugify_filename("../../etc/passwd")
    assert "/" not in result
    assert ".." not in result
    assert result == "etcpasswd"


def test_slugify_normalizes_whitespace():
    assert slugify_filename("The Georgia Review") == "The-Georgia-Review"


def test_slugify_empty_falls_back():
    assert slugify_filename("...") == "untitled"
    assert slugify_filename("") == "untitled"
    assert slugify_filename("/") == "untitled"


def test_venue_write_path_stays_inside_dir(tmp_path):
    venues_dir = tmp_path / "venues"
    venues_dir.mkdir()
    evil = "../../../etc/passwd"
    output_path = venues_dir / f"{slugify_filename(evil)}.md"
    # The resolved write path must remain under venues_dir.
    assert venues_dir.resolve() in output_path.resolve().parents
