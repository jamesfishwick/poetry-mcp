"""MCP tools for enriching poetry catalog with connections and metadata."""

from pathlib import Path
from typing import Optional, List
import logging

from ..models.nexus import NexusRegistry
from ..models.results import SyncResult
from ..models.enrichment import ThemeDetectionResult, ThemeSuggestion
from ..parsers.nexus_parser import load_nexus_registry
from ..writers.frontmatter_writer import (
    update_poem_tags,
    FrontmatterUpdateResult,
)
from ..catalog.catalog import Catalog
from ..config import load_config
logger = logging.getLogger(__name__)

# Global state (will be initialized by server)
_catalog: Optional[Catalog] = None
_nexus_registry: Optional[NexusRegistry] = None


def initialize_enrichment_tools(catalog: Catalog) -> None:
    """Initialize global state for enrichment tools.

    Args:
        catalog: Catalog instance to use for lookups
    """
    global _catalog, _nexus_registry
    _catalog = catalog

    # Load nexus registry on initialization
    config = load_config()
    _nexus_registry = load_nexus_registry(config.vault.path)


async def get_all_nexuses() -> NexusRegistry:
    """Get all nexuses (themes/motifs/forms) from the registry.

    Returns complete registry with all nexus entries, organized by category.
    Use this to discover available themes, motifs, and forms for tagging poems.

    Returns:
        NexusRegistry with themes, motifs, and forms

    Example:
        >>> registry = await get_all_nexuses()
        >>> registry.total_count
        25
        >>> [t.name for t in registry.themes[:3]]
        ['Water-Liquid', 'Body-Bones', 'Childhood']
        >>> registry.themes[0].canonical_tag
        'water-liquid'
    """
    if _nexus_registry is None:
        raise RuntimeError("Enrichment tools not initialized. Call initialize_enrichment_tools() first.")

    return _nexus_registry


async def link_poem_to_nexus(
    poem_id: str,
    nexus_name: str,
    nexus_type: str = "theme",
) -> dict[str, any]:
    """Link a poem to a nexus by adding the nexus's canonical tag to the poem's frontmatter.

    Safely updates the poem's tags field in frontmatter, preserving all other fields.
    Creates a backup before modification. Automatically resyncs catalog after update.

    Args:
        poem_id: Poem identifier (ID or title)
        nexus_name: Name of nexus to link (e.g., "Water-Liquid", "Childhood")
        nexus_type: Type of nexus (theme/motif/form), defaults to "theme"

    Returns:
        Dictionary with operation details:
        - success: Whether operation succeeded
        - poem_title: Title of updated poem
        - tag_added: Canonical tag that was added
        - backup_path: Path to backup file
        - error: Error message if failed

    Example:
        >>> result = await link_poem_to_nexus(
        ...     poem_id="antlion",
        ...     nexus_name="Water-Liquid",
        ...     nexus_type="theme"
        ... )
        >>> result['success']
        True
        >>> result['tag_added']
        'water-liquid'
    """
    if _catalog is None or _nexus_registry is None:
        raise RuntimeError("Enrichment tools not initialized. Call initialize_enrichment_tools() first.")

    # Find the poem
    poem = _catalog.index.get_poem(poem_id)
    if poem is None:
        return {
            "success": False,
            "error": f"Poem not found: {poem_id}",
        }

    # Find the nexus
    nexus_lists = {
        "theme": _nexus_registry.themes,
        "motif": _nexus_registry.motifs,
        "form": _nexus_registry.forms,
    }

    nexus_list = nexus_lists.get(nexus_type)
    if nexus_list is None:
        return {
            "success": False,
            "error": f"Invalid nexus type: {nexus_type}. Must be theme/motif/form.",
        }

    # Find nexus by name (case-insensitive partial match)
    nexus = None
    nexus_name_lower = nexus_name.lower()
    for n in nexus_list:
        if nexus_name_lower in n.name.lower():
            nexus = n
            break

    if nexus is None:
        return {
            "success": False,
            "error": f"Nexus not found: {nexus_name} (type: {nexus_type})",
        }

    if not nexus.canonical_tag:
        return {
            "success": False,
            "error": f"Nexus '{nexus.name}' has no canonical_tag defined",
        }

    # Update poem tags
    poem_path = Path(poem.file_path)
    result = update_poem_tags(
        poem_path,
        tags_to_add=[nexus.canonical_tag],
        create_backup_file=True,
    )

    if not result.success:
        return {
            "success": False,
            "poem_title": poem.title,
            "error": result.error,
        }

    # Resync catalog to pick up changes
    sync_result = _catalog.sync(force_rescan=True)

    return {
        "success": True,
        "poem_title": poem.title,
        "poem_id": poem.id,
        "nexus_name": nexus.name,
        "tag_added": nexus.canonical_tag,
        "backup_path": result.backup_path,
        "catalog_resynced": True,
        "new_poem_count": sync_result.total_poems,
    }


