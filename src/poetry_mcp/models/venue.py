"""
Venue data model.

Represents metadata about a publication venue (journal, magazine, press).
This is relatively static information about the venue itself.
"""

from typing import Optional
from pydantic import BaseModel, HttpUrl, Field, ConfigDict


class Venue(BaseModel):
    """
    Publication venue metadata.

    Represents the static information about a venue: payment rates,
    response times, editorial aesthetic, and submission requirements.
    """

    name: str = Field(
        ...,
        description="Full name of the venue",
        examples=["Palette Poetry", "Rattle", "The Georgia Review"],
    )

    payment: Optional[str] = Field(
        None,
        description="Payment information: specific amount, 'yes', 'no', or 'unknown'",
        examples=["$50/poem", "$50 + 2 copies", "yes", "no", "unknown"],
    )

    response_time_days: Optional[int | str] = Field(
        None,
        description="Expected response time in days, or 'unknown'/'check'",
        examples=[30, 90, 180, "unknown", "check"],
    )

    simultaneous: Optional[str | bool] = Field(
        None,
        description="Accepts simultaneous submissions: yes/no/check",
        examples=["yes", "no", "check", True, False],
    )

    aesthetic: Optional[str] = Field(
        None,
        description="Editorial focus, aesthetic preferences, themes",
        examples=[
            "Highly selective, innovative poetry, marginalized voices prioritized",
            "Accessible poetry, conversation-driven",
            "Dark publishing house, horror/weird",
        ],
    )

    url: Optional[HttpUrl] = Field(None, description="Venue website URL")

    submission_format: Optional[str] = Field(
        None,
        description="Technical submission requirements",
        examples=[
            "Up to 5 poems, max 10 pages, all in ONE doc",
            "Online form, name & page numbers in header",
            "Max 3 poems per submission",
        ],
    )

    submission_frequency: Optional[str] = Field(
        None,
        description="Submission window schedule",
        examples=["Quarterly (solstice/equinox)", "Year-round", "September 1 - November 30"],
    )

    # File location for roundtrip editing
    file_path: Optional[str] = Field(None, description="Path to the venue's markdown file")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Palette Poetry",
                "payment": "$50/poem",
                "response_time_days": 90,
                "simultaneous": "yes",
                "aesthetic": "Highly selective, innovative poetry, marginalized voices prioritized",
                "url": "https://palettepoetry.com",
                "submission_format": "Up to 5 poems, max 10 pages, all in ONE doc",
                "file_path": "/Users/jamesfishwick/.local/share/obsidian/art/Poetry/venues/Palette Poetry.md",
            }
        }
    )
