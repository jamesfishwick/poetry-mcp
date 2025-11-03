"""
Submission data model.

Represents transactional submission tracking data: what was submitted,
when, to where, and what the outcome was.
"""

from typing import Optional, Literal
from datetime import date
from pydantic import BaseModel, Field, validator


SubmissionStatus = Literal[
    "planned",  # Considering for this venue, not yet submitted
    "submitted",  # Submitted and awaiting response
    "accepted",  # Accepted for publication
    "rejected",  # Rejected
    "withdrawn",  # Withdrawn by author before decision
]


class Submission(BaseModel):
    """
    Submission tracking record.

    Represents a single submission event: poems sent to a venue,
    tracking dates, status, costs, and outcomes.
    """

    # Core identity
    venue_name: str = Field(
        ...,
        description="Name of the venue this submission is for",
        examples=["Palette Poetry", "Rattle", "The Georgia Review"],
    )

    poems: list[str] = Field(
        ...,
        description="List of poem titles included in this submission",
        min_items=1,
        examples=[["Second Bridge Out Old Route 12"], ["Dead Deer", "Black Bread", "The Formula"]],
    )

    # Submission lifecycle
    status: SubmissionStatus = Field("planned", description="Current status of this submission")

    submitted: bool = Field(
        False, description="Whether this has actually been submitted (vs. planned)"
    )

    # Dates
    submitted_date: Optional[date | str] = Field(
        None, description="Date when submission was sent", examples=["2025-08-15", "2025-August"]
    )

    due_date: Optional[date | str] = Field(
        None,
        description="Submission deadline (for planned submissions)",
        examples=["2025-10-31", "2025-October"],
    )

    response_date: Optional[date | str] = Field(
        None,
        description="Expected response date or actual response date",
        examples=["2025-11-15", "2025-November"],
    )

    # Financial
    cost: Optional[str] = Field(
        None, description="Reading fee or submission cost", examples=["$3", "free", "$5"]
    )

    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes about this submission")

    # Source tracking for debugging/auditing
    source_file: Optional[str] = Field(
        None, description="Source file where this submission was parsed from"
    )

    @validator("status", always=True)
    def sync_status_with_submitted(cls, v: str, values: dict) -> str:
        """Ensure status and submitted flag are consistent."""
        submitted: bool = values.get("submitted", False)  # type: ignore

        # If submitted=True but status is 'planned', upgrade to 'submitted'
        if submitted and v == "planned":
            return "submitted"

        # If status is 'submitted'/'accepted'/'rejected' but submitted=False, fix it
        if v in ("submitted", "accepted", "rejected") and not submitted:
            values["submitted"] = True

        return v

    @property
    def poem_count(self) -> int:
        """Number of poems in this submission."""
        return len(self.poems)

    @property
    def is_active(self) -> bool:
        """Whether this submission is actively pending response."""
        return self.status == "submitted" and self.submitted

    @property
    def is_completed(self) -> bool:
        """Whether this submission has reached a final state."""
        return self.status in ("accepted", "rejected", "withdrawn")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "examples": [
                {
                    "venue_name": "Palette Poetry",
                    "poems": ["Second Bridge Out Old Route 12", "Ceramics", "About the Moon"],
                    "status": "submitted",
                    "submitted": True,
                    "submitted_date": "2025-07-15",
                    "response_date": "2025-10-15",
                    "cost": "$3",
                    "notes": None,
                },
                {
                    "venue_name": "Frontier Poetry",
                    "poems": ["The Formula", "Refugees", "Affirm Megiddo"],
                    "status": "planned",
                    "submitted": False,
                    "due_date": "2025-11-01",
                    "cost": "free",
                    "notes": "Good fit for experimental work",
                },
            ]
        }


class SubmissionSummary(BaseModel):
    """
    Aggregated submission statistics.

    Useful for dashboard views and reporting.
    """

    total_submissions: int = Field(..., description="Total number of submission records")

    by_status: dict[SubmissionStatus, int] = Field(
        default_factory=dict, description="Count of submissions by status"
    )

    active_submissions: int = Field(
        0, description="Number of submissions currently pending response"
    )

    total_poems_submitted: int = Field(
        0, description="Total number of individual poems across all submissions"
    )

    acceptance_rate: Optional[float] = Field(
        None, description="Percentage of completed submissions that were accepted"
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "total_submissions": 25,
                "by_status": {
                    "planned": 5,
                    "submitted": 8,
                    "accepted": 3,
                    "rejected": 9,
                    "withdrawn": 0,
                },
                "active_submissions": 8,
                "total_poems_submitted": 67,
                "acceptance_rate": 25.0,
            }
        }
