"""Chains written by the chain tools survive a catalog re-sync.

The chain tools persist membership in each poem's frontmatter (`chains`,
`chain_positions`) and then call catalog.sync() expecting to read it back.
These tests go through the real writer, parser and catalog, with no mocked
poem objects, because a mock with chains pre-set is exactly what let the
parser silently drop the keys for as long as the feature existed.
"""

from pathlib import Path

import pytest

from poetry_mcp.catalog.catalog import Catalog
from poetry_mcp.parsers.frontmatter_parser import parse_poem_file
from poetry_mcp.writers.frontmatter_writer import update_poem_chains


def _poem(vault: Path, name: str) -> Path:
    path = vault / "catalog" / "completed" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nstate: completed\nform: free_verse\n---\n\n# {name.title()}\n\nA line.\n",
        encoding="utf-8",
    )
    return path


def test_parser_reads_chains_written_by_the_writer(tmp_path: Path):
    path = _poem(tmp_path, "water")
    result = update_poem_chains(
        path, chains_to_add=["river-cycle"], position_updates={"river-cycle": 2}
    )
    assert result.success, result.error

    poem = parse_poem_file(path, tmp_path)

    assert poem.chains == ["river-cycle"]
    assert poem.chain_positions == {"river-cycle": 2}


def test_parser_reads_chains_declared_by_hand(tmp_path: Path):
    path = tmp_path / "catalog" / "completed" / "earth.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nstate: completed\nform: free_verse\nchains:\n  - River-Cycle\n"
        "chain_positions:\n  River-Cycle: 1\n---\n\n# Earth\n\nA line.\n",
        encoding="utf-8",
    )

    poem = parse_poem_file(path, tmp_path)

    # The model's validators normalize chain ids to lowercase.
    assert poem.chains == ["river-cycle"]
    assert poem.chain_positions == {"river-cycle": 1}


def test_catalog_indexes_chains_after_resync(tmp_path: Path):
    water = _poem(tmp_path, "water")
    earth = _poem(tmp_path, "earth")
    catalog = Catalog(vault_root=tmp_path)
    catalog.sync()
    assert catalog.index.by_chain == {}

    for i, path in enumerate([water, earth], start=1):
        assert update_poem_chains(
            path, chains_to_add=["river-cycle"], position_updates={"river-cycle": i}
        ).success
    catalog.sync(force_rescan=True)

    assert catalog.index.by_chain["river-cycle"] == ["water", "earth"] or sorted(
        catalog.index.by_chain["river-cycle"]
    ) == ["earth", "water"]
    assert catalog.index.get_by_id("earth").chain_positions == {"river-cycle": 2}


@pytest.mark.parametrize("missing", [None, [], {}])
def test_absent_chain_keys_parse_to_empty(tmp_path: Path, missing):
    path = _poem(tmp_path, "fire")
    poem = parse_poem_file(path, tmp_path)
    assert poem.chains == []
    assert poem.chain_positions is None
