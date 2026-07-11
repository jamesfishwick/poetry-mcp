"""Similarity tools for finding related poems by metadata connections.

Scores poems by shared nexus membership, tag overlap, chain
co-membership, and form to find poems similar to a given poem.
"""

import logging
import time

from ..catalog.catalog import Catalog
from ..models.nexus import NexusRegistry
from ..models.results import SimilarityResult, SimilarPoemMatch

logger = logging.getLogger(__name__)

# Scoring weights (ordered by signal strength)
NEXUS_WEIGHT = 3.0
CHAIN_WEIGHT = 2.0
TAG_WEIGHT = 1.0
FORM_WEIGHT = 0.5

# Module-level state (initialized by server)
_catalog: Catalog | None = None
_nexus_registry: NexusRegistry | None = None


def initialize_similarity_tools(
    catalog: Catalog,
    nexus_registry: NexusRegistry | None = None,
) -> None:
    """Initialize similarity tools with catalog and optional nexus registry.

    Args:
        catalog: Initialized Catalog instance
        nexus_registry: Loaded NexusRegistry. If None, all tags are
            treated as plain tags (graceful degradation).
    """
    global _catalog, _nexus_registry
    _catalog = catalog
    _nexus_registry = nexus_registry
    logger.info(
        "Similarity tools initialized "
        f"(nexus_registry={'loaded' if nexus_registry else 'not available'})"
    )


def _get_catalog() -> Catalog:
    if _catalog is None:
        raise RuntimeError(
            "Similarity tools not initialized. Call initialize_similarity_tools() first."
        )
    return _catalog


def _get_nexus_canonical_tags() -> set[str]:
    """Build set of all nexus canonical_tags for tag classification.

    Returns empty set if nexus registry is not available,
    causing all tags to be treated as plain tags.
    """
    if _nexus_registry is None:
        return set()
    tags: set[str] = set()
    for nexus_list in [
        _nexus_registry.themes,
        _nexus_registry.motifs,
        _nexus_registry.forms,
    ]:
        for nexus in nexus_list:
            if nexus.canonical_tag:
                tags.add(nexus.canonical_tag.lower())
    return tags


async def find_similar_poems(
    poem_id: str,
    limit: int = 10,
    include_content: bool = False,
) -> SimilarityResult:
    """Find poems similar to a given poem through metadata connections.

    Scores candidates by four signals (ordered by strength):
    1. Shared nexus membership (canonical_tags) -- weight 3.0
    2. Shared chain co-membership -- weight 2.0
    3. Shared plain tags (non-nexus) -- weight 1.0
    4. Same form -- weight 0.5

    Args:
        poem_id: Poem identifier (ID or title)
        limit: Maximum number of similar poems to return (default 10)
        include_content: Whether to include full poem text in results

    Returns:
        SimilarityResult with ranked matches and similarity metadata
    """
    start_time = time.perf_counter()
    cat = _get_catalog()

    # Resolve source poem
    source = cat.index.get_by_id_or_title(poem_id)
    if source is None:
        return SimilarityResult(
            success=False,
            source_poem_id=poem_id,
            source_poem_title="",
            total_candidates_scored=0,
            query_time_ms=0.0,
            error=f"Poem not found: {poem_id}",
        )

    # Classify source poem's tags into nexus vs. plain
    nexus_canonical_tags = _get_nexus_canonical_tags()
    source_tags_lower = {t.lower() for t in source.tags}
    source_nexus_tags = source_tags_lower & nexus_canonical_tags
    source_plain_tags = source_tags_lower - nexus_canonical_tags
    source_chains = {c.lower() for c in source.chains}

    # Gather candidate poem IDs from index lookups (no full-catalog scan)
    candidate_ids: set[str] = set()

    for tag in source_tags_lower:
        for pid in cat.index.by_tag.get(tag, set()):
            candidate_ids.add(pid)

    for chain in source_chains:
        for pid in cat.index.by_chain.get(chain, []):
            candidate_ids.add(pid)

    for p in cat.index.get_by_form(source.form):
        candidate_ids.add(p.id)

    # Remove source poem
    candidate_ids.discard(source.id)

    # Score each candidate
    scored: list[SimilarPoemMatch] = []

    for cid in candidate_ids:
        candidate = cat.index.get_by_id(cid)
        if candidate is None:
            continue

        score = 0.0
        cand_tags_lower = {t.lower() for t in candidate.tags}
        cand_chains_lower = {c.lower() for c in candidate.chains}

        # Nexus overlap (strongest signal)
        common_nexus = source_nexus_tags & cand_tags_lower
        score += len(common_nexus) * NEXUS_WEIGHT

        # Plain tag overlap
        common_plain = source_plain_tags & cand_tags_lower
        score += len(common_plain) * TAG_WEIGHT

        # Chain overlap
        common_chains = source_chains & cand_chains_lower
        score += len(common_chains) * CHAIN_WEIGHT

        # Form match
        same_form = candidate.form == source.form
        if same_form:
            score += FORM_WEIGHT

        if score > 0:
            poem_out = candidate
            if not include_content:
                poem_out = candidate.model_copy(update={"content": None})
            scored.append(
                SimilarPoemMatch(
                    poem=poem_out,
                    similarity_score=round(score, 2),
                    shared_nexuses=sorted(common_nexus),
                    shared_tags=sorted(common_plain),
                    shared_chains=sorted(common_chains),
                    same_form=same_form,
                )
            )

    # Sort by score descending, then title ascending for determinism
    scored.sort(key=lambda m: (-m.similarity_score, m.poem.title.lower()))
    total_scored = len(scored)
    scored = scored[:limit]

    query_time_ms = (time.perf_counter() - start_time) * 1000

    return SimilarityResult(
        success=True,
        source_poem_id=source.id,
        source_poem_title=source.title,
        matches=scored,
        total_candidates_scored=total_scored,
        query_time_ms=round(query_time_ms, 2),
    )
