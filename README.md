# Poetry MCP Server

A Model Context Protocol (MCP) server for managing poetry catalogs, nexuses, and submissions.

**Status:** Production Ready - 30 tools implemented, 343 tests passing (65% coverage), all core features operational

## Overview

Poetry MCP is a specialized MCP server that treats poems as **artifacts** (not knowledge graph nodes), providing:

- State-based catalog tracking (fledgeling → completed)
- Thematic connections via "nexuses" (themes, motifs, forms)
- Quality scoring on multiple dimensions
- Submission tracking to literary venues
- Influence lineage tracking

**Architecture:** No database - all data lives in markdown frontmatter. On startup, the MCP server scans poem files and loads frontmatter into Pydantic models in memory.

### Tag Policy (Strict)

**Tags represent thematic connections ONLY** - they must match canonical_tags from nexuses:

```yaml
---
title: My Poem
tags: [water, bones, childhood]  # ✅ Must match nexus canonical_tags
status: fledgeling               # ✅ Workflow metadata → dedicated field
form: american-sentence          # ✅ Structural metadata → dedicated field
---
```

**No free-text tags allowed.** Use dedicated fields for workflow metadata:
- Workflow states → `status: fledgeling`
- Submission tracking → `submitted: true` (use submission files)
- Quality → `quality: {detail: 8, mystery: 9}`
- Notes → Use poem body or separate notes field

**Validation:**
- Manual: Use `validate_poem_tags()` to check compliance anytime
- Automatic: Tag validation runs once on server startup by default
- Configure: Set `validation.auto_validate_on_sync: false` in config.yaml to disable

### Three Types of Metadata

Poetry MCP uses three complementary ways to evaluate poems:

| Type | What It Measures | Example |
|------|-----------------|---------|
| **Nexus** (binary) | What does this poem **contain**? | Contains water imagery (yes/no) |
| **Quality** (scalar) | What does this poem **achieve**? | Scores 8/10 on "Surprise" |
| **Influence** (lineage) | Where does this poem **come from**? | Descended from William Bronk |

**8 Universal Quality Dimensions:** Detail, Life, Music, Mystery, Sufficient Thought, Surprise, Syntax, Unity. The MCP server provides `grade_poem_quality()` which returns poem content and quality rubrics for agent-based scoring (0-10 scale with reasoning).

### Architectural Philosophy

Poetry workflow requires **catalog-based tracking** (poems as artifacts with states/metadata) rather than knowledge graph systems (atomic ideas with semantic links).

**Why poems aren't notes:**

- Move through production states (fledgeling → completed)
- Connect to thematic/formal nexuses (not logical relationships)
- Get scored on quality dimensions (scalar ratings)
- Have submission histories (transactions with venues)
- Descend from influences (lineage, not logic)

### Vault Directory Structure

The Poetry vault organizes poems and metadata across specialized directories:

```
/Poetry/
├── catalog/           # State-based poem organization (381 poems)
│   ├── catalog.base   # View definition for all poems
│   ├── Completed/     # 49 poems
│   ├── Fledgelings/   # 172 poems
│   ├── Needs Research/# 10 poems
│   ├── Risks/         # 22 poems
│   └── Still Cooking/ # 65 poems
├── nexus/             # Thematic/formal connection points
│   ├── nexus.base     # Registry of available nexuses
│   ├── themes/        # 17 thematic connections
│   ├── forms/         # 4 structural patterns
│   └── motifs/        # 4 compositional patterns
├── Qualities/         # 8 universal quality dimensions
│   └── qualities.base # Quality definitions and rubrics
├── influences/        # Writer/movement/aesthetic lineage
│   └── influences.base
├── techniques/        # Generative methods and processes
│   └── techniques.base
├── venues/            # Publication venue metadata (22 venues)
│   ├── venues.base    # Venue registry (payment, response time, aesthetic)
│   └── [venue files]  # Individual venue profiles
├── Submissions/       # Historical submission records
│   ├── Submissions.base # Submission tracking
│   └── [submission files] # Date_PoemTitle_VenueName.md
├── analysis/          # Research documents and comparisons
└── craft-notes/       # Personal aphorisms and principles
```

**Personal Directories:** Users may create additional directories for personal workflow (e.g., `journal/`, `scripts/`, transitional poem collections). These are not indexed by the MCP server.

### Nexus Taxonomy

