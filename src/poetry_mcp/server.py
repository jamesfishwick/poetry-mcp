"""Poetry MCP Server.

FastMCP server providing tools for poetry catalog and nexus management.
"""

import logging
import sys
from typing import Optional, List, Any

# Check Python version before any imports
if sys.version_info < (3, 10):
    print("Error: Poetry MCP requires Python 3.10 or higher")
    print(f"Current version: {sys.version_info.major}.{sys.version_info.minor}")
    sys.exit(1)

from fastmcp import FastMCP

from .config import load_config
from .catalog.catalog import Catalog
from .catalog.submission_catalog import SubmissionCatalog
from .catalog.venue_catalog import VenueCatalog
from .catalog.nexus_manager import NexusManager
from .models.poem import Poem
from .models.submission import Submission, SubmissionSummary, SubmissionStatus
from .models.venue import Venue
from .models.results import SyncResult, SearchResult, CatalogStats
from .models.nexus import NexusRegistry
from .writers.venue_writer import VenueWriter
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
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("poetry-mcp")

# Global catalog instances
catalog: Optional[Catalog] = None
submission_catalog: Optional[SubmissionCatalog] = None
venue_catalog: Optional[VenueCatalog] = None
nexus_manager: Optional[NexusManager] = None


def get_catalog() -> Catalog:
    """Get or initialize catalog instance."""
    global catalog

    if catalog is None:
        logger.info("Initializing catalog...")
        config = load_config()
        catalog = Catalog(
            vault_root=config.vault.path,
            exclude_dirs=config.vault.exclude_catalog_dirs,
            custom_states=config.vault.custom_states,
        )
        logger.info(f"Catalog initialized with vault: {config.vault.path}")
        if config.vault.exclude_catalog_dirs:
            logger.info(f"Excluding directories: {config.vault.exclude_catalog_dirs}")
        if config.vault.custom_states:
            logger.info(f"Custom states enabled: {config.vault.custom_states}")

    return catalog


def get_submission_catalog() -> SubmissionCatalog:
    """Get or initialize submission catalog instance."""
    global submission_catalog

    if submission_catalog is None:
        logger.info("Initializing submission catalog...")
        config = load_config()
        submissions_dir = config.vault.path / config.vault.submissions_dir
        submission_catalog = SubmissionCatalog(submissions_dir=submissions_dir)
        logger.info(f"Submission catalog initialized: {submissions_dir}")

    return submission_catalog


def get_venue_catalog() -> VenueCatalog:
    """Get or initialize venue catalog instance."""
    global venue_catalog

    if venue_catalog is None:
        logger.info("Initializing venue catalog...")
        config = load_config()
        venues_dir = config.vault.path / config.vault.venues_dir
        venue_catalog = VenueCatalog(venues_dir=venues_dir)
        logger.info(f"Venue catalog initialized: {venues_dir}")

    return venue_catalog


def get_nexus_manager() -> NexusManager:
    """Get or initialize nexus manager instance."""
    global nexus_manager

    if nexus_manager is None:
        logger.info("Initializing nexus manager...")
        config = load_config()
        nexus_root = config.vault.path / config.vault.nexus_dir
        nexus_manager = NexusManager(nexus_root=nexus_root)
        logger.info(f"Nexus manager initialized: {nexus_root}")

    return nexus_manager


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
async def get_poem(identifier: str, include_content: bool = True) -> Optional[Poem]:
    """
    Get a poem by ID or title.

    Args:
        identifier: Poem ID or exact title
        include_content: Whether to include full poem text

    Returns:
        Poem object or None if not found
    """
    cat = get_catalog()

    # Get poem by ID or title
    poem = cat.index.get_by_id_or_title(identifier.lower())

    if poem and not include_content:
        # Return copy without content
        poem_dict = poem.model_dump()
        poem_dict["content"] = None
        poem = Poem(**poem_dict)

    return poem


