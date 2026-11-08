"""Every MCP tool answers a valid call with structuredContent that matches its own outputSchema.

This is the contract an MCP client enforces. The TypeScript SDK validates
structuredContent against outputSchema with ajv-formats, so a response that
breaks the schema is thrown away whole and the user sees "The connector
returned an error or an invalid response." Unit tests on the Python objects
cannot see that boundary. This file drives the real server through an
in-memory fastmcp client against a scratch vault and validates each reply
with a format-checking JSON Schema validator.

The cases run in one session, in order, because later tools read state that
earlier ones write (a chain must exist before get_chain). Failures are
collected per tool and reported together so one bad tool does not hide the
rest.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator, FormatChecker

import poetry_mcp.server as server_module
from poetry_mcp.config import PoetryMCPConfig, VaultConfig
from poetry_mcp.parsers.nexus_parser import load_nexus_registry
from poetry_mcp.tools.chain_tools import initialize_chain_tools
from poetry_mcp.tools.enrichment_tools import initialize_enrichment_tools
from poetry_mcp.tools.similarity_tools import initialize_similarity_tools

# Every module that does `from ..config import load_config` binds its own name.
# Patching only the server's name leaves the rest reading the real config.
LOAD_CONFIG_SITES = [
    "poetry_mcp.server.load_config",
    "poetry_mcp.tools.catalog_tools.load_config",
    "poetry_mcp.tools.enrichment_tools.load_config",
    "poetry_mcp.tools.nexus_tools.load_config",
    "poetry_mcp.tools.submission_tools.load_config",
    "poetry_mcp.tools.venue_tools.load_config",
]

# (tool name, arguments). Order matters: it is one session against one vault.
CASES: list[tuple[str, dict]] = [
    ("sync_catalog", {}),
    ("get_server_info", {}),
    ("get_poem", {"identifier": "water"}),
    ("query_poems", {"limit": 10}),
    ("get_all_nexuses", {}),
    ("find_nexuses_for_poem", {"poem_id": "water"}),
    ("link_poem_to_nexus", {"poem_id": "fire", "nexus_name": "Childhood"}),
    ("get_poems_for_enrichment", {"max_poems": 5}),
    ("sync_nexus_tags", {"poem_id": "water"}),
    ("grade_poem_quality", {"poem_id": "water"}),
    ("commit_quality_scores", {"poem_id": "water", "scores": {"music": 7, "unity": 6}}),
    ("get_quality_scores", {"poem_id": "water"}),
    ("validate_poem_tags", {}),
    ("refresh_nexus_poem_counts", {}),
    (
        "create_nexus",
        {"name": "Rust", "category": "theme", "canonical_tag": "rust", "description": "Decay."},
    ),
    ("delete_nexus", {"name": "Rust", "category": "theme", "force": True}),
    ("create_chain", {"chain_id": "test-chain", "poem_ids": ["water", "earth"], "ordered": True}),
    ("add_poems_to_chain", {"chain_id": "test-chain", "poem_ids": ["fire"]}),
    ("reorder_chain", {"chain_id": "test-chain", "poem_order": ["earth", "water", "fire"]}),
    ("get_chain", {"chain_id": "test-chain"}),
    ("list_chains", {}),
    ("remove_poems_from_chain", {"chain_id": "test-chain", "poem_ids": ["fire"]}),
    ("delete_chain", {"chain_id": "test-chain"}),
    ("find_similar_poems", {"poem_id": "water", "limit": 3}),
    ("move_poem_to_state", {"poem_id": "fire", "new_state": "completed"}),
    ("sync_venues", {}),
    ("list_venues", {}),
    ("get_venue", {"venue_name": "Minimal Journal"}),
    ("regenerate_venue_file", {"venue_name": "Minimal Journal"}),
    ("sync_submissions", {}),
    ("list_submissions", {}),
    ("create_submission", {"venue_name": "Minimal Journal", "poems": ["Water Poem"]}),
    (
        "update_submission_status",
        {"new_status": "accepted", "venue": "Minimal Journal", "dry_run": True},
    ),
    ("get_submission_stats", {}),
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def contract_vault(tmp_path: Path) -> Path:
    """A vault with every kind of record a tool can touch."""
    vault = tmp_path / "vault"
    _write(
        vault / "catalog" / "completed" / "water.md",
        "---\nstate: completed\nform: free_verse\ntags:\n  - water-liquid\n---\n\n"
        "# Water Poem\n\nWater flows through [[Water-Liquid]] imagery\n"
        "Deep and mysterious [[Body-Bones]] references\nClear as crystal\n",
    )
    _write(
        vault / "catalog" / "completed" / "earth.md",
        "---\nstate: completed\nform: american_sentence\ntags:\n  - body-bones\n  - childhood\n---\n\n"
        "# Earth Poem\n\nEarth holds memories of childhood summers and broken bones.\n",
    )
    _write(
        vault / "catalog" / "fledgeling" / "fire.md",
        "---\nstate: fledgeling\nform: free_verse\n---\n\n# Fire Poem\n\nFire burns bright\nNo tags yet\n",
    )
    for category, name, tag, blurb in [
        ("themes", "Water-Liquid", "water-liquid", "Liquids as transformation."),
        ("themes", "Body-Bones", "body-bones", "Corporeal existence."),
        ("themes", "Childhood", "childhood", "Formative experiences."),
        ("motifs", "American Grotesque", "american-grotesque", "Disturbing beauty."),
        ("forms", "Catalog Poem", "catalog-poem", "Anaphora and list structure."),
    ]:
        _write(
            vault / "nexus" / category / f"{name}.md",
            f"---\ncanonical_tag: {tag}\n---\n\n# {name}\n\n{blurb}\n",
        )
    _write(
        vault / "venues" / "minimal-journal.md",
        "---\nname: Minimal Journal\nurl: https://minimal.com\n---\n\n# Minimal Journal\n\n"
        "A minimal journal with no submissions.\n",
    )
    _write(
        vault / "submissions" / "2025-01-01_Earth_MinimalJournal.md",
        "---\nvenue_name: Minimal Journal\nstatus: submitted\nsubmitted_date: 2025-01-01\n---\n\n"
        "## Poems\n[[Earth Poem]]\n",
    )
    (vault / "Qualities").mkdir()
    return vault


@pytest.fixture
def served_vault(contract_vault: Path):
    """Point the module-global server at the scratch vault, the way main() does."""
    config = PoetryMCPConfig(vault=VaultConfig(path=contract_vault))
    patches = [patch(site, return_value=config) for site in LOAD_CONFIG_SITES]
    for p in patches:
        p.start()
    globals_to_reset = ("catalog", "submission_catalog", "venue_catalog", "nexus_manager")
    for name in globals_to_reset:
        setattr(server_module, name, None)
    try:
        catalog = server_module.get_catalog()
        catalog.sync()
        initialize_enrichment_tools(catalog)
        initialize_similarity_tools(catalog, load_nexus_registry(contract_vault))
        initialize_chain_tools(catalog)
        yield contract_vault
    finally:
        for name in globals_to_reset:
            setattr(server_module, name, None)
        for p in patches:
            p.stop()


def test_format_checker_enforces_date_time():
    """Positive control: without the rfc3339-validator extra, date-time is a no-op
    and the contract test below would pass on the exact bug it exists to catch."""
    validator = Draft202012Validator(
        {"type": "string", "format": "date-time"}, format_checker=FormatChecker()
    )
    assert validator.is_valid("2024-01-01T10:30:00Z")
    assert not validator.is_valid("2024-01-01T10:30:00"), "date-time format is not being checked"


@pytest.mark.asyncio
async def test_every_tool_is_declared_with_a_contract_case(served_vault):
    async with Client(server_module.mcp) as client:
        declared = {t.name for t in await client.list_tools()}
    cased = {name for name, _ in CASES}
    assert declared == cased, (
        f"tools without a case: {sorted(declared - cased)}; "
        f"cases without a tool: {sorted(cased - declared)}"
    )


@pytest.mark.asyncio
async def test_every_tool_reply_matches_its_output_schema(served_vault):
    failures: list[str] = []
    async with Client(server_module.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for name, args in CASES:
            tool = tools[name]
            if tool.outputSchema is None:
                failures.append(f"{name}: declares no outputSchema")
                continue
            try:
                result = await client.call_tool(name, args)
            except Exception as exc:  # the client raised instead of returning a result
                failures.append(f"{name}{json.dumps(args)}: raised {type(exc).__name__}: {exc}")
                continue
            if result.is_error:
                text = " ".join(getattr(c, "text", "") for c in result.content)[:300]
                failures.append(f"{name}{json.dumps(args)}: isError with {text!r}")
                continue
            if result.structured_content is None:
                failures.append(f"{name}: no structuredContent despite an outputSchema")
                continue
            validator = Draft202012Validator(tool.outputSchema, format_checker=FormatChecker())
            errors = sorted(validator.iter_errors(result.structured_content), key=str)
            for err in errors[:3]:
                where = "/".join(str(p) for p in err.absolute_path) or "<root>"
                failures.append(f"{name}: {where}: {err.message[:200]}")
            payload = result.structured_content
            inner = payload.get("result", payload) if isinstance(payload, dict) else payload
            if isinstance(inner, dict) and (inner.get("error") or inner.get("success") is False):
                failures.append(f"{name}{json.dumps(args)}: tool reported an error: {inner}")
    assert not failures, "\n" + "\n".join(failures)