async def find_nexuses_for_poem(
    poem_id: str,
    max_suggestions: int = 5,
) -> dict:
    """Prepare poem and nexus data for theme analysis by the MCP agent.

    Returns poem content and available themes for the agent (Claude) to analyze.
    The agent will identify which themes match and provide confidence scores.

    Args:
        poem_id: Poem identifier (ID or title)
        max_suggestions: Maximum number of theme suggestions to request

    Returns:
        Dictionary with:
        - poem: Poem data (title, content, current_tags)
        - available_themes: List of theme options with descriptions
        - instructions: Analysis prompt for the agent
        - max_suggestions: Requested number of suggestions

    Example:
        >>> result = await find_nexuses_for_poem("antlion", max_suggestions=3)
        >>> # Agent analyzes result['poem'] against result['available_themes']
        >>> # Agent returns theme suggestions with confidence scores
    """
    if _catalog is None or _nexus_registry is None:
        raise RuntimeError("Enrichment tools not initialized.")

    # Find the poem
    poem = _catalog.index.get_poem(poem_id)
    if poem is None:
        return {
            "success": False,
            "error": f"Poem not found: {poem_id}",
        }

    # Load full content if not already loaded
    if not poem.content:
        try:
            poem_path = Path(poem.file_path)
            full_content = poem_path.read_text(encoding='utf-8')
            # Extract just the poem content (after frontmatter)
            if '---' in full_content:
                parts = full_content.split('---', 2)
                if len(parts) >= 3:
                    poem.content = parts[2].strip()
                else:
                    poem.content = full_content
            else:
                poem.content = full_content
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load poem content: {e}",
            }

    # Format available themes with descriptions
    themes_data = []
    for nexus in _nexus_registry.themes:
        # Extract brief description
        desc_lines = nexus.description.split('\n')
        brief_desc = []
        for line in desc_lines:
            if line.strip() and not line.startswith('#'):
                brief_desc.append(line.strip())
                if len(brief_desc) >= 3:
                    break
        brief_text = ' '.join(brief_desc)[:200]

        themes_data.append({
            "name": nexus.name,
            "canonical_tag": nexus.canonical_tag,
            "description": brief_text,
        })

    # Build analysis instructions
    instructions = f"""Analyze this poem and identify which themes it engages with.

For each matching theme, provide:
1. **name**: Theme name (exactly as listed)
2. **canonical_tag**: Tag to use (exactly as listed)
3. **confidence**: Float 0.0-1.0 (how strongly theme appears)
4. **evidence**: Brief quote or description of why this theme is present

Return up to {max_suggestions} themes, sorted by confidence (highest first).
Only suggest themes with clear textual evidence.

Confidence guide:
- 0.8-1.0: Central/dominant theme
- 0.6-0.8: Significant presence
- 0.4-0.6: Present but not dominant
- <0.4: Marginal or absent"""

    logger.info(f"Prepared theme analysis data for '{poem.title}'")

    return {
        "success": True,
        "poem": {
            "id": poem.id,
            "title": poem.title,
            "content": poem.content,
            "current_tags": poem.tags or [],
            "state": poem.state,
        },
        "available_themes": themes_data,
        "instructions": instructions,
        "max_suggestions": max_suggestions,
    }


