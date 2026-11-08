"""Tests for update_poem_chains in the frontmatter writer.

Every test writes a real poem file under tmp_path and reads the bytes back.
Nothing is mocked: the writer mutates an Obsidian vault with no backups, so
the thing worth proving is what actually lands on disk.

The round-trip test at the end parses the written file through
parse_poem_file, which is the read the chain tools depend on after a sync.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from poetry_mcp.parsers.frontmatter_parser import parse_poem_file
from poetry_mcp.writers.frontmatter_writer import update_poem_chains

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POEM_FILENAME = "river.md"
BACKUP_SUFFIX = ".md.bak"

CHAIN_WATER = "water-sequence"
CHAIN_STONE = "stone-cycle"
CHAIN_ABSENT = "never-joined"

POSITION_FIRST = 1
POSITION_THIRD = 3
POSITION_FIFTH = 5

ORIGINAL_UPDATED_AT = "2024-01-01T12:00:00"

# Leading blank line and trailing newline are deliberate: the body-preservation
# test checks these bytes survive untouched.
POEM_BODY = """
# The River

The river flows
through ancient stones

carrying stories
from mountain to sea
"""

# Frontmatter the chain writer must never touch.
UNRELATED_FRONTMATTER: dict[str, Any] = {
    "state": "completed",
    "form": "free_verse",
    "tags": ["nature", "water"],
    "notes": "A poem about rivers",
    "created_at": "2024-01-01T12:00:00",
}


# ---------------------------------------------------------------------------
# Factory and readers (independent of the writer's own parser)
# ---------------------------------------------------------------------------


def write_poem(
    directory: Path,
    frontmatter: dict[str, Any] | None,
    body: str = POEM_BODY,
    filename: str = POEM_FILENAME,
) -> Path:
    """Write a poem file with the given frontmatter and return its path.

    frontmatter=None writes a body-only file with no frontmatter block.
    Chain keys are merged on top of UNRELATED_FRONTMATTER plus the original
    updated_at so each test only names what it cares about.
    """
    path = directory / filename
    if frontmatter is None:
        path.write_text(body, encoding="utf-8")
        return path

    merged = {**UNRELATED_FRONTMATTER, "updated_at": ORIGINAL_UPDATED_AT, **frontmatter}
    yaml_text = yaml.dump(merged, default_flow_style=False, sort_keys=False).strip()
    path.write_text(f"---\n{yaml_text}\n---\n{body}", encoding="utf-8")
    return path


def read_frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    """Split a poem file into (frontmatter dict, raw body) without the writer."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no frontmatter block"
    yaml_text, _, body = text[len("---\n") :].partition("\n---\n")
    return yaml.safe_load(yaml_text) or {}, body


def read_frontmatter(path: Path) -> dict[str, Any]:
    return read_frontmatter_and_body(path)[0]


def backup_path_for(path: Path) -> Path:
    return path.with_suffix(BACKUP_SUFFIX)


# ---------------------------------------------------------------------------
# Adding chains
# ---------------------------------------------------------------------------


def test_add_chain_to_poem_with_no_chains(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_added == [CHAIN_WATER]
    assert result.chains_removed == []
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER]


def test_add_chain_already_present_is_idempotent(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_added == [], "re-adding an existing chain must report nothing added"
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER], "chain must not be duplicated"


def test_add_keeps_existing_chains_and_writes_sorted(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_STONE], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert read_frontmatter(poem)["chains"] == sorted([CHAIN_STONE, CHAIN_WATER])


@pytest.mark.parametrize(
    "raw_chain_id",
    [
        "Water-Sequence",
        "water sequence",
        "  water-sequence  ",
        " Water Sequence ",
    ],
)
def test_add_normalizes_chain_id_to_lowercase_hyphenated(tmp_path, raw_chain_id):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act
    result = update_poem_chains(poem, chains_to_add=[raw_chain_id], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_added == [CHAIN_WATER], f"{raw_chain_id!r} should normalize"
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER]


def test_add_chain_to_poem_without_frontmatter_creates_block(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter=None)

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    frontmatter, body = read_frontmatter_and_body(poem)
    assert frontmatter["chains"] == [CHAIN_WATER]
    assert body == POEM_BODY, "body must be carried under the new frontmatter block unchanged"


