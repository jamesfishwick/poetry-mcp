"""Pydantic model for Influence entity.

Influences are writers, movements, aesthetics, and cultural phenomena that
inform the poetry. Data comes from influences markdown files with frontmatter.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Influence(BaseModel):
    """
    Influence model representing writers, movements, and cultural influences.

    Five types of influences:
    - writer: Individual poets/authors
    - movement: Literary/cultural movements
    - aesthetic: Stylistic approaches
    - visual_artist: Artists in other media
    - cultural_influence: Broader cultural phenomena

    Influences exist as markdown files in influences/ directory.
    """

    name: str = Field(
        ...,
        description="Name of the influence (e.g., 'William Bronk', 'Extreme Metal')"
    )

    type: Literal[
        "writer",
        "movement",
        "aesthetic",
        "visual_artist",
        "cultural_influence"
    ] = Field(
        ...,
        description="Type of influence"
    )

    period: Optional[str] = Field(
        default=None,
        description="Time period or active years (e.g., '1940s-1999', 'Contemporary')"
    )

    bibliography: Optional[str] = Field(
        default=None,
        description="Key works (for writers), bibliography, or reference materials"
    )

    aesthetic: str = Field(
        ...,
        description="Aesthetic description, stylistic approach, or cultural impact"
    )

    file_path: Optional[str] = Field(
        default=None,
        description="Path to influence markdown file relative to vault root"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "name": "William Bronk",
                    "type": "writer",
                    "period": "1940s-1999",
                    "bibliography": "- The World, the Worldless\\n- Life Supports\\n- Vectors and Smoothable Curves",
                    "aesthetic": "Philosophical austerity, cosmic scale, metaphysical doubt. Stripped-down language exploring existence and nothingness.",
                    "file_path": "influences/William Bronk.md"
                },
                {
                    "name": "Extreme Metal",
                    "type": "cultural_influence",
                    "period": "1980s-present",
                    "bibliography": None,
                    "aesthetic": "Transgressive, visceral, confrontational. Explores violence, death, body horror. Sonic brutality as aesthetic stance.",
                    "file_path": "influences/Extreme Metal.md"
                },
                {
                    "name": "The Beats",
                    "type": "movement",
                    "period": "1950s-1960s",
                    "bibliography": "- Howl (Ginsberg)\\n- On the Road (Kerouac)\\n- Naked Lunch (Burroughs)",
                    "aesthetic": "Spontaneous composition, raw authenticity, rejection of conventional form. Jazz influence, American vernacular.",
                    "file_path": "influences/The Beats.md"
                }
            ]
        }
