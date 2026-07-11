"""Small shared utilities."""

import re


def slugify_filename(name: str) -> str:
    """Turn an arbitrary name into a safe filename stem.

    Strips characters that could escape a directory (``/``, ``.``, ``\\``, etc.),
    collapses runs of whitespace/hyphens into a single hyphen, and trims. This
    prevents path traversal when a name taken from data (e.g. a venue name in
    frontmatter) is used to build a write path. Falls back to "untitled" if the
    name has no usable characters.
    """
    slug = re.sub(r"[^\w\s-]", "", name)
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug or "untitled"
