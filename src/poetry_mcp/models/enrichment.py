"""Pydantic models for enrichment tool responses."""

from typing import List
from pydantic import BaseModel, Field


class ThemeSuggestion(BaseModel):
    """A suggested theme for a poem."""

    name: str = Field(
        ...,
        description="Theme name (e.g., 'Water-Liquid', 'Childhood')"
    )

    canonical_tag: str = Field(
        ...,
        description="Canonical tag for frontmatter (e.g., 'water-liquid', 'childhood')"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0"
    )

    evidence: str = Field(
        ...,
        description="Brief textual evidence for this theme"
    )


class ThemeDetectionResult(BaseModel):
    """Result of theme detection for a single poem."""

    themes: List[ThemeSuggestion] = Field(
        default_factory=list,
        description="List of detected themes with confidence scores"
    )


class EnrichmentSuggestion(BaseModel):
    """Enrichment suggestion for a poem (for batch processing)."""

    poem_id: str
    poem_title: str
    suggested_themes: List[ThemeSuggestion]
    auto_applied: bool = False
    auto_applied_tags: List[str] = Field(default_factory=list)


class BatchEnrichmentResult(BaseModel):
    """Result of batch enrichment operation."""

    total_poems_analyzed: int
    total_suggestions: int
    auto_applied_count: int
    manual_review_count: int
    auto_applied_tags: List[str] = Field(default_factory=list)
    requires_review: List[EnrichmentSuggestion] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0