Nexuses represent binary connections - a poem either contains a nexus or doesn't. The taxonomy has three categories:

- **Forms** (4): Structural patterns defining how a poem is arranged (American Sentence, Free Verse, Prose Poem, Catalog Poem)
- **Themes** (17): Subject matter and imagery systems (Water-Liquid Imagery, Body-Mouth, etc.)
- **Motifs** (4): Cross-nexus compositional patterns requiring multiple themes (American Grotesque, Failed Transcendence, etc.)

**Note:** The specific nexuses evolve over time as new patterns emerge in the poetry practice. See `nexus/` directory for current instances.

## Architecture: Agent-Based Analysis

This MCP server follows the **data provider** pattern:

**Server Responsibilities:**

- Catalog management (scan, index, search)
- Data access (poems, nexuses, quality rubrics)
- Data modification (update tags, move files)

**Agent (Claude) Responsibilities:**

- Poetry analysis (theme detection)
- Quality assessment (grading dimensions)
- Batch processing (multiple poem analysis)

**Why This Pattern?**

- ✅ No API keys needed in server
- ✅ Server stays lightweight and data-focused
- ✅ Agent uses natural language understanding
- ✅ Transparent analysis (you see the reasoning)
- ✅ Flexible - agent can adjust analysis approach

**Workflow:**

```
1. Tool call → Server returns poem + analysis context
2. Agent analyzes data using natural language reasoning
3. Agent provides structured results (themes/scores/confidence)
4. User applies results with data modification tools
```

## Requirements

- Python 3.10 or higher
- FastMCP 0.2.0+
- Pydantic 2.0+
- PyYAML for configuration

**Note:** No API keys needed! The MCP server provides data, your MCP client (Claude Desktop) performs analysis.

## Testing & Quality

- **Test Coverage:** 85% (343 tests, 100% pass rate)
- **Test Framework:** pytest with fixtures and parametrized tests
- **Quality Tools:** black, ruff, mypy
- **CI/CD:** Ready for integration with GitHub Actions

See [TEST_STATUS.md](TEST_STATUS.md) for detailed test suite information.

## Development Setup

### Installation

```bash
# Clone repository
git clone <repository-url>
cd poetry-mcp

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=poetry_mcp --cov-report=html

# Run specific test file
pytest tests/test_models.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Project Structure

```
src/poetry_mcp/
├── __init__.py          # Package metadata
├── server.py            # FastMCP server (8 core tools, 61% coverage)
├── config.py            # Configuration management (51% coverage)
├── errors.py            # Custom exceptions (100% coverage)
├── models/              # Pydantic data models (90-100% coverage)
│   ├── poem.py          # Poem model with state validation
│   ├── nexus.py         # Nexus and NexusRegistry models
│   ├── quality.py       # Quality scores and QualityRegistry
│   ├── venue.py         # Venue metadata model
│   ├── submission.py    # Submission tracking model
│   ├── influence.py     # Influence lineage model
│   ├── results.py       # Search and sync results
│   └── enrichment.py    # LLM response models
├── parsers/             # Frontmatter and registry parsers
│   ├── frontmatter_parser.py  # YAML extraction (96% coverage)
│   ├── nexus_parser.py        # Nexus registry (100% coverage)
│   └── venue_parser.py        # Venue registry (97% coverage)
├── writers/             # Frontmatter modification tools
│   └── frontmatter_writer.py  # Atomic updates (100% coverage)
├── catalog/             # Catalog management and indexing
│   └── catalog.py       # Main catalog class with search
└── tools/               # MCP tool implementations
    └── enrichment_tools.py  # All enrichment operations (90% coverage)

tests/                   # 343 tests, 100% pass rate
├── conftest.py          # Pytest fixtures and helpers
├── test_models.py       # Model validation tests (24 tests)
├── test_config.py       # Config system tests (47 tests)
├── test_venue_parser.py # Venue parser tests (24 tests)
├── test_venue_parser_edge_cases.py # Edge case tests (12 tests)
├── test_enrichment.py   # Enrichment workflow tests (16 tests)
├── test_frontmatter_writer.py  # Writer tests (16 tests)
├── test_frontmatter_writer_errors.py # Error path tests (22 tests)
├── test_quality_scoring.py     # Quality tools tests (22 tests)
└── fixtures/            # Test data and sample poems

