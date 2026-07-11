"""Frontmatter parser for markdown files.

Extracts YAML frontmatter from poem markdown files and converts to Poem objects.
This is the core of the v2.0 architecture: data comes from frontmatter, not BASE files.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml

from ..models.poem import Poem
from ..errors import FrontmatterParseError


# Canonical mapping from a poem's top-level catalog subfolder to its state.
# Folder is authoritative; this is the single source of truth for that mapping
# and is also used as the default for VaultConfig.folder_state_map. Note the
# deliberate singular/plural handling: "Risks" -> "risk", "Fledgelings" ->
# "fledgeling". "phone-poetry" is the one subfolder whose state slug differs
# from a simple lowercase of the folder name.
DEFAULT_FOLDER_STATE_MAP: dict[str, str] = {
    "Completed": "completed",
    "Fledgelings": "fledgeling",
    "Needs Research": "needs_research",
    "Risks": "risk",
    "Still Cooking": "still_cooking",
    "phone-poetry": "phone_poetry",
}


def parse_poem_file(
    file_path: Path,
    vault_root: Path,
    folder_state_map: Optional[dict[str, str]] = None,
) -> Poem:
    """
    Parse a poem markdown file into a Poem object.

    Args:
        file_path: Absolute path to the markdown file
        vault_root: Absolute path to vault root (for relative paths)
        folder_state_map: Optional folder->state map used to derive state from
            the poem's top-level catalog subfolder. When None, defaults to
            DEFAULT_FOLDER_STATE_MAP. Passing it explicitly (as Catalog does)
            keeps parsing decoupled from the global config singleton.

    Returns:
        Poem object with frontmatter metadata and computed fields

    Raises:
        FrontmatterParseError: If file cannot be parsed
        FileNotFoundError: If file doesn't exist
        ValueError: If required frontmatter fields are missing
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Poem file not found: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise FrontmatterParseError(f"Failed to read {file_path}: {e}")

    # Extract frontmatter and content
    frontmatter, poem_content = extract_frontmatter(content, file_path)

    # Generate ID from filename
    poem_id = generate_poem_id(file_path)

    # Extract title (from first # heading or fallback to filename)
    title = extract_title(poem_content, file_path)

    # Get file timestamps
    created_at = datetime.fromtimestamp(file_path.stat().st_ctime)
    updated_at = datetime.fromtimestamp(file_path.stat().st_mtime)

    # Compute metrics
    word_count = count_words(poem_content)
    line_count = count_lines(poem_content)
    stanza_count = count_stanzas(poem_content)

    # Build relative file path
    try:
        relative_path = str(file_path.relative_to(vault_root))
    except ValueError:
        # File is not under vault_root
        relative_path = str(file_path)

    # Extract required fields with defaults
    form = frontmatter.get("form")

    # State is derived from folder location, which is authoritative.
    # The frontmatter "state" field (if present) is ignored except as a
    # fallback for files in folders not covered by the folder_state_map.
    state = derive_state_from_path(file_path, vault_root, folder_state_map)
    if not state:
        state = frontmatter.get("state")
    if not state:
        # Legacy heuristic fallback for anything still unresolved
        state = infer_state_from_path(file_path)

    if not form:
        # Detect form heuristically if missing
        form = detect_form(poem_content)

    # Extract optional fields
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        # Handle legacy comma-separated tags
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    keywords = frontmatter.get("keywords")
    notes = frontmatter.get("notes")
    qualities = frontmatter.get("qualities")  # Optional quality scores dict

    # Build Poem object
    try:
        poem = Poem(
            id=poem_id,
            title=title,
            file_path=relative_path,
            state=state,
            form=form,
            tags=tags,
            keywords=keywords,
            notes=notes,
            word_count=word_count,
            line_count=line_count,
            stanza_count=stanza_count,
            created_at=created_at,
            updated_at=updated_at,
            content=poem_content,  # Include full content
            qualities=qualities,  # Include quality scores if present
        )
    except Exception as e:
        raise FrontmatterParseError(f"Failed to create Poem object for {file_path}: {e}")

    return poem


