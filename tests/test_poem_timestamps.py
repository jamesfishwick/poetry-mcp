"""Poem timestamps are timezone-aware in memory and RFC 3339 on the wire.

The Poem JSON schema declares created_at/updated_at as format "date-time",
which requires a UTC offset. MCP clients that validate structuredContent
against the tool's outputSchema (the TypeScript SDK does, with ajv-formats)
reject the whole get_poem response when the offset is missing. Symptom as it
surfaced in claude.ai: "The connector returned an error or an invalid
response." These tests guard the cause (an offset on the wire, one comparable
representation in memory), not that message. See Poem.ensure_aware.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

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


def _write_poem(catalog: Path, name: str, body: str) -> Path:
    poem_file = catalog / f"{name}.md"
    poem_file.write_text(f"---\nstate: completed\nform: free_verse\n---\n{body}", encoding="utf-8")
    return poem_file


def test_naive_timestamps_become_aware_at_construction():
    poem = _poem()
    assert poem.created_at.tzinfo is not None
    assert poem.updated_at.tzinfo is not None


def test_naive_timestamps_gain_an_offset_in_json_mode():
    data = _poem().model_dump(mode="json")
    for key in ("created_at", "updated_at"):
        assert RFC3339.match(data[key]), f"{key}={data[key]!r} is not RFC 3339"


def test_aware_timestamps_are_left_alone():
    utc = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
    assert _poem(created_at=utc).model_dump(mode="json")["created_at"] == "2024-01-01T10:30:00Z"

    # A non-UTC offset must survive as given, not be normalized to Z.
    ist = datetime(2024, 1, 1, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert (
        _poem(created_at=ist).model_dump(mode="json")["created_at"] == "2024-01-01T10:30:00+05:30"
    )


def test_python_mode_dump_keeps_datetime_objects():
    # get_poem_impl round-trips through Poem(**poem.model_dump()); the validator
    # must not turn those fields into strings in python mode.
    data = _poem().model_dump()
    assert isinstance(data["created_at"], datetime)
    assert isinstance(data["updated_at"], datetime)
    assert Poem(**data).created_at == data["created_at"]


def test_parser_produces_aware_timestamps_for_the_right_instant(tmp_path: Path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    poem_file = catalog / "no-frontmatter.md"
    poem_file.write_text("\nONE LINE\nTWO LINE\n", encoding="utf-8")

    poem = parse_poem_file(poem_file, tmp_path)

    stat = poem_file.stat()
    assert poem.created_at.tzinfo is not None
    assert poem.updated_at.tzinfo is not None
    assert poem.created_at.timestamp() == pytest.approx(stat.st_ctime)
    assert poem.updated_at.timestamp() == pytest.approx(stat.st_mtime)


def test_parsed_and_constructed_poems_sort_together(tmp_path: Path):
    # catalog_tools.query_poems and Catalog.get_stats sort on these fields.
    # A naive/aware mix raises TypeError, so every constructor must agree.
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    parsed = parse_poem_file(_write_poem(catalog, "parsed", "A line\n"), tmp_path)

    ordered = sorted([parsed, _poem()], key=lambda p: p.created_at)

    assert ordered[0] is not ordered[1]


@pytest.mark.asyncio
async def test_tool_structured_content_timestamps_are_rfc3339(tmp_path: Path):
    """The layer that broke: structuredContent as an MCP client receives it."""
    vault = tmp_path / "vault"
    catalog = vault / "catalog"
    catalog.mkdir(parents=True)
    _write_poem(catalog, "wire-poem", "First line\nSecond line\n")

    import poetry_mcp.server as server_module

    config = Mock(
        vault=Mock(path=vault, exclude_catalog_dirs=[], custom_states=[], custom_forms=[]),
        search=Mock(default_limit=20),
    )
    # query_poems_impl imports load_config from poetry_mcp.config directly, so
    # patching the server's name alone leaves it reading the real config (or,
    # on a machine with none, raising "No configuration found").
    with (
        patch("poetry_mcp.server.load_config", return_value=config),
        patch("poetry_mcp.tools.catalog_tools.load_config", return_value=config),
    ):
        server_module.catalog = None
        server_module.get_catalog().sync()
        try:
            async with Client(server_module.mcp) as client:
                tools = {t.name: t for t in await client.list_tools()}
                for name in ("get_poem", "query_poems"):
                    assert '"date-time"' in json.dumps(tools[name].outputSchema), name

                found = await client.call_tool("get_poem", {"identifier": "wire-poem"})
                poem = found.structured_content["result"]
                for key in ("created_at", "updated_at"):
                    assert RFC3339.match(poem[key]), f"get_poem {key}={poem[key]!r}"

                listed = await client.call_tool("query_poems", {"limit": 10})
                assert listed.structured_content["poems"], "query_poems returned no poems"
                for entry in listed.structured_content["poems"]:
                    for key in ("created_at", "updated_at"):
                        assert RFC3339.match(entry[key]), f"query_poems {key}={entry[key]!r}"
        finally:
            server_module.catalog = None
