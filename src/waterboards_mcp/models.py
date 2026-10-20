"""Pydantic models and enums for tool parameters and responses.

Typed parameters give MCP clients a precise schema, which helps the LLM call
your tools correctly. Prefer enums for closed sets of values and Pydantic
models for structured inputs/outputs.

These are illustrative — replace them with models for your own service.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

ZipCode = Annotated[
    str,
    Field(pattern=r"^\d{5}$", description="5-digit US ZIP code, e.g. 94103."),
]

KM_PER_MILE = 1.609344

# Gold distance pairs are precomputed up to 50 km (~31 miles).
RadiusMiles = Annotated[
    float,
    Field(ge=1, le=31, description="Search radius in miles (1-31)."),
]


PwsId = Annotated[
    str,
    Field(
        pattern=r"^CA\d{7}$",
        description="California public water system ID, e.g. CA0110005.",
    ),
]

ChemicalName = Annotated[
    str,
    Field(
        pattern=r"^[A-Za-z0-9 ,()\-]{2,60}$",
        description="Chemical name or fragment, e.g. 'arsenic' or 'nitrate'.",
    ),
]


class ResponseFormat(str, Enum):
    """How a tool should shape its return value.

    - JSON     → machine-readable dict/list (best for chaining tool calls)
    - MARKDOWN → human-readable text (best for direct display)
    """

    JSON = "json"
    MARKDOWN = "markdown"


class PaginationParams(BaseModel):
    """Reusable pagination inputs for list-style tools.

    Federal APIs almost always paginate. Expose these to the caller (or handle
    paging internally) and return `has_more` / `next_offset` in your response.
    """

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return (1–100).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip from the start of the result set.",
    )
