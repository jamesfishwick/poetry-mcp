# Poetry MCP - Implementation Checklist

Reference: See README.md for architectural philosophy and system design.

## Phase 0: Project Setup ✅

- [x] Initialize pyproject.toml with dependencies
  - fastmcp>=0.2.0
  - pydantic>=2.0.0
  - pyyaml>=6.0
  - Dev deps: pytest, pytest-cov, pytest-asyncio, black, ruff, mypy
- [x] Create proper directory structure under `src/poetry_mcp/`
  - models/, parsers/, catalog/, tools/
  - errors.py, config.py, server.py
- [x] Add `.gitignore` (Python, IDEs, __pycache__, .pytest_cache, etc.)
- [x] Set up Python 3.10+ version check in main entry point
- [x] Create initial README with installation instructions
- [x] Create tests/ structure with conftest.py and fixtures/

## Phase 1: Core Data Models

### Pydantic Models (`src/poetry_mcp/models/`)

- [ ] `poem.py` - Poem model
  - All required fields (see FRONTMATTER_SCHEMA.md)
  - Validators for enums (state, form)
  - Optional content field
  - Optional qualities field (dict[str, int]) for quality scores (0-10)
- [ ] `nexus.py` - Nexus model
  - name, category (theme/motif/form), description, file_path
- [ ] `quality.py` - Quality model
  - name, category, scale_min, scale_max, description, file_path
  - Support for quality scores in poem frontmatter (qualities dict)
  - Validators for score range (0-10)
- [ ] `venue.py` - Venue model
  - name, payment, response_time_days, simultaneous, aesthetic, url, submission_format
- [ ] `influence.py` - Influence model
  - name, type, period, bibliography, aesthetic
- [ ] `technique.py` - Technique model (if needed)
- [ ] `results.py` - Result/response models
  - SyncResult, SearchResult, BaseFileResult, NexusRegistry, QualityRegistry, CatalogStats

### Test Models

- [ ] Unit tests for each model in `tests/test_models.py`
- [ ] Test validation (invalid enums, missing required fields)
- [ ] Test JSON serialization/deserialization

## Phase 2: Configuration System

### Config Module (`src/poetry_mcp/config.py`)

- [ ] VaultConfig Pydantic model with path validation
- [ ] SearchConfig, ThresholdsConfig, LoggingConfig, PerformanceConfig models
- [ ] PoetryMCPConfig composite model
- [ ] `load_config()` function with search path logic
- [ ] `find_config_file()` checking $POETRY_MCP_CONFIG, ~/.config/poetry-mcp/config.yaml, etc.
- [ ] `prompt_for_vault_path()` for first-run setup
- [ ] `create_default_config()` and `save_config()`
- [ ] Environment variable override support

### Test Config

- [ ] Test config loading from each search path
- [ ] Test environment variable overrides
- [ ] Test validation failures (nonexistent vault path)
- [ ] Create fixture config files in `tests/fixtures/`

## Phase 3: BASE File Parser

### Parser Module (`src/poetry_mcp/parsers/base_parser.py`)

- [ ] `parse_base_file()` - Main YAML parser
  - Handle `views:` config section
  - Parse `---` separated entries
  - Return (entries, views, warnings)
- [ ] `parse_base_entry()` - Convert dict to Pydantic model
  - Type dispatch based on base_type parameter
  - Skip invalid entries with warning
- [ ] Error classes: `BaseParseError`, `YAMLSyntaxError`
- [ ] Detailed error messages with line numbers

### Test Parser

- [ ] Create fixture BASE files (valid, malformed, empty, partial)
  - `tests/fixtures/base_files/catalog.base` (10 sample poems)
  - `tests/fixtures/base_files/nexus.base` (5 nexuses)
  - `tests/fixtures/base_files/qualities.base` (3 qualities)
  - `tests/fixtures/base_files/malformed.base` (YAML syntax error)
  - `tests/fixtures/base_files/empty.base` (only views config)
- [ ] Test successful parsing
- [ ] Test malformed YAML → detailed error
- [ ] Test missing required fields → skip with warning
- [ ] Test empty BASE → return empty list

## Phase 4: Catalog Management

### Catalog Module (`src/poetry_mcp/catalog/`)

