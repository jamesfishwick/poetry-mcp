"""Tests for frontmatter writer module."""

import pytest
from pathlib import Path
import tempfile
import shutil

from poetry_mcp.writers.frontmatter_writer import (
    update_poem_tags,
    update_poem_chains,
    update_poem_frontmatter,
    extract_frontmatter_and_content,
    serialize_frontmatter_and_content,
    rollback_from_backup,
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


# =============================================================================
# Tests for update_poem_chains
# =============================================================================


@pytest.fixture
def sample_poem_with_chains(temp_dir):
    """Create a sample poem file with existing chains."""
    poem_content = """---
state: completed
form: free_verse
tags:
  - nature
chains:
  - water-sequence
  - grief-cycle
chain_positions:
  water-sequence: 3
created_at: '2024-01-01T12:00:00'
updated_at: '2024-01-01T12:00:00'
---

# A Poem with Chains

Content goes here.
"""
    poem_path = temp_dir / "poem_with_chains.md"
    poem_path.write_text(poem_content)
    return poem_path


class TestUpdatePoemChains:
    """Tests for update_poem_chains function."""

    def test_add_chain_to_poem_without_chains(self, sample_poem_with_frontmatter):
        """Test adding a chain to a poem that has no chains."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_add=["water-sequence"],
            create_backup_file=True,
        )

        assert result.success
        assert "water-sequence" in result.chains_added
        assert result.backup_path is not None

        # Verify chains were added
        content = sample_poem_with_frontmatter.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_frontmatter
        )
        assert "water-sequence" in frontmatter["chains"]

    def test_add_chain_with_position(self, sample_poem_with_frontmatter):
        """Test adding a chain with position (ordered sequence)."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_add=["my-sequence"],
            position_updates={"my-sequence": 5},
            create_backup_file=True,
        )

        assert result.success
        assert "my-sequence" in result.chains_added
        assert result.positions_updated == {"my-sequence": 5}

        # Verify chain and position
        content = sample_poem_with_frontmatter.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_frontmatter
        )
        assert "my-sequence" in frontmatter["chains"]
        assert frontmatter["chain_positions"]["my-sequence"] == 5

    def test_add_multiple_chains(self, sample_poem_with_frontmatter):
        """Test adding multiple chains at once."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_add=["chain-a", "chain-b", "chain-c"],
            create_backup_file=False,
        )

        assert result.success
        assert len(result.chains_added) == 3
        assert "chain-a" in result.chains_added
        assert "chain-b" in result.chains_added
        assert "chain-c" in result.chains_added

    def test_remove_chain_from_poem(self, sample_poem_with_chains):
        """Test removing a chain from a poem."""
        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_remove=["water-sequence"],
            create_backup_file=True,
        )

        assert result.success
        assert "water-sequence" in result.chains_removed

        # Verify chain was removed
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert "water-sequence" not in frontmatter["chains"]
        # Position should also be removed
        assert "water-sequence" not in frontmatter.get("chain_positions", {})

    def test_remove_chain_clears_position(self, sample_poem_with_chains):
        """Test that removing a chain also clears its position."""
        # Verify initial state
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert frontmatter["chain_positions"]["water-sequence"] == 3

        # Remove the chain
        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_remove=["water-sequence"],
        )

        assert result.success

        # Verify position was cleared
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        positions = frontmatter.get("chain_positions", {})
        assert "water-sequence" not in positions

    def test_add_and_remove_chains_simultaneously(self, sample_poem_with_chains):
        """Test adding and removing chains in the same operation."""
        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["new-chain"],
            chains_to_remove=["grief-cycle"],
            create_backup_file=True,
        )

        assert result.success
        assert "new-chain" in result.chains_added
        assert "grief-cycle" in result.chains_removed

        # Verify changes
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert "new-chain" in frontmatter["chains"]
        assert "grief-cycle" not in frontmatter["chains"]
        assert "water-sequence" in frontmatter["chains"]  # Preserved

    def test_update_position_for_existing_chain(self, sample_poem_with_chains):
        """Test updating position for an existing chain."""
        result = update_poem_chains(
            sample_poem_with_chains,
            position_updates={"water-sequence": 7},
        )

        assert result.success
        assert result.positions_updated == {"water-sequence": 7}

        # Verify position was updated
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert frontmatter["chain_positions"]["water-sequence"] == 7

    def test_remove_position_to_convert_to_loose(self, sample_poem_with_chains):
        """Test removing position (converting ordered to loose collection)."""
        result = update_poem_chains(
            sample_poem_with_chains,
            position_updates={"water-sequence": None},  # Remove position
        )

        assert result.success

        # Verify position was removed but chain remains
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert "water-sequence" in frontmatter["chains"]
        # chain_positions may be empty or not have water-sequence
        positions = frontmatter.get("chain_positions", {})
        assert "water-sequence" not in positions

    def test_chain_id_normalization(self, sample_poem_with_frontmatter):
        """Test that chain IDs are normalized (lowercase, hyphens)."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_add=["Water Sequence", "GRIEF CYCLE"],
        )

        assert result.success
        # Check normalized IDs were used
        assert "water-sequence" in result.chains_added
        assert "grief-cycle" in result.chains_added

        # Verify in file
        content = sample_poem_with_frontmatter.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_frontmatter
        )
        assert "water-sequence" in frontmatter["chains"]
        assert "grief-cycle" in frontmatter["chains"]

    def test_adding_duplicate_chain_is_idempotent(self, sample_poem_with_chains):
        """Test that adding an existing chain doesn't duplicate it."""
        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["water-sequence"],  # Already exists
        )

        assert result.success
        assert len(result.chains_added) == 0  # Not added again

        # Verify only one instance
        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )
        assert frontmatter["chains"].count("water-sequence") == 1

    def test_removing_nonexistent_chain_is_idempotent(
        self, sample_poem_with_frontmatter
    ):
        """Test that removing a nonexistent chain doesn't cause error."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_remove=["nonexistent-chain"],
        )

        assert result.success
        assert len(result.chains_removed) == 0

    def test_position_update_for_nonexistent_chain_ignored(
        self, sample_poem_with_frontmatter
    ):
        """Test that position update for chain not in poem is ignored."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            position_updates={"nonexistent": 5},  # Chain not in poem
        )

        assert result.success
        # Position should not be set since chain doesn't exist
        assert result.positions_updated is None or "nonexistent" not in (
            result.positions_updated or {}
        )

    def test_preserves_other_frontmatter_fields(self, sample_poem_with_chains):
        """Test that chain updates preserve all other frontmatter."""
        # Get original frontmatter
        content = sample_poem_with_chains.read_text()
        original_fm, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )

        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["new-chain"],
        )

        assert result.success

        # Verify other fields preserved
        content = sample_poem_with_chains.read_text()
        new_fm, _ = extract_frontmatter_and_content(content, sample_poem_with_chains)

        assert new_fm["state"] == original_fm["state"]
        assert new_fm["form"] == original_fm["form"]
        assert new_fm["tags"] == original_fm["tags"]
        assert new_fm["created_at"] == original_fm["created_at"]

    def test_preserves_poem_body_content(self, sample_poem_with_chains):
        """Test that chain updates don't modify poem body."""
        content = sample_poem_with_chains.read_text()
        _, original_body = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )

        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["new-chain"],
            chains_to_remove=["grief-cycle"],
            position_updates={"new-chain": 1},
        )

        assert result.success

        content = sample_poem_with_chains.read_text()
        _, new_body = extract_frontmatter_and_content(content, sample_poem_with_chains)

        assert new_body.strip() == original_body.strip()

    def test_file_not_found_error(self, temp_dir):
        """Test error when file doesn't exist."""
        fake_path = temp_dir / "nonexistent.md"
        result = update_poem_chains(
            fake_path,
            chains_to_add=["test-chain"],
        )

        assert not result.success
        assert "not found" in result.error.lower()

    def test_chains_sorted_alphabetically(self, sample_poem_with_frontmatter):
        """Test that chains are stored in alphabetical order."""
        result = update_poem_chains(
            sample_poem_with_frontmatter,
            chains_to_add=["zebra", "alpha", "middle"],
        )

        assert result.success

        content = sample_poem_with_frontmatter.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_frontmatter
        )

        assert frontmatter["chains"] == ["alpha", "middle", "zebra"]

    def test_empty_chains_after_all_removed(self, sample_poem_with_chains):
        """Test that chain_positions is removed when all chains are removed."""
        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_remove=["water-sequence", "grief-cycle"],
        )

        assert result.success

        content = sample_poem_with_chains.read_text()
        frontmatter, _ = extract_frontmatter_and_content(
            content, sample_poem_with_chains
        )

        # chains should be empty list
        assert frontmatter["chains"] == []
        # chain_positions should not exist (or be empty)
        assert "chain_positions" not in frontmatter or not frontmatter.get(
            "chain_positions"
        )

    def test_backup_file_creation(self, sample_poem_with_chains):
        """Test that backup file is created correctly."""
        backup_path = sample_poem_with_chains.with_suffix(".md.bak")
        if backup_path.exists():
            backup_path.unlink()

        original_content = sample_poem_with_chains.read_text()

        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["new-chain"],
            create_backup_file=True,
        )

        assert result.success
        assert backup_path.exists()
        assert backup_path.read_text() == original_content

    def test_no_backup_when_disabled(self, sample_poem_with_chains):
        """Test that no backup is created when create_backup_file=False."""
        backup_path = sample_poem_with_chains.with_suffix(".md.bak")
        if backup_path.exists():
            backup_path.unlink()

        result = update_poem_chains(
            sample_poem_with_chains,
            chains_to_add=["new-chain"],
            create_backup_file=False,
        )

        assert result.success
        assert result.backup_path is None
        assert not backup_path.exists()

    def test_string_path_converted_to_path_object(self, sample_poem_with_chains):
        """Test that string paths are handled correctly."""
        result = update_poem_chains(
            str(sample_poem_with_chains),  # Pass as string
            chains_to_add=["new-chain"],
        )

        assert result.success
        assert "new-chain" in result.chains_added