docs/
├── CANONICAL_TAGS.md         # Canonical tag reference
├── FRONTMATTER_SCHEMA.md     # Frontmatter property definitions
├── IMPLEMENTATION_CHECKLIST.md  # Development progress tracking
└── TEST_STATUS.md            # Test suite status and coverage
```

## Configuration

Poetry MCP supports multiple configuration methods with automatic fallback:

### Configuration Priority (highest to lowest)

1. **YAML config file** - Most flexible, supports all options
2. **Environment variables** - Quick setup for vault path
3. **Interactive setup** - First-run wizard (when run in terminal)
4. **Default location** - `~/.local/share/obsidian/art/Poetry` (if exists)

### Config File Locations

Poetry MCP checks these locations in order:

1. `$POETRY_MCP_CONFIG` - Environment variable pointing to config file
2. `~/.config/poetry-mcp/config.yaml` - XDG config directory (recommended)
3. `~/.poetry-mcp/config.yaml` - Home directory fallback

### Full Config File Example

See `config.yaml.example` in the repository for a complete template:

```yaml
vault:
  # Required: Absolute path to your Poetry vault
  path: /path/to/your/Poetry/vault

  # Optional: Subdirectory names (defaults shown)
  catalog_dir: catalog
  nexus_dir: nexus
  qualities_dir: Qualities
  venues_dir: venues
  influences_dir: influences

search:
  # Default number of results (1-100)
  default_limit: 50

  # Case-sensitive search
  case_sensitive: false

logging:
  # Log level: DEBUG, INFO, WARNING, ERROR
  level: INFO

  # Log file path (null = console only)
  file: null
  # file: ~/.config/poetry-mcp/poetry-mcp.log

  # Log message format
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

performance:
  # File watching for auto-reload (requires watchdog library)
  watch_files: false

  # Debounce time for file changes (seconds)
  watch_debounce_seconds: 2.0

  # Cache expiry (seconds)
  cache_expiry_seconds: 3600

# Tag validation settings
validation:
  # Automatically validate tags on server startup (after initial sync)
  auto_validate_on_sync: true

  # Enforce strict tag policy (tags must match nexus canonical_tags)
  strict_mode: true
```

### Quick Setup with Environment Variable

Minimum configuration using just an environment variable:

```bash
export POETRY_VAULT_PATH="/path/to/your/Poetry/vault"
```

All other settings will use defaults. This is the quickest way to get started.

## MCP Client Setup

Poetry MCP implements the Model Context Protocol (MCP) standard and can be used with any MCP-compatible client.

### Configuration Format

MCP clients typically use JSON configuration to connect to servers. Add this to your MCP client's config:

```json
{
  "mcpServers": {
    "poetry-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/poetry-mcp",
        "run",
        "poetry-mcp"
      ],
      "env": {
        "POETRY_VAULT_PATH": "/path/to/your/Poetry/vault"
      }
    }
  }
}
```

**Alternative: Using python directly**

If you have the package installed globally:

```json
{
  "mcpServers": {
    "poetry-mcp": {
      "command": "python",
      "args": ["-m", "poetry_mcp.server"],
      "env": {
        "POETRY_VAULT_PATH": "/path/to/your/Poetry/vault"
      }
    }
  }
}
```

### Client-Specific Setup

**Claude Desktop:**

- Config location (macOS): `~/Library/Application Support/Claude/claude_desktop_config.json`
- Config location (Windows): `%APPDATA%\Claude\claude_desktop_config.json`
- After updating config, restart Claude Desktop completely

**Other MCP Clients:**

- Consult your client's documentation for config file location
- Use the JSON format above with your specific vault path

### Verification

After configuring your MCP client:

1. Restart the client application
2. Start a new conversation/session
3. Check that poetry-mcp tools are available
4. Try: "What poetry tools are available?"
5. Try: "Get catalog stats" - should show your poem count

### Troubleshooting

**Server won't start:**

- Verify `POETRY_VAULT_PATH` points to correct directory
- Check the vault has a `catalog/` subdirectory
- Review client logs for error messages

**No poems found:**

- Run `sync_catalog` tool first to index poems
- Verify vault path is correct
- Check markdown files have proper frontmatter (see FRONTMATTER_SCHEMA.md)

**Tools not appearing:**

- Completely restart your MCP client
- Validate JSON config syntax
- Verify `uv` or `python` is in system PATH

## Quick Start

### Basic Usage

```bash
# Start the server (auto-syncs catalog on startup)
poetry-mcp start

