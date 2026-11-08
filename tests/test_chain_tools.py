"""Tests for chain tools - linking poems into sequences and collections.

The tool tests run against a real ``Catalog`` over real poem files in a
temporary vault, synced for real, and wired through ``initialize_chain_tools``
exactly as the server does. No catalog or writer is mocked. An earlier version
of this file used ``Mock(spec=Catalog)`` with a no-op ``sync``, which kept these
tests green for the whole life of a bug where the parser never read ``chains``
or ``chain_positions`` back from frontmatter, so every chain vanished on the
next sync. Each tool test therefore asserts on two real outcomes: the poem
file's frontmatter after the call, and the catalog index after the real sync.
"""

from datetime import datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from poetry_mcp.catalog.catalog import Catalog, CatalogIndex
from poetry_mcp.models.poem import Poem
from poetry_mcp.tools.chain_tools import (
    create_chain,
    delete_chain,
    get_chain,
    initialize_chain_tools,
    list_chains,
    reorder_chain,
)

# The parser derives a poem's state from its top-level catalog folder, so this
# folder name is what makes every test poem a "completed" poem.
COMPLETED_FOLDER = "Completed"
COMPLETED_STATE = "completed"
POEM_FORM = "free_verse"
POEM_BODY = "This is poem content."

# Poem ids are the slugified filename stem, so these double as filenames.
POEM_1 = "poem-1"
POEM_2 = "poem-2"
POEM_3 = "poem-3"
MISSING_POEM = "nonexistent"

WATER_SEQUENCE = "water-sequence"
UNNORMALIZED_WATER_SEQUENCE = "Water Sequence"  # normalizes to WATER_SEQUENCE
GRIEF_CYCLE = "grief-cycle"
GRIEF_POEMS = "grief-poems"
WATER = "water"
GRIEF = "grief"
OTHER = "other"
MISSING_CHAIN = "nonexistent"

# Fixed timestamps for in-memory Poem objects in the model and index tests.
CREATED_AT = datetime(2024, 1, 1)
UPDATED_AT = datetime(2024, 6, 1)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_poem(
    poem_id: str,
    title: str | None = None,
    chains: list[str] | None = None,
    chain_positions: dict[str, int] | None = None,
) -> Poem:
    """Build an in-memory Poem for model and index tests (no file involved)."""
    return Poem(
        id=poem_id,
        title=title or default_title(poem_id),
        file_path=f"catalog/{COMPLETED_FOLDER}/{poem_id}.md",
        state=COMPLETED_STATE,
        form=POEM_FORM,
        tags=["test"],
        word_count=100,
        line_count=20,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
        chains=chains or [],
        chain_positions=chain_positions,
    )


def default_title(poem_id: str) -> str:
    """Title the factories give a poem when none is supplied ("poem-1" -> "Poem 1")."""
    return poem_id.replace("-", " ").title()


def poem_file(vault: Path, poem_id: str) -> Path:
    """Where write_poem puts a poem with this id."""
    return vault / "catalog" / COMPLETED_FOLDER / f"{poem_id}.md"


def write_poem(
    vault: Path,
    poem_id: str,
    title: str | None = None,
    chains: list[str] | None = None,
    chain_positions: dict[str, int] | None = None,
) -> str:
    """Write a real poem file into the vault and return its id.

    The id is what the parser will derive from the filename on sync. Chains
    and positions, when given, are declared in frontmatter the way the writer
    would persist them, so a test can start from a poem already in a chain.
    """
    frontmatter: dict = {"form": POEM_FORM, "tags": ["test"]}
    if chains:
        frontmatter["chains"] = chains
    if chain_positions:
        frontmatter["chain_positions"] = chain_positions

    path = poem_file(vault, poem_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n"
        f"# {title or default_title(poem_id)}\n\n{POEM_BODY}\n",
        encoding="utf-8",
    )
    return poem_id


def read_frontmatter(vault: Path, poem_id: str) -> dict:
    """Read a poem file's frontmatter straight off disk.

    Deliberately bypasses the project's parser: the parser is the component
    whose silence hid the original bug, so the file itself is the witness.
    """
    text = poem_file(vault, poem_id).read_text(encoding="utf-8")
    _, block, _ = text.split("---", 2)
    return yaml.safe_load(block) or {}