def extract_frontmatter(content: str, file_path: Path) -> tuple[dict, str]:
    """
    Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown file content
        file_path: Path to file (for error messages)

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)

    Raises:
        FrontmatterParseError: If frontmatter is malformed
    """
    # Match YAML frontmatter: ---\n...\n---
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        # No frontmatter found - return empty dict and full content
        return {}, content

    yaml_content = match.group(1)
    body_content = match.group(2)

    # Parse YAML
    try:
        frontmatter = yaml.safe_load(yaml_content)
        if frontmatter is None:
            frontmatter = {}
        if not isinstance(frontmatter, dict):
            raise FrontmatterParseError(f"Frontmatter in {file_path} is not a valid YAML object")
    except yaml.YAMLError as e:
        raise FrontmatterParseError(f"Invalid YAML in {file_path} frontmatter: {e}")

    return frontmatter, body_content


def generate_poem_id(file_path: Path) -> str:
    """
    Generate poem ID from filename.

    Removes .md extension and normalizes to lowercase-with-dashes.

    Args:
        file_path: Path to poem file

    Returns:
        Normalized poem ID
    """
    # Remove .md extension
    name = file_path.stem

    # Remove leading numbers and dashes (e.g., "11 - Toeses" -> "Toeses")
    name = re.sub(r"^\d+\s*-\s*", "", name)

    # Convert to lowercase and replace spaces with dashes
    poem_id = name.lower().replace(" ", "-")

    # Remove any other special characters except dashes
    poem_id = re.sub(r"[^a-z0-9-]", "", poem_id)

    return poem_id


def extract_title(content: str, file_path: Path) -> str:
    """
    Extract poem title from first # heading or filename.

    Args:
        content: Poem content (without frontmatter)
        file_path: Path to file (fallback for title)

    Returns:
        Poem title
    """
    # Look for first # heading
    heading_pattern = r"^#\s+(.+)$"
    match = re.search(heading_pattern, content, re.MULTILINE)

    if match:
        title = match.group(1).strip()
        # Remove duplicate # symbols (e.g., "# # Toeses" -> "Toeses")
        title = re.sub(r"^#+\s*", "", title)
        return title

    # Fallback to filename without extension
    name = file_path.stem
    # Remove leading numbers (e.g., "11 - Toeses" -> "Toeses")
    name = re.sub(r"^\d+\s*-\s*", "", name)
    return name


