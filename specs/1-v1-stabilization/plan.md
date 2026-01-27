# Implementation Plan: v1-stabilization

## Technical Context

| Aspect | Value |
|--------|-------|
| Language | Python 3.10+ |
| Test Framework | pytest with pytest-cov |
| Current Coverage | 63% |
| Target Coverage | 85% |
| Test Failures | 3 (all same root cause) |

### Key Dependencies

- `pytest` - test runner
- `pytest-cov` - coverage measurement
- `pytest-asyncio` - async test support (chain_tools uses async)

### Integration Points

- `src/poetry_mcp/config.py` - SearchConfig model (test fix)
- `src/poetry_mcp/tools/chain_tools.py` - needs test coverage
- `src/poetry_mcp/writers/venue_writer.py` - needs test coverage
- `src/poetry_mcp/writers/nexus_writer.py` - needs test coverage

---

## Constitution Check

No constitution file defined. Following project conventions from CLAUDE.md:

| Principle | Status | Notes |
|-----------|--------|-------|
| Security | N/A | Test-only changes, no security impact |
| Accessibility | N/A | Backend/test changes only |
| Testing | FOCUS | This is the primary goal |
| Code Quality | PASS | Following existing test patterns |

---

## Research Findings

See [research.md](research.md) for detailed analysis.

**Key Findings:**
1. All 3 test failures are the same issue: `default_limit` changed from 20→50
2. Coverage gap is primarily in writers and chain_tools modules
3. Documentation is 14+ tools behind current implementation

---

## Implementation Phases

### Phase 1: Fix Test Failures (5 minutes)

**Goal:** All tests pass (0 failures)

| Task | File | Change |
|------|------|--------|
| 1.1 | tests/test_config.py:152 | Change `== 20` to `== 50` |
| 1.2 | tests/test_config.py:315 | Change `== 20` to `== 50` |
| 1.3 | tests/test_config.py:500 | Change `== 20` to `== 50` |

**Verification:** `uv run pytest tests/test_config.py -v`

---

### Phase 2: Add chain_tools.py Tests (30-45 minutes)

**Goal:** Coverage from 56% to 80%+

**Test File:** `tests/test_chain_tools.py` (enhance existing)

| Task | Function to Test | Test Cases |
|------|------------------|------------|
| 2.1 | `add_poems_to_chain` | Add to existing, add to new, with positions, validation errors |
| 2.2 | `remove_poems_from_chain` | Remove single, remove multiple, reposition remaining |
| 2.3 | `reorder_chain` | Move up, move down, swap positions |
| 2.4 | `delete_chain` | Delete existing, delete nonexistent |
| 2.5 | `get_chain` | With content, without content, nonexistent |
| 2.6 | `list_chains` | Empty, single, multiple chains |

**Fixtures Needed:**
- `catalog_with_chains` - catalog with poems already in chains
- `mock_frontmatter_writer` - mock write operations

**Verification:** `uv run pytest tests/test_chain_tools.py --cov=poetry_mcp.tools.chain_tools`

---

### Phase 3: Add venue_writer.py Tests (30-45 minutes)

**Goal:** Coverage from 12% to 70%+

**Test File:** `tests/test_venue_writer.py` (new file)

| Task | Function to Test | Test Cases |
|------|------------------|------------|
| 3.1 | `write_venue` | Create new venue file, overwrite existing |
| 3.2 | `update_venue` | Update fields, add fields, remove fields |
| 3.3 | `delete_venue` | Delete existing, delete nonexistent |
| 3.4 | `regenerate_venue_file` | Regenerate from model, preserve custom content |

**Fixtures Needed:**
- `venue_dir` - temporary directory with venue files
- `sample_venue` - Venue model instance for testing

**Verification:** `uv run pytest tests/test_venue_writer.py --cov=poetry_mcp.writers.venue_writer`

---

### Phase 4: Add nexus_writer.py Tests (20-30 minutes)

**Goal:** Coverage from 38% to 70%+

**Test File:** `tests/test_nexus_writer.py` (new file)

| Task | Function to Test | Test Cases |
|------|------------------|------------|
| 4.1 | `write_nexus` | Create new nexus file |
| 4.2 | `update_nexus` | Update description, update category |
| 4.3 | `delete_nexus` | Delete existing, handle missing |

**Verification:** `uv run pytest tests/test_nexus_writer.py --cov=poetry_mcp.writers.nexus_writer`

---

### Phase 5: Update Documentation (15-20 minutes)

**Goal:** IMPLEMENTATION_CHECKLIST.md matches reality

| Task | Section | Update |
|------|---------|--------|
| 5.1 | Tool count | Update from 17 to 31 |
| 5.2 | Test count | Update from 343 to actual |
| 5.3 | Coverage | Update to post-fix percentage |
| 5.4 | New sections | Add Chain Tools, Venue Management, Submission Tracking |
| 5.5 | Phase status | Audit and update completion marks |

**Verification:** Manual review against `grep -c "@mcp.tool" src/poetry_mcp/server.py`

---

### Phase 6 (Optional): Add server.py Tests

**Goal:** Server coverage from 38% to 60%+

Lower priority - only if time permits after meeting 85% target.

---

## Success Verification

```bash
# Run all tests - expect 0 failures
uv run pytest tests/ -v

# Check coverage - expect 85%+
uv run pytest tests/ --cov=poetry_mcp --cov-report=term-missing

# Verify tool count
grep -c "@mcp.tool" src/poetry_mcp/server.py
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Async test complexity | Use existing test_chain_tools.py patterns |
| Writer tests need filesystem | Use pytest tmp_path fixture |
| Mock complexity | Prefer real fixtures over mocks where possible |
| Coverage calculation changes | Run full suite after each phase |

---

## Time Estimate

| Phase | Estimate |
|-------|----------|
| Phase 1 | 5 min |
| Phase 2 | 30-45 min |
| Phase 3 | 30-45 min |
| Phase 4 | 20-30 min |
| Phase 5 | 15-20 min |
| **Total** | **~2-2.5 hours** |

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-26 | Claude | Initial plan from research |