def synced_catalog(vault: Path) -> Catalog:
    """Build a real catalog over the vault, sync it, and wire the chain tools to it."""
    catalog = Catalog(vault_root=vault)
    catalog.sync()
    initialize_chain_tools(catalog)
    return catalog


def chain_ids_in_order(catalog: Catalog, chain_id: str) -> list[str]:
    """Poem ids in a chain as the index orders them (positions first, then title)."""
    return [poem.id for poem in catalog.index.get_by_chain(chain_id, ordered=True)]


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """An empty vault with the catalog folder the Catalog expects to scan."""
    (tmp_path / "catalog" / COMPLETED_FOLDER).mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Poem model
# ---------------------------------------------------------------------------


class TestPoemChainFields:
    """Chain fields on the Poem model."""

    def test_poem_with_chains_has_no_positions_by_default(self):
        # Arrange / Act
        poem = make_poem(POEM_1, chains=[WATER_SEQUENCE, GRIEF_CYCLE])

        # Assert
        assert poem.chains == [WATER_SEQUENCE, GRIEF_CYCLE]
        assert poem.chain_positions is None

    def test_poem_keeps_chain_positions(self):
        # Arrange / Act
        poem = make_poem(POEM_1, chains=[WATER_SEQUENCE], chain_positions={WATER_SEQUENCE: 3})

        # Assert
        assert poem.chains == [WATER_SEQUENCE]
        assert poem.chain_positions == {WATER_SEQUENCE: 3}

    def test_chain_ids_are_normalized_to_lowercase_hyphenated(self):
        # Arrange / Act
        poem = make_poem(POEM_1, chains=["Water Sequence", "GRIEF-CYCLE", "  loose  "])

        # Assert
        assert poem.chains == [WATER_SEQUENCE, GRIEF_CYCLE, "loose"]

    def test_chain_position_below_one_is_rejected(self):
        # Arrange
        invalid_position = 0  # positions are 1-based

        # Act
        with pytest.raises(ValidationError) as exc_info:
            make_poem(POEM_1, chains=[WATER], chain_positions={WATER: invalid_position})

        # Assert
        assert "positive integer" in str(exc_info.value)

    def test_chains_default_to_empty(self):
        # Arrange / Act
        poem = make_poem(POEM_1)

        # Assert
        assert poem.chains == []
        assert poem.chain_positions is None


# ---------------------------------------------------------------------------
# CatalogIndex
# ---------------------------------------------------------------------------


class TestCatalogIndexChains:
    """Chain indexing in CatalogIndex, on in-memory poems."""

    def test_add_poem_indexes_each_chain_membership(self):
        # Arrange
        index = CatalogIndex()

        # Act
        index.add_poem(make_poem(POEM_1, chains=[WATER]))
        index.add_poem(make_poem(POEM_2, chains=[WATER, GRIEF]))
        index.add_poem(make_poem(POEM_3, chains=[GRIEF]))

        # Assert
        assert set(index.by_chain[WATER]) == {POEM_1, POEM_2}
        assert set(index.by_chain[GRIEF]) == {POEM_2, POEM_3}

    def test_get_by_chain_orders_positioned_poems_first_then_loose_by_title(self):
        # Arrange
        index = CatalogIndex()
        index.add_poem(make_poem(POEM_1, chains=[WATER], chain_positions={WATER: 2}))
        index.add_poem(make_poem(POEM_2, chains=[WATER], chain_positions={WATER: 1}))
        index.add_poem(make_poem(POEM_3, chains=[WATER]))  # no position: loose

        # Act
        ordered_ids = [poem.id for poem in index.get_by_chain(WATER, ordered=True)]

        # Assert
        assert ordered_ids == [POEM_2, POEM_1, POEM_3]

    def test_get_all_chains_counts_members_per_chain(self):
        # Arrange
        index = CatalogIndex()
        index.add_poem(make_poem(POEM_1, chains=[WATER, GRIEF]))
        index.add_poem(make_poem(POEM_2, chains=[WATER]))
        index.add_poem(make_poem(POEM_3, chains=[OTHER]))

        # Act
        counts = index.get_all_chains()

        # Assert
        assert counts == {WATER: 2, GRIEF: 1, OTHER: 1}

    def test_clear_empties_the_chain_index(self):
        # Arrange
        index = CatalogIndex()
        index.add_poem(make_poem(POEM_1, chains=[WATER]))
        assert index.by_chain, "precondition: chain index should be populated"

        # Act
        index.clear()

        # Assert
        assert index.by_chain == {}