@mcp.tool()
async def search_poems(
    query: str,
    states: Optional[List[str]] = None,
    forms: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    limit: Optional[int] = None,
    include_content: bool = False,
) -> SearchResult:
    """
    Search for poems matching criteria.

    Args:
        query: Text to search for in titles, content, and notes
        states: Filter by states (e.g., ["completed", "fledgeling"])
        forms: Filter by forms (e.g., ["free_verse", "prose_poem"])
        tags: Filter by tags (poems must have all specified tags)
        limit: Maximum number of results to return (default from config)
        include_content: Whether to include full poem text in results

    Returns:
        SearchResult with matched poems and query metadata
    """
    import time

    start_time = time.perf_counter()

    cat = get_catalog()
    config = load_config()

    # Use config defaults
    if limit is None:
        limit = config.search.default_limit

    # Start with text search if query provided
    if query:
        results = cat.index.search_content(query, case_sensitive=config.search.case_sensitive)
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
            p for p in results if all(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
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
        results = [Poem(**{**p.model_dump(), "content": None}) for p in results]

    query_time_ms = (time.perf_counter() - start_time) * 1000

    return SearchResult(poems=results, total_matches=total_matches, query_time_ms=query_time_ms)


@mcp.tool()
async def find_poems_by_tag(
    tags: List[str], match_mode: str = "all", states: Optional[List[str]] = None, limit: int = 20
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
    poems = [Poem(**{**p.model_dump(), "content": None}) for p in poems]

    return poems


@mcp.tool()
async def list_poems_by_state(state: str, sort_by: str = "title", limit: int = 100) -> List[Poem]:
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
    poems = [Poem(**{**p.model_dump(), "content": None}) for p in poems]

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
        "total_poems": len(catalog.index.all_poems) if catalog else 0,
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


def commit_quality_scores_impl(
    poem_id: str,
    scores: dict,
    notes: Optional[str] = None,
    catalog: Optional[Any] = None,
) -> dict:
    """
    Implementation of quality score committing logic.

    Extracted for testability. See commit_quality_scores() for full documentation.
    """
    cat = catalog if catalog else get_catalog()

    # Get poem
    poem = cat.index.get_by_id_or_title(poem_id)
    if not poem:
        return {"success": False, "error": f"Poem not found: {poem_id}"}

    # Validate scores
    valid_dimensions = {
        "detail",
        "life",
        "music",
        "mystery",
        "sufficient thought",
        "surprise",
        "syntax",
        "unity",
    }

    normalized_scores = {}
    for dimension, score in scores.items():
        dim_lower = dimension.lower().strip()
        if dim_lower not in valid_dimensions:
            return {
                "success": False,
                "error": f"Invalid dimension '{dimension}'. Valid: {sorted(valid_dimensions)}",
            }
        if not isinstance(score, int) or score < 0 or score > 10:
            return {
                "success": False,
                "error": f"Score for '{dimension}' must be integer 0-10, got: {score}",
            }
        normalized_scores[dim_lower] = score

    # Read and update file
    from pathlib import Path
    from poetry_mcp.parsers.frontmatter_parser import extract_frontmatter

    vault_root = Path(cat.vault_root)
    file_path = vault_root / poem.file_path

    if not file_path.exists():
        return {"success": False, "error": f"Poem file not found: {file_path}"}

    # Read current content
    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content, file_path)

    # Update qualities
    frontmatter["qualities"] = normalized_scores
    if notes:
        frontmatter["quality_notes"] = notes

    # Write back
    import yaml
    from poetry_mcp.writers.frontmatter_writer import create_backup

    fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    new_content = f"---\n{fm_yaml}---\n{body}"

    # Create backup and write new content
    backup_path = create_backup(file_path)
    file_path.write_text(new_content, encoding="utf-8")

    # Resync catalog
    cat.sync()

    logger.info(f"Committed quality scores for '{poem.title}': {normalized_scores}")

    return {
        "success": True,
        "poem_id": poem.id,
        "scores_committed": normalized_scores,
        "notes": notes,
        "file_path": str(file_path),
    }


@mcp.tool()
async def commit_quality_scores(
    poem_id: str,
    scores: dict,
    notes: Optional[str] = None,
) -> dict:
    """
    Write quality scores to poem frontmatter after agent grading.

    After YOU grade a poem using grade_poem_quality(), use this tool to save
    your scores to the poem's frontmatter.

    Args:
        poem_id: Poem identifier (ID or title)
        scores: Dictionary of dimension name → score (0-10)
                Example: {"detail": 8, "life": 7, "music": 6}
        notes: Optional grading notes or reasoning summary

    Returns:
        Dictionary with:
        - success: Boolean indicating if save succeeded
        - poem_id: ID of the graded poem
        - scores_committed: The scores that were written
        - file_path: Path to the updated file

    Example:
        ```
        # After grading with grade_poem_quality
        result = await commit_quality_scores(
            poem_id="antlion",
            scores={
                "detail": 8,
                "life": 7,
                "music": 6,
                "mystery": 9,
                "sufficient thought": 8,
                "surprise": 7,
                "syntax": 8,
                "unity": 9
            },
            notes="Strong imagery and mystery, adequate music"
        )
        ```
    """
    return commit_quality_scores_impl(poem_id, scores, notes)


def get_quality_scores_impl(
    poem_id: str,
    catalog: Optional[Any] = None,
) -> dict:
    """
    Implementation of quality score retrieval logic.

    Extracted for testability. See get_quality_scores() for full documentation.
    """
    cat = catalog if catalog else get_catalog()

    # Get poem
    poem = cat.index.get_by_id_or_title(poem_id)
    if not poem:
        return {"success": False, "error": f"Poem not found: {poem_id}"}

    scores = poem.qualities if poem.qualities else {}

    # Read quality notes if present
    from pathlib import Path
    from poetry_mcp.parsers.frontmatter_parser import extract_frontmatter

    vault_root = Path(cat.vault_root)
    file_path = vault_root / poem.file_path

    notes = None
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        frontmatter, _ = extract_frontmatter(content, file_path)
        notes = frontmatter.get("quality_notes")

    return {
        "success": True,
        "poem_id": poem.id,
        "poem_title": poem.title,
        "scores": scores,
        "notes": notes,
        "has_scores": len(scores) > 0,
    }


@mcp.tool()
async def get_quality_scores(
    poem_id: str,
) -> dict:
    """
    Retrieve existing quality scores from a poem's frontmatter.

    Args:
        poem_id: Poem identifier (ID or title)

    Returns:
        Dictionary with:
        - success: Boolean
        - poem_id: ID of the poem
        - poem_title: Title of the poem
        - scores: Dictionary of dimension → score (or None if unscored)
        - notes: Optional grading notes

    Example:
        ```
        result = await get_quality_scores("antlion")
        if result['success']:
            for dim, score in result['scores'].items():
                print(f"{dim}: {score}/10")
        ```
    """
    return get_quality_scores_impl(poem_id)


def find_high_scoring_poems_impl(
    qualities: List[str],
    min_score: int = 8,
    states: Optional[List[str]] = None,
    limit: int = 20,
    catalog: Optional[Any] = None,
) -> dict:
    """
    Implementation of high-scoring poem finding logic.

    Extracted for testability. See find_high_scoring_poems() for full documentation.
    """
    cat = catalog if catalog else get_catalog()

    # Normalize quality names
    valid_dimensions = {
        "detail",
        "life",
        "music",
        "mystery",
        "sufficient thought",
        "surprise",
        "syntax",
        "unity",
    }

    normalized_qualities = []
    for q in qualities:
        q_lower = q.lower().strip()
        if q_lower not in valid_dimensions:
            return {
                "success": False,
                "error": f"Invalid quality dimension '{q}'. Valid: {sorted(valid_dimensions)}",
            }
        normalized_qualities.append(q_lower)

    # Filter poems
    matching_poems = []

    for poem in cat.index.all_poems:
        # State filter
        if states and poem.state not in states:
            continue

        # Must have quality scores
        if not poem.qualities:
            continue

        # Check if poem scores meet threshold on all requested dimensions
        matches_all = True
        dimension_scores = {}

        for quality in normalized_qualities:
            score = poem.qualities.get(quality)
            if score is None or score < min_score:
                matches_all = False
                break
            dimension_scores[quality] = score

        if matches_all:
            # Calculate average score across requested dimensions
            avg_score = sum(dimension_scores.values()) / len(dimension_scores)

            matching_poems.append(
                {
                    "id": poem.id,
                    "title": poem.title,
                    "state": poem.state,
                    "form": poem.form,
                    "scores": dimension_scores,
                    "avg_score": round(avg_score, 1),
                    "all_scores": poem.qualities,
                }
            )

    # Sort by average score (descending)
    matching_poems.sort(key=lambda p: p["avg_score"], reverse=True)  # type: ignore[arg-type,return-value]

    # Apply limit
    limited_poems = matching_poems[:limit]

    logger.info(f"Found {len(matching_poems)} poems scoring {min_score}+ on {normalized_qualities}")

    return {
        "success": True,
        "poems": limited_poems,
        "total_matches": len(matching_poems),
        "returned": len(limited_poems),
        "query": {
            "qualities": normalized_qualities,
            "min_score": min_score,
            "states": states,
            "limit": limit,
        },
    }


@mcp.tool()
async def find_high_scoring_poems(
    qualities: List[str],
    min_score: int = 8,
    states: Optional[List[str]] = None,
    limit: int = 20,
) -> dict:
    """
    Find poems with high scores on specified quality dimensions.

    Args:
        qualities: List of quality dimensions to filter on
                   Example: ["detail", "mystery"]
        min_score: Minimum score threshold (0-10), default 8
        states: Optional list of states to filter by (e.g., ["completed"])
        limit: Maximum number of results (default 20)

    Returns:
        Dictionary with:
        - success: Boolean
        - poems: List of matching poems with their scores
        - total_matches: Count of matching poems
        - query: The search parameters used

    Example:
        ```
        # Find completed poems scoring 8+ on detail and mystery
        result = await find_high_scoring_poems(
            qualities=["detail", "mystery"],
            min_score=8,
            states=["completed"],
            limit=10
        )

        for poem in result['poems']:
            print(f"{poem['title']}: {poem['avg_score']}/10")
        ```
    """
    return find_high_scoring_poems_impl(qualities, min_score, states, limit)


# ============================================================================
# Submission Management Tools
# ============================================================================


@mcp.tool()
async def sync_submissions(force_rescan: bool = False) -> dict:
    """
    Synchronize submission catalog from filesystem.

    Scans all submission markdown files in submissions/ directory
    and builds in-memory indices for fast lookup.

    Args:
        force_rescan: If True, rescan all files even if already loaded

    Returns:
        Dictionary with sync statistics:
        - total_submissions: Total submissions indexed
        - new_submissions: Newly discovered submissions
        - errors: List of parse errors encountered
        - duration_seconds: Time taken

    Example:
        ```
        result = await sync_submissions()
        print(f"Loaded {result['total_submissions']} submissions")
        ```
    """
    logger.info(f"Syncing submissions (force_rescan={force_rescan})...")
    sub_cat = get_submission_catalog()
    result = sub_cat.sync(force_rescan=force_rescan)
    logger.info(f"Submission sync complete: {result['total_submissions']} submissions")
    return result


@mcp.tool()
async def list_submissions(
    venue: Optional[str] = None,
    status: Optional[SubmissionStatus] = None,
    poem: Optional[str] = None,
    limit: Optional[int] = 50,
) -> dict:
    """
    List submissions with optional filtering.

    Args:
        venue: Filter by venue name
        status: Filter by status (planned, submitted, accepted, rejected, withdrawn)
        poem: Filter by poem title
        limit: Maximum results to return

    Returns:
        Dictionary with:
        - submissions: List of matching Submission objects
        - total: Total matches before limit
        - filters_applied: Summary of filters used

    Example:
        ```
        # Get all pending submissions
        result = await list_submissions(status="submitted")

        # Get submissions to a specific venue
        result = await list_submissions(venue="Rattle")

        # Find all submissions of a poem
        result = await list_submissions(poem="Second Bridge Out Old Route 12")
        ```
    """
    sub_cat = get_submission_catalog()

    # Filter submissions
    submissions = sub_cat.filter_submissions(venue=venue, status=status, poem=poem)

    # Apply limit
    total = len(submissions)
    if limit:
        submissions = submissions[:limit]

    return {
        "submissions": [sub.model_dump() for sub in submissions],
        "total": total,
        "filters_applied": {
            "venue": venue,
            "status": status,
            "poem": poem,
            "limit": limit,
        },
    }


@mcp.tool()
async def get_submission_stats() -> SubmissionSummary:
    """
    Get submission statistics and metrics.

    Returns:
        SubmissionSummary with:
        - total_submissions: Total count
        - by_status: Breakdown by status
        - active_submissions: Currently pending
        - total_poems_submitted: Count of individual poems
        - acceptance_rate: Percentage accepted

    Example:
        ```
        stats = await get_submission_stats()
        print(f"Acceptance rate: {stats.acceptance_rate}%")
        print(f"Active submissions: {stats.active_submissions}")
        ```
    """
    sub_cat = get_submission_catalog()
    return sub_cat.get_summary()


# ============================================================================
# Venue Management Tools
# ============================================================================


@mcp.tool()
async def sync_venues(force_rescan: bool = False) -> dict:
    """
    Synchronize venue catalog from filesystem.

    Scans all venue markdown files in venues/ directory
    and extracts venue metadata from frontmatter.

    Args:
        force_rescan: If True, rescan all files even if already loaded

    Returns:
        Dictionary with sync statistics:
        - total_venues: Total venues indexed
        - new_venues: Newly discovered venues
        - errors: List of parse errors encountered
        - duration_seconds: Time taken

    Example:
        ```
        result = await sync_venues()
        print(f"Loaded {result['total_venues']} venues")
        ```
    """
    logger.info(f"Syncing venues (force_rescan={force_rescan})...")
    ven_cat = get_venue_catalog()
    result = ven_cat.sync(force_rescan=force_rescan)
    logger.info(f"Venue sync complete: {result['total_venues']} venues")
    return result


@mcp.tool()
async def list_venues(
    payment_filter: Optional[str] = None,
    simultaneous_filter: Optional[bool] = None,
) -> dict:
    """
    List all venues with optional filtering.

    Args:
        payment_filter: Filter by payment (e.g., "yes", "no", "$50")
        simultaneous_filter: Filter by simultaneous submissions acceptance

    Returns:
        Dictionary with:
        - venues: List of Venue objects
        - total: Total count
        - filters_applied: Summary of filters used

    Example:
        ```
        # Get all paying venues
        result = await list_venues(payment_filter="yes")

        # Get venues accepting simultaneous submissions
        result = await list_venues(simultaneous_filter=True)
        ```
    """
    ven_cat = get_venue_catalog()

    venues = ven_cat.filter_venues(
        payment_filter=payment_filter,
        simultaneous_filter=simultaneous_filter,
    )

    return {
        "venues": [v.model_dump() for v in venues],
        "total": len(venues),
        "filters_applied": {
            "payment": payment_filter,
            "simultaneous": simultaneous_filter,
        },
    }


@mcp.tool()
async def get_venue(venue_name: str) -> dict:
    """
    Get venue metadata and submission history.

    Args:
        venue_name: Name of the venue

    Returns:
        Dictionary with:
        - venue: Venue metadata
        - submissions: All submissions to this venue
        - stats: Venue-specific statistics

    Example:
        ```
        result = await get_venue("Rattle")
        print(f"Venue: {result['venue']['name']}")
        print(f"Total submissions: {result['stats']['total']}")
        ```
    """
    ven_cat = get_venue_catalog()
    sub_cat = get_submission_catalog()

    # Get venue metadata
    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return {
            "success": False,
            "error": f"Venue not found: {venue_name}",
        }

    # Get submissions for this venue
    submissions = sub_cat.get_by_venue(venue_name)

    # Calculate stats
    stats = {
        "total": len(submissions),
        "by_status": {},
    }

    for sub in submissions:
        status = sub.status
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

    return {
        "success": True,
        "venue": venue.model_dump(),
        "submissions": [sub.model_dump() for sub in submissions],
        "stats": stats,
    }


@mcp.tool()
async def regenerate_venue_file(venue_name: str) -> dict:
    """
    Regenerate venue markdown file from metadata and submissions.

    Rebuilds the venue file with current metadata and all submissions
    organized by status. This is useful after updating submission data.

    Args:
        venue_name: Name of the venue to regenerate

    Returns:
        Dictionary with:
        - success: Boolean
        - file_path: Path to regenerated file
        - submissions_count: Number of submissions included

    Example:
        ```
        result = await regenerate_venue_file("Rattle")
        print(f"Regenerated: {result['file_path']}")
        ```
    """
    ven_cat = get_venue_catalog()
    sub_cat = get_submission_catalog()
    config = load_config()

    # Get venue metadata
    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return {
            "success": False,
            "error": f"Venue not found: {venue_name}",
        }

    # Get submissions
    submissions = sub_cat.get_by_venue(venue_name)

    # Generate file
    venues_dir = config.vault.path / config.vault.venues_dir
    output_path = venues_dir / f"{venue_name}.md"

    writer = VenueWriter()
    writer.generate_venue_file(venue, submissions, output_path)

    logger.info(f"Regenerated venue file: {output_path}")

    return {
        "success": True,
        "file_path": str(output_path),
        "submissions_count": len(submissions),
    }


# ============================================================================
# Nexus Management Tools
# ============================================================================


@mcp.tool()
async def get_poems_by_nexus(
    nexus_name: str,
    category: str = "theme",
    limit: Optional[int] = 50,
) -> dict:
    """
    Get all poems tagged with a specific nexus.

    Reverse lookup: finds all poems that reference this nexus via their tags.
    Returns the nexus metadata along with matching poems.

    Args:
        nexus_name: Name of the nexus (e.g., "Water-Liquid", "American Grotesque")
        category: Nexus category - "theme", "motif", or "form" (default: "theme")
        limit: Maximum number of poems to return (default: 50)

    Returns:
        Dictionary with:
        - success: Boolean
        - nexus: Nexus metadata (name, canonical_tag, description)
        - poems: List of poems tagged with this nexus
        - total_count: Total number of matching poems
        - returned_count: Number of poems returned (limited by limit param)

    Example:
        ```
        # Find all poems with water imagery
        result = await get_poems_by_nexus("Water-Liquid", "theme")
        print(f"Found {result['total_count']} water poems")
        for poem in result['poems']:
            print(f"  - {poem['title']}")

        # Find all American Sentences
        result = await get_poems_by_nexus("American Sentence", "form")
        ```

    Note:
        This provides the reverse direction of link_poem_to_nexus().
        Use this to explore what poems are connected to a nexus.
    """
    cat = get_catalog()

    # Get nexus registry to find the canonical_tag
    registry = await get_all_nexuses()

    # Find the nexus in the appropriate category
    nexus_list = {
        "theme": registry.themes,
        "motif": registry.motifs,
        "form": registry.forms,
    }.get(category)

    if not nexus_list:
        return {
            "success": False,
            "error": f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        }

    # Find nexus by name (case-insensitive)
    nexus = None
    for n in nexus_list:
        if n.name.lower() == nexus_name.lower():
            nexus = n
            break

    if not nexus:
        return {
            "success": False,
            "error": f"Nexus '{nexus_name}' not found in category '{category}'",
            "available_nexuses": [n.name for n in nexus_list],
        }

    # Get poems with this canonical tag
    poems = cat.index.get_by_tag(nexus.canonical_tag)

    # Apply limit
    total_count = len(poems)
    if limit:
        poems = poems[:limit]

    logger.info(f"Found {total_count} poems for nexus '{nexus_name}' ({nexus.canonical_tag})")

    return {
        "success": True,
        "nexus": nexus.model_dump(),
        "poems": [poem.model_dump() for poem in poems],
        "total_count": total_count,
        "returned_count": len(poems),
    }


@mcp.tool()
async def refresh_nexus_poem_counts() -> dict:
    """
    Compute and populate poem_count for all nexuses.

    Scans all poems in the catalog and counts how many are tagged
    with each nexus's canonical_tag. Updates the nexus registry
    with these counts.

    Returns:
        Dictionary with:
        - success: Boolean
        - nexuses_updated: Number of nexuses processed
        - stats: Breakdown by category (themes, motifs, forms)
        - top_nexuses: Top 5 most-connected nexuses

    Example:
        ```
        result = await refresh_nexus_poem_counts()
        print(f"Updated {result['nexuses_updated']} nexuses")

        for nexus in result['top_nexuses']:
            print(f"  {nexus['name']}: {nexus['poem_count']} poems")
        ```

    Note:
        This is useful for seeing which nexuses are most prevalent
        in your poetry collection. Run periodically to keep counts fresh.
    """
    cat = get_catalog()
    registry = await get_all_nexuses()

    stats = {
        "themes": {"count": 0, "total_poems": 0},
        "motifs": {"count": 0, "total_poems": 0},
        "forms": {"count": 0, "total_poems": 0},
    }

    all_nexuses_with_counts = []

    # Update poem_count for each nexus
    for category_name, nexus_list in [
        ("themes", registry.themes),
        ("motifs", registry.motifs),
        ("forms", registry.forms),
    ]:
        for nexus in nexus_list:
            # Count poems with this canonical tag
            poems = cat.index.get_by_tag(nexus.canonical_tag)
            nexus.poem_count = len(poems)

            stats[category_name]["count"] += 1
            stats[category_name]["total_poems"] += len(poems)

            all_nexuses_with_counts.append({
                "name": nexus.name,
                "category": nexus.category,
                "canonical_tag": nexus.canonical_tag,
                "poem_count": nexus.poem_count,
            })

    # Sort to find top nexuses
    all_nexuses_with_counts.sort(key=lambda n: n["poem_count"], reverse=True)
    top_nexuses = all_nexuses_with_counts[:5]

    total_updated = sum(s["count"] for s in stats.values())

    logger.info(f"Refreshed poem counts for {total_updated} nexuses")

    return {
        "success": True,
        "nexuses_updated": total_updated,
        "stats": stats,
        "top_nexuses": top_nexuses,
    }


@mcp.tool()
async def find_orphaned_tags() -> dict:
    """
    Find tags in poems that don't match any nexus.

    Scans all tags used in poems and compares them against the
    canonical_tags defined in nexuses. Returns tags that exist
    in poems but have no corresponding nexus definition.

    Returns:
        Dictionary with:
        - success: Boolean
        - orphaned_tags: List of tags without nexus definitions
        - orphaned_count: Number of orphaned tags found
        - affected_poems: List of poems with orphaned tags
        - valid_tags: List of all valid nexus tags for reference

    Example:
        ```
        result = await find_orphaned_tags()
        print(f"Found {result['orphaned_count']} orphaned tags")

        for tag in result['orphaned_tags']:
            print(f"  - {tag} (no nexus definition)")

        for poem in result['affected_poems']:
            print(f"  {poem['title']}: {poem['orphaned_tags']}")
        ```

    Note:
        Orphaned tags usually indicate:
        - Typos in manual tagging
        - Deleted nexuses that weren't cleaned up
        - Legacy tags from old schema
        Use this to maintain data integrity.
    """
    cat = get_catalog()
    registry = await get_all_nexuses()

    # Collect all valid canonical tags from nexuses
    valid_tags = set()
    for nexus_list in [registry.themes, registry.motifs, registry.forms]:
        for nexus in nexus_list:
            if nexus.canonical_tag:
                valid_tags.add(nexus.canonical_tag.lower())

    # Collect all tags used in poems
    all_poem_tags = set()
    poems_with_orphaned = []

    for poem in cat.index.all_poems:
        if poem.tags:
            for tag in poem.tags:
                tag_lower = tag.lower()
                all_poem_tags.add(tag_lower)

                # Check if this tag is orphaned
                if tag_lower not in valid_tags:
                    # Find if this poem is already in the list
                    existing = next((p for p in poems_with_orphaned if p["id"] == poem.id), None)
                    if existing:
                        existing["orphaned_tags"].append(tag)
                    else:
                        poems_with_orphaned.append({
                            "id": poem.id,
                            "title": poem.title,
                            "orphaned_tags": [tag],
                            "file_path": str(poem.file_path),
                        })

    # Find orphaned tags
    orphaned_tags = sorted(all_poem_tags - valid_tags)

    logger.info(f"Found {len(orphaned_tags)} orphaned tags across {len(poems_with_orphaned)} poems")

    return {
        "success": True,
        "orphaned_tags": orphaned_tags,
        "orphaned_count": len(orphaned_tags),
        "affected_poems": poems_with_orphaned,
        "affected_poems_count": len(poems_with_orphaned),
        "valid_tags": sorted(valid_tags),
    }


@mcp.tool()
async def create_nexus(
    name: str,
    category: str,
    canonical_tag: str,
    description: str,
    custom_template: Optional[str] = None,
) -> dict:
    """
    Create a new nexus (theme, motif, or form).

    Creates a new nexus markdown file in the appropriate directory
    (nexus/themes/, nexus/motifs/, or nexus/forms/).

    Args:
        name: Nexus name (e.g., "Water-Liquid", "American Grotesque", "Sonnet")
        category: Nexus category - must be "theme", "motif", or "form"
        canonical_tag: Tag for poems (e.g., "water", "american-grotesque", "sonnet")
        description: What this nexus represents and its characteristics
        custom_template: Optional custom markdown template for the nexus file

    Returns:
        Dictionary with:
        - success: Boolean
        - nexus: Created nexus object
        - file_path: Path to created file

    Example:
        ```
        # Create a new theme
        result = await create_nexus(
            name="Urban Decay",
            category="theme",
            canonical_tag="urban-decay",
            description="Images of deteriorating cities, abandoned buildings, and industrial ruins"
        )
        print(f"Created: {result['file_path']}")

        # Create a new form
        result = await create_nexus(
            name="Sonnet",
            category="form",
            canonical_tag="sonnet",
            description="14-line poem with specific rhyme scheme and meter"
        )
        ```

    Note:
        After creating a nexus, sync the catalog to make it available for poem tagging:
        `await get_all_nexuses()` will include the new nexus.
    """
    # Validate category
    if category not in ["theme", "motif", "form"]:
        return {
            "success": False,
            "error": f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        }

    try:
        manager = get_nexus_manager()
        nexus = manager.create_nexus(
            name=name,
            category=category,
            canonical_tag=canonical_tag,
            description=description,
            custom_template=custom_template,
        )

        logger.info(f"Created nexus: {nexus.name} ({category})")

        # Refresh nexus registry to include new nexus
        cat = get_catalog()
        initialize_enrichment_tools(cat)
        logger.info("Nexus registry refreshed")

        return {
            "success": True,
            "nexus": nexus.model_dump(),
            "file_path": nexus.file_path,
        }

    except Exception as e:
        logger.error(f"Failed to create nexus: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
async def delete_nexus(
    name: str,
    category: str,
    cleanup_poems: bool = False,
    force: bool = False,
) -> dict:
    """
    Delete a nexus (theme, motif, or form).

    Removes the nexus markdown file from the vault. Optionally removes
    the corresponding tag from all poems that reference it.

    Args:
        name: Nexus name to delete
        category: Nexus category - must be "theme", "motif", or "form"
        cleanup_poems: If True, remove tag from all poems before deleting (default False)
        force: If True, delete even if poems reference it (default False)

    Returns:
        Dictionary with:
        - success: Boolean
        - deleted: Path to deleted file
        - nexus_name: Name of deleted nexus
        - category: Category of deleted nexus
        - poems_cleaned: Number of poems that had tag removed (if cleanup_poems=True)

    Example:
        ```
        # Delete a theme (poems keep the tag)
        result = await delete_nexus(
            name="Urban Decay",
            category="theme"
        )
        print(f"Deleted: {result['deleted']}")

        # Delete and clean up all references
        result = await delete_nexus(
            name="Old Theme",
            category="theme",
            cleanup_poems=True
        )
        print(f"Removed tag from {result['poems_cleaned']} poems")
        ```

    Warning:
        This operation cannot be undone. The nexus file will be permanently
        deleted from the filesystem.

        If cleanup_poems=False, poems with this tag will keep the tag,
        creating orphaned references (use find_orphaned_tags to detect).

        If cleanup_poems=True, the tag will be removed from all poems,
        which may affect your tagging structure.
    """
    # Validate category
    if category not in ["theme", "motif", "form"]:
        return {
            "success": False,
            "error": f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        }

    try:
        cat = get_catalog()
        registry = await get_all_nexuses()

        # Find the nexus to get its canonical_tag
        nexus_list = {
            "theme": registry.themes,
            "motif": registry.motifs,
            "form": registry.forms,
        }[category]

        nexus = None
        for n in nexus_list:
            if n.name.lower() == name.lower():
                nexus = n
                break

        if not nexus:
            return {
                "success": False,
                "error": f"Nexus '{name}' not found in category '{category}'",
            }

        poems_cleaned = 0

        # Clean up poems if requested
        if cleanup_poems and nexus.canonical_tag:
            poems_with_tag = cat.index.get_by_tag(nexus.canonical_tag)
            logger.info(f"Cleaning up {len(poems_with_tag)} poems with tag '{nexus.canonical_tag}'")

            for poem in poems_with_tag:
                try:
                    # Remove the tag from poem
                    update_poem_tags(
                        poem_path=poem.file_path,
                        tags_to_remove=[nexus.canonical_tag],
                    )
                    poems_cleaned += 1
                except Exception as e:
                    logger.warning(f"Failed to remove tag from {poem.title}: {e}")

            # Resync catalog after tag removals
            cat.sync(force_rescan=True)
            logger.info(f"Catalog resynced after cleaning {poems_cleaned} poems")

        # Delete the nexus file
        manager = get_nexus_manager()
        result = manager.delete_nexus(
            name=name,
            category=category,
            force=force,
        )

        logger.info(f"Deleted nexus: {name} ({category})")

        # Refresh nexus registry to remove deleted nexus
        initialize_enrichment_tools(cat)
        logger.info("Nexus registry refreshed")

        # Add cleanup info to result
        result["poems_cleaned"] = poems_cleaned

        return result

    except Exception as e:
        logger.error(f"Failed to delete nexus: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def main() -> None:
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