async def get_poems_for_enrichment(
    poem_ids: Optional[List[str]] = None,
    max_poems: int = 50,
) -> dict:
    """Get list of poems needing theme enrichment for agent analysis.

    Returns poems with minimal or no tags for the agent to analyze and suggest themes.
    The agent can analyze multiple poems and suggest which themes to apply.

    Args:
        poem_ids: List of poem IDs to include (None = all untagged poems)
        max_poems: Maximum poems to return (default 50)

    Returns:
        Dictionary with:
        - poems: List of poem data (id, title, content, current_tags, state)
        - available_themes: Theme options with descriptions
        - total_count: Total poems returned
        - instructions: Guidance for batch analysis

    Example:
        >>> result = await get_poems_for_enrichment(max_poems=10)
        >>> # Agent analyzes result['poems'] against result['available_themes']
        >>> # Agent suggests themes for each poem
        >>> # User applies tags with link_poem_to_nexus()
    """
    if _catalog is None or _nexus_registry is None:
        raise RuntimeError("Enrichment tools not initialized.")

    # Determine which poems to return
    if poem_ids is None:
        # Default: all poems with no tags or very few tags
        poems_to_return = [
            poem for poem in _catalog.index.all_poems
            if not poem.tags or len(poem.tags) < 2
        ]
    else:
        # Specific poem IDs
        poems_to_return = []
        for pid in poem_ids:
            poem = _catalog.index.get_poem(pid)
            if poem:
                poems_to_return.append(poem)

    # Limit to max_poems
    poems_to_return = poems_to_return[:max_poems]

    # Format poems data
    poems_data = []
    for poem in poems_to_return:
        # Load content if needed
        content = poem.content
        if not content:
            try:
                poem_path = Path(poem.file_path)
                full_content = poem_path.read_text(encoding='utf-8')
                if '---' in full_content:
                    parts = full_content.split('---', 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                    else:
                        content = full_content
                else:
                    content = full_content
            except Exception:
                content = "[Content unavailable]"

        poems_data.append({
            "id": poem.id,
            "title": poem.title,
            "content": content[:500] + "..." if len(content) > 500 else content,  # Truncate for efficiency
            "current_tags": poem.tags or [],
            "state": poem.state,
        })

    # Format available themes
    themes_data = []
    for nexus in _nexus_registry.themes:
        desc_lines = nexus.description.split('\n')
        brief_desc = []
        for line in desc_lines:
            if line.strip() and not line.startswith('#'):
                brief_desc.append(line.strip())
                if len(brief_desc) >= 2:
                    break
        brief_text = ' '.join(brief_desc)[:150]

        themes_data.append({
            "name": nexus.name,
            "canonical_tag": nexus.canonical_tag,
            "description": brief_text,
        })

    instructions = """Analyze these poems and suggest themes for each.

For each poem, provide 1-3 most relevant themes with:
- **name**: Theme name (exactly as listed)
- **canonical_tag**: Tag to use
- **confidence**: Float 0.0-1.0
- **evidence**: Brief reasoning

After analysis, user can apply tags with link_poem_to_nexus(poem_id, nexus_name, "theme")"""

    logger.info(f"Prepared {len(poems_data)} poems for batch enrichment")

    return {
        "success": True,
        "poems": poems_data,
        "available_themes": themes_data,
        "total_count": len(poems_data),
        "instructions": instructions,
    }


async def sync_nexus_tags(
    poem_id: str,
    direction: str = "both",
) -> dict:
    """Synchronize [[Nexus]] links in poem body with frontmatter tags.

    Reconciles Obsidian wikilinks (`[[Nexus Name]]`) in the poem body with
    the frontmatter tags field. Can sync in either direction or both.

    Args:
        poem_id: Poem identifier (ID or title)
        direction: Sync direction:
            - "links_to_tags": Add tags based on [[Nexus]] links found in body
            - "tags_to_links": Add [[Nexus]] links based on frontmatter tags
            - "both": Bidirectional sync (default)

    Returns:
        Dictionary with:
        - success: Whether sync succeeded
        - poem_title: Title of poem
        - tags_added: Tags added to frontmatter
        - links_found: [[Nexus]] links found in body
        - conflicts: Tags without corresponding nexus or vice versa
        - changes_made: Whether any changes were applied

    Example:
        >>> result = await sync_nexus_tags(
        ...     poem_id="antlion",
        ...     direction="links_to_tags"
        ... )
        >>> result['tags_added']
        ['water-liquid', 'body-bones']
    """
    import re

    if _catalog is None or _nexus_registry is None:
        raise RuntimeError("Enrichment tools not initialized.")

    # Find the poem
    poem = _catalog.index.get_poem(poem_id)
    if poem is None:
        return {
            "success": False,
            "error": f"Poem not found: {poem_id}",
        }

    # Load full content
    poem_path = Path(poem.file_path)
    try:
        full_content = poem_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read poem file: {e}",
        }

    # Extract frontmatter and body
    from ..writers.frontmatter_writer import extract_frontmatter_and_content
    try:
        frontmatter, body = extract_frontmatter_and_content(full_content, poem_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse frontmatter: {e}",
        }

    # Get current tags
    current_tags = set(frontmatter.get('tags', []))

    # Find all [[Nexus Name]] style links in body
    wikilink_pattern = r'\[\[([^\]]+)\]\]'
    wikilinks = set(re.findall(wikilink_pattern, body))

    # Map wikilinks to canonical tags
    links_to_tags = {}
    for link in wikilinks:
        # Try to find matching nexus
        link_lower = link.lower()
        for nexus in (_nexus_registry.themes + _nexus_registry.motifs + _nexus_registry.forms):
            if link_lower in nexus.name.lower():
                links_to_tags[link] = nexus.canonical_tag
                break

    # Map current tags to nexus names
    tags_to_names = {}
    for tag in current_tags:
        for nexus in (_nexus_registry.themes + _nexus_registry.motifs + _nexus_registry.forms):
            if tag == nexus.canonical_tag:
                tags_to_names[tag] = nexus.name
                break

    # Determine what changes to make based on direction
    tags_to_add = []
    conflicts = []
    changes_made = False

    if direction in ["links_to_tags", "both"]:
        # Add tags based on links found
        for link, tag in links_to_tags.items():
            if tag not in current_tags:
                tags_to_add.append(tag)
                changes_made = True

        # Report links that don't match any nexus
        for link in wikilinks:
            if link not in links_to_tags:
                conflicts.append(f"Link [[{link}]] has no matching nexus")

    if direction in ["tags_to_links", "both"]:
        # Check for tags that don't have corresponding links
        for tag, name in tags_to_names.items():
            # Check if link exists in body
            if name not in wikilinks and not any(name.lower() in link.lower() for link in wikilinks):
                conflicts.append(f"Tag #{tag} ({name}) has no corresponding [[link]] in body")

    # Apply tag changes if any
    if tags_to_add:
        from ..writers.frontmatter_writer import update_poem_tags
        result = update_poem_tags(
            poem_path,
            tags_to_add=tags_to_add,
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "error": f"Failed to update tags: {result.error}",
            }

        # Resync catalog
        _catalog.sync(force_rescan=True)

    logger.info(
        f"Synced nexus tags for '{poem.title}': {len(tags_to_add)} tags added, "
        f"{len(conflicts)} conflicts"
    )

    return {
        "success": True,
        "poem_id": poem.id,
        "poem_title": poem.title,
        "direction": direction,
        "tags_added": tags_to_add,
        "links_found": list(wikilinks),
        "canonical_tags_from_links": list(links_to_tags.values()),
        "conflicts": conflicts,
        "changes_made": changes_made,
    }