#### catalog.py - Core catalog operations

- [ ] `CatalogIndex` class with hash maps (by_id, by_title, by_state, by_form, by_tag)
- [ ] `build_indices()` - Create all indices from poem list
- [ ] `scan_directory()` - Recursively find .md files in catalog/
- [ ] `parse_poem_file()` - Extract frontmatter + content from markdown
  - Handle missing frontmatter (use defaults)
  - Extract tags from frontmatter and bottom-of-file tags
  - Count words, lines, stanzas
- [ ] `detect_form()` - Form detection heuristics
  - American sentence (1 line, ~17 syllables)
  - Catalog poem (anaphora, list structure)
  - Prose poem (paragraph format)
  - Free verse (default)

#### Test Catalog

- [ ] Create fixture poem files in `tests/fixtures/markdown/`
  - completed/poem_with_frontmatter.md
  - completed/poem_without_frontmatter.md
  - fledgeling/poem_partial_frontmatter.md
- [ ] Test poem parsing (with/without frontmatter)
- [ ] Test form detection heuristics
- [ ] Test index building
- [ ] Test lookup operations (by_id, by_state, by_tag)

## Phase 5: MCP Tools - Phase 1

### Tool: sync_catalog (`src/poetry_mcp/tools/catalog_tools.py`)

- [ ] Implement async `sync_catalog()`
- [ ] Scan filesystem for all .md files
- [ ] Parse each poem file
- [ ] Handle errors (skip bad files, log warnings)
- [ ] Build indices
- [ ] Return SyncResult with statistics
- [ ] Test with fixture directory

### Tool: get_poem

- [ ] Implement `get_poem(identifier, include_content)`
- [ ] Lookup by ID or title
- [ ] Return Poem or None
- [ ] Test exact match, case sensitivity

### Tool: search_poems

- [ ] Implement `search_poems(query, states, forms, tags, limit, include_content)`
- [ ] Text search across title/content/notes
- [ ] Apply filters (state, form, tags)
- [ ] Return SearchResult with query_time_ms
- [ ] Test with various filter combinations

### Tool: load_base_file (`src/poetry_mcp/tools/base_tools.py`)

- [ ] Implement `load_base_file(base_file_path, base_type)`
- [ ] Call parser, convert to proper Pydantic models
- [ ] Return BaseFileResult
- [ ] Test with fixture BASE files

### Tool: get_all_nexuses

- [ ] Implement `get_all_nexuses()`
- [ ] Load nexus.base
- [ ] Organize by category (themes, motifs, forms)
- [ ] Return NexusRegistry
- [ ] Test with fixture nexus.base

### Tool: get_all_qualities

- [ ] Implement `get_all_qualities()`
- [ ] Load qualities.base
- [ ] Organize by category
- [ ] Return QualityRegistry
- [ ] Test with fixture qualities.base

### Tool: get_all_venues

- [ ] Implement `get_all_venues()`
- [ ] Load venues.base
- [ ] Return List[Venue]
- [ ] Test with fixture venues.base

### Tool: find_poems_by_tag (`src/poetry_mcp/tools/search_tools.py`)

- [ ] Implement `find_poems_by_tag(tags, match_mode, states, limit)`
- [ ] Set intersection for "all" mode
- [ ] Set union for "any" mode
- [ ] Filter by state if provided
- [ ] Test both match modes

### Tool: list_poems_by_state

- [ ] Implement `list_poems_by_state(state, sort_by, limit)`
- [ ] Lookup in by_state index
- [ ] Sort by requested field
- [ ] Test all states and sort orders

### Tool: get_catalog_stats

- [ ] Implement `get_catalog_stats()`
- [ ] Calculate all statistics from CatalogStats model
- [ ] Test with known catalog

## Phase 6: MCP Server Setup

### Server Entry Point (`src/poetry_mcp/server.py`)

- [ ] FastMCP server initialization
- [ ] Load configuration on startup
- [ ] Initialize catalog (sync on startup)
- [ ] Register all Phase 1 tools
- [ ] Add `get_config()` tool for inspection
- [ ] Add `get_version()` tool
- [ ] Logging setup (file + console)
- [ ] Error handling wrapper for all tools
- [ ] `main()` function for CLI entry point

### Test Server

