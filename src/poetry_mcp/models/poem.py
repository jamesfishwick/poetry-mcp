"""Pydantic model for Poem entity.

Data comes from markdown file frontmatter, not BASE files.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class Poem(BaseModel):
    """
    Poem model representing a single poem with metadata from frontmatter.

    Required frontmatter properties:
    - state: Production state (completed, fledgeling, etc.)
    - form: Structural pattern (free_verse, prose_poem, etc.)

    Optional frontmatter properties:
    - tags: Thematic tags for nexus connections
    - keywords: Legacy comma-separated tags

    Computed properties:
    - id: Generated from filename
    - word_count, line_count, stanza_count: Computed from content
    - created_at, updated_at: From filesystem timestamps
    """

    # Core identity
    id: str = Field(..., description="Unique identifier (filename without .md)")
    title: str = Field(..., description="Poem title from first # heading or filename")
    file_path: str = Field(..., description="Relative path from vault root")

    # Frontmatter: Required properties
    state: Literal[
        "completed",
        "fledgeling",
        "still_cooking",
        "needs_research",
        "risk"
    ] = Field(..., description="Production state of the poem")

    form: Literal[
        "free_verse",
        "prose_poem",
        "american_sentence",
        "catalog_poem"
    ] = Field(..., description="Structural/formal pattern")

    # Frontmatter: Optional properties
    tags: list[str] = Field(
        default_factory=list,
        description="Thematic tags for nexus connections"
    )
    keywords: Optional[str] = Field(
        default=None,
        description="Legacy comma-separated keywords (prefer tags)"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Editorial notes about the poem"
    )

    # Computed metrics
    word_count: int = Field(..., description="Total word count")
    line_count: int = Field(..., description="Total line count")
    stanza_count: Optional[int] = Field(
        default=None,
        description="Number of stanzas (blank-line separated)"
    )

    # Filesystem metadata
    created_at: datetime = Field(..., description="File creation timestamp")
    updated_at: datetime = Field(..., description="File modification timestamp")

    # Content (optional, for search/display)
    content: Optional[str] = Field(
        default=None,
        description="Full poem text (only included if requested)"
    )

    @field_validator('state')
    @classmethod
    def validate_state(cls, v: str) -> str:
        """Validate state enum value."""
        valid_states = {
            "completed", "fledgeling", "still_cooking",
            "needs_research", "risk"
        }
        if v not in valid_states:
            raise ValueError(
                f"Invalid state '{v}'. Must be one of: {', '.join(valid_states)}"
            )
        return v

    @field_validator('form')
    @classmethod
    def validate_form(cls, v: str) -> str:
        """Validate form enum value."""
        valid_forms = {
            "free_verse", "prose_poem",
            "american_sentence", "catalog_poem"
        }
        if v not in valid_forms:
            raise ValueError(
                f"Invalid form '{v}'. Must be one of: {', '.join(valid_forms)}"
            )
        return v

    @field_validator('tags')
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        """Normalize tags: lowercase, strip whitespace, remove duplicates."""
        if not v:
            return []
        normalized = [tag.lower().strip() for tag in v if tag.strip()]
        return list(dict.fromkeys(normalized))  # Preserve order, remove dupes

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "second-bridge-out-old-route-12",
                "title": "Second Bridge Out Old Route 12",
                "file_path": "catalog/Completed/second-bridge-out-old-route-12.md",
                "state": "completed",
                "form": "free_verse",
                "tags": ["water", "body", "memory", "Vermont"],
                "word_count": 358,
                "line_count": 42,
                "stanza_count": 7,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-06-20T14:22:00Z"
            }
        }
