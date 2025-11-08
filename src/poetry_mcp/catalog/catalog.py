"""Catalog management and indexing.

Scans markdown files in catalog/ directory and builds in-memory indices
for fast querying. This is the core data structure for the MCP server.
"""

import time
import logging
from pathlib import Path
from typing import Optional
from collections import defaultdict

from ..models.poem import Poem
from ..models.results import SyncResult, CatalogStats
from ..parsers.frontmatter_parser import parse_poem_file, FrontmatterParseError


logger = logging.getLogger(__name__)


class CatalogIndex:
    """
    In-memory index structure for fast poem lookups.

    Maintains multiple indices for different query patterns:
    - by_id: O(1) lookup by poem ID
    - by_title: O(1) lookup by exact title
    - by_state: O(1) lookup of all poems in a state
    - by_form: O(1) lookup of all poems in a form
    - by_tag: O(1) lookup of all poems with a tag
    """

    def __init__(self) -> None:
        """Initialize empty indices."""
        # Primary indices
        self.by_id: dict[str, Poem] = {}
        self.by_title: dict[str, Poem] = {}

        # Secondary indices (grouping)
        self.by_state: dict[str, list[Poem]] = defaultdict(list)
        self.by_form: dict[str, list[Poem]] = defaultdict(list)

        # Tag index (poem_id -> tags, tag -> poem_ids)
        self.by_tag: dict[str, set[str]] = defaultdict(set)  # tag -> poem IDs

        # All poems list (for iteration)
        self.all_poems: list[Poem] = []

    def add_poem(self, poem: Poem) -> None:
        """
        Add a poem to all indices.

        Args:
            poem: Poem to index
        """
        # Primary indices
        self.by_id[poem.id] = poem
        self.by_title[poem.title.lower()] = poem

        # Secondary indices
        self.by_state[poem.state].append(poem)
        self.by_form[poem.form].append(poem)

        # Tag index
        for tag in poem.tags:
            self.by_tag[tag.lower()].add(poem.id)

        # All poems
        self.all_poems.append(poem)

    def get_by_id(self, poem_id: str) -> Optional[Poem]:
        """Get poem by ID (O(1) lookup)."""
        return self.by_id.get(poem_id)

    def get_poem(self, poem_id: str) -> Optional[Poem]:
        """Alias for get_by_id for compatibility with enrichment tools."""
        return self.get_by_id(poem_id)

    def get_by_id_or_title(self, identifier: str) -> Optional[Poem]:
        """Get poem by ID or title (fallback lookup).

        Args:
            identifier: Poem ID or exact title

        Returns:
            Poem if found by ID or title, None otherwise
        """
        # Try by ID first
        poem = self.get_by_id(identifier)
        # Fallback to title search
        if not poem:
            poem = self.get_by_title(identifier)
        return poem

    def get_by_title(self, title: str) -> Optional[Poem]:
        """Get poem by exact title (case-insensitive, O(1) lookup)."""
        return self.by_title.get(title.lower())

    def get_by_state(self, state: str) -> list[Poem]:
        """Get all poems in a state."""
        return self.by_state.get(state, [])

    def get_by_form(self, form: str) -> list[Poem]:
        """Get all poems in a form."""
        return self.by_form.get(form, [])

    def get_by_tag(self, tag: str) -> list[Poem]:
        """Get all poems with a specific tag."""
        poem_ids = self.by_tag.get(tag.lower(), set())
        return [self.by_id[pid] for pid in poem_ids if pid in self.by_id]

    def get_by_tags(self, tags: list[str], match_mode: str = "all") -> list[Poem]:
        """
        Get poems matching tag criteria.

        Args:
            tags: List of tags to match
            match_mode: "all" (AND) or "any" (OR)

        Returns:
            List of matching poems
        """
        if not tags:
            return []

        tag_sets = [self.by_tag.get(tag.lower(), set()) for tag in tags]

        if match_mode == "all":
            # Intersection: poems must have all tags
            matching_ids = set.intersection(*tag_sets) if tag_sets else set()
        else:  # "any"
            # Union: poems must have at least one tag
            matching_ids = set.union(*tag_sets) if tag_sets else set()

        return [self.by_id[pid] for pid in matching_ids if pid in self.by_id]

    def search_content(self, query: str, case_sensitive: bool = False) -> list[Poem]:
        """
        Search poem content for query string.

        Args:
            query: Text to search for
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of poems containing query
        """
        if not query:
            return []

        if not case_sensitive:
            query = query.lower()

        results = []
        for poem in self.all_poems:
            # Search in title, content, notes
            search_text = f"{poem.title} {poem.content or ''} {poem.notes or ''}"
            if not case_sensitive:
                search_text = search_text.lower()

            if query in search_text:
                results.append(poem)

        return results

    def get_stats(self) -> dict:
        """Get catalog statistics."""
        total_poems = len(self.all_poems)

        # Count by state
        by_state = {state: len(poems) for state, poems in self.by_state.items()}

        # Count by form
        by_form = {form: len(poems) for form, poems in self.by_form.items()}

        # Count poems without tags
        poems_without_tags = sum(1 for p in self.all_poems if not p.tags)

        # Total word count
        total_word_count = sum(p.word_count for p in self.all_poems)
        avg_word_count = total_word_count / total_poems if total_poems > 0 else 0

        # Newest and oldest poems
        if self.all_poems:
            sorted_by_created = sorted(self.all_poems, key=lambda p: p.created_at)
            oldest_poem = sorted_by_created[0].title
            newest_poem = sorted_by_created[-1].title
        else:
            oldest_poem = ""
            newest_poem = ""

        return {
            "total_poems": total_poems,
            "by_state": by_state,
            "by_form": by_form,
            "poems_without_tags": poems_without_tags,
            "total_word_count": total_word_count,
            "avg_word_count": avg_word_count,
            "oldest_poem": oldest_poem,
            "newest_poem": newest_poem,
        }

    def clear(self) -> None:
        """Clear all indices."""
        self.by_id.clear()
        self.by_title.clear()
        self.by_state.clear()
        self.by_form.clear()
        self.by_tag.clear()
        self.all_poems.clear()


