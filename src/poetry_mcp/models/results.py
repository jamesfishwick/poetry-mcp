"""Result models for MCP tool responses.

These models structure the data returned by various MCP tools.
"""

from typing import Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict

from .poem import Poem
from .nexus import Nexus
from .quality import Quality
from .venue import Venue
from .influence import Influence
from .submission import Submission


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

    model_config = ConfigDict(
        json_schema_extra={
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
    )


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

    model_config = ConfigDict(
        json_schema_extra={
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
    )


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

    model_config = ConfigDict(
        json_schema_extra={
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
    )


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

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class ValidationResult(BaseModel):
    """
    Result from validate_poem_tags operation.

    Reports tag validation results and violations.
    """

    success: bool = Field(..., description="Whether validation passed (no invalid tags)")
    valid: bool = Field(..., description="Alias for success (backward compatibility)")
    invalid_tags: List[str] = Field(default_factory=list, description="Tags that don't match any nexus")
    violations_count: int = Field(..., description="Number of invalid tags found")
    affected_poems: List[dict] = Field(
        default_factory=list, description="Poems containing invalid tags"
    )
    total_poems_checked: int = Field(..., description="Total number of poems validated")
    total_tags_checked: int = Field(..., description="Total unique tags encountered")
    valid_tags: List[str] = Field(default_factory=list, description="All valid nexus canonical tags")


class NexusOperationResult(BaseModel):
    """
    Result from nexus creation or deletion operations.

    Reports success status and operation details.
    """

    success: bool = Field(..., description="Whether operation succeeded")
    nexus: Optional[Nexus] = Field(None, description="Nexus object (for create operations)")
    operation: str = Field(..., description="Operation performed (created/deleted/updated)")
    file_path: Optional[str] = Field(None, description="Path to nexus file")
    poems_cleaned: int = Field(default=0, description="Number of poems cleaned up (delete only)")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class ChainOperationResult(BaseModel):
    """
    Result from chain modification operations.

    Reports success status, affected poems, and position updates.
    """

    success: bool = Field(..., description="Whether operation succeeded")
    chain_id: str = Field(..., description="Chain identifier")
    poems_affected: list[str] = Field(
        default_factory=list, description="Poem IDs modified"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    positions: Optional[dict[str, int]] = Field(
        None, description="Final positions after operation (for ordered chains)"
    )
    backup_paths: Optional[list[str]] = Field(
        None, description="Backup file paths created"
    )


class ChainInfo(BaseModel):
    """
    Information about a chain and its poems.

    Used by get_chain and list_chains tools.
    """

    chain_id: str = Field(..., description="Chain identifier")
    poem_count: int = Field(..., description="Number of poems in chain")
    is_ordered: bool = Field(
        ..., description="Whether chain has any poems with positions"
    )
    poems: Optional[list[Poem]] = Field(
        None, description="Poems in chain (if requested)"
    )


class ChainListResult(BaseModel):
    """
    Result from list_chains operation.

    Returns all chains with basic stats.
    """

    chains: list[ChainInfo] = Field(..., description="All chains with info")
    total_chains: int = Field(..., description="Total number of chains")


class PoemsByNexusResult(BaseModel):
    """
    Result from get_poems_by_nexus operation.

    Returns all poems tagged with a specific nexus.
    """

    success: bool = Field(..., description="Whether lookup succeeded")
    nexus: Optional[Nexus] = Field(None, description="The nexus being queried")
    poems: List[Poem] = Field(default_factory=list, description="Poems tagged with this nexus")
    total_count: int = Field(..., description="Total number of poems with this tag")
    error: Optional[str] = Field(None, description="Error message if lookup failed")


class NexusCountsResult(BaseModel):
    """
    Result from refresh_nexus_poem_counts operation.

    Reports updated poem counts across all nexuses.
    """

    success: bool = Field(..., description="Whether refresh succeeded")
    nexuses_updated: int = Field(..., description="Number of nexuses updated")
    stats: dict = Field(
        ...,
        description="Statistics by category (themes/motifs/forms with count and total_poems)",
    )
    top_nexuses: List[dict] = Field(..., description="Top 5 nexuses by poem count")


class ServerInfo(BaseModel):
    """
    Server information and configuration.

    Returned by get_server_info() tool.
    """

    server_name: str = Field(..., description="MCP server name")
    version: str = Field(..., description="Server version")
    config: dict = Field(..., description="Current configuration")
    catalog_stats: CatalogStats = Field(..., description="Current catalog statistics")


class SyncSubmissionsResult(BaseModel):
    """
    Result from sync_submissions operation.

    Reports submission catalog sync statistics.
    """

    success: bool = Field(..., description="Whether sync succeeded")
    total_submissions: int = Field(..., description="Total number of submissions indexed")
    new_submissions: int = Field(..., description="Number of newly discovered submissions")
    errors: list[str] = Field(default_factory=list, description="List of parse errors encountered")
    duration_seconds: float = Field(..., description="Time taken for sync operation")


class SyncVenuesResult(BaseModel):
    """
    Result from sync_venues operation.

    Reports venue catalog sync statistics.
    """

    success: bool = Field(..., description="Whether sync succeeded")
    total_venues: int = Field(..., description="Total number of venues indexed")
    new_venues: int = Field(..., description="Number of newly discovered venues")
    errors: list[str] = Field(default_factory=list, description="List of parse errors encountered")
    duration_seconds: float = Field(..., description="Time taken for sync operation")


class VenueDetailResult(BaseModel):
    """
    Result from get_venue operation.

    Returns venue details with all submissions.
    """

    success: bool = Field(..., description="Whether venue lookup succeeded")
    venue: Optional[Venue] = Field(None, description="Venue metadata")
    submissions: List[Submission] = Field(default_factory=list, description="All venue submissions")
    error: Optional[str] = Field(None, description="Error message if lookup failed")


class RegenerateVenueResult(BaseModel):
    """
    Result from regenerate_venue_file operation.

    Reports venue file regeneration details.
    """

    success: bool = Field(..., description="Whether regeneration succeeded")
    venue_name: str = Field(..., description="Name of venue regenerated")
    file_path: str = Field(..., description="Path to regenerated venue file")
    submissions_count: int = Field(..., description="Number of submissions in venue")
    error: Optional[str] = Field(None, description="Error message if regeneration failed")


class SubmissionListResult(BaseModel):
    """
    Result from list_submissions operation.

    Returns filtered list of submissions with metadata.
    """

    success: bool = Field(..., description="Whether query succeeded")
    submissions: List[Submission] = Field(default_factory=list, description="Matching submissions")
    total_count: int = Field(..., description="Total number of matching submissions")
    filters_applied: dict = Field(..., description="Filters used in query")


class VenueListResult(BaseModel):
    """
    Result from list_venues operation.

    Returns filtered list of venues.
    """

    success: bool = Field(..., description="Whether query succeeded")
    venues: List[Venue] = Field(default_factory=list, description="Matching venues")
    total_count: int = Field(..., description="Total number of matching venues")
    filters_applied: dict = Field(..., description="Filters used in query")


class SubmissionStatusChange(BaseModel):
    """A single submission whose status was (or would be) changed."""

    source_file: str = Field(..., description="Absolute path to the submission file")
    venue_name: str = Field(..., description="Venue for this submission")
    poems: List[str] = Field(default_factory=list, description="Poems in this submission")
    old_status: str = Field(..., description="Status before the change")
    new_status: str = Field(..., description="Status after the change")


class UpdateSubmissionStatusResult(BaseModel):
    """
    Result from update_submission_status operation.

    In dry_run mode the changes are previewed but not written; the `changes`
    list still reflects exactly what would be modified.
    """

    success: bool = Field(..., description="Whether the operation succeeded")
    dry_run: bool = Field(..., description="If True, no files were written")
    new_status: str = Field(..., description="Target status applied to matches")
    matched_count: int = Field(..., description="Number of submissions matched")
    changes: List[SubmissionStatusChange] = Field(
        default_factory=list, description="Per-file changes made (or previewed)"
    )
    backups: List[str] = Field(
        default_factory=list, description="Paths to .bak backups created (empty on dry_run)"
    )
    filters_applied: dict = Field(..., description="Selection filters used")
    error: Optional[str] = Field(None, description="Error message if the operation failed")


class SimilarPoemMatch(BaseModel):
    """A poem matched as similar to a reference poem, with explanation."""

    poem: Poem = Field(..., description="The similar poem")
    similarity_score: float = Field(
        ..., description="Weighted similarity score (higher = more similar)"
    )
    shared_nexuses: List[str] = Field(
        default_factory=list,
        description="Nexus canonical_tags shared with source poem",
    )
    shared_tags: List[str] = Field(
        default_factory=list,
        description="Non-nexus tags shared with source poem",
    )
    shared_chains: List[str] = Field(
        default_factory=list,
        description="Chain IDs both poems belong to",
    )
    same_form: bool = Field(
        default=False,
        description="Whether the poem has the same form as the source",
    )


class SimilarityResult(BaseModel):
    """Result from find_similar_poems operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    source_poem_id: str = Field(..., description="ID of the reference poem")
    source_poem_title: str = Field(..., description="Title of the reference poem")
    matches: List[SimilarPoemMatch] = Field(
        default_factory=list,
        description="Similar poems ranked by score (highest first)",
    )
    total_candidates_scored: int = Field(
        ..., description="Number of candidate poems evaluated"
    )
    query_time_ms: float = Field(..., description="Time taken in milliseconds")
    error: Optional[str] = Field(None, description="Error message if operation failed")