# Or run directly with Python
python -m poetry_mcp.server
```

### Example Workflows

**Agent-Based Theme Analysis:**

```python
# 1. Server provides poem and theme data
data = await find_nexuses_for_poem("my-poem-id", max_suggestions=3)

# 2. Agent (Claude) analyzes the poem against available themes
# Agent sees:
#   - data['poem']: {id, title, content, current_tags}
#   - data['available_themes']: [{name, canonical_tag, description}, ...]
#   - data['instructions']: Analysis guidance

# 3. Agent identifies matching themes with confidence:
# Example agent response:
# "This poem strongly engages with:
#  - Water-Liquid (0.85): 'river flows through ancient stones'
#  - Body-Bones (0.67): skeletal imagery in stanza 2"

# 4. User applies suggested tags
await link_poem_to_nexus("my-poem-id", "Water-Liquid", "theme")
```

**Batch Theme Discovery:**

```python
# 1. Get poems needing enrichment
data = await get_poems_for_enrichment(max_poems=10)

# 2. Agent analyzes data['poems'] against data['available_themes']
# Agent suggests themes for each poem

# 3. User applies high-confidence tags
for poem in analyzed_poems:
    await link_poem_to_nexus(poem['id'], suggested_theme, "theme")
```

**Agent-Based Quality Grading:**

```python
# 1. Server provides poem and quality rubric
data = await grade_poem_quality("my-poem-id")

# 2. Agent grades data['poem'] on data['dimensions']
# Agent sees 8 quality dimensions with descriptions
# Agent provides scores 0-10 with evidence

# Example agent response:
# "Quality Assessment:
#  - Detail: 8/10 - Strong sensory imagery ('ancient stones worn smooth')
#  - Life: 6/10 - Adequate vitality but some static passages
#  - Music: 9/10 - Excellent rhythm and sonic patterns"
```

**Maintenance:**

```python
# Sync wikilinks with tags
result = await sync_nexus_tags("my-poem-id", direction="both")
print(f"Tags added: {result['tags_added']}")
print(f"Links added: {result['links_added']}")