- [ ] Test server startup
- [ ] Test tool registration
- [ ] Test error handling (bad vault path)
- [ ] Mock MCP tool calls

## Phase 7: Error Handling & Logging

### Error Classes (`src/poetry_mcp/errors.py`)

- [ ] `BaseParseError`
- [ ] `NexusNotFoundError`
- [ ] `FileSystemError`
- [ ] `ValidationError` (if not using Pydantic's)

### Logging Setup (`src/poetry_mcp/logging.py`)

- [ ] Configure logging from config.yaml
- [ ] File handler with rotation
- [ ] Console handler
- [ ] Format: timestamp, level, message
- [ ] Test log levels

## Phase 8: Integration Tests

### Full Workflow Tests (`tests/test_integration.py`)

- [ ] End-to-end test: startup → sync_catalog → search → get_poem
- [ ] Test with complete fixture vault structure
- [ ] Test error recovery (malformed files)
- [ ] Performance benchmarks (see Performance Considerations section)

## Phase 9: Documentation & Distribution

### Documentation

- [ ] Update README with:
  - Installation instructions (uv, pipx)
  - Configuration setup
  - Claude Desktop integration
  - Example queries
- [ ] Add docstrings to all public functions
- [ ] Create CONTRIBUTING.md if open source
- [ ] Add LICENSE (MIT or similar)

### Package Distribution

- [ ] Verify pyproject.toml metadata
- [ ] Test `uv build`
- [ ] Test local installation (`uv pip install -e .`)
- [ ] Create release checklist

## Testing Checklist

### Coverage Goals

- [ ] Public API (tools): 100% coverage
- [ ] Parsers: 95% coverage
- [ ] Core models: 90% coverage
- [ ] Overall: 85% minimum

### Run Tests

```bash
pytest tests/ -v
pytest tests/ --cov=poetry_mcp --cov-report=html
pytest tests/ --cov=poetry_mcp --cov-report=term-missing
```

### Performance Tests

- [ ] Catalog sync: <5 seconds (316 poems)
- [ ] Text search: <500ms
- [ ] Tag search: <50ms
- [ ] Memory footprint: <100MB

## Pre-Release Checklist

- [ ] All tests passing
- [ ] Coverage meets goals (85%+)
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)
- [ ] Formatting passes (black)
- [ ] Manual testing with real Poetry vault
- [ ] Test in Claude Desktop
- [ ] Version number updated in pyproject.toml
- [ ] CHANGELOG.md created
- [ ] Git tag created (v0.1.0)

## Phase 7: Enrichment Tools - Foundation (Sprint 1) ✅

**Status**: COMPLETE

### Frontmatter Writer Module ✅

- [x] `src/poetry_mcp/writers/frontmatter_writer.py`
- [x] `update_poem_tags(file_path, tags_to_add, tags_to_remove)`
- [x] Atomic writes with temp file + rename
- [x] Preserve all frontmatter fields (state, form, notes)
- [x] YAML validation before writing
- [x] Backup creation (`.bak` files)
- [x] Rollback on error
- [x] Test: update tags without breaking frontmatter
- [x] Test: handle missing frontmatter
- [x] Test: atomic write failure recovery

### Nexus/Influence Parsers ✅

- [x] `src/poetry_mcp/parsers/nexus_parser.py`
- [x] `load_nexus_registry(vault_root)` - Parse all nexus markdown files
- [x] Extract frontmatter `canonical_tag` field
- [x] Parse nexus descriptions from markdown body
- [x] Organize by category (themes/motifs/forms)
- [ ] `src/poetry_mcp/parsers/influence_parser.py` (deferred to Sprint 2)
- [ ] `load_influence_registry(vault_root)` - Parse influence files (deferred to Sprint 2)
- [x] Test with real vault nexus files (17 themes loaded successfully)

### Tool: get_all_nexuses ✅

- [x] Implement `get_all_nexuses()` MCP tool
- [x] Return NexusRegistry with all nexuses (25 total: 17 themes, 4 motifs, 4 forms)
- [x] Include descriptions for LLM context
- [x] Test with real vault data

### Tool: link_poem_to_nexus ⭐ ✅

