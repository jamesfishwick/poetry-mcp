"""Tests for similarity tools - finding related poems by metadata connections."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from poetry_mcp.models.poem import Poem
from poetry_mcp.models.nexus import Nexus, NexusRegistry
from poetry_mcp.catalog.catalog import Catalog, CatalogIndex
from poetry_mcp.tools.similarity_tools import (
    initialize_similarity_tools,
    find_similar_poems,
    _get_nexus_canonical_tags,
    NEXUS_WEIGHT,
    CHAIN_WEIGHT,
    TAG_WEIGHT,
    FORM_WEIGHT,
)


def _make_poem(
    id: str,
    title: str = None,
    tags: list[str] = None,
    chains: list[str] = None,
    form: str = "free_verse",
) -> Poem:
    """Helper to create a poem with minimal boilerplate."""
    return Poem(
        id=id,
        title=title or id.replace("-", " ").title(),
        file_path=f"catalog/Completed/{id}.md",
        content=f"Content of {id}",
        state="completed",
        form=form,
        tags=tags or [],
        word_count=100,
        line_count=20,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 6, 1),
        chains=chains or [],
    )


def _make_nexus_registry(canonical_tags: list[str]) -> NexusRegistry:
    """Create a NexusRegistry with given canonical tags as themes."""
    themes = [
        Nexus(
            name=tag.replace("-", " ").title(),
            canonical_tag=tag,
            category="theme",
            description=f"Test theme for {tag}",
        )
        for tag in canonical_tags
    ]
    return NexusRegistry(themes=themes, motifs=[], forms=[], total_count=len(themes))


@pytest.fixture
def catalog_with_poems():
    """Create a mock catalog with poems designed for known overlap patterns.

    Source poem: has nexus tags (water, bones), plain tag (draft-notes),
                 chain membership (water-sequence), free_verse form.

    Candidates:
    - nexus-match: shares 2 nexus tags + same form -> 6.0 + 0.5 = 6.5
    - chain-match: shares chain only -> 2.0
    - tag-match: shares plain tag only -> 1.0
    - form-only: shares only form -> 0.5
    - no-match: shares nothing -> excluded
    """
    cat = Mock(spec=Catalog)
    cat.index = CatalogIndex()

    poems = [
        _make_poem(
            "source",
            title="Source Poem",
            tags=["water", "bones", "draft-notes"],
            chains=["water-sequence"],
            form="free_verse",
        ),
        _make_poem(
            "nexus-match",
            title="Nexus Match",
            tags=["water", "bones"],
            form="free_verse",
        ),
        _make_poem(
            "chain-match",
            title="Chain Match",
            tags=["unrelated-tag"],
            chains=["water-sequence"],
            form="prose_poem",
        ),
        _make_poem(
            "tag-match",
            title="Tag Match",
            tags=["draft-notes"],
            form="prose_poem",
        ),
        _make_poem(
            "form-only",
            title="Form Only",
            tags=["completely-different"],
            form="free_verse",
        ),
        _make_poem(
            "no-match",
            title="No Match",
            tags=["alien-tag"],
            form="prose_poem",
        ),
    ]

    for poem in poems:
        cat.index.add_poem(poem)

    return cat


@pytest.fixture
def nexus_registry():
    """Registry where 'water' and 'bones' are nexus canonical tags."""
    return _make_nexus_registry(["water", "bones"])


class TestSimilarityScoring:
    """Test that scoring ranks poems correctly."""

    @pytest.mark.asyncio
    async def test_scoring_order(self, catalog_with_poems, nexus_registry):
        """Nexus > chain > plain tag > form in scoring order."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")

        assert result.success is True
        assert result.source_poem_id == "source"
        assert result.source_poem_title == "Source Poem"

        titles = [m.poem.title for m in result.matches]

        # nexus-match: 2 nexus * 3.0 + form 0.5 = 6.5
        # chain-match: 1 chain * 2.0 = 2.0
        # tag-match:   1 plain tag * 1.0 = 1.0
        # form-only:   form 0.5 = 0.5
        assert titles == ["Nexus Match", "Chain Match", "Tag Match", "Form Only"]

    @pytest.mark.asyncio
    async def test_exact_scores(self, catalog_with_poems, nexus_registry):
        """Verify exact score calculations."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")
        scores = {m.poem.id: m.similarity_score for m in result.matches}

        assert scores["nexus-match"] == 2 * NEXUS_WEIGHT + FORM_WEIGHT  # 6.5
        assert scores["chain-match"] == 1 * CHAIN_WEIGHT  # 2.0
        assert scores["tag-match"] == 1 * TAG_WEIGHT  # 1.0
        assert scores["form-only"] == FORM_WEIGHT  # 0.5

    @pytest.mark.asyncio
    async def test_shared_metadata_reported(self, catalog_with_poems, nexus_registry):
        """Each match explains why it's similar."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")
        matches_by_id = {m.poem.id: m for m in result.matches}

        nexus_m = matches_by_id["nexus-match"]
        assert sorted(nexus_m.shared_nexuses) == ["bones", "water"]
        assert nexus_m.shared_tags == []
        assert nexus_m.same_form is True

        chain_m = matches_by_id["chain-match"]
        assert chain_m.shared_chains == ["water-sequence"]
        assert chain_m.shared_nexuses == []

        tag_m = matches_by_id["tag-match"]
        assert tag_m.shared_tags == ["draft-notes"]
        assert tag_m.shared_nexuses == []

    @pytest.mark.asyncio
    async def test_source_excluded(self, catalog_with_poems, nexus_registry):
        """Source poem is never in its own results."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")
        result_ids = [m.poem.id for m in result.matches]
        assert "source" not in result_ids

    @pytest.mark.asyncio
    async def test_no_match_excluded(self, catalog_with_poems, nexus_registry):
        """Poems with zero overlap are excluded entirely."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")
        result_ids = [m.poem.id for m in result.matches]
        assert "no-match" not in result_ids

    @pytest.mark.asyncio
    async def test_total_candidates_scored(self, catalog_with_poems, nexus_registry):
        """total_candidates_scored counts poems with score > 0."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source")
        assert result.total_candidates_scored == 4


class TestSimilarityParameters:
    """Test limit, include_content, and error handling."""

    @pytest.mark.asyncio
    async def test_limit_parameter(self, catalog_with_poems, nexus_registry):
        """Limit restricts number of results."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source", limit=2)
        assert len(result.matches) == 2
        assert result.total_candidates_scored == 4  # Still scores all

    @pytest.mark.asyncio
    async def test_include_content_false(self, catalog_with_poems, nexus_registry):
        """Content stripped by default."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source", include_content=False)
        for match in result.matches:
            assert match.poem.content is None

    @pytest.mark.asyncio
    async def test_include_content_true(self, catalog_with_poems, nexus_registry):
        """Content included when requested."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("source", include_content=True)
        for match in result.matches:
            assert match.poem.content is not None

    @pytest.mark.asyncio
    async def test_poem_not_found(self, catalog_with_poems, nexus_registry):
        """Returns error result for unknown poem."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry)

        result = await find_similar_poems("nonexistent-poem")
        assert result.success is False
        assert "not found" in result.error.lower()


class TestGracefulDegradation:
    """Test behavior when nexus registry is unavailable."""

    @pytest.mark.asyncio
    async def test_no_registry_all_tags_plain(self, catalog_with_poems):
        """Without registry, all tags scored at plain-tag weight."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry=None)

        result = await find_similar_poems("source")
        scores = {m.poem.id: m.similarity_score for m in result.matches}

        # Without registry: water and bones are plain tags, not nexus
        # nexus-match: 2 plain tags * 1.0 + form 0.5 = 2.5
        # chain-match: 1 chain * 2.0 = 2.0
        # tag-match: 1 plain tag * 1.0 = 1.0
        # form-only: form 0.5 = 0.5
        assert scores["nexus-match"] == 2 * TAG_WEIGHT + FORM_WEIGHT  # 2.5
        assert scores["chain-match"] == 1 * CHAIN_WEIGHT  # 2.0

    @pytest.mark.asyncio
    async def test_no_registry_tags_reported_as_plain(self, catalog_with_poems):
        """Without registry, all shared tags reported as shared_tags, not shared_nexuses."""
        initialize_similarity_tools(catalog_with_poems, nexus_registry=None)

        result = await find_similar_poems("source")
        matches_by_id = {m.poem.id: m for m in result.matches}

        nexus_m = matches_by_id["nexus-match"]
        # Tags that would be nexus tags are now plain tags
        assert nexus_m.shared_nexuses == []
        assert sorted(nexus_m.shared_tags) == ["bones", "water"]