async def move_poem_to_state(
    poem_id: str,
    new_state: str,
) -> dict:
    """Move a poem to a different state directory and update frontmatter.

    Promotes or demotes a poem by:
    1. Moving the file to the appropriate state directory
    2. Updating the `state` field in frontmatter
    3. Resyncing the catalog

    Args:
        poem_id: Poem identifier (ID or title)
        new_state: Target state (completed/fledgeling/still_cooking/needs_research/risk)

    Returns:
        Dictionary with:
        - success: Whether move succeeded
        - poem_title: Title of poem
        - old_state: Previous state
        - new_state: New state
        - old_path: Previous file path
        - new_path: New file path
        - backup_path: Backup file path

    Example:
        >>> result = await move_poem_to_state(
        ...     poem_id="my-poem",
        ...     new_state="completed"
        ... )
        >>> result['new_path']
        'catalog/Completed/my-poem.md'
    """
    import shutil

    if _catalog is None:
        raise RuntimeError("Enrichment tools not initialized.")

    # Validate new_state
    valid_states = ["completed", "fledgeling", "still_cooking", "needs_research", "risk"]
    if new_state not in valid_states:
        return {
            "success": False,
            "error": f"Invalid state: {new_state}. Must be one of: {', '.join(valid_states)}",
        }

    # Find the poem
    poem = _catalog.index.get_poem(poem_id)
    if poem is None:
        return {
            "success": False,
            "error": f"Poem not found: {poem_id}",
        }

    # Check if already in target state
    if poem.state == new_state:
        return {
            "success": True,
            "poem_title": poem.title,
            "old_state": poem.state,
            "new_state": new_state,
            "message": "Poem already in target state",
            "changes_made": False,
        }

    # Map state names to directory names
    state_to_dir = {
        "completed": "Completed",
        "fledgeling": "Fledgelings",
        "still_cooking": "Still Cooking",
        "needs_research": "Needs Research",
        "risk": "Risks",
    }

    # Get paths
    config = load_config()
    catalog_root = config.vault.path / "catalog"
    old_path = Path(poem.file_path)
    new_dir = catalog_root / state_to_dir[new_state]
    new_path = new_dir / old_path.name

    # Check for file conflicts
    if new_path.exists():
        return {
            "success": False,
            "error": f"File already exists at destination: {new_path}",
        }

    # Create new directory if it doesn't exist
    new_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Update frontmatter first (before moving)
        from ..writers.frontmatter_writer import update_poem_frontmatter
        fm_result = update_poem_frontmatter(
            old_path,
            updates={"state": new_state},
            create_backup_file=True,
        )

        if not fm_result.success:
            return {
                "success": False,
                "error": f"Failed to update frontmatter: {fm_result.error}",
            }

        # Move the file
        shutil.move(str(old_path), str(new_path))

        # Also move backup if it exists
        backup_path = old_path.with_suffix(old_path.suffix + '.bak')
        new_backup_path = new_path.with_suffix(new_path.suffix + '.bak')
        if backup_path.exists():
            shutil.move(str(backup_path), str(new_backup_path))

        logger.info(f"Moved '{poem.title}' from {poem.state} to {new_state}: {new_path}")

        # Resync catalog
        _catalog.sync(force_rescan=True)

        return {
            "success": True,
            "poem_id": poem.id,
            "poem_title": poem.title,
            "old_state": poem.state,
            "new_state": new_state,
            "old_path": str(old_path),
            "new_path": str(new_path),
            "backup_path": str(new_backup_path) if backup_path.exists() else None,
            "changes_made": True,
        }

    except Exception as e:
        logger.error(f"Failed to move poem '{poem.title}': {e}")
        return {
            "success": False,
            "poem_title": poem.title,
            "error": str(e),
        }


