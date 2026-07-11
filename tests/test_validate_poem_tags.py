"""Regression test for validate_poem_tags and the startup validation path.

validate_poem_tags called `await get_all_nexuses()` (a non-callable
FunctionTool) and the startup block then dict-subscripted its result
(`validation_result['valid']`), even though the tool returns a
ValidationResult model. Both raised at runtime. This locks the contract the
startup block depends on: the tool returns a ValidationResult whose fields
are read as attributes.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import poetry_mcp.server as server_module
from poetry_mcp.models.results import ValidationResult


def test_validate_poem_tags_returns_model_with_attribute_fields():
    # One poem with a valid tag, one with a tag that matches no nexus.
    good = Mock(id="p1", title="Good", tags=["water"], file_path="catalog/p1.md")
    bad = Mock(id="p2", title="Bad", tags=["not_a_nexus"], file_path="catalog/p2.md")
    cat = Mock()
    cat.index.all_poems = [good, bad]

    theme = Mock()
    theme.canonical_tag = "water"
    registry = Mock(themes=[theme], motifs=[], forms=[])

    # get_all_nexuses is a FunctionTool; validate_poem_tags calls it via `.fn()`.
    nexuses_tool = Mock(fn=AsyncMock(return_value=registry))

    with patch.object(server_module, "get_catalog", return_value=cat), patch.object(
        server_module, "get_all_nexuses", nexuses_tool
    ):
        result = asyncio.run(server_module.validate_poem_tags.fn())

    # The startup block reads these as ATTRIBUTES (dict-subscript used to fail).
    assert isinstance(result, ValidationResult)
    assert result.valid is False
    assert "not_a_nexus" in result.invalid_tags
    assert result.violations_count == 1
    assert len(result.affected_poems) == 1