class TestDeterminism:
    """Test deterministic ordering."""

    @pytest.mark.asyncio
    async def test_tiebreaker_by_title(self):
        """Poems with equal scores are sorted alphabetically by title."""
        cat = Mock(spec=Catalog)
        cat.index = CatalogIndex()

        poems = [
            _make_poem("source", tags=["shared"], form="free_verse"),
            _make_poem("zebra", title="Zebra Poem", tags=["shared"], form="prose_poem"),
            _make_poem("alpha", title="Alpha Poem", tags=["shared"], form="prose_poem"),
        ]
        for p in poems:
            cat.index.add_poem(p)

        initialize_similarity_tools(cat, nexus_registry=None)
        result = await find_similar_poems("source")

        # Both have score 1.0 (1 plain tag), so alphabetical by title
        titles = [m.poem.title for m in result.matches]
        assert titles == ["Alpha Poem", "Zebra Poem"]


class TestNexusCanonicalTags:
    """Test the internal helper for nexus tag classification."""

    def test_extracts_canonical_tags(self):
        """Extracts canonical tags from all nexus categories."""
        registry = NexusRegistry(
            themes=[
                Nexus(name="Water", canonical_tag="water", category="theme", description=""),
            ],
            motifs=[
                Nexus(name="Bones", canonical_tag="bones", category="motif", description=""),
            ],
            forms=[
                Nexus(name="Sonnet", canonical_tag="sonnet", category="form", description=""),
            ],
            total_count=3,
        )
        initialize_similarity_tools(Mock(spec=Catalog), registry)

        tags = _get_nexus_canonical_tags()
        assert tags == {"water", "bones", "sonnet"}

    def test_empty_without_registry(self):
        """Returns empty set when no registry."""
        initialize_similarity_tools(Mock(spec=Catalog), nexus_registry=None)

        tags = _get_nexus_canonical_tags()
        assert tags == set()

    def test_case_insensitive(self):
        """Canonical tags are lowercased."""
        registry = _make_nexus_registry(["Water-Liquid"])
        initialize_similarity_tools(Mock(spec=Catalog), registry)

        tags = _get_nexus_canonical_tags()
        assert "water-liquid" in tags


class TestNotInitialized:
    """Test error when tools not initialized."""

    @pytest.mark.asyncio
    async def test_raises_without_init(self):
        """Calling find_similar_poems before init raises RuntimeError."""
        # Reset module state by initializing with None catalog
        import poetry_mcp.tools.similarity_tools as mod
        mod._catalog = None

        with pytest.raises(RuntimeError, match="not initialized"):
            await find_similar_poems("any-poem")
