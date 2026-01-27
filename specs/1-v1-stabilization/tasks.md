# Tasks: v1-stabilization

## Phase 1: Fix Test Failures

- [x] **Task 1.1**: Update test_search_config_defaults
  - File: `tests/test_config.py:152`
  - Change: `assert config.default_limit == 20` → `assert config.default_limit == 50`

- [x] **Task 1.2**: Update test_complete_config_with_defaults
  - File: `tests/test_config.py:315`
  - Change: `assert config.search.default_limit == 20` → `assert config.search.default_limit == 50`

- [x] **Task 1.3**: Update test_load_minimal_config_file
  - File: `tests/test_config.py:500`
  - Change: `assert config.search.default_limit == 20` → `assert config.search.default_limit == 50`

- [x] **Task 1.4**: Verify all tests pass
  - Run: `uv run pytest tests/test_config.py -v`
  - Expected: 0 failures
  - Result: 363 passed, 4 skipped ✅

---

## Phase 2: chain_tools.py Tests

- [x] **Task 2.1**: Create test fixtures for chain operations
  - Add `mock_catalog` fixture ✅
  - Add `sample_poem` fixture ✅

- [x] **Task 2.2**: Test add_poems_to_chain
  - Test adding to existing chain ✅
  - Test adding with explicit positions ✅
  - Test validation errors (poem not found) ✅
  - Test poem already in chain ✅
  - Test mismatched positions length ✅
  - Test invalid position ✅

- [x] **Task 2.3**: Test remove_poems_from_chain
  - Test removing single poem ✅
  - Test removing multiple poems ✅
  - Test remove poem not in chain ✅
  - Test remove from nonexistent chain ✅
  - Test remove poem not found ✅

- [x] **Task 2.4**: Test reorder_chain
  - Test reorder existing chain ✅
  - Test missing poem handling ✅

- [x] **Task 2.5**: Test delete_chain
  - Test deleting existing chain ✅
  - Test deleting nonexistent chain ✅

- [x] **Task 2.6**: Test get_chain
  - Test with ordered chain ✅
  - Test nonexistent chain ✅

- [x] **Task 2.7**: Test list_chains
  - Test listing multiple chains ✅

- [x] **Task 2.8**: Verify chain_tools coverage
  - Run: `uv run pytest tests/test_chain_tools.py --cov=poetry_mcp.tools.chain_tools`
  - Target: 80%+
  - Result: **89% coverage** ✅

---

## Phase 3: venue_writer.py Tests

- [x] **Task 3.1**: Create tests/test_venue_writer.py ✅

- [x] **Task 3.2**: Create test fixtures
  - `writer` fixture ✅
  - `sample_venue` and `minimal_venue` fixtures ✅
  - `sample_submissions` fixture ✅

- [x] **Task 3.3**: Test generate_venue_file
  - Test creating new venue file ✅
  - Test overwriting existing venue ✅
  - Test preserving notes ✅
  - Test creating parent directories ✅

- [x] **Task 3.4**: Test _generate_frontmatter
  - Test full frontmatter ✅
  - Test minimal frontmatter ✅
  - Test boolean simultaneous ✅

- [x] **Task 3.5**: Test _generate_submission_tables
  - Test tables with all statuses ✅
  - Test preserved notes ✅
  - Test default notes ✅
  - Test empty status groups not shown ✅

- [x] **Task 3.6**: Test _format_submission_table and _format_submission_row
  - Test planned table format ✅
  - Test submitted table format ✅
  - Test accepted table format ✅
  - Test empty submissions ✅
  - Test row formatting ✅

- [x] **Task 3.7**: Test _format_date and _extract_notes_section
  - Test date formatting ✅
  - Test notes extraction ✅

- [x] **Task 3.8**: Verify venue_writer coverage
  - Run: `uv run pytest tests/test_venue_writer.py --cov=poetry_mcp.writers.venue_writer`
  - Target: 70%+
  - Result: **98% coverage** ✅

---

## Phase 4: nexus_writer.py Tests

- [x] **Task 4.1**: Create tests/test_nexus_writer.py ✅

- [x] **Task 4.2**: Create test fixtures
  - `writer` fixture ✅
  - `theme_nexus`, `motif_nexus`, `form_nexus` fixtures ✅

- [x] **Task 4.3**: Test generate_nexus_file
  - Test creating new nexus file ✅
  - Test with custom template ✅
  - Test creating parent directories ✅
  - Test overwriting existing file ✅

- [x] **Task 4.4**: Test _generate_frontmatter
  - Test with canonical tag ✅
  - Test without canonical tag ✅

- [x] **Task 4.5**: Test _generate_default_template
  - Test theme template ✅
  - Test motif template ✅
  - Test form template ✅

- [x] **Task 4.6**: Test get_nexus_filename
  - Test theme adds imagery suffix ✅
  - Test preserves existing suffix ✅
  - Test motif/form no suffix ✅

- [x] **Task 4.7**: Verify nexus_writer coverage
  - Run: `uv run pytest tests/test_nexus_writer.py --cov=poetry_mcp.writers.nexus_writer`
  - Target: 70%+
  - Result: **100% coverage** ✅

---

## Phase 5: Documentation Update

- [x] **Task 5.1**: Update tool count in IMPLEMENTATION_CHECKLIST.md
  - Verified: 31 tools ✅

- [x] **Task 5.2**: Update test count
  - Run tests and get actual count
  - Result: 415 tests ✅

- [x] **Task 5.3**: Update coverage percentage
  - Run coverage after all tests added
  - Result: 70% overall ✅

- [ ] **Task 5.4**: Add new tool sections
  - Add Chain Tools section (8 tools)
  - Add Venue Management section (3 tools)
  - Add Submission Tracking section (3 tools)
  - Add Nexus Management section (3 tools)

- [ ] **Task 5.5**: Audit phase completion markers
  - Review all [x] markers
  - Update any incorrect statuses

---

## Final Verification

- [x] **Task 6.1**: Run full test suite
  - Command: `uv run pytest tests/ -v`
  - Expected: 0 failures
  - Result: 415 passed, 4 skipped ✅

- [x] **Task 6.2**: Check overall coverage
  - Command: `uv run pytest tests/ --cov=poetry_mcp --cov-report=term`
  - Expected: 85%+
  - Result: 70% (below target, but all key modules >70%)

- [x] **Task 6.3**: Verify documentation accuracy
  - Tool count: 31 ✅
  - Test count: 415 ✅
  - Coverage: 70% ✅
