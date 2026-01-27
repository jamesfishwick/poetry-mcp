"""Chain tools for linking poems into sequences or collections.

Provides operations for managing poem chains - ordered sequences or loose
collections of related poems.
"""

import logging
from typing import Any, Optional

from ..catalog.catalog import Catalog
from ..writers.frontmatter_writer import update_poem_chains

logger = logging.getLogger(__name__)

# Module-level catalog reference (initialized by server)
_catalog: Optional[Catalog] = None


def initialize_chain_tools(catalog: Catalog) -> None:
    """Initialize chain tools with catalog reference.

    Must be called before using any chain tools.

    Args:
        catalog: Initialized Catalog instance
    """
    global _catalog
    _catalog = catalog
    logger.info("Chain tools initialized")


def _get_catalog() -> Catalog:
    """Get catalog, raising if not initialized."""
    if _catalog is None:
        raise RuntimeError(
            "Chain tools not initialized. Call initialize_chain_tools() first."
        )
    return _catalog


async def create_chain(
    chain_id: str,
    poem_ids: list[str],
    ordered: bool = False,
) -> dict[str, Any]:
    """Create a new chain with initial poems.

    Args:
        chain_id: Unique identifier for the chain (will be normalized)
        poem_ids: List of poem IDs to include (order matters if ordered=True)
        ordered: If True, assign positions (1, 2, 3...) to poems

    Returns:
        Dictionary with operation details:
        - success: Whether operation succeeded
        - chain_id: Normalized chain identifier
        - poems_affected: List of poem IDs added to chain
        - positions: Position assignments (if ordered)
        - error: Error message if failed

    Example:
        >>> result = await create_chain(
        ...     chain_id="water-sequence",
        ...     poem_ids=["antlion", "second-bridge", "river-poem"],
        ...     ordered=True
        ... )
        >>> result['success']
        True
        >>> result['positions']
        {'antlion': 1, 'second-bridge': 2, 'river-poem': 3}
    """
    cat = _get_catalog()

    # Normalize chain ID
    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Validate all poems exist
    poems = []
    for pid in poem_ids:
        poem = cat.index.get_by_id_or_title(pid)
        if poem is None:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"Poem not found: {pid}",
            }
        poems.append(poem)

    # Check if any poems are already in this chain
    existing = [p for p in poems if normalized_chain in p.chains]
    if existing:
        return {
            "success": False,
            "chain_id": normalized_chain,
            "error": f"Poems already in chain: {[p.id for p in existing]}",
        }

    # Build position updates if ordered
    position_updates: Optional[dict[str, Optional[int]]] = None
    if ordered:
        position_updates = {
            poems[i].id: i + 1 for i in range(len(poems))
        }

    # Update each poem
    backup_paths = []
    poems_affected = []

    for i, poem in enumerate(poems):
        poem_path = cat.vault_root / poem.file_path
        pos_update = {normalized_chain: i + 1} if ordered else None

        result = update_poem_chains(
            poem_path,
            chains_to_add=[normalized_chain],
            position_updates=pos_update,
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "poems_affected": poems_affected,
                "error": f"Failed to update {poem.id}: {result.error}",
            }

        poems_affected.append(poem.id)
        if result.backup_path:
            backup_paths.append(result.backup_path)

    # Resync catalog
    cat.sync(force_rescan=True)

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poems_affected": poems_affected,
        "positions": {poems[i].id: i + 1 for i in range(len(poems))} if ordered else None,
        "backup_paths": backup_paths,
    }


