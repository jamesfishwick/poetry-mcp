# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-03

### Added

#### Core MCP Tools (8 tools)
- **get_poem_details** - Retrieve comprehensive poem information with quality scores
- **update_poem_frontmatter** - Safe frontmatter updates with validation and backup
- **commit_quality_scores** - Track quality dimensions with evidence-based scores
- **get_quality_scores** - Retrieve quality assessment history
- **find_high_scoring_poems** - Query poems by quality thresholds and states
- **link_poem_to_nexus** - Establish semantic relationships in knowledge graph
- **sync_catalog_state** - Bidirectional synchronization between files and memory
- **suggest_nexus_links** - LLM-powered smart linking recommendations

#### Poetry Catalog Management
- PoemIndex with in-memory catalog and file-system persistence
- Comprehensive metadata tracking (state, form, quality, tags, dates)
- Safe file operations with atomic writes and backup/rollback capability
- Bidirectional sync between files and memory state

#### Nexus (Knowledge Graph) System
- Nexus parser for markdown-based knowledge structures
- Semantic linking with `links_to_poems` and `links_to_tags`
- Poem enrichment through nexus relationships
- Bidirectional tag propagation

#### Quality Assessment Framework
- 9 quality dimensions (clarity, imagery, structure, rhythm, originality, emotion, depth, coherence, precision)
- 10-point evidence-based scoring system
- Historical tracking with timestamps and notes
- Query and aggregation capabilities

#### Parsers and Writers
- Frontmatter parser with YAML validation and error handling
- Venue parser for submission tracking with status workflows
- Nexus parser for knowledge graph structures
- Frontmatter writer with atomic operations and validation gates

#### Testing Infrastructure
- **343 tests** passing with 100% success rate
- **79% code coverage** (improved from 17%)
- Comprehensive test suites:
  - Happy path testing (core functionality)
  - Error path testing (edge cases and failures)
  - Integration testing (end-to-end workflows)
  - Edge case testing (boundary conditions)
- High-priority module coverage:
  - Parsers: 96-100% coverage
  - Writers: 100% coverage
  - Enrichment tools: 90% coverage
  - Core models: 90-100% coverage
  - Public API: 90% coverage

#### Code Quality
- **Type checking**: mypy compliance with full type annotations
- **Linting**: ruff configuration with auto-fix capabilities
- **Formatting**: black configuration (100 char line length)
- **CI-ready**: All quality gates automated and passing

### Technical Highlights

#### Architecture
- FastMCP server framework with tool decorators
- Pydantic models for data validation and serialization
- Modular design with clear separation of concerns:
  - `/models` - Core data structures
  - `/parsers` - File format parsing
  - `/writers` - Safe file operations
  - `/tools` - Enrichment and linking
  - `/catalog` - Central state management

#### Error Handling
- Comprehensive error types (FrontmatterParseError, NexusParseError)
- Graceful degradation with detailed error messages
- Validation gates preventing corruption
- Backup/rollback for safe recovery

#### Performance
- In-memory catalog for fast queries
- Lazy loading of poem content
- Efficient bidirectional sync
- Optimized quality score aggregation

### Implementation Journey

**Phase 0-12 Completed**:
- ✅ Project structure and configuration
- ✅ Core models and data structures
- ✅ File parsers (frontmatter, venue, nexus)
- ✅ Poem catalog and indexing
- ✅ Frontmatter writer with safety features
- ✅ Quality scoring framework
- ✅ Nexus enrichment tools
- ✅ LLM-powered smart linking
- ✅ Venue submission tracking
- ✅ Comprehensive testing (343 tests)
- ✅ Code quality automation (mypy, ruff, black)
- ✅ Documentation and examples

### Known Limitations

- Overall test coverage at 79% (target: 85%)
- Config module at 51% coverage (needs additional tests)
- Some complex type annotations use `Any` for flexibility
- Git tag creation deferred to manual process

### Dependencies

**Core**:
- fastmcp >= 0.2.0
- pydantic >= 2.0.0
- pyyaml >= 6.0

**Development**:
- pytest >= 7.4.0 (with asyncio and coverage plugins)
- black >= 23.0.0
- ruff >= 0.1.0
- mypy >= 1.5.0

### Documentation

- Comprehensive README with setup and usage examples
- Technical reference in IMPLEMENTATION_CHECKLIST.md
- Frontmatter schema documentation
- Test coverage reports

[0.1.0]: https://github.com/jamesfishwick/poetry-mcp/releases/tag/v0.1.0
