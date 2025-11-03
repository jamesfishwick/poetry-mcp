"""Result models for MCP tool responses.

These models structure the data returned by various MCP tools.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .poem import Poem
from .nexus import Nexus
from .quality import Quality
from .venue import Venue
from .influence import Influence


class SyncResult(BaseModel):
    """
    Result from sync_catalog operation.

    Reports statistics about catalog synchronization:
    how many poems were discovered, added, updated, or skipped.
    """

    total_poems: int = Field(..., description="Total number of poems in catalog after sync")

    new_poems: int = Field(..., description="Number of new poems discovered in this sync")

    updated_poems: int = Field(..., description="Number of existing poems with updated metadata")

    skipped_poems: int = Field(default=0, description="Number of poems skipped due to parse errors")

    warnings: list[str] = Field(
        default_factory=list, description="List of warning messages encountered during sync"
    )

    duration_seconds: float = Field(..., description="Time taken for sync operation")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "total_poems": 381,
                "new_poems": 5,
                "updated_poems": 12,
                "skipped_poems": 2,
                "warnings": [
                    "poem_without_frontmatter.md: missing frontmatter, used defaults",
                    "broken_file.md: invalid YAML, skipped",
                ],
                "duration_seconds": 2.34,
            }
        }


class SearchResult(BaseModel):
    """
    Result from search_poems operation.

    Contains matched poems and query metadata.
    """

    poems: list[Poem] = Field(..., description="List of poems matching search criteria")

    total_matches: int = Field(
        ..., description="Total number of poems matching query (may be > len(poems) if limited)"
    )

    query_time_ms: float = Field(..., description="Time taken to execute query in milliseconds")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "poems": [
                    {
                        "id": "second-bridge",
                        "title": "Second Bridge Out Old Route 12",
                        "state": "completed",
                        "form": "free_verse",
                        "tags": ["water", "memory"],
                    }
                ],
                "total_matches": 23,
                "query_time_ms": 45.2,
            }
        }


class BaseFileResult(BaseModel):
    """
    Result from load_base_file operation.

    Contains parsed entries from a BASE file and view configurations.
    """

    entries: list[Poem | Nexus | Quality | Venue | Influence] = Field(
        ..., description="Parsed entries from BASE file"
    )

    count: int = Field(..., description="Number of entries parsed")

    views: list[dict[str, Any]] = Field(
        default_factory=list, description="Parsed view configurations from BASE file"
    )

    warnings: list[str] = Field(
        default_factory=list, description="Warnings encountered during parsing"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "entries": [
                    {"name": "Water-Liquid Imagery", "category": "theme"},
                    {"name": "Body-Bones Imagery", "category": "theme"},
                ],
                "count": 2,
                "views": [{"type": "table", "name": "Table"}],
                "warnings": [],
            }
        }


class CatalogStats(BaseModel):
    """
    Catalog statistics and health metrics.

    Returned by get_catalog_stats() tool.
    """

    total_poems: int = Field(..., description="Total number of poems in catalog")

    by_state: dict[str, int] = Field(..., description="Count of poems by state")

    by_form: dict[str, int] = Field(..., description="Count of poems by form")

    poems_without_tags: int = Field(..., description="Number of poems with no tags")

    poems_missing_frontmatter: int = Field(
        default=0, description="Number of poems with incomplete frontmatter"
    )

    total_word_count: int = Field(..., description="Total words across all poems")

    avg_word_count: float = Field(..., description="Average word count per poem")

    newest_poem: str = Field(..., description="Title of most recently created poem")

    oldest_poem: str = Field(..., description="Title of oldest poem")

    last_sync: Optional[str] = Field(default=None, description="Timestamp of last catalog sync")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "total_poems": 381,
                "by_state": {
                    "completed": 49,
                    "fledgeling": 172,
                    "still_cooking": 65,
                    "needs_research": 10,
                    "risk": 22,
                    "phone_poetry": 63,
                },
                "by_form": {
                    "free_verse": 310,
                    "prose_poem": 45,
                    "american_sentence": 18,
                    "catalog_poem": 8,
                },
                "poems_without_tags": 350,
                "poems_missing_frontmatter": 0,
                "total_word_count": 125430,
                "avg_word_count": 329.2,
                "newest_poem": "November Rain",
                "oldest_poem": "First Poem",
                "last_sync": "2025-10-30T21:45:00Z",
            }
        }