- [x] Implement `link_poem_to_nexus(poem_id, nexus_name, nexus_type)`
- [x] Get poem file path from catalog
- [x] Get canonical tag from nexus registry
- [x] Call frontmatter_writer to add tag
- [x] Resync catalog after update
- [x] Return update status
- [x] Test: integration tested with real vault (simulation mode)
- [x] Error handling for invalid nexus name
- [x] Error handling for poem not found

## Phase 8: Enrichment Tools - Discovery (Sprint 2) ✅

**Status**: COMPLETE

### LLM Integration Setup ✅

- [x] `src/poetry_mcp/llm/` module
- [x] Claude API client wrapper (`client.py`)
- [x] Prompt templates for theme analysis (`prompts.py`)
- [x] Structured JSON output parsing (ThemeDetectionResult model)
- [x] Response validation (Pydantic models)
- [x] Error handling and retries (exponential backoff)
- [x] Cost tracking and logging (per-request and cumulative)

### Tool: find_nexuses_for_poem ⭐ ✅

- [x] Implement `find_nexuses_for_poem(poem_id, min_confidence, max_suggestions)`
- [x] Load poem content (with frontmatter extraction)
- [x] Load all nexus descriptions (from registry)
- [x] Build LLM prompt comparing poem to nexuses
- [x] Parse JSON response with confidence scores
- [x] Return ranked suggestions
- [x] Confidence threshold filtering
- [x] Error handling and graceful degradation

### Tool: suggest_enrichments_batch ⭐ ✅

- [x] Implement `suggest_enrichments_batch(poem_ids, auto_apply_threshold, max_poems, min_confidence)`
- [x] Default: analyze all poems with `tags: []`
- [x] For each poem, call `find_nexuses_for_poem`
- [x] Auto-apply suggestions with confidence >= threshold (0.7 default)
- [x] Collect lower-confidence suggestions for review
- [x] Return summary + review list + costs
- [x] Single catalog resync after all updates
- [x] Error handling for batch failures (continues on error)

## Phase 9: Enrichment Tools - Advanced Discovery (Sprint 3)

### Tool: extract_emerging_themes ⭐

- [ ] Implement `extract_emerging_themes(poem_ids, min_poems, existing_only)`
- [ ] Collect all poem content
- [ ] LLM multi-pass analysis:
  - [ ] Pass 1: Extract imagery/motifs per poem
  - [ ] Pass 2: Cluster recurring patterns
  - [ ] Pass 3: Compare to existing nexuses
  - [ ] Pass 4: Suggest new themes for unmatched clusters
- [ ] Filter by min_poems threshold
- [ ] Return existing themes found + new theme suggestions
- [ ] Test: detect "Clock/Time" pattern in sample poems
- [ ] Test: match existing themes correctly

### Tool: suggest_influences_for_poem

- [ ] Implement `suggest_influences_for_poem(poem_id, min_confidence)`
- [ ] Load influence aesthetic descriptions
- [ ] Compare poem style against influences
- [ ] Return ranked influence matches
- [ ] Test: poem matching Bronk's austerity
- [ ] Test: poem matching Beat aesthetic

### Tool: detect_motifs

- [ ] Implement `detect_motifs(poem_ids, min_poems)`
- [ ] Build theme co-occurrence matrix
- [ ] Statistical clustering (chi-square test)
- [ ] LLM semantic analysis of clusters
- [ ] Suggest motif names and descriptions
- [ ] Test: Water + Body + Failure pattern detection

## Phase 10: Enrichment Tools - Maintenance (Sprint 4)

### Tool: sync_nexus_tags

- [ ] Implement `sync_nexus_tags(poem_id, direction)`
- [ ] Parse `[[Nexus]]` links from markdown body
- [ ] Parse `#tag` from frontmatter
- [ ] Sync in requested direction (links→tags, tags→links, both)
- [ ] Report conflicts (tag without nexus)
- [ ] Test: sync after manual Obsidian edits
- [ ] Test: detect and report conflicts

### Tool: move_poem_to_state

- [ ] Implement `move_poem_to_state(poem_id, new_state)`
- [ ] Get current poem file path
- [ ] Determine new directory from state
- [ ] Move file to new directory
- [ ] Update frontmatter `state` field
- [ ] Resync catalog
- [ ] Test: fledgeling → completed promotion
- [ ] Test: handle file conflicts

