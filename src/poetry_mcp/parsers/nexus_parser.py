"""Nexus parser for loading theme/motif/form registry from vault.

Parses nexus markdown files from the vault's nexus/ directory and builds
a registry organized by category (themes, motifs, forms).
"""

from pathlib import Path
from typing import Any

import yaml

from ..models.nexus import Nexus, NexusRegistry
from ..errors import FrontmatterParseError


def extract_canonical_tag(file_path: Path) -> tuple[str, str]:
    """Extract canonical_tag from nexus markdown file.

    Args:
        file_path: Path to nexus markdown file

    Returns:
        Tuple of (canonical_tag, full_content)

    Raises:
        FrontmatterParseError: If frontmatter is malformed or missing canonical_tag
    """
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Check for frontmatter delimiter
    if not lines or lines[0].strip() != '---':
        raise FrontmatterParseError(
            f"Missing frontmatter in {file_path}: expected '---' delimiter"
        )

    # Find closing delimiter
    try:
        end_idx = lines[1:].index('---') + 1
    except ValueError:
        raise FrontmatterParseError(
            f"Unclosed frontmatter in {file_path}: missing closing '---'"
        )

    # Extract frontmatter YAML
    frontmatter_lines = lines[1:end_idx]
    frontmatter_text = '\n'.join(frontmatter_lines)

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        raise FrontmatterParseError(
            f"Invalid YAML in frontmatter of {file_path}: {e}"
        )

    # Get canonical_tag
    canonical_tag = frontmatter.get('canonical_tag')
    if not canonical_tag:
        raise FrontmatterParseError(
            f"Missing 'canonical_tag' field in frontmatter of {file_path}"
        )

    return canonical_tag, content


def parse_nexus_file(file_path: Path, category: str) -> Nexus:
    """Parse a single nexus markdown file.

    Args:
        file_path: Path to nexus markdown file
        category: Category (theme/motif/form)

    Returns:
        Nexus model instance

    Raises:
        FrontmatterParseError: If file is malformed
    """
    canonical_tag, full_content = extract_canonical_tag(file_path)

    # Extract name from filename (remove .md and "Imagery" suffix if present)
    name = file_path.stem
    if name.endswith(' Imagery'):
        name = name[:-8]  # Remove " Imagery"

    # Build description from file content (for LLM context)
    # We'll include the full markdown content for now
    description = full_content

    return Nexus(
        name=name,
        category=category,
        canonical_tag=canonical_tag,
        description=description,
        file_path=str(file_path),
    )


def scan_nexus_directory(
    nexus_dir: Path,
    category: str,
) -> list[Nexus]:
    """Scan a nexus directory for markdown files.

    Args:
        nexus_dir: Path to nexus category directory (e.g., nexus/themes/)
        category: Category name (theme/motif/form)

    Returns:
        List of Nexus instances
    """
    nexuses = []

    if not nexus_dir.exists():
        return nexuses

    for md_file in nexus_dir.glob("*.md"):
        try:
            nexus = parse_nexus_file(md_file, category)
            nexuses.append(nexus)
        except FrontmatterParseError as e:
            # Log warning and skip malformed files
            print(f"Warning: Skipping {md_file}: {e}")
            continue

    return nexuses


def load_nexus_registry(vault_root: Path) -> NexusRegistry:
    """Load all nexuses from vault into organized registry.

    Scans the vault's nexus/ directory for themes, motifs, and forms.

    Args:
        vault_root: Path to Obsidian vault root

    Returns:
        NexusRegistry with all nexuses organized by category

    Example:
        >>> vault_path = Path("/Users/user/Poetry")
        >>> registry = load_nexus_registry(vault_path)
        >>> len(registry.themes)
        26
        >>> registry.themes[0].canonical_tag
        'water-liquid'
    """
    nexus_root = vault_root / "nexus"

    # Scan each category directory
    themes = scan_nexus_directory(nexus_root / "themes", "theme")
    motifs = scan_nexus_directory(nexus_root / "motifs", "motif")
    forms = scan_nexus_directory(nexus_root / "forms", "form")

    # Calculate total count
    total_count = len(themes) + len(motifs) + len(forms)

    return NexusRegistry(
        themes=themes,
        motifs=motifs,
        forms=forms,
        total_count=total_count,
    )
