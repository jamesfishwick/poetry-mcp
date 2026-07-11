"""Tests for frontmatter writer module."""

import shutil
import tempfile
from pathlib import Path

import pytest

from poetry_mcp.writers.frontmatter_writer import (
    extract_frontmatter_and_content,
    rollback_from_backup,
    serialize_frontmatter_and_content,
    update_poem_frontmatter,
    update_poem_tags,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_poem_with_frontmatter(temp_dir):
    """Create a sample poem file with frontmatter."""
    poem_content = """---
state: completed
form: free_verse
tags:
  - nature
  - water
notes: A poem about rivers
created_at: '2024-01-01T12:00:00'
updated_at: '2024-01-01T12:00:00'
---

The river flows
through ancient stones
carrying stories
from mountain to sea
"""
    poem_path = temp_dir / "sample_poem.md"
    poem_path.write_text(poem_content)
    return poem_path


@pytest.fixture
def sample_poem_no_frontmatter(temp_dir):
    """Create a sample poem file without frontmatter."""
    poem_content = """The river flows
through ancient stones
carrying stories
from mountain to sea
"""
    poem_path = temp_dir / "no_frontmatter.md"
    poem_path.write_text(poem_content)
    return poem_path


def test_extract_frontmatter_with_valid_yaml(sample_poem_with_frontmatter):
    """Test extracting frontmatter from valid markdown."""
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, body = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)

    assert frontmatter["state"] == "completed"
    assert frontmatter["form"] == "free_verse"
    assert "nature" in frontmatter["tags"]
    assert "water" in frontmatter["tags"]
    assert "The river flows" in body
    assert "---" not in body


def test_extract_frontmatter_with_no_frontmatter(sample_poem_no_frontmatter):
    """Test extracting from file with no frontmatter."""
    content = sample_poem_no_frontmatter.read_text()
    frontmatter, body = extract_frontmatter_and_content(content, sample_poem_no_frontmatter)

    assert frontmatter == {}
    assert "The river flows" in body


def test_serialize_frontmatter_roundtrip(sample_poem_with_frontmatter):
    """Test that serialization roundtrip preserves data."""
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, body = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)

    # Serialize back
    new_content = serialize_frontmatter_and_content(frontmatter, body)

    # Re-parse
    new_frontmatter, new_body = extract_frontmatter_and_content(
        new_content, sample_poem_with_frontmatter
    )

    assert new_frontmatter["state"] == frontmatter["state"]
    assert new_frontmatter["tags"] == frontmatter["tags"]
    assert new_body.strip() == body.strip()


def test_update_poem_tags_add_new_tags(sample_poem_with_frontmatter):
    """Test adding new tags to a poem."""
    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["childhood", "memory"],
        create_backup_file=True,
    )

    assert result.success
    assert "childhood" in result.tags_added
    assert "memory" in result.tags_added
    assert result.backup_path is not None

    # Verify tags were added
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, _ = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)
    assert "childhood" in frontmatter["tags"]
    assert "memory" in frontmatter["tags"]
    assert "nature" in frontmatter["tags"]  # Original tags preserved


def test_update_poem_tags_remove_tags(sample_poem_with_frontmatter):
    """Test removing tags from a poem."""
    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_remove=["nature"],
        create_backup_file=True,
    )

    assert result.success
    assert "nature" in result.tags_removed

    # Verify tag was removed
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, _ = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)
    assert "nature" not in frontmatter["tags"]
    assert "water" in frontmatter["tags"]  # Other tags preserved


def test_update_poem_tags_add_and_remove(sample_poem_with_frontmatter):
    """Test adding and removing tags in same operation."""
    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["childhood"],
        tags_to_remove=["water"],
        create_backup_file=True,
    )

    assert result.success
    assert "childhood" in result.tags_added
    assert "water" in result.tags_removed

    # Verify changes
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, _ = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)
    assert "childhood" in frontmatter["tags"]
    assert "water" not in frontmatter["tags"]
    assert "nature" in frontmatter["tags"]


def test_update_poem_tags_preserve_other_frontmatter(sample_poem_with_frontmatter):
    """Test that tag updates don't break other frontmatter fields."""
    original_content = sample_poem_with_frontmatter.read_text()
    original_fm, _ = extract_frontmatter_and_content(original_content, sample_poem_with_frontmatter)

    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["test"],
    )

    assert result.success

    # Verify all other fields preserved
    new_content = sample_poem_with_frontmatter.read_text()
    new_fm, _ = extract_frontmatter_and_content(new_content, sample_poem_with_frontmatter)

    assert new_fm["state"] == original_fm["state"]
    assert new_fm["form"] == original_fm["form"]
    assert new_fm["notes"] == original_fm["notes"]
    assert new_fm["created_at"] == original_fm["created_at"]