### Tool: grade_poem_quality ✅

- [x] Implement `grade_poem_quality(poem_id, dimensions)` - Agent-based pattern
- [x] Load quality dimension rubrics from qualities.base
- [x] Return poem + dimensions for agent analysis
- [x] Agent provides scores (0-10) with reasoning
- [x] Test: score sample poem on all 8 dimensions
- [x] Test: score on specific dimensions only

### Backup and Rollback Tools

- [ ] `create_enrichment_backup(backup_id)`
- [ ] `rollback_enrichment(backup_id, poem_ids)`
- [ ] Git integration for auto-commits
- [ ] Backup management and cleanup

## Phase 11: Documentation & Testing

### Integration Tests

- [ ] Full enrichment workflow test (end-to-end)
- [ ] Batch processing 50 poems
- [ ] Error recovery and rollback
- [ ] LLM output validation
- [ ] Cost tracking accuracy

### Documentation

- [ ] Update README with enrichment features
- [ ] Add enrichment workflow examples
- [ ] Document LLM prompt templates
- [ ] Add troubleshooting guide
- [ ] Create user guide for batch enrichment

### Performance Testing

- [ ] Batch processing performance (50 poems < 60s)
- [ ] API cost tracking (< $0.50 total)
- [ ] Memory usage (< 200MB)
- [ ] Concurrent enrichment operations

## Phase 12: Quality Scoring Tools (Future)

### Tool: suggest_quality_scores

- [ ] Implement `suggest_quality_scores(poem_id, qualities, auto_commit)`
- [ ] Analyze poem against quality rubrics
- [ ] Generate scores (0-10) with reasoning
- [ ] Return structured suggestions
- [ ] Test: suggest scores for sample poem
- [ ] Test: auto_commit flag functionality

### Tool: commit_quality_scores

- [ ] Implement `commit_quality_scores(poem_id, scores, notes)`
- [ ] Write quality scores to poem frontmatter
- [ ] Optional quality_notes for reasoning
- [ ] Validate score ranges (0-10)
- [ ] Test: commit scores to frontmatter
- [ ] Test: update existing scores

### Tool: get_quality_scores

- [ ] Implement `get_quality_scores(poem_id)`
- [ ] Read quality scores from frontmatter
- [ ] Return scores with optional notes
- [ ] Test: retrieve scores for scored poem
- [ ] Test: handle unscored poems

### Tool: find_high_scoring_poems

- [ ] Implement `find_high_scoring_poems(qualities, min_score, states)`
- [ ] Query poems by quality scores
- [ ] Support multiple quality filters
- [ ] Filter by state
- [ ] Test: find poems scoring 8+ on Detail
- [ ] Test: combine quality and state filters

### v2 Enhancements

- [ ] Learn from scoring adjustments (improve suggestions)
- [ ] Track agreement rates (how often suggestions accepted)
- [ ] Score visualization/analytics
- [ ] Quality score trends over time
- [ ] Comparative scoring tool
- [ ] Batch scoring with review workflow
- [ ] Score history tracking (see how scores change over time)

## Known Deferred Features (Future)

- File watching (watchdog integration)
- Combination Generator (creative prompts)
- Analysis Prompt Generator (analytical questions)
- Submission Tracker (venue tracking)
- Web interface for batch approval
- Real-time enrichment during writing

---

## Technical Reference

### Error Handling Strategy

**Philosophy: Permissive with loud warnings.** Continue operation when possible, log extensively, surface issues to user.

#### BASE File Errors

**Malformed BASE file (syntax errors):**
- **Action**: Fail fast - refuse to start MCP server
- **Rationale**: Corrupt BASE file = corrupt data. User must fix before proceeding.
- **Error message**: Detailed YAML parse error with line number

**Empty BASE file (only views config):**
- **Action**: Load successfully, return empty dataset
- **Log**: INFO level - "catalog.base contains no entries"
- **Rationale**: Valid state during initialization

**Missing required properties in entry:**
- **Action**: Skip entry, log warning, continue parsing
- **Log**: WARN - "Skipped entry missing required field 'title' at line {line}"
- **Rationale**: One bad entry shouldn't break entire catalog

#### Poem Frontmatter Issues