# ---------------------------------------------------------------------------
# create_chain
# ---------------------------------------------------------------------------


class TestCreateChain:
    """create_chain against a real catalog."""

    @pytest.mark.asyncio
    async def test_ordered_chain_assigns_positions_and_persists_them(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2), write_poem(vault, POEM_3)]
        catalog = synced_catalog(vault)
        expected_positions = {POEM_1: 1, POEM_2: 2, POEM_3: 3}

        # Act
        result = await create_chain(chain_id=WATER_SEQUENCE, poem_ids=ids, ordered=True)

        # Assert: reported outcome
        assert result["success"] is True, result.get("error")
        assert result["chain_id"] == WATER_SEQUENCE
        assert result["poems_affected"] == ids
        assert result["positions"] == expected_positions

        # Assert: frontmatter on disk
        for poem_id, position in expected_positions.items():
            frontmatter = read_frontmatter(vault, poem_id)
            assert frontmatter["chains"] == [WATER_SEQUENCE], f"{poem_id} chains on disk"
            assert frontmatter["chain_positions"] == {WATER_SEQUENCE: position}, (
                f"{poem_id} position on disk"
            )

        # Assert: index after the real sync
        assert chain_ids_in_order(catalog, WATER_SEQUENCE) == ids

    @pytest.mark.asyncio
    async def test_ordered_chain_backs_up_each_poem_file(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2)]
        synced_catalog(vault)

        # Act
        result = await create_chain(chain_id=WATER_SEQUENCE, poem_ids=ids, ordered=True)

        # Assert
        assert result["success"] is True, result.get("error")
        backups = [Path(p) for p in result["backup_paths"]]
        assert [b.name for b in backups] == [f"{POEM_1}.md.bak", f"{POEM_2}.md.bak"]
        for backup in backups:
            assert backup.exists(), f"backup not written: {backup}"

    @pytest.mark.asyncio
    async def test_loose_chain_records_membership_without_positions(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2)]
        catalog = synced_catalog(vault)

        # Act
        result = await create_chain(chain_id=GRIEF_POEMS, poem_ids=ids, ordered=False)

        # Assert: reported outcome
        assert result["success"] is True, result.get("error")
        assert result["chain_id"] == GRIEF_POEMS
        assert result["positions"] is None

        # Assert: frontmatter on disk has membership and no positions key
        for poem_id in ids:
            frontmatter = read_frontmatter(vault, poem_id)
            assert frontmatter["chains"] == [GRIEF_POEMS], f"{poem_id} chains on disk"
            assert "chain_positions" not in frontmatter, f"{poem_id} should have no positions"

        # Assert: index after the real sync holds both as loose members
        members = catalog.index.get_by_chain(GRIEF_POEMS, ordered=False)
        assert sorted(poem.id for poem in members) == ids
        assert all(poem.chain_positions is None for poem in members)

    @pytest.mark.asyncio
    async def test_unknown_poem_fails_before_writing_anything(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1)
        catalog = synced_catalog(vault)

        # Act
        result = await create_chain(chain_id=WATER, poem_ids=[POEM_1, MISSING_POEM], ordered=False)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error"]
        assert "chains" not in read_frontmatter(vault, POEM_1), "poem-1 must be untouched"
        assert catalog.index.by_chain == {}

    @pytest.mark.asyncio
    async def test_chain_id_is_normalized_in_result_and_on_disk(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1)
        catalog = synced_catalog(vault)

        # Act
        result = await create_chain(
            chain_id=UNNORMALIZED_WATER_SEQUENCE, poem_ids=[POEM_1], ordered=False
        )

        # Assert
        assert result["success"] is True, result.get("error")
        assert result["chain_id"] == WATER_SEQUENCE
        assert read_frontmatter(vault, POEM_1)["chains"] == [WATER_SEQUENCE]
        assert list(catalog.index.by_chain) == [WATER_SEQUENCE]


# ---------------------------------------------------------------------------
# get_chain
# ---------------------------------------------------------------------------


