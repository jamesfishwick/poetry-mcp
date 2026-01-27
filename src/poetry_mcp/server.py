"""Poetry MCP Server.

FastMCP server providing tools for poetry catalog and nexus management.
"""

import asyncio
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
from .models.results import (
    SyncResult,
    SearchResult,
    CatalogStats,
    ValidationResult,
    NexusOperationResult,
    PoemsByNexusResult,
    NexusCountsResult,
    ServerInfo,
    SyncSubmissionsResult,
    SyncVenuesResult,
    VenueDetailResult,
    RegenerateVenueResult,
    SubmissionListResult,
    VenueListResult,
)
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
from .tools.chain_tools import (
    initialize_chain_tools,
    create_chain as _create_chain,
    add_poems_to_chain as _add_poems_to_chain,
    remove_poems_from_chain as _remove_poems_from_chain,
    reorder_chain as _reorder_chain,
    delete_chain as _delete_chain,
    get_chain as _get_chain,
    list_chains as _list_chains,
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
async def get_server_info() -> ServerInfo:
    """
    Get server information and status.

    Returns:
        ServerInfo with server metadata and catalog statistics
    """
    config = load_config()
    cat = get_catalog()
    stats = cat.get_stats()

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


@mcp.tool()
async def query_poems(
    # Text search
    query: Optional[str] = None,
    # Filters
    states: Optional[List[str]] = None,
    forms: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    tag_match_mode: str = "all",  # "all" or "any"
    chain_id: Optional[str] = None,  # Filter by chain membership
    # Quality filters  
    min_quality_score: Optional[int] = None,
    quality_dimensions: Optional[List[str]] = None,
    # Sorting
    sort_by: str = "relevance",  # relevance, title, created_at, updated_at, word_count, chain_position
    # Output control
    limit: Optional[int] = None,
    include_content: bool = False,
) -> SearchResult:
    """
    Unified search and query interface for poems.
    
    Replaces: search_poems, find_poems_by_tag, list_poems_by_state,
              get_poems_by_nexus, find_high_scoring_poems
    
    Args:
        query: Text to search in titles, content, notes (optional)
        states: Filter by states (e.g., ["completed", "fledgeling"])
        forms: Filter by forms (e.g., ["free_verse", "prose_poem"])
        tags: Filter by tags  
        tag_match_mode: "all" (must have all tags) or "any" (at least one tag)
        chain_id: Filter by chain membership (only poems in this chain)
        min_quality_score: Minimum score threshold (0-10) for quality filtering
        quality_dimensions: Quality dimensions to filter on (e.g., ["detail", "mystery"])
        sort_by: Sort field - "relevance" (default), "title", "created_at", "updated_at", 
                 "word_count", "chain_position" (requires chain_id)
        limit: Maximum results (default from config)
        include_content: Include full poem text in results
    
    Returns:
        SearchResult with matched poems and query metadata
        
    Examples:
        ```
        # Text search with state filter
        await query_poems(query="water", states=["completed"])
        
        # Tag search with ANY mode
        await query_poems(tags=["water", "memory"], tag_match_mode="any")
        
        # State list with sorting
        await query_poems(states=["completed"], sort_by="updated_at")
        
        # Quality-based search
        await query_poems(
            quality_dimensions=["detail", "mystery"],
            min_quality_score=8,
            states=["completed"]
        )
        
        # Single nexus lookup (reverse tag lookup)
        await query_poems(tags=["Water-Liquid Imagery"])
        
        # Get poems in a chain, sorted by position
        await query_poems(chain_id="water-sequence", sort_by="chain_position")
        ```
    """
    import time
    
    start_time = time.perf_counter()
    cat = get_catalog()
    config = load_config()
    
    # Use config default for limit
    if limit is None:
        limit = config.search.default_limit
    
    # Start with text search or all poems
    if query:
        results = cat.index.search_content(query, case_sensitive=config.search.case_sensitive)
    else:
        results = cat.index.all_poems.copy()
    
    # Apply state filter
    if states:
        results = [p for p in results if p.state in states]
    
    # Apply form filter
    if forms:
        results = [p for p in results if p.form in forms]
    
    # Apply tag filter with match mode
    if tags:
        if tag_match_mode == "all":
            # Must have all tags
            results = [
                p for p in results 
                if all(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
            ]
        elif tag_match_mode == "any":
            # Must have at least one tag
            results = [
                p for p in results
                if any(tag.lower() in [t.lower() for t in p.tags] for tag in tags)
            ]
    
    # Apply chain filter
    if chain_id:
        normalized_chain = chain_id.lower().strip().replace(" ", "-")
        chain_poem_ids = set(cat.index.by_chain.get(normalized_chain, []))
        results = [p for p in results if p.id in chain_poem_ids]
    
    # Apply quality score filter
    if min_quality_score is not None and quality_dimensions:
        filtered_results = []
        for poem in results:
            if not poem.quality or not poem.quality.scores:
                continue
                
            # Check if poem meets threshold on ALL specified dimensions
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
    
    # Sort results
    if sort_by == "title":
        results.sort(key=lambda p: p.title.lower())
    elif sort_by == "created_at":
        results.sort(key=lambda p: p.created_at, reverse=True)
    elif sort_by == "updated_at":
        results.sort(key=lambda p: p.updated_at, reverse=True)
    elif sort_by == "word_count":
        results.sort(key=lambda p: p.word_count, reverse=True)
    elif sort_by == "chain_position" and chain_id:
        # Sort by position in chain (ordered poems first, then loose by title)
        normalized_chain = chain_id.lower().strip().replace(" ", "-")
        def chain_sort_key(poem: Poem) -> tuple:
            if poem.chain_positions and normalized_chain in poem.chain_positions:
                return (0, poem.chain_positions[normalized_chain], "")
            return (1, 0, poem.title.lower())
        results.sort(key=chain_sort_key)
    elif sort_by == "relevance" and tags:
        # Sort by tag match relevance
        def relevance_score(poem: Poem) -> int:
            return sum(1 for tag in tags if tag.lower() in [t.lower() for t in poem.tags])
        results.sort(key=relevance_score, reverse=True)
    # else: keep original order for relevance without tags
    
    # Limit results
    total_matches = len(results)
    results = results[:limit]
    
    # Remove content if not requested
    if not include_content:
        results = [Poem(**{**p.model_dump(), "content": None}) for p in results]
    
    query_time_ms = (time.perf_counter() - start_time) * 1000
    
    return SearchResult(poems=results, total_matches=total_matches, query_time_ms=query_time_ms)


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


# ============================================================================
# Submission Management Tools
# ============================================================================


@mcp.tool()
async def sync_submissions(force_rescan: bool = False) -> SyncSubmissionsResult:
    """
    Synchronize submission catalog from filesystem.

    Scans all submission markdown files in submissions/ directory,
    builds in-memory indices, and auto-regenerates venue files.

    Args:
        force_rescan: If True, rescan all files even if already loaded

    Returns:
        SyncSubmissionsResult with sync statistics:
        - success: Always True for successful sync
        - total_submissions: Total submissions indexed
        - new_submissions: Newly discovered submissions
        - errors: List of parse errors encountered
        - duration_seconds: Time taken

    Example:
        ```
        result = await sync_submissions()
        print(f"Loaded {result.total_submissions} submissions")
        ```
    """
    logger.info(f"Syncing submissions (force_rescan={force_rescan})...")
    sub_cat = get_submission_catalog()
    result = sub_cat.sync(force_rescan=force_rescan)
    logger.info(f"Submission sync complete: {result['total_submissions']} submissions")

    # Auto-regenerate venue files for all venues with submissions
    logger.info("Auto-regenerating venue files...")
    ven_cat = get_venue_catalog()
    config = load_config()
    venues_dir = config.vault.path / config.vault.venues_dir

    # Get all unique venue names from submissions
    all_submissions = sub_cat.all_submissions
    venue_names = set(sub.venue_name for sub in all_submissions)

    # Regenerate each venue file
    regenerated_count = 0
    for venue_name in venue_names:
        venue = ven_cat.get_by_name(venue_name)
        if venue:
            submissions = sub_cat.get_by_venue(venue_name)
            output_path = venues_dir / f"{venue_name}.md"

            writer = VenueWriter()
            writer.generate_venue_file(venue, submissions, output_path)
            regenerated_count += 1
            logger.debug(f"Regenerated venue file: {venue_name}")

    logger.info(f"Regenerated {regenerated_count} venue files")

    return SyncSubmissionsResult(
        success=True,
        total_submissions=result["total_submissions"],
        new_submissions=result["new_submissions"],
        errors=result["errors"],
        duration_seconds=result["duration_seconds"],
    )


@mcp.tool()
async def list_submissions(
    venue: Optional[str] = None,
    status: Optional[SubmissionStatus] = None,
    poem: Optional[str] = None,
    limit: Optional[int] = 50,
) -> SubmissionListResult:
    """
    List submissions with optional filtering.

    Args:
        venue: Filter by venue name
        status: Filter by status (planned, submitted, accepted, rejected, withdrawn)
        poem: Filter by poem title
        limit: Maximum results to return

    Returns:
        SubmissionListResult with:
        - success: Always True
        - submissions: List of matching Submission objects
        - total_count: Total matches before limit
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

    return SubmissionListResult(
        success=True,
        submissions=submissions,
        total_count=total,
        filters_applied={
            "venue": venue,
            "status": status,
            "poem": poem,
            "limit": limit,
        },
    )


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
async def sync_venues(force_rescan: bool = False) -> SyncVenuesResult:
    """
    Synchronize venue catalog from filesystem.

    Scans all venue markdown files in venues/ directory
    and extracts venue metadata from frontmatter.

    Args:
        force_rescan: If True, rescan all files even if already loaded

    Returns:
        SyncVenuesResult with sync statistics:
        - success: Always True for successful sync
        - total_venues: Total venues indexed
        - new_venues: Newly discovered venues
        - errors: List of parse errors encountered
        - duration_seconds: Time taken

    Example:
        ```
        result = await sync_venues()
        print(f"Loaded {result.total_venues} venues")
        ```
    """
    logger.info(f"Syncing venues (force_rescan={force_rescan})...")
    ven_cat = get_venue_catalog()
    result = ven_cat.sync(force_rescan=force_rescan)
    logger.info(f"Venue sync complete: {result['total_venues']} venues")
    
    return SyncVenuesResult(
        success=True,
        total_venues=result["total_venues"],
        new_venues=result["new_venues"],
        errors=result["errors"],
        duration_seconds=result["duration_seconds"],
    )


@mcp.tool()
async def list_venues(
    payment_filter: Optional[str] = None,
    simultaneous_filter: Optional[bool] = None,
) -> VenueListResult:
    """
    List all venues with optional filtering.

    Args:
        payment_filter: Filter by payment (e.g., "yes", "no", "$50")
        simultaneous_filter: Filter by simultaneous submissions acceptance

    Returns:
        VenueListResult with:
        - success: Always True
        - venues: List of Venue objects
        - total_count: Total count
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

    return VenueListResult(
        success=True,
        venues=venues,
        total_count=len(venues),
        filters_applied={
            "payment": payment_filter,
            "simultaneous": simultaneous_filter,
        },
    )


@mcp.tool()
async def get_venue(venue_name: str) -> VenueDetailResult:
    """
    Get venue metadata and submission history.

    Args:
        venue_name: Name of the venue

    Returns:
        VenueDetailResult with:
        - success: Whether venue was found
        - venue: Venue metadata (if found)
        - submissions: All submissions to this venue
        - error: Error message if venue not found

    Example:
        ```
        result = await get_venue("Rattle")
        if result.success:
            print(f"Venue: {result.venue.name}")
            print(f"Total submissions: {len(result.submissions)}")
        ```
    """
    ven_cat = get_venue_catalog()
    sub_cat = get_submission_catalog()

    # Get venue metadata
    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return VenueDetailResult(
            success=False,
            error=f"Venue not found: {venue_name}",
        )

    # Get submissions for this venue
    submissions = sub_cat.get_by_venue(venue_name)

    return VenueDetailResult(
        success=True,
        venue=venue,
        submissions=submissions,
    )


@mcp.tool()
async def regenerate_venue_file(venue_name: str) -> RegenerateVenueResult:
    """
    Regenerate venue markdown file from metadata and submissions.

    Rebuilds the venue file with current metadata and all submissions
    organized by status. This is useful after updating submission data.

    Args:
        venue_name: Name of the venue to regenerate

    Returns:
        RegenerateVenueResult with:
        - success: Whether regeneration succeeded
        - venue_name: Name of venue regenerated
        - file_path: Path to regenerated file
        - submissions_count: Number of submissions included
        - error: Error message if venue not found

    Example:
        ```
        result = await regenerate_venue_file("Rattle")
        if result.success:
            print(f"Regenerated: {result.file_path}")
        ```
    """
    ven_cat = get_venue_catalog()
    sub_cat = get_submission_catalog()
    config = load_config()

    # Get venue metadata
    venue = ven_cat.get_by_name(venue_name)
    if not venue:
        return RegenerateVenueResult(
            success=False,
            venue_name=venue_name,
            file_path="",
            submissions_count=0,
            error=f"Venue not found: {venue_name}",
        )

    # Get submissions
    submissions = sub_cat.get_by_venue(venue_name)

    # Generate file
    venues_dir = config.vault.path / config.vault.venues_dir
    output_path = venues_dir / f"{venue_name}.md"

    writer = VenueWriter()
    writer.generate_venue_file(venue, submissions, output_path)

    logger.info(f"Regenerated venue file: {output_path}")

    return RegenerateVenueResult(
        success=True,
        venue_name=venue_name,
        file_path=str(output_path),
        submissions_count=len(submissions),
    )


# ============================================================================
# Nexus Management Tools
# ============================================================================

@mcp.tool()
async def refresh_nexus_poem_counts() -> NexusCountsResult:
    """
    Compute and populate poem_count for all nexuses.

    Scans all poems in the catalog and counts how many are tagged
    with each nexus's canonical_tag. Updates the nexus registry
    with these counts.

    Returns:
        NexusCountsResult with refresh statistics and top nexuses

    Example:
        ```
        result = await refresh_nexus_poem_counts()
        print(f"Updated {result.nexuses_updated} nexuses")

        for nexus in result.top_nexuses:
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

    return NexusCountsResult(
        success=True,
        nexuses_updated=total_updated,
        stats=stats,
        top_nexuses=top_nexuses,
    )


@mcp.tool()
async def validate_poem_tags() -> ValidationResult:
    """
    Validate that all poem tags match nexus canonical_tags.

    STRICT VALIDATION: Tags in poems MUST match canonical_tags defined
    in nexuses. This tool identifies violations of the tag policy.

    Tag Policy:
    - Tags represent thematic connections (water, bones, childhood)
    - All tags must match a nexus canonical_tag
    - No free-text tags allowed (use dedicated fields instead)
    - Workflow metadata goes in specific fields (status, draft, etc.)

    Returns:
        ValidationResult with validation status and detailed violations

    Example:
        ```
        result = await validate_poem_tags()

        if not result.valid:
            print(f"❌ Found {result.violations_count} invalid tags")
            for tag in result.invalid_tags:
                print(f"  - '{tag}' (no nexus definition)")

            print(f"\nAffected poems ({len(result.affected_poems)}):")
            for poem in result.affected_poems:
                print(f"  {poem['title']}: {poem['invalid_tags']}")
        else:
            print("✅ All tags valid!")
        ```

    Note:
        Invalid tags indicate:
        - Typos in manual tagging → Fix the tag
        - Free-text metadata → Move to dedicated field
        - Deleted nexus → Create nexus or remove tag
        - Legacy tags → Clean up or migrate to nexuses

        Use cleanup workflow:
        1. Run validate_poem_tags() to find violations
        2. Fix manually in Obsidian or use frontmatter_writer
        3. Re-sync catalog
        4. Validate again until clean
    """
    cat = get_catalog()
    registry = await get_all_nexuses()

    # Collect all valid canonical tags from nexuses
    valid_tags = set()
    for nexus_list in [registry.themes, registry.motifs, registry.forms]:
        for nexus in nexus_list:
            if nexus.canonical_tag:
                valid_tags.add(nexus.canonical_tag.lower())

    # Validate all tags in poems
    all_tags_checked = set()
    poems_with_invalid = []
    total_poems_checked = 0

    for poem in cat.index.all_poems:
        total_poems_checked += 1
        if poem.tags:
            invalid_tags_in_poem = []
            for tag in poem.tags:
                tag_lower = tag.lower()
                all_tags_checked.add(tag_lower)

                # Check if tag is invalid (doesn't match any nexus)
                if tag_lower not in valid_tags:
                    invalid_tags_in_poem.append(tag)

            # If poem has invalid tags, record it
            if invalid_tags_in_poem:
                poems_with_invalid.append({
                    "id": poem.id,
                    "title": poem.title,
                    "invalid_tags": invalid_tags_in_poem,
                    "file_path": str(poem.file_path),
                })

    # Find all unique invalid tags
    invalid_tags = sorted(all_tags_checked - valid_tags)

    # Determine if validation passed
    is_valid = len(invalid_tags) == 0

    if is_valid:
        logger.info(f"✅ Tag validation passed: {total_poems_checked} poems, {len(all_tags_checked)} tags, all valid")
    else:
        logger.warning(f"❌ Tag validation failed: {len(invalid_tags)} invalid tags across {len(poems_with_invalid)} poems")

    return ValidationResult(
        success=is_valid,
        valid=is_valid,
        invalid_tags=invalid_tags,
        violations_count=len(invalid_tags),
        affected_poems=poems_with_invalid,
        total_poems_checked=total_poems_checked,
        total_tags_checked=len(all_tags_checked),
        valid_tags=sorted(valid_tags),
    )


@mcp.tool()
async def create_nexus(
    name: str,
    category: str,
    canonical_tag: str,
    description: str,
    custom_template: Optional[str] = None,
) -> NexusOperationResult:
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
        NexusOperationResult with success status and created nexus

    Example:
        ```
        # Create a new theme
        result = await create_nexus(
            name="Urban Decay",
            category="theme",
            canonical_tag="urban-decay",
            description="Images of deteriorating cities, abandoned buildings, and industrial ruins"
        )
        print(f"Created: {result.file_path}")

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
        return NexusOperationResult(
            success=False,
            operation="created",
            error=f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        )

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

        return NexusOperationResult(
            success=True,
            nexus=nexus,
            operation="created",
            file_path=nexus.file_path,
        )

    except Exception as e:
        logger.error(f"Failed to create nexus: {e}")
        return NexusOperationResult(
            success=False,
            operation="created",
            error=str(e),
        )


@mcp.tool()
async def delete_nexus(
    name: str,
    category: str,
    cleanup_poems: bool = False,
    force: bool = False,
) -> NexusOperationResult:
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
        NexusOperationResult with deletion status and cleanup details

    Example:
        ```
        # Delete a theme (poems keep the tag)
        result = await delete_nexus(
            name="Urban Decay",
            category="theme"
        )
        print(f"Deleted: {result.file_path}")

        # Delete and clean up all references
        result = await delete_nexus(
            name="Old Theme",
            category="theme",
            cleanup_poems=True
        )
        print(f"Removed tag from {result.poems_cleaned} poems")
        ```

    Warning:
        This operation cannot be undone. The nexus file will be permanently
        deleted from the filesystem.

        If cleanup_poems=False, poems with this tag will keep the tag,
        creating orphaned references (use validate_poem_tags to detect).

        If cleanup_poems=True, the tag will be removed from all poems,
        which may affect your tagging structure.
    """
    # Validate category
    if category not in ["theme", "motif", "form"]:
        return NexusOperationResult(
            success=False,
            operation="deleted",
            error=f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        )

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
            return NexusOperationResult(
                success=False,
                operation="deleted",
                error=f"Nexus '{name}' not found in category '{category}'",
            )

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
        delete_result = manager.delete_nexus(
            name=name,
            category=category,
            force=force,
        )

        logger.info(f"Deleted nexus: {name} ({category})")

        # Refresh nexus registry to remove deleted nexus
        initialize_enrichment_tools(cat)
        logger.info("Nexus registry refreshed")

        return NexusOperationResult(
            success=True,
            operation="deleted",
            file_path=delete_result["deleted"],
            poems_cleaned=poems_cleaned,
        )

    except Exception as e:
        logger.error(f"Failed to delete nexus: {e}")
        return NexusOperationResult(
            success=False,
            operation="deleted",
            error=str(e),
        )


# =============================================================================
# CHAIN TOOLS - For linking poems into sequences or collections
# =============================================================================


@mcp.tool()
async def create_chain(
    chain_id: str,
    poem_ids: list[str],
    ordered: bool = False,
) -> dict:
    """
    Create a new chain with initial poems.

    Chains allow grouping poems into ordered sequences (for reading in order)
    or loose collections (thematic groupings). All chain data is stored in
    poem frontmatter.

    Args:
        chain_id: Unique identifier for the chain (will be normalized to lowercase-with-hyphens)
        poem_ids: List of poem IDs to include. Order matters if ordered=True.
        ordered: If True, assign positions (1, 2, 3...) to poems for reading order

    Returns:
        Dictionary with operation details including success status and positions

    Example:
        Create an ordered reading sequence:
        ```
        result = await create_chain(
            chain_id="water-sequence",
            poem_ids=["antlion", "second-bridge", "river-poem"],
            ordered=True
        )
        print(f"Created chain with {len(result['poems_affected'])} poems")
        print(f"Positions: {result['positions']}")
        ```

        Create a loose thematic collection:
        ```
        result = await create_chain(
            chain_id="grief-poems",
            poem_ids=["elegy", "absence", "memorial"],
            ordered=False
        )
        ```
    """
    return await _create_chain(chain_id, poem_ids, ordered)


@mcp.tool()
async def add_poems_to_chain(
    chain_id: str,
    poem_ids: list[str],
    positions: Optional[List[int]] = None,
) -> dict:
    """
    Add poems to an existing chain.

    Args:
        chain_id: Chain to add poems to
        poem_ids: Poems to add
        positions: Optional positions for ordered chains. Must match length of poem_ids.
                  If not provided, poems are added without positions (loose collection style).

    Returns:
        Dictionary with operation details

    Example:
        Add with specific positions:
        ```
        result = await add_poems_to_chain(
            chain_id="water-sequence",
            poem_ids=["new-poem"],
            positions=[4]  # Add as 4th in sequence
        )
        ```

        Add to loose collection:
        ```
        result = await add_poems_to_chain(
            chain_id="grief-poems",
            poem_ids=["new-elegy", "another-loss"]
        )
        ```
    """
    return await _add_poems_to_chain(chain_id, poem_ids, positions)


@mcp.tool()
async def remove_poems_from_chain(
    chain_id: str,
    poem_ids: list[str],
    compact_positions: bool = True,
) -> dict:
    """
    Remove poems from a chain.

    Args:
        chain_id: Chain to remove poems from
        poem_ids: Poems to remove
        compact_positions: If True (default), renumber remaining poems to close gaps
                          in ordered chains. E.g., [1,2,4,5] becomes [1,2,3,4]

    Returns:
        Dictionary with operation details and updated positions

    Example:
        ```
        result = await remove_poems_from_chain(
            chain_id="water-sequence",
            poem_ids=["river-poem"],
            compact_positions=True
        )
        print(f"Remaining positions: {result['positions']}")
        ```
    """
    return await _remove_poems_from_chain(chain_id, poem_ids, compact_positions)


@mcp.tool()
async def reorder_chain(
    chain_id: str,
    poem_order: list[str],
) -> dict:
    """
    Reorder poems in a chain.

    Sets new positions for all poems in the chain. Useful for rearranging
    a reading sequence.

    Args:
        chain_id: Chain to reorder
        poem_order: New order of poem IDs. Must include ALL poems currently in chain.

    Returns:
        Dictionary with new positions

    Example:
        ```
        # Move "river-poem" to the front
        result = await reorder_chain(
            chain_id="water-sequence",
            poem_order=["river-poem", "antlion", "second-bridge"]
        )
        print(f"New order: {result['positions']}")
        # Output: {'river-poem': 1, 'antlion': 2, 'second-bridge': 3}
        ```
    """
    return await _reorder_chain(chain_id, poem_order)


@mcp.tool()
async def delete_chain(chain_id: str) -> dict:
    """
    Delete a chain entirely, removing it from all poems.

    This removes the chain membership and any positions from all poems in the chain.
    Poems themselves are not deleted.

    Args:
        chain_id: Chain to delete

    Returns:
        Dictionary with list of affected poems

    Example:
        ```
        result = await delete_chain("old-sequence")
        print(f"Removed chain from {len(result['poems_affected'])} poems")
        ```
    """
    return await _delete_chain(chain_id)


@mcp.tool()
async def get_chain(
    chain_id: str,
    include_content: bool = False,
) -> dict:
    """
    Get information about a chain and its poems.

    Returns poems in order (by position for ordered chains, then alphabetically
    for loose members).

    Args:
        chain_id: Chain to retrieve
        include_content: If True, include full poem text in results

    Returns:
        Dictionary with chain info and poem list

    Example:
        ```
        result = await get_chain("water-sequence")
        print(f"Chain has {result['poem_count']} poems")
        print(f"Is ordered: {result['is_ordered']}")
        for poem in result['poems']:
            print(f"  {poem.get('position', '-')}. {poem['title']}")
        ```
    """
    return await _get_chain(chain_id, include_content)


@mcp.tool()
async def list_chains() -> dict:
    """
    List all chains with basic stats.

    Returns:
        Dictionary with list of chains, each containing:
        - chain_id: Identifier
        - poem_count: Number of poems in chain
        - is_ordered: Whether any poems have positions

    Example:
        ```
        result = await list_chains()
        print(f"Total chains: {result['total_chains']}")
        for chain in result['chains']:
            order_type = "ordered" if chain['is_ordered'] else "loose"
            print(f"  {chain['chain_id']}: {chain['poem_count']} poems ({order_type})")
        ```
    """
    return await _list_chains()


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

    # Initialize chain tools
    logger.info("Initializing chain tools...")
    try:
        initialize_chain_tools(cat)
        logger.info("Chain tools initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize chain tools: {e}")

    # Auto-validate tags on startup if enabled
    try:
        from .config import get_config
        cfg = get_config()
        if cfg.validation.auto_validate_on_sync:
            logger.info("Running tag validation on startup...")
            validation_result = asyncio.run(validate_poem_tags())

            if validation_result['valid']:
                logger.info("✅ Tag validation passed - all tags match nexus definitions")
            else:
                logger.warning(
                    f"⚠️  Found {validation_result['violations_count']} invalid tags "
                    f"across {len(validation_result['affected_poems'])} poems"
                )
                logger.warning(f"Invalid tags: {', '.join(validation_result['invalid_tags'][:5])}")
                if len(validation_result['invalid_tags']) > 5:
                    logger.warning(f"... and {len(validation_result['invalid_tags']) - 5} more")
    except Exception as e:
        logger.error(f"Tag validation failed: {e}")
        # Continue anyway - validation failure shouldn't prevent server startup

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()