**Missing frontmatter entirely:**
- **Action**: Use defaults, log warning
- **Defaults**:
  - `state`: "fledgeling" (assume incomplete)
  - `form`: Auto-detect via heuristics
  - `tags`: []
- **Log**: WARN - "{filename} missing frontmatter - using defaults"

**Invalid enum values:**
- **Action**: Use closest match or default, log warning
- **Log**: WARN - "Invalid state 'completedd', using 'completed'"
- **Suggest**: Show valid options in error

#### Nexus Linking Edge Cases

**Nonexistent nexus when linking:**
- **Action**: **REJECT - require manual creation**
- **Rationale**: Nexus creation is a deliberate aesthetic decision
- **Error**: `NexusNotFoundError` with suggestion
- **Compromise**: Provide `create_nexus` tool for explicit creation

**Why reject auto-create:**
- Nexuses define your poetic vocabulary
- Auto-creating "foo" nexus from typo pollutes taxonomy
- Forces intentional curation vs accidental proliferation

#### Logging Levels

- **ERROR**: Operation failed, cannot continue (malformed BASE file, file permission failures)
- **WARN**: Issue detected, operation continues with fallback (missing frontmatter, invalid BASE entries)
- **INFO**: Normal operations (catalog scanned, poems loaded)

### Search Architecture: Native + LLM Hybrid

#### Dual Search Strategy

**Native MCP tools** handle structured queries:
- Precise filtering (state, form, tags)
- Fast execution (<500ms)
- Return structured data (Pydantic models)
- Reliable, repeatable results

**LLM capabilities** handle semantic/conceptual queries:
- Interpret vague requests
- Multi-step reasoning chains
- Cross-reference external knowledge
- Synthesize insights from results

**Both coexist.** LLM can call native tools AND use its own reasoning.

#### When to Use Each

**Use native tools:**
```
"Find all completed poems tagged with water"
→ find_poems_by_tag(["water"], states=["completed"])

"List fledgelings in prose poem form"
→ search_poems("", forms=["prose_poem"], states=["fledgeling"])
```

**Use LLM reasoning:**
```
"Find poems about drowning but not literally"
→ LLM: Call search_poems("drowning"), read results,
   filter for metaphorical/symbolic treatment

"Which poems are similar to 'Second Bridge Out' but darker?"
→ LLM: Get poem, identify themes, search for those themes,
   read candidates, assess tone
```

#### Tool Design Implications

**Keep tools atomic and composable:**
- Don't build "find_high_visceral_water_poems" tool
- Build "find_by_tag" + "get_quality_scores" + LLM composition
- LLM handles complex query logic

**Return full poem objects when possible:**
- Let LLM read content and make judgments
- Don't pre-filter too aggressively
- Trust LLM to synthesize results

### Performance Considerations

#### Memory Footprint Analysis

**Current scale: 381 poems**

Estimated memory per poem:
- Pydantic model overhead: ~500 bytes
- Title (avg 30 chars): 30 bytes
- Content (avg 300 words = 1500 chars): 1.5 KB
- Tags (avg 5): 100 bytes
- Metadata fields: 200 bytes
- **Total per poem: ~2.3 KB**

**Full catalog**: 381 poems × 2.3 KB = **~875 KB**

**Supporting data:**
- 26 nexuses × 500 bytes = 13 KB
- 8 qualities × 300 bytes = 2.4 KB
- 22 venues × 400 bytes = 8.8 KB
- **Total supporting: ~24 KB**

**Grand total: ~900 KB in-memory**

**Verdict**: Trivial. Keep everything in memory. No pagination needed.

#### Caching Strategy

**On startup:**
1. Parse all BASE files → Pydantic models
2. Scan catalog directory → load all poems
3. Build search indices
4. Hold in memory until shutdown

**No re-parsing on every tool call.** Memory-resident data structure.

**Cache invalidation:**
- **v1**: Never. User restarts MCP server to reload.
- **v2**: Add `reload_catalog()` tool or file watchers with debouncing

#### Search Performance

**Text search over 381 poems:**
- Python string matching: ~1ms per poem
- 381 poems × 1ms = **381ms total**
- **Acceptable for <1000 poems**

