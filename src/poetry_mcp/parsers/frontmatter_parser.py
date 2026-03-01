"""Frontmatter parser for markdown files.

Extracts YAML frontmatter from poem markdown files and converts to Poem objects.
This is the core of the v2.0 architecture: data comes from frontmatter, not BASE files.
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import yaml

from ..models.poem import Poem
from ..errors import FrontmatterParseError


def parse_poem_file(file_path: Path, vault_root: Path) -> Poem:
    """
    Parse a poem markdown file into a Poem object.

    Args:
        file_path: Absolute path to the markdown file
        vault_root: Absolute path to vault root (for relative paths)

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
    created_at = datetime.fromtimestamp(file_path.stat().st_ctime, tz=timezone.utc)
    updated_at = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

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
    state = frontmatter.get("state")
    form = frontmatter.get("form")

    # Validate required fields
    if not state:
        # Infer state from directory structure if missing
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


def infer_state_from_path(file_path: Path) -> str:
    """
    Infer poem state from directory structure.

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
