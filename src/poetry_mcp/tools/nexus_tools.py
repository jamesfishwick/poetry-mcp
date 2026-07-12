"""Nexus management tool implementations.

Extracted from server.py. The catalog, nexus registry, and nexus manager are
passed in (keyword-only) by the server wrappers; the wrappers resolve them via
get_catalog(), the plain get_all_nexuses impl, and get_nexus_manager().
"""

import logging
from typing import Any

from ..config import load_config
from ..models.results import NexusCountsResult, NexusOperationResult, ValidationResult
from ..parsers.nexus_parser import load_nexus_registry
from ..writers.frontmatter_writer import update_poem_tags
from .enrichment_tools import initialize_enrichment_tools
from .similarity_tools import initialize_similarity_tools

logger = logging.getLogger(__name__)


def _refresh_registry(catalog: Any) -> None:
    """Re-initialize the enrichment/similarity registries after a nexus change."""
    initialize_enrichment_tools(catalog)
    initialize_similarity_tools(catalog, load_nexus_registry(load_config().vault.path))


async def refresh_nexus_poem_counts_impl(*, catalog: Any, registry: Any) -> NexusCountsResult:
    """Count tagged poems per nexus and update the registry."""
    stats = {
        "themes": {"count": 0, "total_poems": 0},
        "motifs": {"count": 0, "total_poems": 0},
        "forms": {"count": 0, "total_poems": 0},
    }

    all_nexuses_with_counts = []

    for category_name, nexus_list in [
        ("themes", registry.themes),
        ("motifs", registry.motifs),
        ("forms", registry.forms),
    ]:
        for nexus in nexus_list:
            poems = catalog.index.get_by_tag(nexus.canonical_tag)
            nexus.poem_count = len(poems)

            stats[category_name]["count"] += 1
            stats[category_name]["total_poems"] += len(poems)

            all_nexuses_with_counts.append(
                {
                    "name": nexus.name,
                    "category": nexus.category,
                    "canonical_tag": nexus.canonical_tag,
                    "poem_count": nexus.poem_count,
                }
            )

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


async def validate_poem_tags_impl(*, catalog: Any, registry: Any) -> ValidationResult:
    """Validate that all poem tags match a nexus canonical_tag."""
    valid_tags = set()
    for nexus_list in [registry.themes, registry.motifs, registry.forms]:
        for nexus in nexus_list:
            if nexus.canonical_tag:
                valid_tags.add(nexus.canonical_tag.lower())

    all_tags_checked = set()
    poems_with_invalid = []
    total_poems_checked = 0

    for poem in catalog.index.all_poems:
        total_poems_checked += 1
        if poem.tags:
            invalid_tags_in_poem = []
            for tag in poem.tags:
                tag_lower = tag.lower()
                all_tags_checked.add(tag_lower)
                if tag_lower not in valid_tags:
                    invalid_tags_in_poem.append(tag)

            if invalid_tags_in_poem:
                poems_with_invalid.append(
                    {
                        "id": poem.id,
                        "title": poem.title,
                        "invalid_tags": invalid_tags_in_poem,
                        "file_path": str(poem.file_path),
                    }
                )

    invalid_tags = sorted(all_tags_checked - valid_tags)
    is_valid = len(invalid_tags) == 0

    if is_valid:
        logger.info(
            f"✅ Tag validation passed: {total_poems_checked} poems, "
            f"{len(all_tags_checked)} tags, all valid"
        )
    else:
        logger.warning(
            f"❌ Tag validation failed: {len(invalid_tags)} invalid tags "
            f"across {len(poems_with_invalid)} poems"
        )

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


async def create_nexus_impl(
    name: str,
    category: str,
    canonical_tag: str,
    description: str,
    custom_template: str | None = None,
    *,
    catalog: Any,
    nexus_manager: Any,
) -> NexusOperationResult:
    """Create a new nexus file and refresh the registry."""
    if category not in ["theme", "motif", "form"]:
        return NexusOperationResult(
            success=False,
            operation="created",
            error=f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        )

    try:
        nexus = nexus_manager.create_nexus(
            name=name,
            category=category,
            canonical_tag=canonical_tag,
            description=description,
            custom_template=custom_template,
        )

        logger.info(f"Created nexus: {nexus.name} ({category})")
        _refresh_registry(catalog)
        logger.info("Nexus registry refreshed")

        return NexusOperationResult(
            success=True,
            nexus=nexus,
            operation="created",
            file_path=nexus.file_path,
        )

    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to create nexus: {e}")
        return NexusOperationResult(
            success=False,
            operation="created",
            error=str(e),
        )


async def delete_nexus_impl(
    name: str,
    category: str,
    cleanup_poems: bool = False,
    force: bool = False,
    *,
    catalog: Any,
    registry: Any,
    nexus_manager: Any,
) -> NexusOperationResult:
    """Delete a nexus, optionally cleaning its tag off poems. See server wrapper."""
    if category not in ["theme", "motif", "form"]:
        return NexusOperationResult(
            success=False,
            operation="deleted",
            error=f"Invalid category '{category}'. Must be 'theme', 'motif', or 'form'",
        )

    try:
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
        cleanup_errors: list[str] = []

        if cleanup_poems and nexus.canonical_tag:
            poems_with_tag = catalog.index.get_by_tag(nexus.canonical_tag)
            logger.info(f"Cleaning up {len(poems_with_tag)} poems with tag '{nexus.canonical_tag}'")

            for poem in poems_with_tag:
                try:
                    result = update_poem_tags(
                        catalog.vault_root / poem.file_path,
                        tags_to_remove=[nexus.canonical_tag],
                        create_backup_file=True,
                    )
                    if result.success:
                        poems_cleaned += 1
                    else:
                        msg = f"Failed to remove tag from {poem.title}: {result.error}"
                        logger.warning(msg)
                        cleanup_errors.append(msg)
                except OSError as e:
                    msg = f"Failed to remove tag from {poem.title}: {e}"
                    logger.warning(msg)
                    cleanup_errors.append(msg)

            catalog.sync(force_rescan=True)
            logger.info(f"Catalog resynced: {poems_cleaned} cleaned, {len(cleanup_errors)} failed")

        delete_result = nexus_manager.delete_nexus(
            name=name,
            category=category,
            force=force,
        )

        logger.info(f"Deleted nexus: {name} ({category})")
        _refresh_registry(catalog)
        logger.info("Nexus registry refreshed")

        return NexusOperationResult(
            success=True,
            operation="deleted",
            file_path=delete_result["deleted"],
            poems_cleaned=poems_cleaned,
            poems_failed=len(cleanup_errors),
            cleanup_errors=cleanup_errors,
        )

    except (OSError, KeyError, RuntimeError) as e:
        logger.error(f"Failed to delete nexus: {e}")
        return NexusOperationResult(
            success=False,
            operation="deleted",
            error=str(e),
        )
