"""Catalog/poem query tool implementations.

Extracted from server.py. Each impl takes an explicit `catalog` (keyword-only);
the server wrappers pass get_catalog(). load_config is imported directly.
"""

import logging
import time
from typing import Any

from ..config import load_config
from ..models.poem import Poem
from ..models.results import SearchResult, ServerInfo, SyncResult

logger = logging.getLogger(__name__)


async def sync_catalog_impl(force_rescan: bool = False, *, catalog: Any) -> SyncResult:
    """Scan the vault and rebuild the in-memory catalog indices."""
    logger.info(f"Syncing catalog (force_rescan={force_rescan})...")
    result = catalog.sync(force_rescan=force_rescan)
    logger.info(f"Sync complete: {result.total_poems} poems")
    return result


async def get_poem_impl(
    identifier: str, include_content: bool = True, *, catalog: Any
) -> Poem | None:
    """Get a poem by ID or title."""
    poem = catalog.index.get_by_id_or_title(identifier.lower())

    if poem and not include_content:
        poem_dict = poem.model_dump()
        poem_dict["content"] = None
        poem = Poem(**poem_dict)

    return poem


async def get_server_info_impl(*, catalog: Any) -> ServerInfo:
    """Server metadata + catalog statistics."""
    config = load_config()
    stats = catalog.get_stats()

    return ServerInfo(
        server_name="poetry-mcp",
        version="0.1.0",
        config={
            "vault_path": str(config.vault.path),
            "catalog_dir": config.vault.catalog_dir,
            "nexus_dir": config.vault.nexus_dir,
        },
        catalog_stats=stats,
    )


async def query_poems_impl(
    query: str | None = None,
    states: list[str] | None = None,
    forms: list[str] | None = None,
    tags: list[str] | None = None,
    tag_match_mode: str = "all",
    chain_id: str | None = None,
    min_quality_score: int | None = None,
    quality_dimensions: list[str] | None = None,
    sort_by: str = "relevance",
    limit: int | None = None,
    include_content: bool = False,
    *,
    catalog: Any,
) -> SearchResult:
    """Unified search/filter/sort over poems. See the server wrapper for docs."""
    start_time = time.perf_counter()
    cat = catalog
    config = load_config()

    if limit is None:
        limit = config.search.default_limit

    if query:
        results = cat.index.search_content(query, case_sensitive=config.search.case_sensitive)
    else:
        results = cat.index.all_poems.copy()

    if states:
        results = [p for p in results if p.state in states]

    if forms:
        results = [p for p in results if p.form in forms]

    if tags:
        if tag_match_mode == "all":
            results = [
                p
                for p in results
                if all(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
            ]
        elif tag_match_mode == "any":
            results = [
                p
                for p in results
                if any(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
            ]

    if chain_id:
        normalized_chain = chain_id.lower().strip().replace(" ", "-")
        chain_poem_ids = set(cat.index.by_chain.get(normalized_chain, []))
        results = [p for p in results if p.id in chain_poem_ids]

    if min_quality_score is not None and quality_dimensions:
        filtered_results = []
        for poem in results:
            if not poem.quality or not poem.quality.scores:
                continue

            meets_threshold = True
            for dim in quality_dimensions:
                dim_lower = dim.lower().strip()
                score = poem.quality.scores.get(dim_lower)
                if score is None or score < min_quality_score:
                    meets_threshold = False
                    break

            if meets_threshold:
                filtered_results.append(poem)

        results = filtered_results

    if sort_by == "title":
        results.sort(key=lambda p: p.title.lower())
    elif sort_by == "created_at":
        results.sort(key=lambda p: p.created_at, reverse=True)
    elif sort_by == "updated_at":
        results.sort(key=lambda p: p.updated_at, reverse=True)
    elif sort_by == "word_count":
        results.sort(key=lambda p: p.word_count, reverse=True)
    elif sort_by == "chain_position" and chain_id:
        normalized_chain = chain_id.lower().strip().replace(" ", "-")

        def chain_sort_key(poem: Poem) -> tuple:
            if poem.chain_positions and normalized_chain in poem.chain_positions:
                return (0, poem.chain_positions[normalized_chain], "")
            return (1, 0, poem.title.lower())

        results.sort(key=chain_sort_key)
    elif sort_by == "relevance" and tags:

        def relevance_score(poem: Poem) -> int:
            return sum(1 for tag in tags if tag.lower() in [t.lower() for t in poem.tags])

        results.sort(key=relevance_score, reverse=True)

    total_matches = len(results)
    results = results[:limit]

    if not include_content:
        results = [Poem(**{**p.model_dump(), "content": None}) for p in results]

    query_time_ms = (time.perf_counter() - start_time) * 1000

    return SearchResult(poems=results, total_matches=total_matches, query_time_ms=query_time_ms)