class TestGetChain:
    """get_chain against a real catalog."""

    @pytest.mark.asyncio
    async def test_ordered_chain_lists_poems_by_position(self, vault: Path):
        # Arrange: declared on disk in reverse of their positions
        write_poem(vault, POEM_1, chains=[WATER], chain_positions={WATER: 2})
        write_poem(vault, POEM_2, chains=[WATER], chain_positions={WATER: 1})
        synced_catalog(vault)

        # Act
        result = await get_chain(WATER)

        # Assert
        assert result["success"] is True, result.get("error")
        assert result["chain_id"] == WATER
        assert result["poem_count"] == 2
        assert result["is_ordered"] is True
        assert result["poems"] == [
            {
                "id": POEM_2,
                "title": default_title(POEM_2),
                "state": COMPLETED_STATE,
                "form": POEM_FORM,
                "position": 1,
            },
            {
                "id": POEM_1,
                "title": default_title(POEM_1),
                "state": COMPLETED_STATE,
                "form": POEM_FORM,
                "position": 2,
            },
        ]

    @pytest.mark.asyncio
    async def test_unknown_chain_is_reported_not_found(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1)
        synced_catalog(vault)

        # Act
        result = await get_chain(MISSING_CHAIN)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# list_chains
# ---------------------------------------------------------------------------


class TestListChains:
    """list_chains against a real catalog."""

    @pytest.mark.asyncio
    async def test_lists_every_chain_with_member_counts(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1, chains=[WATER, GRIEF])
        write_poem(vault, POEM_2, chains=[WATER])
        write_poem(vault, POEM_3, chains=[OTHER])
        synced_catalog(vault)

        # Act
        result = await list_chains()

        # Assert: sorted by chain id, none ordered since no positions were declared
        assert result["success"] is True, result.get("error")
        assert result["total_chains"] == 3
        assert result["chains"] == [
            {"chain_id": GRIEF, "poem_count": 1, "is_ordered": False},
            {"chain_id": OTHER, "poem_count": 1, "is_ordered": False},
            {"chain_id": WATER, "poem_count": 2, "is_ordered": False},
        ]


# ---------------------------------------------------------------------------
# reorder_chain
# ---------------------------------------------------------------------------


class TestReorderChain:
    """reorder_chain against a real catalog."""

    @pytest.mark.asyncio
    async def test_reverse_order_rewrites_positions_on_disk_and_in_index(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1, chains=[WATER], chain_positions={WATER: 1})
        write_poem(vault, POEM_2, chains=[WATER], chain_positions={WATER: 2})
        catalog = synced_catalog(vault)
        reversed_order = [POEM_2, POEM_1]

        # Act
        result = await reorder_chain(chain_id=WATER, poem_order=reversed_order)

        # Assert: reported outcome
        assert result["success"] is True, result.get("error")
        assert result["positions"] == {POEM_2: 1, POEM_1: 2}

        # Assert: frontmatter on disk
        assert read_frontmatter(vault, POEM_2)["chain_positions"] == {WATER: 1}
        assert read_frontmatter(vault, POEM_1)["chain_positions"] == {WATER: 2}

        # Assert: index after the real sync
        assert chain_ids_in_order(catalog, WATER) == reversed_order

    @pytest.mark.asyncio
    async def test_order_missing_a_member_fails_and_changes_nothing(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1, chains=[WATER], chain_positions={WATER: 1})
        write_poem(vault, POEM_2, chains=[WATER], chain_positions={WATER: 2})
        catalog = synced_catalog(vault)

        # Act
        result = await reorder_chain(chain_id=WATER, poem_order=[POEM_1])  # POEM_2 omitted

        # Assert
        assert result["success"] is False
        assert "Missing poems" in result["error"]
        assert POEM_2 in result["error"], "error should name the omitted poem"
        assert read_frontmatter(vault, POEM_1)["chain_positions"] == {WATER: 1}
        assert read_frontmatter(vault, POEM_2)["chain_positions"] == {WATER: 2}
        assert chain_ids_in_order(catalog, WATER) == [POEM_1, POEM_2]


# ---------------------------------------------------------------------------
# delete_chain
# ---------------------------------------------------------------------------