**Tag filtering:**
- Hash map lookup: O(1) per tag
- Intersection of sets: O(n) where n = smallest tag set
- **<1ms for any tag combination**

#### Target Response Times

| Operation | Target | Rationale |
|-----------|--------|-----------|
| `get_poem` | <10ms | Hash lookup |
| `search_poems` | <500ms | Scan 381 poems |
| `find_poems_by_tag` | <50ms | Set intersection |
| `list_poems_by_state` | <20ms | Index lookup + sort |
| `sync_catalog` | <5s | Full filesystem scan |

**All achievable with naive implementations.**

#### Scalability Limits

Current architecture scales to:
- ~5,000 poems before search becomes sluggish
- ~10,000 poems before memory becomes concern (23 MB)
- ~50,000 poems before needing real database

For poetry MCP: 381 poems → 5,000 poems is 13x growth. Unlikely to hit limits.

### LLM Integration Strategies (Future Enhancements)

**Current**: Agent-based pattern (MCP server provides data, Claude analyzes)
**Future possibilities**: Enhanced prompting, cost optimization, hybrid approaches

#### Prompt Engineering Patterns

**Key Principles**:
1. **Structured output** - Always request JSON with schema
2. **Few-shot examples** - Include 2-3 example analyses in prompts
3. **Confidence scores** - Require 0.0-1.0 confidence with reasoning
4. **Evidence-based** - Cite specific poem excerpts in reasoning
5. **Batch optimization** - Process multiple poems per call when possible

**Example Template Structure**:
```
You are analyzing poetry for thematic connections.

POEM CONTENT:
"""
{poem_content}
"""

AVAILABLE NEXUSES:
1. Water-Liquid Imagery
   Description: Water, blood, beer, tears - liquids as transformation
   Tag: water-liquid
[... all nexuses ...]

TASK: Identify which nexuses apply. For each match:
- Provide confidence (0.0-1.0)
- Explain with specific excerpts
- Only suggest if confidence >= 0.6

Return JSON:
{
  "matches": [
    {"nexus_name": "...", "confidence": 0.85, "reasoning": "...", "tag": "..."}
  ]
}
```

#### Cost Optimization Strategies

**Caching approaches**:
- Cache nexus descriptions (reused across poems)
- Cache quality rubrics (reused across scoring)
- Store previous analyses to avoid re-processing

**Batching strategies**:
- Process 5-10 poems per API call instead of 1-by-1
- Combine related operations (theme detection + quality scoring)

**Tiered processing**:
- Local embeddings for candidate filtering (free)
- LLM only for top candidates (precision)
- Progressive enrichment (completed poems first, then fledgelings)

**Estimated costs (if implementing API integration)**:
- 381 poems × $0.001 per analysis = $0.38 total
- With caching/batching: $0.15-0.20 one-time
- Ongoing enrichment: ~$0.05/month (new poems only)

#### Provider Options

**Claude API** (if direct integration added):
- Native Anthropic integration
- High quality semantic analysis
- Streaming for batch operations
- Best for: Nuanced literary analysis

**Local embedding models** (alternative):
- Faster, no API costs
- Lower quality semantic matching
- Best for: Pre-filtering candidates

**Hybrid approach** (recommended):
- Local embeddings for filtering (top 10-20)
- Agent-based Claude analysis for final ranking (top 5)
- Current MCP pattern already implements this

### Enrichment Testing Strategies

**Unit Tests**:
- Frontmatter parsing and writing (tag merging, deduplication)
- YAML validation (schema conformance)
- File atomicity (temp write + rename)
- Tag normalization (canonical tag matching)

**Integration Tests**:
- Full enrichment workflow (discover → suggest → apply → verify)
- Batch processing (50+ poems)
- Error recovery (malformed frontmatter, missing nexuses)
- Rollback capability (restore from backup)

**Validation Tests** (if adding LLM API integration):
- JSON output parsing (handle malformed responses)
- Confidence score calibration (match actual accuracy)
- False positive rate (user feedback tracking)
- Consistency checks (same poem → similar results)

---

__Implementation Strategy:__

1. Work through checklist top to bottom
2. Write tests BEFORE implementation (TDD)
3. Run tests frequently
4. Commit after each completed section
5. Reference README.md and docs/ for current specifications
