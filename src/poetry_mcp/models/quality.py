"""Pydantic model for Quality entity.

Quality dimensions define rating scales with rubrics for scoring poems.
Data comes from Qualities markdown files with frontmatter.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Quality(BaseModel):
    """
    Quality dimension model for poem scoring.

    8 Universal Quality Dimensions:
    - Detail: Concrete sensory specificity
    - Life: Vitality, breathing quality
    - Music: Sound patterns, rhythm
    - Mystery: Ambiguity, layers, engagement
    - Sufficient Thought: Intellectual depth
    - Surprise: Unexpected elements, fresh perspectives
    - Syntax: Sentence structure, line breaks
    - Unity: Coherence, wholeness

    Each quality has a scale (0-10) and a rubric description.
    """

    name: str = Field(
        ..., description="Quality dimension name (e.g., 'Detail', 'Surprise', 'Music')"
    )

    scale_min: int = Field(default=0, description="Minimum score on this scale (typically 0)")

    scale_max: int = Field(default=10, description="Maximum score on this scale (typically 10)")

    description: str = Field(
        ..., description="Rubric describing what scores mean on this dimension"
    )

    file_path: Optional[str] = Field(
        default=None, description="Path to individual quality note file"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Detail",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Grounds abstract concepts in concrete sensory experience. 0 = purely abstract, 10 = richly concrete.",
                    "file_path": "Qualities/Detail.md",
                },
                {
                    "name": "Surprise",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Unexpected turns, fresh imagery, defamiliarization. 0 = clichéd/predictable, 10 = radically new perspective.",
                    "file_path": "Qualities/Surprise.md",
                },
                {
                    "name": "Music",
                    "scale_min": 0,
                    "scale_max": 10,
                    "description": "Sound quality, rhythmic elements, sonic patterns. 0 = flat/prosaic, 10 = exceptional musicality.",
                    "file_path": "Qualities/Music.md",
                },
            ]
        }
    )


class QualityRegistry(BaseModel):
    """
    Complete quality registry with 8 universal dimensions.

    Returned by get_all_qualities() tool (if implemented).
    """

    qualities: list[Quality] = Field(
        default_factory=list, description="All quality dimensions (8 universal dimensions)"
    )

    total_count: int = Field(..., description="Total number of quality dimensions (should be 8)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qualities": [
                    {
                        "name": "Detail",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Concrete sensory specificity",
                    },
                    {
                        "name": "Life",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Vitality, breathing quality",
                    },
                    {
                        "name": "Music",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Sound patterns, rhythm",
                    },
                    {
                        "name": "Mystery",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Ambiguity, layers, engagement",
                    },
                    {
                        "name": "Sufficient Thought",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Intellectual depth",
                    },
                    {
                        "name": "Surprise",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Unexpected elements, fresh perspectives",
                    },
                    {
                        "name": "Syntax",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Sentence structure, line breaks",
                    },
                    {
                        "name": "Unity",
                        "scale_min": 0,
                        "scale_max": 10,
                        "description": "Coherence, wholeness",
                    },
                ],
                "total_count": 8,
            }
        }
    )
