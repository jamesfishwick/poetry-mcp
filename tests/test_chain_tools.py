"""Tests for chain tools - linking poems into sequences and collections."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

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


@pytest.fixture
def sample_poem():
    """Create a sample poem for testing."""

    def _create_poem(
        id: str,
        title: str = None,
        chains: list[str] = None,
        chain_positions: dict[str, int] = None,
    ) -> Poem:
        return Poem(
            id=id,
            title=title or id.replace("-", " ").title(),
            file_path=f"catalog/Completed/{id}.md",
            state="completed",
            form="free_verse",
            tags=["test"],
            word_count=100,
            line_count=20,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 6, 1),
            chains=chains or [],
            chain_positions=chain_positions,
        )

    return _create_poem


@pytest.fixture
def mock_catalog(sample_poem, tmp_path):
    """Create a mock catalog with test poems."""
    catalog = Mock(spec=Catalog)
    catalog.vault_root = tmp_path
    catalog.index = CatalogIndex()

    # Add sample poems
    poems = [
        sample_poem("poem-1", "First Poem"),
        sample_poem("poem-2", "Second Poem"),
        sample_poem("poem-3", "Third Poem"),
    ]

    for poem in poems:
        catalog.index.add_poem(poem)
        # Create actual files for the poems
        poem_path = tmp_path / poem.file_path
        poem_path.parent.mkdir(parents=True, exist_ok=True)
        poem_path.write_text(f"""---
state: completed
form: free_verse
tags: [test]
---

# {poem.title}

