"""Regression test for delete_nexus(cleanup_poems=True).

This path was broken two ways, both silent:
  1. It called `await get_all_nexuses()`, but @mcp.tool wraps that in a
     non-callable FunctionTool, so it raised TypeError before doing anything.
  2. The tag-removal called `update_poem_tags(poem_path=..., tags_to_remove=...)`
     without importing the function and with the wrong keyword (the parameter
     is `file_path`) and an unresolved vault-relative path.

Both failures sat inside a broad try/except, so the tool reported success with
poems_cleaned=0 instead of raising. This test drives the real cleanup with a
real poem file and asserts the tag is actually removed and counted.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import poetry_mcp.server as server_module


def _write_tagged_poem(tmp_path):
    vault = tmp_path / "vault"
    (vault / "catalog").mkdir(parents=True)
    poem_file = vault / "catalog" / "obsolete_poem.md"
    poem_file.write_text(
        "---\n"
        "state: completed\n"
        "tags:\n"
        "  - obsolete\n"
        "  - keep\n"
        "---\n\n"
        "# A Poem\n\nBody line\n"
    )
    return vault, poem_file


def test_delete_nexus_cleanup_removes_tag_and_counts(tmp_path):
    vault, poem_file = _write_tagged_poem(tmp_path)

    # The catalog index stores a vault-relative file_path.
    poem = Mock(title="A Poem", file_path="catalog/obsolete_poem.md")
    cat = Mock()
    cat.vault_root = vault
    cat.index.get_by_tag.return_value = [poem]

    theme = Mock()
    theme.name = "Obsolete"
    theme.canonical_tag = "obsolete"
    registry = Mock(themes=[theme], motifs=[], forms=[])

    manager = Mock()
    manager.delete_nexus.return_value = {"deleted": "nexus/themes/obsolete.md"}

    # get_all_nexuses is a FunctionTool; delete_nexus calls it via `.fn()`.
    nexuses_tool = Mock(fn=AsyncMock(return_value=registry))

    with patch.object(server_module, "get_catalog", return_value=cat), patch.object(
        server_module, "get_all_nexuses", nexuses_tool
    ), patch.object(server_module, "get_nexus_manager", return_value=manager), patch.object(
        server_module, "initialize_enrichment_tools"
    ):
        result = asyncio.run(
            server_module.delete_nexus.fn(
                name="Obsolete", category="theme", cleanup_poems=True, force=True
            )
        )

    assert result.success is True
    # Before the fix this was silently 0 (swallowed TypeError/NameError).
    assert result.poems_cleaned == 1

    updated = poem_file.read_text()
    assert "obsolete" not in updated  # the tag was actually removed
    assert "keep" in updated  # sibling tags preserved


def test_delete_nexus_cleanup_surfaces_partial_failures(tmp_path):
    """A poem that fails cleanup must be reported, not silently dropped."""
    vault, _poem_file = _write_tagged_poem(tmp_path)

    good = Mock(title="A Poem", file_path="catalog/obsolete_poem.md")
    # Second poem points at a file that doesn't exist -> update_poem_tags fails.
    missing = Mock(title="Ghost", file_path="catalog/does_not_exist.md")
    cat = Mock()
    cat.vault_root = vault
    cat.index.get_by_tag.return_value = [good, missing]

    theme = Mock()
    theme.name = "Obsolete"
    theme.canonical_tag = "obsolete"
    registry = Mock(themes=[theme], motifs=[], forms=[])

    manager = Mock()
    manager.delete_nexus.return_value = {"deleted": "nexus/themes/obsolete.md"}
    nexuses_tool = Mock(fn=AsyncMock(return_value=registry))

    with patch.object(server_module, "get_catalog", return_value=cat), patch.object(
        server_module, "get_all_nexuses", nexuses_tool
    ), patch.object(server_module, "get_nexus_manager", return_value=manager), patch.object(
        server_module, "initialize_enrichment_tools"
    ):
        result = asyncio.run(
            server_module.delete_nexus.fn(
                name="Obsolete", category="theme", cleanup_poems=True, force=True
            )
        )

    assert result.poems_cleaned == 1
    assert result.poems_failed == 1  # was silently 0 before
    assert len(result.cleanup_errors) == 1
    assert "Ghost" in result.cleanup_errors[0]
