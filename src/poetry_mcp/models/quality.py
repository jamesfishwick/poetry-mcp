"""Pydantic model for Quality entity.

Quality dimensions define rating scales with rubrics for scoring poems.
Data comes from Qualities markdown files with frontmatter.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Quality(BaseModel):
    """
    Quality dimension model for poem scoring.

    Three categories:
    - craft: Technical craft dimensions (Surprise, Music, Detail, etc.)
    - aesthetic: Aesthetic dimensions (Life, Visceral, Punk Aesthetic, etc.)
    - accessibility: Reader accessibility dimension

    Each quality has a scale (typically 0-10) and a rubric description.
    """

    name: str = Field(
        ...,
        description="Quality dimension name (e.g., 'Surprise', 'Visceral')"
    )

    category: Literal["craft", "aesthetic", "accessibility"] = Field(
        ...,
        description="Quality category"
    )

    scale_min: int = Field(
        default=0,
        description="Minimum score on this scale (typically 0)"
    )

    scale_max: int = Field(
        default=10,
        description="Maximum score on this scale (typically 10)"
    )

    description: str = Field(
        ...,
        description="Rubric describing what scores mean on this dimension"
    )

    file_path: Optional[str] = Field(
        default=None,
        description="Path to individual quality note file"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "name": "Surprise",
                    "category": "craft",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Unexpected turns, fresh imagery, defamiliarization. 10 = radically new perspective. 0 = clichéd, predictable.",
                    "file_path": "Qualities/Surprise.md"
                },
                {
                    "name": "Visceral",
                    "category": "aesthetic",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Physical immediacy, body-focused language. 10 = makes you taste/feel/flinch. 0 = purely cerebral, disembodied.",
                    "file_path": "Qualities/Visceral.md"
                },
                {
                    "name": "Accessible",
                    "category": "accessibility",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Clarity for general readers. 10 = immediately graspable. 0 = requires extensive context/research.",
                    "file_path": "Qualities/Accessible.md"
                }
            ]
        }


class QualityRegistry(BaseModel):
    """
    Complete quality registry organized by category.

    Returned by get_all_qualities() tool.
    """

    craft: list[Quality] = Field(
        default_factory=list,
        description="Craft quality dimensions (7 dimensions)"
    )

    aesthetic: list[Quality] = Field(
        default_factory=list,
        description="Aesthetic quality dimensions (4 dimensions)"
    )

    accessibility: list[Quality] = Field(
        default_factory=list,
        description="Accessibility dimension (1 dimension)"
    )

    total_count: int = Field(
        ...,
        description="Total number of quality dimensions"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "craft": [
                    {
                        "name": "Surprise",
                        "category": "craft",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Unexpected turns, fresh imagery"
                    },
                    {
                        "name": "Music",
                        "category": "craft",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Sonic qualities, rhythm, sound patterns"
                    }
                ],
                "aesthetic": [
                    {
                        "name": "Visceral",
                        "category": "aesthetic",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Physical immediacy, body-focused language"
                    }
                ],
                "accessibility": [
                    {
                        "name": "Accessible",
                        "category": "accessibility",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Clarity for general readers"
                    }
                ],
                "total_count": 12
            }
        }