class Catalog:
    """
    Catalog manager for poem collection.

    Handles scanning filesystem, parsing poems, and maintaining indices.
    """

    def __init__(
        self,
        vault_root: Path,
        exclude_dirs: Optional[list[str]] = None,
        custom_states: Optional[list[str]] = None,
    ):
        """
        Initialize catalog with vault root.

        Args:
            vault_root: Absolute path to Poetry vault root
            exclude_dirs: Optional list of catalog subdirectories to exclude from scanning
            custom_states: Optional list of custom states to accept (beyond standard states)
        """
        self.vault_root = Path(vault_root)
        self.catalog_dir = self.vault_root / "catalog"
        self.exclude_dirs = exclude_dirs or []
        self.index = CatalogIndex()
        self.last_sync: Optional[str] = None

        # Set custom states on Poem model for validation
        if custom_states:
            from ..models.poem import Poem

            Poem.set_custom_states(custom_states)

    def sync(self, force_rescan: bool = False, update_missing_metadata: bool = True) -> SyncResult:
        """
        Sync catalog from filesystem.

        Scans catalog/ directory recursively for .md files and builds indices.

        Args:
            force_rescan: If True, rescan all files even if already loaded
            update_missing_metadata: Auto-populate missing frontmatter

        Returns:
            SyncResult with statistics
        """
        start_time = time.perf_counter()

        if force_rescan:
            self.index.clear()

        # Track statistics
        new_poems = 0
        updated_poems = 0
        skipped_poems = 0
        warnings: list[str] = []

        # Scan for markdown files
        logger.info(f"Scanning catalog directory: {self.catalog_dir}")

        if not self.catalog_dir.exists():
            raise FileNotFoundError(f"Catalog directory not found: {self.catalog_dir}")

        # Get all markdown files
        all_markdown_files = list(self.catalog_dir.rglob("*.md"))

        # Filter out excluded directories
        markdown_files = []
        for md_file in all_markdown_files:
            # Get relative path from catalog_dir to check if it's in excluded dir
            rel_path = md_file.relative_to(self.catalog_dir)
            first_dir = rel_path.parts[0] if len(rel_path.parts) > 1 else None

            # Skip if in excluded directory
            if first_dir and first_dir in self.exclude_dirs:
                logger.debug(f"Skipping {md_file.name} (in excluded dir: {first_dir})")
                continue

            markdown_files.append(md_file)

        logger.info(
            f"Found {len(markdown_files)} markdown files (excluded {len(all_markdown_files) - len(markdown_files)} from excluded directories)"
        )

        # Parse each file
        for md_file in markdown_files:
            try:
                poem = parse_poem_file(md_file, self.vault_root)

                # Check if poem already exists
                existing = self.index.get_by_id(poem.id)
                if existing:
                    # Check if updated (don't actually need to track this for now)
                    # Just always add the new version
                    if not force_rescan:
                        updated_poems += 1
                else:
                    new_poems += 1

                # Always add the poem (will overwrite if exists)
                self.index.add_poem(poem)

            except FrontmatterParseError as e:
                skipped_poems += 1
                warning_msg = f"{md_file.name}: {str(e)}"
                warnings.append(warning_msg)
                logger.warning(warning_msg)
            except Exception as e:
                skipped_poems += 1
                warning_msg = f"{md_file.name}: Unexpected error: {str(e)}"
                warnings.append(warning_msg)
                logger.error(warning_msg)

        total_after = len(self.index.all_poems)
        duration = time.perf_counter() - start_time

        # Update last sync timestamp
        from datetime import datetime

        self.last_sync = datetime.now().isoformat()

        logger.info(
            f"Catalog sync complete: {total_after} poems "
            f"({new_poems} new, {updated_poems} updated, {skipped_poems} skipped) "
            f"in {duration:.2f}s"
        )

        return SyncResult(
            total_poems=total_after,
            new_poems=new_poems,
            updated_poems=updated_poems,
            skipped_poems=skipped_poems,
            warnings=warnings,
            duration_seconds=duration,
        )

    def get_stats(self) -> CatalogStats:
        """Get catalog statistics."""
        stats = self.index.get_stats()
        return CatalogStats(
            total_poems=stats["total_poems"],
            by_state=stats["by_state"],
            by_form=stats["by_form"],
            poems_without_tags=stats["poems_without_tags"],
            poems_missing_frontmatter=0,  # All poems have frontmatter now
            total_word_count=stats["total_word_count"],
            avg_word_count=stats["avg_word_count"],
            newest_poem=stats["newest_poem"],
            oldest_poem=stats["oldest_poem"],
            last_sync=self.last_sync,
        )