class TestDeleteChain:
    """delete_chain against a real catalog."""

    @pytest.mark.asyncio
    async def test_removes_chain_from_every_member_on_disk_and_in_index(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1, chains=[WATER])
        write_poem(vault, POEM_2, chains=[WATER])
        catalog = synced_catalog(vault)

        # Act
        result = await delete_chain(WATER)

        # Assert: reported outcome
        assert result["success"] is True, result.get("error")
        assert sorted(result["poems_affected"]) == [POEM_1, POEM_2]

        # Assert: frontmatter on disk
        for poem_id in (POEM_1, POEM_2):
            assert read_frontmatter(vault, poem_id)["chains"] == [], f"{poem_id} still in a chain"

        # Assert: index after the real sync
        assert WATER not in catalog.index.by_chain

    @pytest.mark.asyncio
    async def test_unknown_chain_is_reported_not_found(self, vault: Path):
        # Arrange
        write_poem(vault, POEM_1)
        synced_catalog(vault)

        # Act
        result = await delete_chain(MISSING_CHAIN)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Flows across tools and across restarts
# ---------------------------------------------------------------------------


class TestChainFlows:
    """One tool's write is the next tool's read, on the same real catalog.

    These are the flows a mocked, never-synced catalog could not express, and
    they are where the parser bug actually showed up for a user.
    """

    @pytest.mark.asyncio
    async def test_create_then_get_sees_the_new_chain_in_order(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2), write_poem(vault, POEM_3)]
        synced_catalog(vault)

        # Act
        created = await create_chain(chain_id=WATER_SEQUENCE, poem_ids=ids, ordered=True)
        fetched = await get_chain(WATER_SEQUENCE)

        # Assert
        assert created["success"] is True, created.get("error")
        assert fetched["success"] is True, fetched.get("error")
        assert fetched["is_ordered"] is True
        assert [(p["id"], p["position"]) for p in fetched["poems"]] == [
            (POEM_1, 1),
            (POEM_2, 2),
            (POEM_3, 3),
        ]

    @pytest.mark.asyncio
    async def test_reorder_then_get_returns_the_new_order(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2), write_poem(vault, POEM_3)]
        synced_catalog(vault)
        created = await create_chain(chain_id=WATER_SEQUENCE, poem_ids=ids, ordered=True)
        assert created["success"] is True, created.get("error")
        new_order = [POEM_3, POEM_1, POEM_2]

        # Act
        reordered = await reorder_chain(chain_id=WATER_SEQUENCE, poem_order=new_order)
        fetched = await get_chain(WATER_SEQUENCE)

        # Assert
        assert reordered["success"] is True, reordered.get("error")
        assert [p["id"] for p in fetched["poems"]] == new_order
        assert [p["position"] for p in fetched["poems"]] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_delete_then_list_shows_no_chains(self, vault: Path):
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2)]
        synced_catalog(vault)
        created = await create_chain(chain_id=WATER, poem_ids=ids, ordered=False)
        assert created["success"] is True, created.get("error")

        # Act
        deleted = await delete_chain(WATER)
        listed = await list_chains()

        # Assert
        assert deleted["success"] is True, deleted.get("error")
        assert listed["success"] is True, listed.get("error")
        assert listed["total_chains"] == 0
        assert listed["chains"] == []

    @pytest.mark.asyncio
    async def test_chain_survives_a_fresh_catalog_sync_on_the_same_files(self, vault: Path):
        """The restart case: a new Catalog over the same vault must read the chain back."""
        # Arrange
        ids = [write_poem(vault, POEM_1), write_poem(vault, POEM_2), write_poem(vault, POEM_3)]
        synced_catalog(vault)
        created = await create_chain(chain_id=WATER_SEQUENCE, poem_ids=ids, ordered=True)
        assert created["success"] is True, created.get("error")

        # Act: a second process starting up over the same vault
        restarted = Catalog(vault_root=vault)
        restarted.sync()
        initialize_chain_tools(restarted)
        fetched = await get_chain(WATER_SEQUENCE)

        # Assert: the index and the tool both see what the first process wrote
        assert chain_ids_in_order(restarted, WATER_SEQUENCE) == ids
        assert restarted.index.get_by_id(POEM_3).chain_positions == {WATER_SEQUENCE: 3}
        assert fetched["success"] is True, fetched.get("error")
        assert [(p["id"], p["position"]) for p in fetched["poems"]] == [
            (POEM_1, 1),
            (POEM_2, 2),
            (POEM_3, 3),
        ]