def test_accepts_string_path(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act
    result = update_poem_chains(str(poem), chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.file_path == str(poem)
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER]


# ---------------------------------------------------------------------------
# Removing chains
# ---------------------------------------------------------------------------


def test_remove_chain(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_STONE, CHAIN_WATER]})

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_removed == [CHAIN_WATER]
    assert read_frontmatter(poem)["chains"] == [CHAIN_STONE]


def test_remove_chain_not_present_is_a_noop(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_ABSENT], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_removed == [], "removing an absent chain must report nothing removed"
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER]


def test_remove_last_chain_leaves_empty_list(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert read_frontmatter(poem)["chains"] == []
    assert result.updated_chains == []


def test_remove_normalizes_chain_id(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(
        poem, chains_to_remove=[" Water Sequence "], create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    assert result.chains_removed == [CHAIN_WATER]
    assert read_frontmatter(poem)["chains"] == []


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


def test_position_update_sets_position_for_member_chain(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(
        poem, position_updates={CHAIN_WATER: POSITION_THIRD}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    assert result.positions_updated == {CHAIN_WATER: POSITION_THIRD}
    assert read_frontmatter(poem)["chain_positions"] == {CHAIN_WATER: POSITION_THIRD}


def test_position_update_overwrites_existing_position(tmp_path):
    # Arrange
    poem = write_poem(
        tmp_path,
        frontmatter={"chains": [CHAIN_WATER], "chain_positions": {CHAIN_WATER: POSITION_FIRST}},
    )

    # Act
    result = update_poem_chains(
        poem, position_updates={CHAIN_WATER: POSITION_FIFTH}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    assert read_frontmatter(poem)["chain_positions"] == {CHAIN_WATER: POSITION_FIFTH}


def test_position_update_for_chain_poem_is_not_in_is_ignored(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(
        poem, position_updates={CHAIN_ABSENT: POSITION_FIRST}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    assert result.positions_updated is None, "a position on a non-member chain must not be set"
    frontmatter = read_frontmatter(poem)
    assert "chain_positions" not in frontmatter, f"unexpected positions: {frontmatter}"
    assert frontmatter["chains"] == [CHAIN_WATER], "membership must not be granted by position"


def test_position_update_none_removes_position_but_keeps_membership(tmp_path):
    # Arrange: two positioned chains so chain_positions survives with one entry
    poem = write_poem(
        tmp_path,
        frontmatter={
            "chains": [CHAIN_STONE, CHAIN_WATER],
            "chain_positions": {CHAIN_STONE: POSITION_FIRST, CHAIN_WATER: POSITION_THIRD},
        },
    )

    # Act
    result = update_poem_chains(
        poem, position_updates={CHAIN_WATER: None}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    frontmatter = read_frontmatter(poem)
    assert frontmatter["chains"] == [CHAIN_STONE, CHAIN_WATER], "poem must stay in the chain"
    assert frontmatter["chain_positions"] == {CHAIN_STONE: POSITION_FIRST}
    assert result.positions_updated is None, "clearing a position is not a position set"


def test_add_and_position_in_one_call(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act: the docstring example, add then position in the same write
    result = update_poem_chains(
        poem,
        chains_to_add=[CHAIN_WATER],
        position_updates={CHAIN_WATER: POSITION_THIRD},
        create_backup_file=False,
    )

    # Assert
    assert result.success, result.error
    assert result.chains_added == [CHAIN_WATER]
    assert result.positions_updated == {CHAIN_WATER: POSITION_THIRD}
    frontmatter = read_frontmatter(poem)
    assert frontmatter["chains"] == [CHAIN_WATER]
    assert frontmatter["chain_positions"] == {CHAIN_WATER: POSITION_THIRD}


def test_position_update_normalizes_chain_id(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})

    # Act
    result = update_poem_chains(
        poem, position_updates={"Water Sequence": POSITION_THIRD}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    assert read_frontmatter(poem)["chain_positions"] == {CHAIN_WATER: POSITION_THIRD}


def test_remove_chain_also_removes_its_position(tmp_path):
    # Arrange
    poem = write_poem(
        tmp_path,
        frontmatter={
            "chains": [CHAIN_STONE, CHAIN_WATER],
            "chain_positions": {CHAIN_STONE: POSITION_FIRST, CHAIN_WATER: POSITION_THIRD},
        },
    )

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    frontmatter = read_frontmatter(poem)
    assert frontmatter["chains"] == [CHAIN_STONE]
    assert frontmatter["chain_positions"] == {CHAIN_STONE: POSITION_FIRST}, (
        "removed chain must not leave an orphaned position"
    )


def test_chain_positions_key_removed_when_last_positioned_chain_goes(tmp_path):
    # Arrange
    poem = write_poem(
        tmp_path,
        frontmatter={"chains": [CHAIN_WATER], "chain_positions": {CHAIN_WATER: POSITION_THIRD}},
    )

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    frontmatter = read_frontmatter(poem)
    assert "chain_positions" not in frontmatter, (
        f"chain_positions should be dropped, not left empty: {frontmatter.get('chain_positions')!r}"
    )
    assert result.updated_positions is None


def test_chain_positions_written_sorted_by_chain_id(tmp_path):
    # Arrange: existing positions in reverse order on disk
    poem = write_poem(
        tmp_path,
        frontmatter={
            "chains": [CHAIN_WATER, CHAIN_STONE],
            "chain_positions": {CHAIN_WATER: POSITION_THIRD, CHAIN_STONE: POSITION_FIRST},
        },
    )

    # Act
    result = update_poem_chains(
        poem, position_updates={CHAIN_WATER: POSITION_FIFTH}, create_backup_file=False
    )

    # Assert
    assert result.success, result.error
    positions = read_frontmatter(poem)["chain_positions"]
    assert list(positions.keys()) == sorted(positions.keys()), f"keys unsorted: {positions}"
    assert positions == {CHAIN_STONE: POSITION_FIRST, CHAIN_WATER: POSITION_FIFTH}


# ---------------------------------------------------------------------------
# Preservation of everything else
# ---------------------------------------------------------------------------


def test_preserves_unrelated_frontmatter_and_body_bytes(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_WATER]})
    _, original_body = read_frontmatter_and_body(poem)

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_STONE], create_backup_file=False)

    # Assert
    assert result.success, result.error
    frontmatter, body = read_frontmatter_and_body(poem)
    assert body == original_body, "poem body must survive byte-for-byte"
    assert body == POEM_BODY
    for key, value in UNRELATED_FRONTMATTER.items():
        assert frontmatter[key] == value, f"frontmatter key {key!r} was changed"


def test_updated_at_is_rewritten_as_iso_timestamp(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})
    before = datetime.now()

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    written = read_frontmatter(poem)["updated_at"]
    assert written != ORIGINAL_UPDATED_AT, "updated_at must be stamped on every chain write"
    assert datetime.fromisoformat(written) >= before, f"updated_at {written} predates the write"


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


def test_backup_created_with_original_bytes_when_requested(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})
    original_bytes = poem.read_bytes()
    backup = backup_path_for(poem)
    assert not backup.exists(), "precondition: no backup before the write"

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=True)

    # Assert
    assert result.success, result.error
    assert result.backup_path == str(backup)
    assert backup.exists(), f"backup missing at {backup}"
    assert backup.read_bytes() == original_bytes, "backup must hold the pre-write bytes"
    assert poem.read_bytes() != original_bytes, "the poem itself must have changed"


def test_no_backup_when_create_backup_file_false(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})
    backup = backup_path_for(poem)

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.backup_path is None
    assert not backup.exists(), f"backup written at {backup} despite create_backup_file=False"


# ---------------------------------------------------------------------------
# Failure paths: return a failed result, never raise, never touch the file
# ---------------------------------------------------------------------------


def test_missing_file_returns_failed_result(tmp_path):
    # Arrange
    missing = tmp_path / "does-not-exist.md"

    # Act
    result = update_poem_chains(missing, chains_to_add=[CHAIN_WATER])

    # Assert
    assert not result.success
    assert result.error is not None and "not found" in result.error.lower(), result.error
    assert result.file_path == str(missing)
    assert result.backup_path is None
    assert not missing.exists(), "a failed update must not create the file"
    # Property fallbacks on a result with no final state recorded
    assert result.updated_chains == [], "falls back to chains_added, which is empty"
    assert result.updated_positions is None


def test_unclosed_frontmatter_returns_failed_result_and_leaves_file_alone(tmp_path):
    # Arrange
    poem = tmp_path / POEM_FILENAME
    poem.write_text("---\nstate: completed\nchains:\n- water-sequence\n\nNo closing fence\n")
    original_bytes = poem.read_bytes()

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_STONE], create_backup_file=True)

    # Assert
    assert not result.success
    assert result.error is not None and "unclosed frontmatter" in result.error.lower(), result.error
    assert poem.read_bytes() == original_bytes, "malformed file must not be rewritten"
    assert not backup_path_for(poem).exists(), "no backup should be taken before parsing succeeds"