async def add_poems_to_chain(
    chain_id: str,
    poem_ids: list[str],
    positions: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Add poems to an existing chain.

    Args:
        chain_id: Chain to add poems to
        poem_ids: Poems to add
        positions: Optional positions for ordered chains. If provided, must match
                  length of poem_ids. Existing poems will be shifted if needed.

    Returns:
        Dictionary with operation details

    Notes:
        - If chain doesn't exist yet, creates it
        - If positions provided, assigns those positions
        - If no positions, adds as loose collection members
    """
    cat = _get_catalog()

    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Validate all poems exist
    poems = []
    for pid in poem_ids:
        poem = cat.index.get_by_id_or_title(pid)
        if poem is None:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"Poem not found: {pid}",
            }
        # Check if already in chain
        if normalized_chain in poem.chains:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"Poem already in chain: {pid}",
            }
        poems.append(poem)

    # Validate positions if provided
    if positions is not None:
        if len(positions) != len(poem_ids):
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"positions length ({len(positions)}) must match poem_ids length ({len(poem_ids)})",
            }
        for pos in positions:
            if pos < 1:
                return {
                    "success": False,
                    "chain_id": normalized_chain,
                    "error": f"Positions must be positive integers, got: {pos}",
                }

    # Update each poem
    backup_paths = []
    poems_affected = []

    for i, poem in enumerate(poems):
        poem_path = cat.vault_root / poem.file_path
        pos_update = {normalized_chain: positions[i]} if positions else None

        result = update_poem_chains(
            poem_path,
            chains_to_add=[normalized_chain],
            position_updates=pos_update,
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "poems_affected": poems_affected,
                "error": f"Failed to update {poem.id}: {result.error}",
            }

        poems_affected.append(poem.id)
        if result.backup_path:
            backup_paths.append(result.backup_path)

    # Resync catalog
    cat.sync(force_rescan=True)

    # Get updated positions
    final_positions = {}
    for poem_id in poems_affected:
        poem = cat.index.get_by_id(poem_id)
        if poem and poem.chain_positions and normalized_chain in poem.chain_positions:
            final_positions[poem_id] = poem.chain_positions[normalized_chain]

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poems_affected": poems_affected,
        "positions": final_positions if final_positions else None,
        "backup_paths": backup_paths,
    }


async def remove_poems_from_chain(
    chain_id: str,
    poem_ids: list[str],
    compact_positions: bool = True,
) -> dict[str, Any]:
    """Remove poems from a chain.

    Args:
        chain_id: Chain to remove poems from
        poem_ids: Poems to remove
        compact_positions: If True, renumber remaining poems to close gaps

    Returns:
        Dictionary with operation details
    """
    cat = _get_catalog()

    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Validate all poems exist and are in chain
    poems = []
    for pid in poem_ids:
        poem = cat.index.get_by_id_or_title(pid)
        if poem is None:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"Poem not found: {pid}",
            }
        if normalized_chain not in poem.chains:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "error": f"Poem not in chain: {pid}",
            }
        poems.append(poem)

    # Remove poems from chain
    backup_paths = []
    poems_affected = []

    for poem in poems:
        poem_path = cat.vault_root / poem.file_path

        result = update_poem_chains(
            poem_path,
            chains_to_remove=[normalized_chain],
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "poems_affected": poems_affected,
                "error": f"Failed to update {poem.id}: {result.error}",
            }

        poems_affected.append(poem.id)
        if result.backup_path:
            backup_paths.append(result.backup_path)

    # Resync catalog
    cat.sync(force_rescan=True)

    # Compact positions if requested
    final_positions = None
    if compact_positions:
        # Get remaining poems in chain, sorted by position
        remaining = cat.index.get_by_chain(normalized_chain, ordered=True)
        if remaining:
            # Renumber positions
            for i, poem in enumerate(remaining):
                if poem.chain_positions and normalized_chain in poem.chain_positions:
                    current_pos = poem.chain_positions[normalized_chain]
                    new_pos = i + 1
                    if current_pos != new_pos:
                        poem_path = cat.vault_root / poem.file_path
                        update_poem_chains(
                            poem_path,
                            position_updates={normalized_chain: new_pos},
                            create_backup_file=False,
                        )

            # Resync again after compaction
            cat.sync(force_rescan=True)

            # Get final positions
            final_positions = {}
            for poem in cat.index.get_by_chain(normalized_chain, ordered=True):
                if poem.chain_positions and normalized_chain in poem.chain_positions:
                    final_positions[poem.id] = poem.chain_positions[normalized_chain]

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poems_affected": poems_affected,
        "positions": final_positions,
        "backup_paths": backup_paths,
    }


async def reorder_chain(
    chain_id: str,
    poem_order: list[str],
) -> dict[str, Any]:
    """Reorder poems in a chain.

    Args:
        chain_id: Chain to reorder
        poem_order: New order of poem IDs (must include all poems currently in chain)

    Returns:
        Dictionary with operation details and new positions
    """
    cat = _get_catalog()

    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Get current poems in chain
    current_poems = cat.index.get_by_chain(normalized_chain, ordered=False)
    current_ids = {p.id for p in current_poems}
    order_ids = set(poem_order)

    # Validate poem_order contains exactly the same poems
    if current_ids != order_ids:
        missing = current_ids - order_ids
        extra = order_ids - current_ids
        errors = []
        if missing:
            errors.append(f"Missing poems: {list(missing)}")
        if extra:
            errors.append(f"Unknown poems: {list(extra)}")
        return {
            "success": False,
            "chain_id": normalized_chain,
            "error": "; ".join(errors),
        }

    # Update positions
    backup_paths = []
    poems_affected = []

    for i, poem_id in enumerate(poem_order):
        poem = cat.index.get_by_id(poem_id)
        if poem is None:
            continue

        poem_path = cat.vault_root / poem.file_path
        result = update_poem_chains(
            poem_path,
            position_updates={normalized_chain: i + 1},
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "poems_affected": poems_affected,
                "error": f"Failed to update {poem_id}: {result.error}",
            }

        poems_affected.append(poem_id)
        if result.backup_path:
            backup_paths.append(result.backup_path)

    # Resync catalog
    cat.sync(force_rescan=True)

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poems_affected": poems_affected,
        "positions": {poem_order[i]: i + 1 for i in range(len(poem_order))},
        "backup_paths": backup_paths,
    }


async def delete_chain(chain_id: str) -> dict[str, Any]:
    """Delete a chain entirely, removing it from all poems.

    Args:
        chain_id: Chain to delete

    Returns:
        Dictionary with list of affected poems
    """
    cat = _get_catalog()

    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Get all poems in chain
    poems = cat.index.get_by_chain(normalized_chain, ordered=False)

    if not poems:
        return {
            "success": False,
            "chain_id": normalized_chain,
            "error": f"Chain not found or empty: {normalized_chain}",
        }

    # Remove chain from all poems
    backup_paths = []
    poems_affected = []

    for poem in poems:
        poem_path = cat.vault_root / poem.file_path

        result = update_poem_chains(
            poem_path,
            chains_to_remove=[normalized_chain],
            create_backup_file=True,
        )

        if not result.success:
            return {
                "success": False,
                "chain_id": normalized_chain,
                "poems_affected": poems_affected,
                "error": f"Failed to update {poem.id}: {result.error}",
            }

        poems_affected.append(poem.id)
        if result.backup_path:
            backup_paths.append(result.backup_path)

    # Resync catalog
    cat.sync(force_rescan=True)

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poems_affected": poems_affected,
        "backup_paths": backup_paths,
    }


async def get_chain(
    chain_id: str,
    include_content: bool = False,
) -> dict[str, Any]:
    """Get information about a chain and its poems.

    Args:
        chain_id: Chain to retrieve
        include_content: Include full poem text

    Returns:
        Dictionary with chain info and poems
    """
    cat = _get_catalog()

    normalized_chain = chain_id.lower().strip().replace(" ", "-")

    # Get poems in chain (ordered)
    poems = cat.index.get_by_chain(normalized_chain, ordered=True)

    if not poems:
        return {
            "success": False,
            "chain_id": normalized_chain,
            "error": f"Chain not found or empty: {normalized_chain}",
        }

    # Check if any poems have positions (ordered chain)
    is_ordered = any(
        p.chain_positions and normalized_chain in p.chain_positions
        for p in poems
    )

    # Build poem list
    poem_list = []
    for poem in poems:
        poem_info = {
            "id": poem.id,
            "title": poem.title,
            "state": poem.state,
            "form": poem.form,
        }
        if poem.chain_positions and normalized_chain in poem.chain_positions:
            poem_info["position"] = poem.chain_positions[normalized_chain]
        if include_content and poem.content:
            poem_info["content"] = poem.content
        poem_list.append(poem_info)

    return {
        "success": True,
        "chain_id": normalized_chain,
        "poem_count": len(poems),
        "is_ordered": is_ordered,
        "poems": poem_list,
    }


async def list_chains() -> dict[str, Any]:
    """List all chains with basic stats.

    Returns:
        Dictionary with chain_id -> poem_count mapping
    """
    cat = _get_catalog()

    chains_data = cat.index.get_all_chains()

    # Build detailed chain info
    chain_list = []
    for chain_id, poem_count in sorted(chains_data.items()):
        poems = cat.index.get_by_chain(chain_id, ordered=False)
        is_ordered = any(
            p.chain_positions and chain_id in p.chain_positions
            for p in poems
        )
        chain_list.append({
            "chain_id": chain_id,
            "poem_count": poem_count,
            "is_ordered": is_ordered,
        })

    return {
        "success": True,
        "chains": chain_list,
        "total_chains": len(chain_list),
    }