# Move poem to completed state
result = await move_poem_to_state("my-poem-id", "completed")
print(f"Moved to: {result['new_path']}")
```

## Available Tools

### Catalog Management

- **sync_catalog** - Scan vault and build in-memory catalog index
- **get_poem** - Retrieve poem by ID or title
- **search_poems** - Search with filters (query, states, forms, tags)
- **find_poems_by_tag** - Find poems by tag combinations
- **list_poems_by_state** - List poems in specific states
- **get_catalog_stats** - Get catalog statistics and health metrics
- **get_server_info** - Server status and configuration

### Enrichment Tools

- **get_all_nexuses** - Browse available themes, motifs, and forms
- **link_poem_to_nexus** - Add nexus tags to poem frontmatter
- **sync_nexus_tags** - Sync [[Nexus]] wikilinks with frontmatter tags
- **move_poem_to_state** - Move poems between state directories

**Nexus Management:**
- **create_nexus** - Create new themes, motifs, or forms
- **delete_nexus** - Remove themes, motifs, or forms (with optional cleanup)
- **get_poems_by_nexus** - Find all poems tagged with a specific nexus (reverse lookup)
- **refresh_nexus_poem_counts** - Populate poem_count for all nexuses
- **validate_poem_tags** - Strict validation that all tags match nexus canonical_tags

### Agent Analysis Tools

*These tools return data for YOUR (the agent's) analysis*

- **find_nexuses_for_poem** - Get poem + themes for agent to analyze and suggest matches
- **get_poems_for_enrichment** - Get batch of poems for agent to analyze and suggest themes
- **grade_poem_quality** - Get poem + quality rubric for agent to grade

### Quality Scoring Tools

*Manage quality scores on poems across 8 universal dimensions*

- **commit_quality_scores** - Write quality scores to poem frontmatter with validation
- **get_quality_scores** - Retrieve existing quality scores from a poem
- **find_high_scoring_poems** - Query poems by quality dimension and minimum score
- **list_quality_dimensions** - Get available quality dimensions and descriptions

### Submission & Venue Management

*Track submissions to literary venues with auto-generated venue views*

**Submission Tools:**
- **sync_submissions** - Scan submissions/ directory and build index
- **list_submissions** - Query submissions by venue, status, or poem (with filters)
- **get_submission_stats** - Get submission statistics and acceptance rate

**Venue Tools:**
- **sync_venues** - Scan venues/ directory and load metadata
- **list_venues** - Browse venues with payment and simultaneous filters
- **get_venue** - Get venue metadata with all submissions
- **regenerate_venue_file** - Rebuild venue markdown from metadata + submissions

**Architecture:** Submissions are source-of-truth (individual .md files), venue files are auto-generated aggregation views

## Development Roadmap

### Completed Phases

- [x] **Phase 0:** Project Setup - Dependencies, structure, tooling, test infrastructure
- [x] **Phase 1:** Core Data Models - Pydantic models for Poem, Nexus, Quality, Venue, Submission
- [x] **Phase 2:** Configuration System - YAML config with multi-source discovery (51% coverage)
- [x] **Phase 3:** Parsers - Frontmatter (96%), Venue (97%), Nexus (100%) coverage
- [x] **Phase 4:** Catalog Management - Scan filesystem, index poems, search operations
- [x] **Phase 5:** MCP Tools - Core catalog/search tools (17 tools implemented)
- [x] **Phase 6:** MCP Server - FastMCP initialization and tool registration
- [x] **Phase 7:** Enrichment Foundation - Frontmatter writer (100%), nexus registry
- [x] **Phase 8:** Enrichment Discovery - Theme detection, batch enrichment workflows
- [x] **Phase 9:** Maintenance Tools - Tag sync, state moves, quality grading
- [x] **Phase 10:** Quality Scoring - 4 quality management tools with validation
- [x] **Phase 11:** Venue & Submission Tracking - Venue registry, submission history
- [x] **Phase 12:** Test Coverage Enhancement - Error paths, edge cases (85% coverage achieved)

### Current Status

- **Test Coverage:** 85% (343 tests, 100% pass rate)
- **Implemented Tools:** 30 MCP tools across all categories
- **Production Ready:** Core functionality operational

### Future Enhancements (v2+)

- [ ] **Advanced Discovery Tools** - Similarity search, theme clustering, motif detection
- [ ] **Backup & Rollback** - Explicit snapshots, batch rollback, git integration
- [ ] **Performance Features** - File watching, hot reload, batch operations
- [x] **Additional Coverage** - 85% target achieved ✅

See [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) and [TEST_STATUS.md](TEST_STATUS.md) for detailed progress tracking.

## Data Synchronization

### How Data Changes Work

Poetry MCP loads poem frontmatter into memory as Pydantic models on startup. Understanding the sync behavior:

**Current Behavior (v1):**

```text
1. Server starts → Scans catalog/ directory → Parses frontmatter → Creates Pydantic models in RAM
2. Models stay in memory during server lifetime
3. Edit poem frontmatter in Obsidian → Models remain unchanged
4. Restart server → Re-scans files → Fresh models loaded
```

**To see your changes:** Simply restart the MCP server (< 3 seconds). Claude Desktop will reconnect automatically.

### Future Convenience Features (v2+)

#### Manual Reload Tool

Call from Claude when you've made changes:

```python
# No server restart needed
reload_catalog()
```

**Benefits:**

- Instant refresh without disconnecting Claude
- Selective reloading (only changed files)
- Maintains conversation context

#### Automatic File Watching

Real-time synchronization using the `watchdog` library (configurable in `config.yaml`):

```yaml
# config.yaml
performance:
  watch_files: true
  watch_debounce_seconds: 2.0
```

**Features:**

- Detects markdown file changes automatically
- Debouncing (waits for all saves to complete)
- Smart reload (only changed files)
- Handles concurrent modifications safely

**When you edit in Obsidian:**

1. Save changes → File watcher detects change
2. Waits 2 seconds (Obsidian may save multiple files)
3. Reloads changed markdown files
4. Updates Pydantic models in memory
5. Changes visible in next Claude query

#### Why Not in v1?

**Complexity trade-offs:**

- File watching adds dependencies (watchdog library)
- Requires debouncing logic (multiple rapid saves)
- Needs concurrent modification handling
- Adds error recovery complexity

**Current approach prioritizes:**

- ✅ Simple implementation
- ✅ Fast manual restart (2-3 seconds total)
- ✅ Reliable data consistency
- ✅ Easier debugging during development

**v2 can add these features based on user feedback.**

## License

MIT
