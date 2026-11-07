"""Poem timestamps must serialize as RFC 3339 date-time.

The Poem JSON schema declares created_at/updated_at as format "date-time".
A naive datetime's isoformat() carries no UTC offset, which fails that format,
and MCP clients that validate structuredContent against the tool's output
schema (the TypeScript SDK behind claude.ai and Claude Desktop) reject the
entire get_poem response: "The connector returned an error or an invalid
response." Regression for that.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from poetry_mcp.models.poem import Poem
from poetry_mcp.parsers.frontmatter_parser import parse_poem_file

# RFC 3339 date-time: date, "T", time, then "Z" or a numeric offset.
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def _poem(**overrides) -> Poem:
    fields = dict(
        id="t",
        title="T",
        file_path="catalog/t.md",
        state="completed",
        form="free_verse",
        word_count=10,
        line_count=2,
        created_at=datetime(2024, 1, 1, 10, 30),
        updated_at=datetime(2024, 6, 1, 14, 22),
    )
    fields.update(overrides)
    return Poem(**fields)


def test_naive_timestamps_gain_an_offset_in_json_mode():
    data = _poem().model_dump(mode="json")
    for key in ("created_at", "updated_at"):
        assert RFC3339.match(data[key]), f"{key}={data[key]!r} is not RFC 3339"


def test_aware_timestamps_are_left_alone():
    created = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
    data = _poem(created_at=created).model_dump(mode="json")
    assert data["created_at"] == "2024-01-01T10:30:00Z"


def test_python_mode_dump_keeps_datetime_objects():
    # get_poem_impl round-trips through Poem(**poem.model_dump()); the guard
    # must not turn those fields into strings in python mode.
    data = _poem().model_dump()
    assert isinstance(data["created_at"], datetime)
    assert isinstance(data["updated_at"], datetime)
    assert Poem(**data).created_at == data["created_at"]


def test_parser_produces_aware_timestamps(tmp_path: Path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    poem_file = catalog / "no-frontmatter.md"
    poem_file.write_text("\nONE LINE\nTWO LINE\n", encoding="utf-8")

    poem = parse_poem_file(poem_file, tmp_path)

    assert poem.created_at.tzinfo is not None
    assert poem.updated_at.tzinfo is not None
    data = poem.model_dump(mode="json")
    assert RFC3339.match(data["created_at"])
    assert RFC3339.match(data["updated_at"])
