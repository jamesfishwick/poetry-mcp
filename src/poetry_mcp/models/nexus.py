"""Pydantic model for Nexus entity.

Nexuses are thematic/formal connection points for poems.
Data comes from nexus markdown files and nexus.base view definition.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Nexus(BaseModel):
    """
    Nexus model representing a thematic/formal connection point.

    Three types of nexuses:
    - theme: Subject matter, imagery systems (water, body, death, etc.)
    - motif: Compositional patterns requiring multiple themes
    - form: Structural patterns (american sentence, catalog poem, etc.)

    Nexuses exist as markdown files in nexus/themes, nexus/motifs, nexus/forms
    directories, with metadata in frontmatter.
    """

    name: str = Field(
        ..., description="Nexus name (e.g., 'Water-Liquid Imagery', 'American Sentence')"
    )

    category: Literal["theme", "motif", "form"] = Field(..., description="Type of nexus")

    description: str = Field(..., description="What this nexus represents, usage patterns")

    file_path: str | None = Field(
        default=None, description="Path to nexus markdown file relative to vault root"
    )

    # Optional: canonical tag for frontmatter tagging
    canonical_tag: str | None = Field(
        default=None,
        description="Canonical tag name for poems (e.g., 'water', 'american-sentence')",
    )

    # Optional: count of linked poems (computed)
    poem_count: int | None = Field(
        default=None, description="Number of poems connected to this nexus (computed)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Water-Liquid Imagery",
                    "category": "theme",
                    "description": "Water, blood, beer, tears, spit - liquids as transformation and dissolution",
                    "file_path": "nexus/themes/Water-Liquid Imagery.md",
                    "canonical_tag": "water",
                    "poem_count": 23,
                },
                {
                    "name": "American Grotesque",
                    "category": "motif",
                    "description": "Bodies consuming beyond capacity, caught between spiritual hunger and material satiation",
                    "file_path": "nexus/motifs/American Grotesque.md",
                    "canonical_tag": "american-grotesque",
                    "poem_count": 8,
                },
                {
                    "name": "American Sentence",
                    "category": "form",
                    "description": "One line, exactly 17 syllables - Ginsberg's American answer to haiku",
                    "file_path": "nexus/forms/American Sentence.md",
                    "canonical_tag": "american-sentence",
                    "poem_count": 12,
                },
            ]
        }
    )


class NexusRegistry(BaseModel):
    """
    Complete nexus registry organized by category.

    Returned by get_all_nexuses() tool.
    """

    themes: list[Nexus] = Field(
        default_factory=list, description="Thematic nexuses (imagery systems, subjects)"
    )

    motifs: list[Nexus] = Field(
        default_factory=list, description="Motif nexuses (compositional patterns)"
    )

    forms: list[Nexus] = Field(
        default_factory=list, description="Form nexuses (structural patterns)"
    )

    total_count: int = Field(..., description="Total number of nexuses across all categories")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "themes": [
                    {
                        "name": "Water-Liquid Imagery",
                        "category": "theme",
                        "description": "Water, blood, beer, tears, spit",
                        "file_path": "nexus/themes/Water-Liquid Imagery.md",
                    }
                ],
                "motifs": [
                    {
                        "name": "American Grotesque",
                        "category": "motif",
                        "description": "Bodies consuming beyond capacity",
                        "file_path": "nexus/motifs/American Grotesque.md",
                    }
                ],
                "forms": [
                    {
                        "name": "American Sentence",
                        "category": "form",
                        "description": "One line, exactly 17 syllables",
                        "file_path": "nexus/forms/American Sentence.md",
                    }
                ],
                "total_count": 3,
            }
        }
    )
