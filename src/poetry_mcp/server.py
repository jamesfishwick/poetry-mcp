"""Poetry MCP Server.

FastMCP server providing tools for poetry catalog and nexus management.
"""

import logging
import sys
from typing import Optional, List

# Check Python version before any imports
if sys.version_info < (3, 10):
    print("Error: Poetry MCP requires Python 3.10 or higher")
    print(f"Current version: {sys.version_info.major}.{sys.version_info.minor}")
    sys.exit(1)

from fastmcp import FastMCP

from .config import load_config
from .catalog.catalog import Catalog
from .models.poem import Poem
from .models.results import SyncResult, SearchResult, CatalogStats
from .models.nexus import NexusRegistry
from .tools.enrichment_tools import (
    initialize_enrichment_tools,
    get_all_nexuses as _get_all_nexuses,
    link_poem_to_nexus as _link_poem_to_nexus,
    find_nexuses_for_poem as _find_nexuses_for_poem,
    get_poems_for_enrichment as _get_poems_for_enrichment,
    sync_nexus_tags as _sync_nexus_tags,
    move_poem_to_state as _move_poem_to_state,
    grade_poem_quality as _grade_poem_quality,
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("poetry-mcp")

# Global catalog instance
catalog: Optional[Catalog] = None


def get_catalog() -> Catalog:
    """Get or initialize catalog instance."""
    global catalog

    if catalog is None:
        logger.info("Initializing catalog...")
        config = load_config()
        catalog = Catalog(vault_root=config.vault.path)
        logger.info(f"Catalog initialized with vault: {config.vault.path}")

    return catalog


@mcp.tool()
async def sync_catalog(force_rescan: bool = False) -> SyncResult:
    """
    Synchronize catalog from filesystem.

    Scans all markdown files in catalog/ directory and builds in-memory indices.
    This should be called before using other catalog tools.

    Args:
        force_rescan: If True, rescan all files even if already loaded

    Returns:
        SyncResult with statistics about the sync operation
    """
    logger.info(f"Syncing catalog (force_rescan={force_rescan})...")
    cat = get_catalog()
    result = cat.sync(force_rescan=force_rescan)
    logger.info(f"Sync complete: {result.total_poems} poems")
    return result


@mcp.tool()
async def get_poem(
    identifier: str,
    include_content: bool = True
) -> Optional[Poem]:
    """
    Get a poem by ID or title.

    Args:
        identifier: Poem ID or exact title
        include_content: Whether to include full poem text

    Returns:
        Poem object or None if not found
    """
    cat = get_catalog()

    # Try by ID first
    poem = cat.index.get_by_id(identifier.lower())

    # Try by title if not found
    if not poem:
        poem = cat.index.get_by_title(identifier)

    if poem and not include_content:
        # Return copy without content
        poem_dict = poem.model_dump()
        poem_dict['content'] = None
        poem = Poem(**poem_dict)

    return poem


@mcp.tool()
async def search_poems(
    query: str,
    states: Optional[List[str]] = None,
    forms: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    limit: int = 20,
    include_content: bool = False
) -> SearchResult:
    """
    Search for poems matching criteria.

    Args:
        query: Text to search for in titles, content, and notes
        states: Filter by states (e.g., ["completed", "fledgeling"])
        forms: Filter by forms (e.g., ["free_verse", "prose_poem"])
        tags: Filter by tags (poems must have all specified tags)
        limit: Maximum number of results to return
        include_content: Whether to include full poem text in results

    Returns:
        SearchResult with matched poems and query metadata
    """
    import time
    start_time = time.perf_counter()

    cat = get_catalog()

    # Start with text search if query provided
    if query:
        results = cat.index.search_content(query, case_sensitive=False)
    else:
        # No query, start with all poems
        results = cat.index.all_poems.copy()

    # Apply state filter
    if states:
        results = [p for p in results if p.state in states]

    # Apply form filter
    if forms:
        results = [p for p in results if p.form in forms]

    # Apply tag filter (must have all tags)
    if tags:
        results = [
            p for p in results
            if all(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
        ]

    # Sort by relevance (poems with more tag matches first)
    if tags:
        def relevance_score(poem: Poem) -> int:
            return sum(1 for tag in tags if tag.lower() in [t.lower() for t in poem.tags])
        results.sort(key=relevance_score, reverse=True)

    # Limit results
    total_matches = len(results)
    results = results[:limit]

    # Remove content if not requested
    if not include_content:
        results = [
            Poem(**{**p.model_dump(), 'content': None})
            for p in results
        ]

    query_time_ms = (time.perf_counter() - start_time) * 1000

    return SearchResult(
        poems=results,
        total_matches=total_matches,
        query_time_ms=query_time_ms
    )


@mcp.tool()
async def find_poems_by_tag(
    tags: List[str],
    match_mode: str = "all",
    states: Optional[List[str]] = None,
    limit: int = 20
) -> List[Poem]:
    """
    Find poems by tags.

    Args:
        tags: List of tags to match
        match_mode: "all" (poems must have all tags) or "any" (at least one tag)
        states: Optional filter by states
        limit: Maximum number of results

    Returns:
        List of matching poems
    """
    cat = get_catalog()

    # Get poems matching tags
    poems = cat.index.get_by_tags(tags, match_mode=match_mode)

    # Apply state filter
    if states:
        poems = [p for p in poems if p.state in states]

    # Limit results
    poems = poems[:limit]

    # Remove content for efficiency
    poems = [
        Poem(**{**p.model_dump(), 'content': None})
        for p in poems
    ]

    return poems


@mcp.tool()
async def list_poems_by_state(
    state: str,
    sort_by: str = "title",
    limit: int = 100
) -> List[Poem]:
    """
    List poems in a specific state.

    Args:
        state: State to filter by (completed, fledgeling, still_cooking, etc.)
        sort_by: Field to sort by (title, created_at, updated_at, word_count)
        limit: Maximum number of results

    Returns:
        List of poems in the specified state
    """
    cat = get_catalog()

    poems = cat.index.get_by_state(state)

    # Sort by requested field
    if sort_by == "title":
        poems.sort(key=lambda p: p.title.lower())
    elif sort_by == "created_at":
        poems.sort(key=lambda p: p.created_at, reverse=True)
    elif sort_by == "updated_at":
        poems.sort(key=lambda p: p.updated_at, reverse=True)
    elif sort_by == "word_count":
        poems.sort(key=lambda p: p.word_count, reverse=True)

    # Limit results
    poems = poems[:limit]

    # Remove content
    poems = [
        Poem(**{**p.model_dump(), 'content': None})
        for p in poems
    ]

    return poems


@mcp.tool()
async def get_catalog_stats() -> CatalogStats:
    """
    Get catalog statistics.

    Returns:
        CatalogStats with counts, metrics, and health information
    """
    cat = get_catalog()
    return cat.get_stats()


@mcp.tool()
async def get_server_info() -> dict:
    """
    Get server information and status.

    Returns:
        Dictionary with server metadata
    """
    config = load_config()

    return {
        "name": "poetry-mcp",
        "version": "0.1.0",
        "vault_path": str(config.vault.path),
        "catalog_loaded": catalog is not None,
        "total_poems": len(catalog.index.all_poems) if catalog else 0
    }


# ===== Enrichment Tools =====

@mcp.tool()
async def get_all_nexuses() -> NexusRegistry:
    """
    Get all nexuses (themes/motifs/forms) from the registry.

    Returns complete registry with all nexus entries, organized by category.
    Use this to discover available themes, motifs, and forms for tagging poems.

    Returns:
        NexusRegistry with themes, motifs, and forms

    Example:
        Get all available themes:
        ```
        registry = await get_all_nexuses()
        for theme in registry.themes:
            print(f"{theme.name} → #{theme.canonical_tag}")
        ```
    """
    return await _get_all_nexuses()


@mcp.tool()
async def link_poem_to_nexus(
    poem_id: str,
    nexus_name: str,
    nexus_type: str = "theme",
) -> dict:
    """
    Link a poem to a nexus by adding the nexus's canonical tag.

    Safely updates the poem's tags field in frontmatter, preserving all other fields.
    Creates a backup before modification. Automatically resyncs catalog after update.

    Args:
        poem_id: Poem identifier (ID or title)
        nexus_name: Name of nexus to link (e.g., "Water-Liquid", "Childhood")
        nexus_type: Type of nexus (theme/motif/form), defaults to "theme"

    Returns:
        Dictionary with operation details including success status

    Example:
        Link a poem to a theme:
        ```
        result = await link_poem_to_nexus(
            poem_id="antlion",
            nexus_name="Water-Liquid",
            nexus_type="theme"
        )
        print(f"Added tag: {result['tag_added']}")
        ```
    """
    return await _link_poem_to_nexus(poem_id, nexus_name, nexus_type)


@mcp.tool()
async def find_nexuses_for_poem(
    poem_id: str,
    max_suggestions: int = 5,
) -> dict:
    """
    Prepare poem and theme data for analysis by the MCP agent.

    Returns poem content and available themes for YOU (the agent) to analyze.
    YOU identify which themes match the poem and provide confidence scores.

    Args:
        poem_id: Poem identifier (ID or title)
        max_suggestions: Maximum number of theme suggestions requested

    Returns:
        Dictionary with:
        - poem: Poem data (title, content, current_tags)
        - available_themes: Theme options with descriptions
        - instructions: Analysis guidance

    Example workflow:
        ```
        # 1. Get data for analysis
        data = await find_nexuses_for_poem("antlion", max_suggestions=3)

        # 2. YOU analyze data['poem'] against data['available_themes']
        # 3. YOU identify matching themes with confidence scores
        # 4. User applies tags with link_poem_to_nexus()
        ```
    """
    return await _find_nexuses_for_poem(poem_id, max_suggestions)


@mcp.tool()
async def get_poems_for_enrichment(
    poem_ids: Optional[List[str]] = None,
    max_poems: int = 50,
) -> dict:
    """
    Get batch of poems needing theme enrichment for agent analysis.

    Returns poems with minimal or no tags for YOU (the agent) to analyze.
    YOU suggest which themes apply to each poem.

    Args:
        poem_ids: List of poem IDs (None = all untagged/lightly-tagged poems)
        max_poems: Maximum poems to return (default 50)

    Returns:
        Dictionary with:
        - poems: List of poem data (id, title, content, current_tags)
        - available_themes: Theme options with descriptions
        - instructions: Batch analysis guidance

    Example workflow:
        ```
        # 1. Get poems needing enrichment
        data = await get_poems_for_enrichment(max_poems=10)

        # 2. YOU analyze data['poems'] against data['available_themes']
        # 3. YOU suggest 1-3 themes for each poem with confidence scores
        # 4. User applies high-confidence tags with link_poem_to_nexus()
        ```
    """
    return await _get_poems_for_enrichment(poem_ids, max_poems)


@mcp.tool()
async def sync_nexus_tags(
    poem_id: str,
    direction: str = "both",
) -> dict:
    """
    Synchronize [[Nexus]] links in poem body with frontmatter tags.

    Analyzes the poem's content for [[Nexus Name]] wikilinks and syncs them
    with the frontmatter tags field. Can sync in either direction or both.

    Args:
        poem_id: Poem identifier (ID or title)
        direction: Sync direction - "links_to_tags", "tags_to_links", or "both"

    Returns:
        Dictionary with sync results and any conflicts found

    Example:
        Sync wikilinks to tags:
        ```
        result = await sync_nexus_tags(
            poem_id="antlion",
            direction="links_to_tags"
        )
        print(f"Tags added: {result['tags_added']}")
        print(f"Conflicts: {result['conflicts']}")
        ```
    """
    return await _sync_nexus_tags(poem_id, direction)


@mcp.tool()
async def move_poem_to_state(
    poem_id: str,
    new_state: str,
) -> dict:
    """
    Move a poem to a different state directory and update frontmatter.

    Moves the poem file between state directories (Completed, Fledgelings, etc.)
    and updates the frontmatter state field. Handles backup files automatically.

    Args:
        poem_id: Poem identifier (ID or title)
        new_state: Target state (completed, fledgeling, still_cooking, etc.)

    Returns:
        Dictionary with move operation results

    Example:
        Promote a poem to completed:
        ```
        result = await move_poem_to_state(
            poem_id="antlion",
            new_state="completed"
        )
        print(f"Moved from {result['old_state']} to {result['new_state']}")
        print(f"New path: {result['new_path']}")
        ```
    """
    return await _move_poem_to_state(poem_id, new_state)


@mcp.tool()
async def grade_poem_quality(
    poem_id: str,
    dimensions: Optional[List[str]] = None,
) -> dict:
    """
    Prepare poem and quality rubric for grading by the MCP agent.

    Returns poem content and quality dimension descriptions for YOU (the agent) to grade.
    YOU provide scores (0-10) and reasoning for each dimension.

    8 Quality Dimensions:
    - Detail: Vividness and specificity of imagery
    - Life: Living, breathing quality and vitality
    - Music: Sound quality and rhythmic elements
    - Mystery: Ambiguity, layers, reader engagement
    - Sufficient Thought: Intellectual depth and insight
    - Surprise: Unexpected elements, fresh perspectives
    - Syntax: Sentence structure and line breaks
    - Unity: Coherence and wholeness

    Args:
        poem_id: Poem identifier (ID or title)
        dimensions: Optional list of specific dimensions to grade (default: all 8)

    Returns:
        Dictionary with:
        - poem: Poem data (title, content)
        - dimensions: Quality dimensions with descriptions
        - instructions: Grading guidance

    Example workflow:
        ```
        # 1. Get poem and rubric
        data = await grade_poem_quality("antlion")

        # 2. YOU grade data['poem'] on data['dimensions']
        # 3. YOU provide scores 0-10 with reasoning for each dimension
        #    - 0-3: Absent/poor
        #    - 4-6: Adequate
        #    - 7-8: Strong
        #    - 9-10: Exceptional
        ```
    """
    return await _grade_poem_quality(poem_id, dimensions)


def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Poetry MCP Server...")

    # Auto-sync catalog on startup
    logger.info("Auto-syncing catalog on startup...")
    try:
        cat = get_catalog()
        result = cat.sync()
        logger.info(
            f"Initial sync complete: {result.total_poems} poems loaded "
            f"in {result.duration_seconds:.2f}s"
        )
    except Exception as e:
        logger.error(f"Failed to sync catalog on startup: {e}")
        # Continue anyway - tools will still work

    # Initialize enrichment tools
    logger.info("Initializing enrichment tools...")
    try:
        initialize_enrichment_tools(cat)
        logger.info("Enrichment tools initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize enrichment tools: {e}")

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