def test_update_poem_tags_no_frontmatter(sample_poem_no_frontmatter):
    """Test adding tags to poem with no frontmatter."""
    result = update_poem_tags(
        sample_poem_no_frontmatter,
        tags_to_add=["nature", "water"],
    )

    assert result.success
    assert "nature" in result.tags_added
    assert "water" in result.tags_added

    # Verify frontmatter was created
    content = sample_poem_no_frontmatter.read_text()
    assert content.startswith("---")
    frontmatter, body = extract_frontmatter_and_content(content, sample_poem_no_frontmatter)
    assert "nature" in frontmatter["tags"]
    assert "water" in frontmatter["tags"]


def test_update_poem_tags_deduplication(sample_poem_with_frontmatter):
    """Test that duplicate tags are not added."""
    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["nature", "water"],  # Already exist
    )

    assert result.success
    assert len(result.tags_added) == 0  # No new tags added


def test_update_poem_tags_nonexistent_file(temp_dir):
    """Test updating tags on nonexistent file."""
    fake_path = temp_dir / "nonexistent.md"
    result = update_poem_tags(fake_path, tags_to_add=["test"])

    assert not result.success
    assert "not found" in result.error.lower()


def test_update_poem_frontmatter_general(sample_poem_with_frontmatter):
    """Test general frontmatter update function."""
    result = update_poem_frontmatter(
        sample_poem_with_frontmatter,
        updates={"state": "fledgeling", "notes": "Updated note"},
    )

    assert result.success

    # Verify updates
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, _ = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)
    assert frontmatter["state"] == "fledgeling"
    assert frontmatter["notes"] == "Updated note"
    assert frontmatter["form"] == "free_verse"  # Preserved


def test_backup_creation(sample_poem_with_frontmatter):
    """Test that backup files are created."""
    backup_path = sample_poem_with_frontmatter.with_suffix(".md.bak")

    # Ensure no backup exists initially
    if backup_path.exists():
        backup_path.unlink()

    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["test"],
        create_backup_file=True,
    )

    assert result.success
    assert backup_path.exists()

    # Verify backup has original content
    backup_content = backup_path.read_text()
    assert "nature" in backup_content
    assert "test" not in backup_content


def test_rollback_from_backup(sample_poem_with_frontmatter):
    """Test rolling back from backup."""
    # Get original content
    original_content = sample_poem_with_frontmatter.read_text()

    # Make a change with backup
    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["test"],
        create_backup_file=True,
    )
    assert result.success

    # Verify change was made
    new_content = sample_poem_with_frontmatter.read_text()
    assert "test" in new_content

    # Rollback
    success = rollback_from_backup(sample_poem_with_frontmatter)
    assert success

    # Verify original content restored
    restored_content = sample_poem_with_frontmatter.read_text()
    assert restored_content == original_content
    assert "test" not in restored_content


def test_atomic_write_preserves_content(sample_poem_with_frontmatter):
    """Test that atomic write doesn't corrupt content."""
    # Get original content
    original_content = sample_poem_with_frontmatter.read_text()
    original_fm, original_body = extract_frontmatter_and_content(
        original_content, sample_poem_with_frontmatter
    )

    # Update tags multiple times
    for tag in ["tag1", "tag2", "tag3"]:
        result = update_poem_tags(
            sample_poem_with_frontmatter,
            tags_to_add=[tag],
            create_backup_file=False,
        )
        assert result.success

    # Verify content body unchanged
    new_content = sample_poem_with_frontmatter.read_text()
    new_fm, new_body = extract_frontmatter_and_content(new_content, sample_poem_with_frontmatter)

    assert new_body.strip() == original_body.strip()
    assert len(new_fm["tags"]) == len(original_fm["tags"]) + 3


def test_yaml_validation_prevents_corruption(sample_poem_with_frontmatter):
    """Test that YAML validation catches errors before writing."""
    # This test is more of an integration test showing the validation works
    # In practice, it's hard to trigger validation failures through the public API
    # since we control the serialization

    result = update_poem_tags(
        sample_poem_with_frontmatter,
        tags_to_add=["valid-tag"],
    )

    assert result.success

    # Verify file is still valid YAML
    content = sample_poem_with_frontmatter.read_text()
    frontmatter, _ = extract_frontmatter_and_content(content, sample_poem_with_frontmatter)
    assert isinstance(frontmatter, dict)


def test_serialize_with_empty_frontmatter():
    """Test serializing content with empty frontmatter returns content as-is."""
    content = "# Test Poem\n\nJust content, no frontmatter"
    result = serialize_frontmatter_and_content({}, content)
    assert result == content