def derive_state_from_path(
    file_path: Path,
    vault_root: Path,
    folder_state_map: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """
    Derive poem state from its top-level catalog subfolder (authoritative).

    The state is determined by parts[0] of the file's path relative to the
    catalog directory, looked up in the folder_state_map. Nested folders
    inherit their top-level parent's state (depth rule): a poem in
    Completed/chapbook/bredan/ resolves to "completed" because its top-level
    folder is "Completed".

    Args:
        file_path: Absolute path to the poem file
        vault_root: Absolute path to the vault root
        folder_state_map: Folder->state map. When None, defaults to
            DEFAULT_FOLDER_STATE_MAP.

    Returns:
        Mapped state string, or None if the folder is not in the map
        (e.g. a file directly under catalog/, or an unmapped subfolder),
        in which case the caller falls back to frontmatter or heuristics.
    """
    if folder_state_map is None:
        folder_state_map = DEFAULT_FOLDER_STATE_MAP

    # Locate the catalog root by walking up from the file to a "catalog"
    # directory under the vault. This avoids a hard dependency on the config
    # singleton in the parse hot path (which would otherwise pollute the
    # cached config during tests).
    catalog_dir = None
    for parent in file_path.parents:
        if parent.name == "catalog" and parent.parent == vault_root:
            catalog_dir = parent
            break
    if catalog_dir is None:
        # Fall back to the conventional location
        catalog_dir = vault_root / "catalog"

    try:
        rel = file_path.relative_to(catalog_dir)
    except ValueError:
        # File is not under the catalog directory
        return None

    # Need at least one subfolder plus the filename
    if len(rel.parts) < 2:
        return None

    top_folder = rel.parts[0]
    return folder_state_map.get(top_folder)


def infer_state_from_path(file_path: Path) -> str:
    """
    Infer poem state from directory structure.

    Legacy heuristic fallback, retained only for files that
    derive_state_from_path cannot resolve (folders absent from the
    folder_state_map). Folder-based derivation is preferred.

    Args:
        file_path: Path to poem file

    Returns:
        Inferred state value
    """
    path_str = str(file_path).lower()

    if "completed" in path_str:
        return "completed"
    elif "fledgeling" in path_str:
        return "fledgeling"
    elif "still cooking" in path_str or "still-cooking" in path_str:
        return "still_cooking"
    elif "needs research" in path_str or "needs-research" in path_str:
        return "needs_research"
    elif "risk" in path_str:
        return "risk"
    else:
        # Default to fledgeling for unknown directories (including personal workflow dirs)
        return "fledgeling"


def detect_form(content: str) -> str:
    """
    Detect poem form using heuristics.

    Args:
        content: Poem content (without frontmatter)

    Returns:
        Detected form value
    """
    # Strip whitespace and split into lines
    lines = [line for line in content.strip().split("\n") if line.strip()]

    # Skip title if present
    if lines and lines[0].strip().startswith("#"):
        lines = lines[1:]
        lines = [line for line in lines if line.strip()]  # Re-filter

    if not lines:
        return "free_verse"

    # American sentence: single line, ~17 syllables
    if len(lines) == 1:
        syllable_count = estimate_syllables(lines[0])
        if 15 <= syllable_count <= 19:
            return "american_sentence"

    # Prose poem: paragraph format (long lines, no stanzas)
    if len(lines) <= 3:  # Very few line breaks
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length > 100:  # Long lines
            return "prose_poem"

    # Catalog poem: anaphora patterns (repeated line beginnings)
    if len(lines) >= 3:
        starting_words = [
            line.strip().split()[0].lower() if line.strip().split() else "" for line in lines
        ]
        # Check for repeated starting words
        from collections import Counter

        word_counts = Counter(starting_words)
        most_common = word_counts.most_common(1)
        if most_common and most_common[0][1] >= 3:
            # Same word starts 3+ lines
            return "catalog_poem"

    # Default to free verse
    return "free_verse"


def estimate_syllables(text: str) -> int:
    """
    Rough syllable estimation for form detection.

    Not linguistically perfect, but good enough for heuristics.

    Args:
        text: Text to analyze

    Returns:
        Estimated syllable count
    """
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text.lower())
    words = text.split()

    syllables = 0
    for word in words:
        # Count vowel groups as syllables
        vowel_groups = re.findall(r"[aeiouy]+", word)
        count = len(vowel_groups)

        # Adjust for silent 'e'
        if word.endswith("e") and count > 1:
            count -= 1

        # Minimum 1 syllable per word
        syllables += max(1, count)

    return syllables


def count_words(content: str) -> int:
    """Count words in poem content."""
    # Remove markdown headings
    content = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)
    # Split on whitespace and count
    words = content.split()
    return len(words)


def count_lines(content: str) -> int:
    """Count non-empty lines in poem content."""
    # Remove markdown headings
    content = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)
    # Count non-empty lines
    lines = [line for line in content.split("\n") if line.strip()]
    return len(lines)


def count_stanzas(content: str) -> Optional[int]:
    """
    Count stanzas (blank-line separated groups) in poem content.

    Returns None if poem has no stanzas (prose poem or single-line).
    """
    # Remove markdown headings
    content = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)

    # Split on blank lines (2+ newlines)
    stanzas = re.split(r"\n\s*\n", content.strip())
    stanzas = [s for s in stanzas if s.strip()]

    # Return None for prose poems or single-line poems
    if len(stanzas) <= 1:
        return None

    return len(stanzas)
