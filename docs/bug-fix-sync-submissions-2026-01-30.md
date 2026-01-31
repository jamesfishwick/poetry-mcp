# Bug Report: sync_submissions AttributeError

**Date:** 2026-01-30  
**Severity:** High (tool completely broken)  
**Status:** Fixed in commit bb3e8c5

## Issue

The `sync_submissions` MCP tool was raising `AttributeError: 'SubmissionCatalog' object has no attribute 'all_submissions'` when called, making the tool completely non-functional.

## Root Cause

In `src/poetry_mcp/server.py` line 973, the code attempted to access `sub_cat.all_submissions` directly:

```python
all_submissions = sub_cat.all_submissions  # ❌ WRONG
venue_names = set(sub.venue_name for sub in all_submissions)
```

However, `SubmissionCatalog` does not expose an `all_submissions` attribute. The submissions are stored in `self.index.all_submissions` (internal implementation detail) and accessed via the public `get_all()` method.

## Fix

Changed line 973 to use the correct public API:

```python
all_submissions = sub_cat.get_all()  # ✅ CORRECT
venue_names = set(sub.venue_name for sub in all_submissions)
```

## Why This Happened

The bug was introduced when the internal storage structure changed from a simple list to an indexed structure. The `SubmissionIndex` class stores submissions internally in `self.all_submissions`, but the `SubmissionCatalog` class wraps this and provides `get_all()` as the public interface.

## Prevention

Added regression test in `tests/test_submission_catalog_api.py` to ensure:
1. Direct attribute access raises AttributeError (confirms encapsulation)
2. `get_all()` method works correctly
3. `sync_submissions` tool completes without errors

## Testing

```bash
# Unit test
pytest tests/test_submission_catalog_api.py -xvs

# Integration test
poetry-mcp:sync_submissions(force_rescan=false)
```

## Related Code Patterns

**Correct patterns for SubmissionCatalog:**
- ✅ `catalog.get_all()` - Get all submissions
- ✅ `catalog.get_by_venue(name)` - Filter by venue
- ✅ `catalog.get_by_status(status)` - Filter by status
- ✅ `catalog.get_by_poem(title)` - Filter by poem
- ✅ `catalog.filter_submissions(...)` - Multi-criteria filter

**Incorrect patterns:**
- ❌ `catalog.all_submissions` - Private, don't access
- ❌ `catalog.index.all_submissions` - Internal, don't access
- ❌ `catalog.index.*` - All index internals are private

## Similar Potential Issues

Searched codebase for other direct attribute access patterns - none found. The `Catalog` and `VenueCatalog` classes use similar patterns and should be reviewed for consistency.
