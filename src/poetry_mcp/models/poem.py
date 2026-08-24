"""Pydantic model for Poem entity.

Data comes from markdown file frontmatter, not BASE files.
"""

import logging
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# Forms the model always accepts. Anything else must be declared in
# config.vault.custom_forms; see Poem.set_custom_forms.
STANDARD_FORMS: frozenset[str] = frozenset(
    {"free_verse", "prose_poem", "american_sentence", "catalog_poem"}
)

# Fallback applied when a poem declares a form nothing recognizes. Form is
# metadata, not identity, so an unknown value must never cost us the poem.
FALLBACK_FORM = "free_verse"


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

    # Class variable for custom states (set by catalog during initialization)
    _custom_states: ClassVar[set[str]] = set()

    # Class variable for custom forms (set by catalog during initialization).
    # Received forms (pantoum, villanelle, sestina...) belong here rather than
    # in STANDARD_FORMS so the taxonomy lives in config, not in source.
    _custom_forms: ClassVar[set[str]] = set()

    @classmethod
    def set_custom_states(cls, custom_states: list[str]) -> None:
        """Set custom states that are valid in addition to standard states."""
        cls._custom_states = set(custom_states)

    @classmethod
    def set_custom_forms(cls, custom_forms: list[str]) -> None:
        """Set custom forms that are valid in addition to STANDARD_FORMS."""
        cls._custom_forms = set(custom_forms)

    # Core identity
    id: str = Field(..., description="Unique identifier (filename without .md)")
    title: str = Field(..., description="Poem title from first # heading or filename")
    file_path: str = Field(..., description="Relative path from vault root")

    # Frontmatter: Required properties
    state: str = Field(..., description="Production state of the poem")

    # Deliberately `str`, not `Literal[...]`. A Literal is enforced by pydantic
    # before any field_validator runs, which made unknown forms a hard
    # ValidationError and dropped the whole poem from the catalog. Validation
    # now happens in validate_form below, which coerces instead of raising.
    form: str = Field(..., description="Structural/formal pattern")

    # Frontmatter: Optional properties
    tags: list[str] = Field(default_factory=list, description="Thematic tags for nexus connections")
    keywords: str | None = Field(
        default=None, description="Legacy comma-separated keywords (prefer tags)"
    )
    notes: str | None = Field(default=None, description="Editorial notes about the poem")

    # Computed metrics
    word_count: int = Field(..., description="Total word count")
    line_count: int = Field(..., description="Total line count")
    stanza_count: int | None = Field(
        default=None, description="Number of stanzas (blank-line separated)"
    )

    # Filesystem metadata
    created_at: datetime = Field(..., description="File creation timestamp")
    updated_at: datetime = Field(..., description="File modification timestamp")

    # Content (optional, for search/display)
    content: str | None = Field(
        default=None, description="Full poem text (only included if requested)"
    )

    # Quality scores (optional, for grading)
    qualities: dict[str, int] | None = Field(
        default=None, description="Quality scores (0-10) keyed by dimension name"
    )

    # Publication history. Non-empty means the poem is ineligible at any venue
    # that does not accept reprints. Each entry: venue, date, and optionally
    # issue, url, note.
    published: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Prior publications; non-empty means previously published",
    )

    @property
    def is_previously_published(self) -> bool:
        """True if this poem has any recorded prior publication."""
        return bool(self.published)

    # Chain membership (for linking poems into sequences or collections)
    chains: list[str] = Field(default_factory=list, description="Chain IDs this poem belongs to")
    chain_positions: dict[str, int] | None = Field(
        default=None,
        description="Position in ordered chains (chain_id -> position). Absence means loose collection.",
    )

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        """Validate state enum value (standard + custom states)."""
        standard_states = {"completed", "fledgeling", "still_cooking", "needs_research", "risk"}
        # Combine standard and custom states
        valid_states = standard_states | cls._custom_states

        if v not in valid_states:
            raise ValueError(
                f"Invalid state '{v}'. Must be one of: {', '.join(sorted(valid_states))}"
            )
        return v

    @field_validator("form")
    @classmethod
    def validate_form(cls, v: str) -> str:
        """Accept known forms; coerce anything else rather than rejecting the poem.

        Rejecting here would raise a ValidationError, which fails construction of
        the entire Poem and silently removes it from the catalog. Form is
        metadata, so an unrecognized value degrades to FALLBACK_FORM and logs a
        warning instead. Declare received forms in config.vault.custom_forms to
        keep them.
        """
        if v in STANDARD_FORMS | cls._custom_forms:
            return v
        logger.warning(
            "Unknown form %r; using %r instead. Add it to vault.custom_forms in "
            "config to keep the declared value.",
            v,
            FALLBACK_FORM,
        )
        return FALLBACK_FORM

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        """Normalize tags: lowercase, strip whitespace, remove duplicates."""
        if not v:
            return []
        normalized = [tag.lower().strip() for tag in v if tag.strip()]
        return list(dict.fromkeys(normalized))  # Preserve order, remove dupes

    @field_validator("qualities")
    @classmethod
    def validate_qualities(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        """Validate quality scores: 0-10 range, known dimension names."""
        if v is None:
            return None

        # 8 universal quality dimensions
        valid_dimensions = {
            "detail",
            "life",
            "music",
            "mystery",
            "sufficient thought",
            "surprise",
            "syntax",
            "unity",
        }

        # Normalize and validate
        normalized = {}
        for key, score in v.items():
            # Normalize key to lowercase
            key_lower = key.lower().strip()

            # Validate dimension name
            if key_lower not in valid_dimensions:
                raise ValueError(
                    f"Invalid quality dimension '{key}'. Must be one of: "
                    f"{', '.join(sorted(valid_dimensions))}"
                )

            # Validate score range
            if not isinstance(score, int) or score < 0 or score > 10:
                raise ValueError(f"Quality score for '{key}' must be integer 0-10, got: {score}")

            normalized[key_lower] = score

        # Return sorted by key for consistency
        return dict(sorted(normalized.items()))

    @field_validator("chains")
    @classmethod
    def normalize_chains(cls, v: list[str]) -> list[str]:
        """Normalize chain IDs: lowercase, replace spaces with hyphens, remove duplicates."""
        if not v:
            return []
        normalized = [chain.lower().strip().replace(" ", "-") for chain in v if chain.strip()]
        return list(dict.fromkeys(normalized))  # Preserve order, remove dupes

    @field_validator("chain_positions")
    @classmethod
    def validate_chain_positions(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        """Validate chain positions: positive integers only, normalize chain IDs."""
        if v is None:
            return None

        validated = {}
        for chain_id, position in v.items():
            chain_normalized = chain_id.lower().strip().replace(" ", "-")
            if not isinstance(position, int) or position < 1:
                raise ValueError(
                    f"Position for chain '{chain_id}' must be positive integer, got: {position}"
                )
            validated[chain_normalized] = position

        return validated

    model_config = ConfigDict(
        json_schema_extra={
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
                "updated_at": "2024-06-20T14:22:00Z",
                "qualities": {
                    "detail": 8,
                    "life": 7,
                    "music": 6,
                    "mystery": 9,
                    "surprise": 7,
                    "syntax": 8,
                    "unity": 9,
                },
                "chains": ["water-sequence", "random-snippets"],
                "chain_positions": {"water-sequence": 3},
            }
        }
    )