async def grade_poem_quality(
    poem_id: str,
    dimensions: Optional[List[str]] = None,
) -> dict:
    """Prepare poem and quality rubric for grading by the MCP agent.

    Returns poem content and quality dimension descriptions for the agent to grade.
    Agent provides scores (0-10) and reasoning for each dimension.

    Quality dimensions:
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
        - poem: Poem data (id, title, content)
        - dimensions: Quality dimensions with descriptions
        - instructions: Grading guidance for agent

    Example:
        >>> result = await grade_poem_quality("antlion")
        >>> # Agent grades result['poem'] on result['dimensions']
        >>> # Agent returns scores 0-10 with reasoning for each
    """
    if _catalog is None:
        raise RuntimeError("Enrichment tools not initialized.")

    # Get poem
    poem = _catalog.index.get_poem(poem_id)
    if not poem:
        return {
            "success": False,
            "error": f"Poem not found: {poem_id}",
        }

    # Load content if needed
    content = poem.content
    if not content:
        try:
            poem_path = Path(poem.file_path)
            full_content = poem_path.read_text(encoding='utf-8')
            if '---' in full_content:
                parts = full_content.split('---', 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
                else:
                    content = full_content
            else:
                content = full_content
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load poem content: {e}",
            }

    # Define all quality dimensions
    all_dimensions = {
        "Detail": "Vividness and specificity of imagery - concrete sensory details vs abstract generalities",
        "Life": "Living, breathing quality - vitality, energy, movement vs static or lifeless",
        "Music": "Sound quality - rhythm, sonic patterns, musicality of language",
        "Mystery": "Ambiguity and layers - capacity to engage reader in meaning-making",
        "Sufficient Thought": "Intellectual depth - insight, wisdom, meaningful observation",
        "Surprise": "Unexpected elements - fresh perspectives, original connections",
        "Syntax": "Sentence structure and line breaks - how grammar serves meaning",
        "Unity": "Coherence and wholeness - integration of parts into cohesive whole",
    }

    # Filter to requested dimensions if specified
    if dimensions:
        dimensions_to_grade = {k: v for k, v in all_dimensions.items() if k in dimensions}
        if not dimensions_to_grade:
            return {
                "success": False,
                "error": f"Invalid dimensions. Valid options: {list(all_dimensions.keys())}",
            }
    else:
        dimensions_to_grade = all_dimensions

    # Format dimensions for agent
    dimensions_data = [
        {"name": name, "description": desc}
        for name, desc in dimensions_to_grade.items()
    ]

    instructions = """Grade this poem on each quality dimension.

For each dimension, provide:
- **dimension**: Dimension name (exactly as listed)
- **score**: Integer 0-10
  - 0-3: Absent or poor
  - 4-6: Adequate, functional
  - 7-8: Strong, effective
  - 9-10: Exceptional, masterful
- **reasoning**: Brief evidence (1-2 sentences, cite specific lines)

Be precise and evidence-based. Reference specific techniques or lines when explaining scores."""

    logger.info(f"Prepared quality grading data for '{poem.title}' ({len(dimensions_to_grade)} dimensions)")

    return {
        "success": True,
        "poem": {
            "id": poem.id,
            "title": poem.title,
            "content": content,
            "state": poem.state,
        },
        "dimensions": dimensions_data,
        "instructions": instructions,
        "dimensions_count": len(dimensions_to_grade),
    }
