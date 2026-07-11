"""
Nexus management operations.

Handles creation, deletion, and management of nexuses (themes, motifs, forms).
"""

import logging
import re
from pathlib import Path
from typing import Literal

from poetry_mcp.models.nexus import Nexus
from poetry_mcp.writers.nexus_writer import NexusWriter
from poetry_mcp.writers.frontmatter_writer import (
    extract_frontmatter_and_content,
    serialize_frontmatter_and_content,
)
from poetry_mcp.errors import BaseParseError as ParseError

logger = logging.getLogger(__name__)

# The description lives in the body's "## Overview" section (see NexusWriter's
# default template), not the frontmatter. This captures that section's text so
# update_nexus can replace it in place without regenerating the whole body.
_OVERVIEW_RE = re.compile(
    r"(?P<head>##\s+Overview\s*\n\n)(?P<body>.*?)(?P<tail>\n\n##|\Z)", re.DOTALL
)


class NexusManager:
    """
    Manages nexus creation, deletion, and updates.

    Coordinates with the file system to maintain nexus registry integrity.
    """

    def __init__(self, nexus_root: Path):
        """
        Initialize nexus manager.

        Args:
            nexus_root: Path to nexus/ directory
        """
        self.nexus_root = Path(nexus_root)
        self.writer = NexusWriter()

    def create_nexus(
        self,
        name: str,
        category: Literal["theme", "motif", "form"],
        canonical_tag: str,
        description: str,
        custom_template: str | None = None,
    ) -> Nexus:
        """
        Create a new nexus.

        Args:
            name: Nexus name (e.g., "Water-Liquid", "American Grotesque")
            category: Nexus category (theme/motif/form)
            canonical_tag: Tag for poems (e.g., "water", "american-grotesque")
            description: What this nexus represents
            custom_template: Optional custom markdown template

        Returns:
            Created Nexus instance

        Raises:
            ParseError: If nexus already exists or creation fails
        """
        # Determine category directory
        category_dir = self.nexus_root / f"{category}s"
        if not category_dir.exists():
            category_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = self.writer.get_nexus_filename(name, category)
        file_path = category_dir / filename

        # Check if already exists
        if file_path.exists():
            raise ParseError(f"Nexus already exists: {file_path}")

        # Create Nexus model
        nexus = Nexus(
            name=name,
            category=category,
            canonical_tag=canonical_tag,
            description=description,
            file_path=str(file_path),
        )

        # Generate and write file
        try:
            self.writer.generate_nexus_file(nexus, file_path, custom_template)
            logger.info(f"Created nexus: {file_path}")
            return nexus
        except OSError as e:
            raise ParseError(f"Failed to create nexus file: {e}") from e

    def delete_nexus(
        self,
        name: str,
        category: Literal["theme", "motif", "form"],
        force: bool = False,
    ) -> dict:
        """
        Delete a nexus.

        Args:
            name: Nexus name to delete
            category: Nexus category (theme/motif/form)
            force: If True, delete even if poems reference it

        Returns:
            Dictionary with deletion results

        Raises:
            ParseError: If nexus not found or deletion fails
        """
        # Determine category directory
        category_dir = self.nexus_root / f"{category}s"

        # Find file
        filename = self.writer.get_nexus_filename(name, category)
        file_path = category_dir / filename

        if not file_path.exists():
            raise ParseError(f"Nexus not found: {file_path}")

        # Check for referenced poems (if not forced)
        # Note: This is a basic check - in production, you'd scan the catalog
        # to see if any poems have this tag
        if not force:
            logger.warning(
                f"Deleting nexus '{name}' - poems with this tag will keep the tag but lose the nexus definition"
            )

        # Delete file
        try:
            file_path.unlink()
            logger.info(f"Deleted nexus: {file_path}")
            return {
                "deleted": str(file_path),
                "nexus_name": name,
                "category": category,
                "status": "success",
            }
        except OSError as e:
            raise ParseError(f"Failed to delete nexus file: {e}") from e

    def update_nexus(
        self,
        name: str,
        category: Literal["theme", "motif", "form"],
        new_canonical_tag: str | None = None,
        new_description: str | None = None,
    ) -> Nexus:
        """
        Update nexus metadata.

        Args:
            name: Nexus name
            category: Nexus category
            new_canonical_tag: Updated canonical tag (optional)
            new_description: Updated description (optional)

        Returns:
            Updated Nexus instance

        Raises:
            ParseError: If nexus not found or update fails

        Note:
            canonical_tag is a frontmatter field; description is the body's
            "## Overview" section. Both are updated in place, preserving the
            rest of the file. Unspecified fields keep their current values.
        """
        # Determine category directory
        category_dir = self.nexus_root / f"{category}s"
        filename = self.writer.get_nexus_filename(name, category)
        file_path = category_dir / filename

        if not file_path.exists():
            raise ParseError(f"Nexus not found: {file_path}")

        # Parse frontmatter + body properly (no fragile string surgery).
        content = file_path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter_and_content(content, file_path)

        if new_canonical_tag:
            frontmatter["canonical_tag"] = new_canonical_tag
        effective_tag = frontmatter.get("canonical_tag", "")

        if new_description is not None:
            if _OVERVIEW_RE.search(body):
                body = _OVERVIEW_RE.sub(
                    lambda m: f"{m.group('head')}{new_description}{m.group('tail')}",
                    body,
                    count=1,
                )
                effective_description = new_description
            else:
                # Don't silently drop the update — surface that it had no home.
                logger.warning(
                    f"No '## Overview' section in {file_path}; "
                    f"description not written to the body"
                )
                effective_description = new_description
        else:
            match = _OVERVIEW_RE.search(body)
            effective_description = match.group("body").strip() if match else ""

        try:
            new_content = serialize_frontmatter_and_content(frontmatter, body)
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Updated nexus: {file_path}")
            return Nexus(
                name=name,
                category=category,
                canonical_tag=effective_tag,
                description=effective_description,
                file_path=str(file_path),
            )
        except OSError as e:
            raise ParseError(f"Failed to update nexus file: {e}") from e