def test_invalid_yaml_frontmatter_returns_failed_result(tmp_path):
    # Arrange
    poem = tmp_path / POEM_FILENAME
    poem.write_text("---\nstate: [unterminated\nchains: {bad\n---\n\n# Broken\n")
    original_bytes = poem.read_bytes()

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert not result.success
    assert result.error is not None and "invalid yaml" in result.error.lower(), result.error
    assert poem.read_bytes() == original_bytes, "malformed file must not be rewritten"


# ---------------------------------------------------------------------------
# Result properties
# ---------------------------------------------------------------------------


def test_result_properties_report_final_state_not_the_delta(tmp_path):
    # Arrange
    poem = write_poem(
        tmp_path,
        frontmatter={"chains": [CHAIN_WATER], "chain_positions": {CHAIN_WATER: POSITION_FIRST}},
    )

    # Act: add one chain and position it; the pre-existing chain is untouched
    result = update_poem_chains(
        poem,
        chains_to_add=[CHAIN_STONE],
        position_updates={CHAIN_STONE: POSITION_THIRD},
        create_backup_file=False,
    )

    # Assert: deltas
    assert result.chains_added == [CHAIN_STONE]
    assert result.positions_updated == {CHAIN_STONE: POSITION_THIRD}, (
        "positions_updated is the delta, only what this call set"
    )
    # Assert: final state, matching what is on disk
    frontmatter = read_frontmatter(poem)
    assert result.updated_chains == [CHAIN_STONE, CHAIN_WATER]
    assert result.updated_chains == frontmatter["chains"]
    assert result.updated_positions == {CHAIN_STONE: POSITION_THIRD, CHAIN_WATER: POSITION_FIRST}
    assert result.updated_positions == frontmatter["chain_positions"]