This is poem content.
""")

    catalog.sync = Mock(return_value=Mock(total_poems=len(poems)))

    return catalog


class TestPoemChainFields:
    """Test chain fields on Poem model."""

    def test_poem_with_chains(self, sample_poem):
        """Test creating a poem with chains."""
        poem = sample_poem(
            "test-poem",
            chains=["water-sequence", "grief-cycle"],
        )
        assert poem.chains == ["water-sequence", "grief-cycle"]
        assert poem.chain_positions is None

    def test_poem_with_chain_positions(self, sample_poem):
        """Test creating a poem with chain positions."""
        poem = sample_poem(
            "test-poem",
            chains=["water-sequence"],
            chain_positions={"water-sequence": 3},
        )
        assert poem.chains == ["water-sequence"]
        assert poem.chain_positions == {"water-sequence": 3}

    def test_chain_normalization(self):
        """Test that chain IDs are normalized."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            chains=["Water Sequence", "GRIEF-CYCLE", "  loose  "],
        )
        assert poem.chains == ["water-sequence", "grief-cycle", "loose"]

    def test_chain_positions_validation(self):
        """Test that chain positions must be positive integers."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="completed",
                form="free_verse",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                chains=["test-chain"],
                chain_positions={"test-chain": 0},  # Invalid: must be >= 1
            )
        assert "positive integer" in str(exc_info.value)

    def test_empty_chains_default(self, sample_poem):
        """Test that empty chains default to empty list."""
        poem = sample_poem("test-poem")
        assert poem.chains == []
        assert poem.chain_positions is None


class TestCatalogIndexChains:
    """Test chain indexing in CatalogIndex."""

    def test_index_by_chain(self, sample_poem):
        """Test that poems are indexed by chain."""
        index = CatalogIndex()

        poem1 = sample_poem("poem-1", chains=["water"])
        poem2 = sample_poem("poem-2", chains=["water", "grief"])
        poem3 = sample_poem("poem-3", chains=["grief"])

        index.add_poem(poem1)
        index.add_poem(poem2)
        index.add_poem(poem3)

        assert set(index.by_chain["water"]) == {"poem-1", "poem-2"}
        assert set(index.by_chain["grief"]) == {"poem-2", "poem-3"}

    def test_get_by_chain(self, sample_poem):
        """Test getting poems by chain."""
        index = CatalogIndex()

        poem1 = sample_poem("poem-1", chains=["water"], chain_positions={"water": 2})
        poem2 = sample_poem("poem-2", chains=["water"], chain_positions={"water": 1})
        poem3 = sample_poem("poem-3", chains=["water"])  # No position = loose

        index.add_poem(poem1)
        index.add_poem(poem2)
        index.add_poem(poem3)

        # Test ordered retrieval
        poems = index.get_by_chain("water", ordered=True)
        assert len(poems) == 3
        # Ordered poems first (sorted by position), then loose (sorted by title)
        assert poems[0].id == "poem-2"  # position 1
        assert poems[1].id == "poem-1"  # position 2
        assert poems[2].id == "poem-3"  # no position, sorted by title

    def test_get_all_chains(self, sample_poem):
        """Test getting all chains with counts."""
        index = CatalogIndex()

        index.add_poem(sample_poem("poem-1", chains=["water", "grief"]))
        index.add_poem(sample_poem("poem-2", chains=["water"]))
        index.add_poem(sample_poem("poem-3", chains=["other"]))

        chains = index.get_all_chains()
        assert chains == {"water": 2, "grief": 1, "other": 1}

    def test_clear_clears_chains(self, sample_poem):
        """Test that clear() also clears chain index."""
        index = CatalogIndex()
        index.add_poem(sample_poem("poem-1", chains=["water"]))

        assert len(index.by_chain) > 0
        index.clear()
        assert len(index.by_chain) == 0


class TestCreateChain:
    """Test create_chain tool."""

    @pytest.mark.asyncio
    async def test_create_ordered_chain(self, mock_catalog):
        """Test creating an ordered chain."""
        initialize_chain_tools(mock_catalog)

        with patch("poetry_mcp.tools.chain_tools.update_poem_chains") as mock_update:
            mock_update.return_value = Mock(
                success=True,
                backup_path="/backup/path",
            )

            result = await create_chain(
                chain_id="water-sequence",
                poem_ids=["poem-1", "poem-2", "poem-3"],
                ordered=True,
            )

            assert result["success"] is True
            assert result["chain_id"] == "water-sequence"
            assert len(result["poems_affected"]) == 3
            assert result["positions"] == {"poem-1": 1, "poem-2": 2, "poem-3": 3}

    @pytest.mark.asyncio
    async def test_create_loose_chain(self, mock_catalog):
        """Test creating a loose collection (unordered)."""
        initialize_chain_tools(mock_catalog)

        with patch("poetry_mcp.tools.chain_tools.update_poem_chains") as mock_update:
            mock_update.return_value = Mock(
                success=True,
                backup_path="/backup/path",
            )

            result = await create_chain(
                chain_id="grief-poems",
                poem_ids=["poem-1", "poem-2"],
                ordered=False,
            )

            assert result["success"] is True
            assert result["chain_id"] == "grief-poems"
            assert result["positions"] is None

    @pytest.mark.asyncio
    async def test_create_chain_poem_not_found(self, mock_catalog):
        """Test creating chain with non-existent poem."""
        initialize_chain_tools(mock_catalog)

        result = await create_chain(
            chain_id="test-chain",
            poem_ids=["nonexistent"],
            ordered=False,
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_chain_id_normalization(self, mock_catalog):
        """Test that chain ID is normalized."""
        initialize_chain_tools(mock_catalog)

        with patch("poetry_mcp.tools.chain_tools.update_poem_chains") as mock_update:
            mock_update.return_value = Mock(success=True, backup_path=None)

            result = await create_chain(
                chain_id="Water Sequence",  # Should normalize
                poem_ids=["poem-1"],
                ordered=False,
            )

            assert result["chain_id"] == "water-sequence"


class TestGetChain:
    """Test get_chain tool."""

    @pytest.mark.asyncio
    async def test_get_chain_ordered(self, mock_catalog, sample_poem):
        """Test getting an ordered chain."""
        # Add poems with chain membership
        mock_catalog.index.clear()
        mock_catalog.index.add_poem(
            sample_poem("poem-1", chains=["water"], chain_positions={"water": 2})
        )
        mock_catalog.index.add_poem(
            sample_poem("poem-2", chains=["water"], chain_positions={"water": 1})
        )

        initialize_chain_tools(mock_catalog)

        result = await get_chain("water")

        assert result["success"] is True
        assert result["chain_id"] == "water"
        assert result["poem_count"] == 2
        assert result["is_ordered"] is True
        # Check poems are in order
        assert result["poems"][0]["id"] == "poem-2"  # position 1
        assert result["poems"][1]["id"] == "poem-1"  # position 2

    @pytest.mark.asyncio
    async def test_get_chain_not_found(self, mock_catalog):
        """Test getting non-existent chain."""
        initialize_chain_tools(mock_catalog)

        result = await get_chain("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestListChains:
    """Test list_chains tool."""

    @pytest.mark.asyncio
    async def test_list_chains(self, mock_catalog, sample_poem):
        """Test listing all chains."""
        mock_catalog.index.clear()
        mock_catalog.index.add_poem(sample_poem("poem-1", chains=["water", "grief"]))
        mock_catalog.index.add_poem(sample_poem("poem-2", chains=["water"]))
        mock_catalog.index.add_poem(sample_poem("poem-3", chains=["other"]))

        initialize_chain_tools(mock_catalog)

        result = await list_chains()

        assert result["success"] is True
        assert result["total_chains"] == 3

        chain_dict = {c["chain_id"]: c["poem_count"] for c in result["chains"]}
        assert chain_dict["water"] == 2
        assert chain_dict["grief"] == 1
        assert chain_dict["other"] == 1


class TestReorderChain:
    """Test reorder_chain tool."""

    @pytest.mark.asyncio
    async def test_reorder_chain(self, mock_catalog, sample_poem):
        """Test reordering poems in a chain."""
        mock_catalog.index.clear()
        mock_catalog.index.add_poem(
            sample_poem("poem-1", chains=["water"], chain_positions={"water": 1})
        )
        mock_catalog.index.add_poem(
            sample_poem("poem-2", chains=["water"], chain_positions={"water": 2})
        )

        initialize_chain_tools(mock_catalog)

        with patch("poetry_mcp.tools.chain_tools.update_poem_chains") as mock_update:
            mock_update.return_value = Mock(success=True, backup_path=None)

            result = await reorder_chain(
                chain_id="water",
                poem_order=["poem-2", "poem-1"],  # Reverse order
            )

            assert result["success"] is True
            assert result["positions"] == {"poem-2": 1, "poem-1": 2}

    @pytest.mark.asyncio
    async def test_reorder_chain_missing_poem(self, mock_catalog, sample_poem):
        """Test reorder with missing poem in order list."""
        mock_catalog.index.clear()
        mock_catalog.index.add_poem(sample_poem("poem-1", chains=["water"]))
        mock_catalog.index.add_poem(sample_poem("poem-2", chains=["water"]))

        initialize_chain_tools(mock_catalog)

        result = await reorder_chain(
            chain_id="water",
            poem_order=["poem-1"],  # Missing poem-2
        )

        assert result["success"] is False
        assert "Missing poems" in result["error"]


class TestDeleteChain:
    """Test delete_chain tool."""

    @pytest.mark.asyncio
    async def test_delete_chain(self, mock_catalog, sample_poem):
        """Test deleting a chain."""
        mock_catalog.index.clear()
        mock_catalog.index.add_poem(sample_poem("poem-1", chains=["water"]))
        mock_catalog.index.add_poem(sample_poem("poem-2", chains=["water"]))

        initialize_chain_tools(mock_catalog)

        with patch("poetry_mcp.tools.chain_tools.update_poem_chains") as mock_update:
            mock_update.return_value = Mock(success=True, backup_path=None)

            result = await delete_chain("water")

            assert result["success"] is True
            assert len(result["poems_affected"]) == 2

    @pytest.mark.asyncio
    async def test_delete_nonexistent_chain(self, mock_catalog):
        """Test deleting non-existent chain."""
        initialize_chain_tools(mock_catalog)

        result = await delete_chain("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]
