# Research Findings: v1-stabilization

## Test Failures Analysis

### Root Cause

All 3 test failures have the **same root cause**: `SearchConfig.default_limit` was changed from `20` to `50` in `config.py`, but tests still assert the old value.

**Affected Tests:**
1. `test_search_config_defaults` - Line 152
2. `test_complete_config_with_defaults` - Line 315
3. `test_load_minimal_config_file` - Line 500

### Decision: Update Tests to Match New Default

**Rationale:**
- The change from 20 to 50 appears intentional (better user experience with more results)
- The Field definition explicitly sets `default=50, ge=1, le=100`
- No other code depends on the value being 20
- Tests should verify the actual behavior, not a historical value

**Alternative Considered:**
- Revert `default_limit` to 20 - Rejected because 50 is a reasonable default for search results

---

## Coverage Analysis

### Current State (63% overall)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| chain_tools.py | 56% | 165-241, 265-343, 382-533 | HIGH |
| venue_writer.py | 12% | Nearly all (42-247) | HIGH |
| nexus_writer.py | 38% | 38-127 | MEDIUM |
| frontmatter_writer.py | 68% | 48-50, 385-489 | MEDIUM |
| server.py | ~38% | Many new tools | LOW (optional) |

### Coverage Strategy

**To reach 85% overall, we need to focus on:**

1. **chain_tools.py** (+24% needed → +~45 lines covered)
   - Missing: `add_poems_to_chain`, `remove_poems_from_chain`, `reorder_chain`, `delete_chain`, `get_chain`, `list_chains`
   - Already tested: `create_chain` (partial)

2. **venue_writer.py** (+58% needed → +~66 lines covered)
   - Missing: All write operations
   - Functions: `write_venue`, `update_venue`, `delete_venue`, `regenerate_venue_file`

3. **nexus_writer.py** (+32% needed → +~8 lines covered)
   - Missing: `write_nexus`, `update_nexus`, `delete_nexus`

---

## Documentation Drift

### IMPLEMENTATION_CHECKLIST.md Updates Needed

| Section | Current Value | Actual Value |
|---------|---------------|--------------|
| Tool count | 17 | 31 |
| Test count | 343 | 363+ |
| Coverage | 85% | 63% (pre-fix) |
| Phase status | Various | Need audit |

### New Tool Categories to Document

1. **Chain Tools** (8 tools): create_chain, add_poems_to_chain, remove_poems_from_chain, reorder_chain, delete_chain, get_chain, list_chains
2. **Venue Management** (3 tools): sync_venues, list_venues, regenerate_venue_file
3. **Submission Tracking** (3 tools): sync_submissions, list_submissions, get_submission_stats
4. **Nexus Management** (3 tools): create_nexus, delete_nexus, validate_poem_tags, refresh_nexus_poem_counts

---

## Test Fixtures Needed

### For chain_tools.py

```python
# Fixture: poems with chain membership
@pytest.fixture
def poems_with_chains(catalog_with_poems):
    """Poems already belonging to chains for testing operations."""
    pass

# Fixture: empty chain state
@pytest.fixture
def clean_catalog(tmp_path):
    """Catalog with poems but no chain assignments."""
    pass
```

### For venue_writer.py

```python
# Fixture: venue file structure
@pytest.fixture
def venue_dir(tmp_path):
    """Directory with sample venue markdown files."""
    pass
```

---

## Implementation Order

Based on coverage impact and dependencies:

1. **Fix test assertions** (3 lines changed, immediate green tests)
2. **Add chain_tools tests** (highest coverage gain per effort)
3. **Add venue_writer tests** (second highest coverage gain)
4. **Add nexus_writer tests** (completes writer coverage)
5. **Update IMPLEMENTATION_CHECKLIST.md** (documentation sync)
6. **(Optional) Add server.py tests** (nice-to-have)