def test_positions_updated_is_none_when_no_position_was_set(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.positions_updated is None
    assert result.updated_positions is None


# ---------------------------------------------------------------------------
# Round trip through the parser the chain tools read with
# ---------------------------------------------------------------------------


def test_written_file_round_trips_through_parse_poem_file(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": [CHAIN_STONE]})

    # Act
    result = update_poem_chains(
        poem,
        chains_to_add=[CHAIN_WATER],
        position_updates={CHAIN_WATER: POSITION_THIRD},
        create_backup_file=False,
    )
    parsed = parse_poem_file(poem, vault_root=tmp_path)

    # Assert
    assert result.success, result.error
    assert parsed.chains == [CHAIN_STONE, CHAIN_WATER]
    assert parsed.chain_positions == {CHAIN_WATER: POSITION_THIRD}
    assert parsed.chains == result.updated_chains, "parser and writer disagree on chains"
    assert parsed.chain_positions == result.updated_positions, (
        "parser and writer disagree on positions"
    )
    assert parsed.state == UNRELATED_FRONTMATTER["state"]


def test_loose_chain_round_trips_with_no_positions(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)
    parsed = parse_poem_file(poem, vault_root=tmp_path)

    # Assert
    assert result.success, result.error
    assert parsed.chains == [CHAIN_WATER]
    assert parsed.chain_positions is None, "a loose chain must parse back with no positions"


# ---------------------------------------------------------------------------
# Existing frontmatter is normalized before matching, and null keys are empty
# ---------------------------------------------------------------------------


def test_remove_matches_unnormalized_chain_already_in_frontmatter(tmp_path):
    # Arrange: chain id as a human might type it in Obsidian
    poem = write_poem(tmp_path, frontmatter={"chains": ["Water Sequence"]})

    # Act
    result = update_poem_chains(poem, chains_to_remove=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert result.chains_removed == [CHAIN_WATER]
    assert read_frontmatter(poem)["chains"] == []


def test_null_chains_key_is_treated_as_empty(tmp_path):
    # Arrange
    poem = write_poem(tmp_path, frontmatter={"chains": None})

    # Act
    result = update_poem_chains(poem, chains_to_add=[CHAIN_WATER], create_backup_file=False)

    # Assert
    assert result.success, result.error
    assert read_frontmatter(poem)["chains"] == [CHAIN_WATER]
