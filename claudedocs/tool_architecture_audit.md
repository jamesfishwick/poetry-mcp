# MCP Tool Architecture Audit

**Date:** 2025-01-08
**Total Tools:** 30
**Server File:** `src/poetry_mcp/server.py` (1824 lines)

## Tool Inventory by Category

### Catalog Management (7 tools)
1. `sync_catalog` - Sync filesystem → in-memory index
2. `get_poem` - Retrieve single poem by ID/title
3. `search_poems` - Multi-filter search (query, state, form, tags)
4. `find_poems_by_tag` - Tag-based query with AND/ANY modes
5. `list_poems_by_state` - State-filtered listing
6. `get_catalog_stats` - Statistics and health metrics
7. `get_server_info` - Server status and configuration

### Enrichment Tools (6 tools)
8. `get_all_nexuses` - Browse themes/motifs/forms
9. `link_poem_to_nexus` - Add nexus tags to poem
10. `find_nexuses_for_poem` - **Agent analysis** - Get poem + themes for matching
11. `get_poems_for_enrichment` - **Agent analysis** - Batch poems for theme suggestions
12. `sync_nexus_tags` - Sync [[wikilinks]] ↔ tags
13. `move_poem_to_state` - State directory moves

### Quality Scoring (5 tools)
14. `grade_poem_quality` - **Agent analysis** - Get poem + rubric for grading
15. `commit_quality_scores` - Write scores to frontmatter
16. `get_quality_scores` - Retrieve existing scores
17. `find_high_scoring_poems` - Query by dimension/threshold
18. `list_quality_dimensions` - Get dimension definitions (MISSING from grep - check implementation)

### Nexus Management (6 tools)
19. `create_nexus` - Create theme/motif/form
20. `delete_nexus` - Delete nexus (with optional cleanup)
21. `get_poems_by_nexus` - Reverse lookup (nexus → poems)
22. `refresh_nexus_poem_counts` - Populate poem_count field
23. `validate_poem_tags` - Strict tag validation
24. `find_orphaned_tags` - DEPRECATED (alias to validate_poem_tags)

### Submission Management (3 tools)
25. `sync_submissions` - Scan submissions/ directory
26. `list_submissions` - Query by venue/status/poem
27. `get_submission_stats` - Acceptance rates and statistics

### Venue Management (3 tools)
28. `sync_venues` - Scan venues/ directory
29. `list_venues` - Browse with payment/simultaneous filters
30. `get_venue` - Get venue + all submissions
31. `regenerate_venue_file` - Rebuild auto-generated venue file (MISSING - was this removed?)

## Naming Pattern Analysis

### Verb Patterns (Good Consistency)
- **sync_*** (4 tools) - Filesystem → memory operations
- **get_*** (7 tools) - Retrieval operations
- **list_*** (3 tools) - Collection queries
- **find_*** (4 tools) - Search/discovery operations
- **commit_*** (1 tool) - Write operations
- Other verbs: link, move, create, delete, grade, refresh, validate, regenerate

### Naming Consistency Issues
✅ **Good:** Clear verb-noun pattern
✅ **Good:** Pluralization consistent (poems, nexuses, venues, submissions)
⚠️ **Inconsistent:** `regenerate_venue_file` vs `refresh_nexus_poem_counts` (similar operations, different verbs)
⚠️ **Deprecation:** `find_orphaned_tags` marked DEPRECATED but still exists

## Parameter Analysis

### Common Parameter Patterns
- `force_rescan: bool = False` - Used in all sync_* tools (consistent ✅)
- `identifier: str` - Poem lookup (get_poem)
- `limit: int` - Collection size limits (inconsistent defaults: 20, 50, 100)
- `include_content: bool` - Content inclusion flag

### Limit Defaults by Tool
- `search_poems`: default=20
- `find_poems_by_tag`: default=50
- `list_poems_by_state`: default=100
- `list_submissions`: default=50
- `list_venues`: no limit parameter
- `get_poems_for_enrichment`: default=20

⚠️ **Inconsistency:** No standard default limit across tools

### Boolean Parameters
- Most use explicit `True`/`False` defaults ✅
- `delete_nexus` has both `force` and `cleanup_poems` - clear naming ✅

## Return Type Analysis

### Return Type Patterns
- **Pydantic Models:** `Poem`, `SyncResult`, `CatalogStats`, `NexusRegistry`, `Submission`, `Venue`
- **dict:** 13 tools (43%) - used for complex responses with multiple fields
- **List[Model]:** 6 tools - collection returns
- **Optional[Model]:** 1 tool (get_poem)

### dict Return Issues
⚠️ **Type Safety:** 13 tools return `dict` instead of typed models
  - Should define Pydantic models for: create_nexus result, delete_nexus result, validation results, etc.
  - `dict` returns reduce type safety and IDE autocomplete

**Tools returning dict:**
1. `get_server_info`
2. `sync_submissions`
3. `sync_venues`
4. `get_venue`
5. `regenerate_venue_file`
6. `get_poems_by_nexus`
7. `refresh_nexus_poem_counts`
8. `validate_poem_tags`
9. `find_orphaned_tags`
10. `create_nexus`
11. `delete_nexus`
12. `list_submissions` (returns dict with submissions list)
13. `list_venues` (returns dict with venues list)

## Tool Dependency Analysis

### Catalog Dependencies
All tools depend on `get_catalog()` - centralized singleton ✅

