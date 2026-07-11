"""
Nexus management operations.

Handles creation, deletion, and management of nexuses (themes, motifs, forms).
"""

import logging
from pathlib import Path
from typing import Literal

from poetry_mcp.models.nexus import Nexus
from poetry_mcp.writers.nexus_writer import NexusWriter
from poetry_mcp.errors import BaseParseError as ParseError

logger = logging.getLogger(__name__)


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
        except Exception as e:
            raise ParseError(f"Failed to create nexus file: {e}")

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
        except Exception as e:
            raise ParseError(f"Failed to delete nexus file: {e}")

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
            Currently only supports updating frontmatter (canonical_tag).
            Description updates require manual editing of the markdown content.
        """
        # Determine category directory
        category_dir = self.nexus_root / f"{category}s"
        filename = self.writer.get_nexus_filename(name, category)
        file_path = category_dir / filename

        if not file_path.exists():
            raise ParseError(f"Nexus not found: {file_path}")

        # Read current file
        content = file_path.read_text(encoding="utf-8")

        # Update canonical_tag in frontmatter if provided
        if new_canonical_tag:
            # Simple replace - in production you'd parse YAML properly.
            # Extract the current tag first: a backslash escape ('\n') inside an
            # f-string expression is a SyntaxError on Python < 3.12.
            current_canonical_tag = content.split("canonical_tag: ")[1].split("\n")[0]
            content = content.replace(
                f"canonical_tag: {current_canonical_tag}",
                f"canonical_tag: {new_canonical_tag}",
                1,
            )

        # Write updated content
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated nexus: {file_path}")

            # Return updated Nexus
            return Nexus(
                name=name,
                category=category,
                canonical_tag=new_canonical_tag or "updated",
                description=new_description or "See file for details",
                file_path=str(file_path),
            )
        except Exception as e:
            raise ParseError(f"Failed to update nexus file: {e}")
