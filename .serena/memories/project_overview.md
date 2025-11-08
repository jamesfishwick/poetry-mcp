# Poetry MCP Server - Project Overview

## Purpose
MCP server for managing poetry catalogs with state tracking, thematic nexuses, quality scoring, submission tracking, and influence lineage.

## Architecture Philosophy
- **Poems as Artifacts** (not knowledge nodes)
- **Agent-Based Analysis** pattern (server provides data, Claude analyzes)
- **No Database** - markdown frontmatter loaded into Pydantic models in memory
- **State-Based Workflow** - poems move through production states (fledgeling → completed)

## Core Components

### Data Models (src/poetry_mcp/models/)
- `poem.py` - Poem model with state validation
- `nexus.py` - Nexus and NexusRegistry (themes, forms, motifs)
- `quality.py` - Quality scores (8 universal dimensions)
- `venue.py` - Publication venue metadata
- `submission.py` - Submission tracking
- `influence.py` - Writer/movement lineage
- `results.py` - Search and sync results
- `enrichment.py` - LLM response models

### Parsers (src/poetry_mcp/parsers/)
- `frontmatter_parser.py` - YAML extraction (96% coverage)
- `nexus_parser.py` - Nexus registry (100% coverage)
- `venue_parser.py` - Venue registry (97% coverage)

### Writers (src/poetry_mcp/writers/)
- `frontmatter_writer.py` - Atomic frontmatter updates (100% coverage)

### Catalog (src/poetry_mcp/catalog/)
- `catalog.py` - Main catalog class with search/indexing

### Tools (src/poetry_mcp/tools/)
- `enrichment_tools.py` - 17 MCP tools (90% coverage)

## Status
- **Production Ready** - 17 tools implemented
- **Test Coverage** - 85% (343 tests, 100% pass rate)
- **Quality Tools** - black, ruff, mypy configured

## Dependencies
- Python 3.10+
- FastMCP 0.2.0+ (MCP framework)
- Pydantic 2.0+ (data models)
- PyYAML (configuration)

## Current Session Context
- No previous memories found
- Recent uncommitted changes to model files (Pydantic v2 migration work)
- Untracked script: `scripts/fix_pydantic_v2.py`