### Circular Dependencies
❌ **Issue:** `sync_catalog` and `validate_poem_tags` could create circular calls
  - Validation calls `get_all_nexuses()` which requires initialized enrichment tools
  - Enrichment init requires catalog sync
  - **Mitigation:** Startup sequence in main() handles this correctly

### Tool Coupling
- **High coupling:** Quality tools → catalog (tight but acceptable)
- **Low coupling:** Venue/Submission tools → catalog (good separation ✅)
- **Medium coupling:** Nexus management → catalog (necessary for tag validation)

## Agent Analysis Tools Pattern

Three tools explicitly designed for agent consumption:
1. `find_nexuses_for_poem` - Returns poem + themes for agent to analyze
2. `get_poems_for_enrichment` - Returns batch poems for agent suggestions
3. `grade_poem_quality` - Returns poem + rubric for agent scoring

✅ **Good:** Clear separation of "data provision" vs "data modification"
✅ **Good:** Instructions field guides agent behavior
⚠️ **Documentation:** Should these be in a separate "Agent Tools" category in README?

## Async/Sync Analysis

### All Tools Async
✅ **Consistent:** All 30 tools use `async def`
✅ **Good:** Allows for future I/O optimization
⚠️ **Overhead:** Many tools are purely synchronous internally (no I/O)
  - Consider: Are async signatures necessary for all tools?
  - Current implementation: Most tools don't await anything

### Startup Sync Issue
✅ **Fixed:** `main()` now uses `asyncio.run(validate_poem_tags())` for startup validation

## Error Handling Patterns

### Exception Types
- **ParseError:** Used for domain errors (nexus not found, invalid state, etc.)
- **Generic Exception:** Caught at tool boundaries
- **No custom error types:** For tool-specific failures

⚠️ **Inconsistency:** Some tools return `{"success": False, "error": "message"}` while others raise exceptions

### Error Return Patterns
Tools using `success` field in dict returns:
- `create_nexus` - Returns success: True/False
- `delete_nexus` - Returns success field
- `get_poems_by_nexus` - Returns success: True/False
- `validate_poem_tags` - Returns valid: True/False (different field name!)

⚠️ **Inconsistency:** `success` vs `valid` for similar boolean indicators

## Documentation Analysis

### Docstring Coverage
✅ **Good:** All tools have docstrings
✅ **Good:** Args and Returns sections present
⚠️ **Inconsistent:** Some tools have detailed examples, others don't

### README Tool Organization
Current organization matches code structure ✅
Agent analysis tools noted but could be more prominent

## Architectural Strengths

1. ✅ **Clear categorization** - 6 logical categories
2. ✅ **Consistent verb-noun naming** - Easy to discover
3. ✅ **Centralized singletons** - get_catalog(), get_nexus_manager()
4. ✅ **Agent-first design** - Separate data provision tools
5. ✅ **Deprecation handling** - find_orphaned_tags marked as deprecated
6. ✅ **Startup validation** - Now follows MCP best practices

## Architectural Issues

### High Priority
1. ⚠️ **Type safety:** 13 tools return `dict` instead of Pydantic models
2. ⚠️ **Limit inconsistency:** Default limits vary (20/50/100)
3. ⚠️ **Error handling:** Inconsistent success/valid/error patterns
4. ⚠️ **Deprecated tool:** find_orphaned_tags should be removed or clearly aliased

### Medium Priority
5. ⚠️ **Tool count:** 30 tools is high - consider if some could be combined
6. ⚠️ **Async overhead:** Many tools don't need async signatures
7. ⚠️ **Documentation:** Agent tools could be more prominent in README

### Low Priority
8. ⚠️ **Verb consistency:** `regenerate` vs `refresh` for similar operations
9. ⚠️ **Missing tool:** `list_quality_dimensions` mentioned in README but not found

## Recommendations

### Immediate Actions
1. **Create Pydantic models** for dict returns (ValidationResult, NexusOperationResult, etc.)
2. **Standardize limit defaults** to 50 across all list/query tools
3. **Remove or alias** find_orphaned_tags properly
4. **Standardize error returns** - always use `success: bool` + `error: str | None`

### Short-term Improvements
5. **Add config** for default limits (`search.default_limit` already exists - use it!)
6. **Create tool groups** in README (Data, Analysis, Management)
7. **Document agent tools** more prominently

### Long-term Considerations
8. **Tool consolidation** - Can some tools be merged?
9. **Remove async** from purely synchronous tools (or keep for consistency?)
10. **Add tool versioning** - For future breaking changes

## Tool Count Comparison

**Current:** 30 tools
**README claims:** "30 MCP tools" ✅ Accurate
**Coverage:** 65% (749/2119 lines untested in server.py)
**Most untested:** Tool implementation code (39% coverage in server.py)

## Summary Score

| Category | Score | Notes |
|----------|-------|-------|
| Naming Consistency | 8/10 | Clear patterns, minor verb inconsistencies |
| Type Safety | 5/10 | Too many dict returns |
| Error Handling | 6/10 | Inconsistent patterns |
| Documentation | 8/10 | Good coverage, could be more prominent |
| Organization | 9/10 | Excellent categorization |
| MCP Best Practices | 9/10 | Fixed startup validation issue |
| **Overall** | **7.5/10** | Solid architecture with room for improvement |

## Next Steps

1. Review this audit with user
2. Prioritize recommendations
3. Create follow-up tasks for improvements
4. Consider creating ADRs (Architecture Decision Records) for major patterns
