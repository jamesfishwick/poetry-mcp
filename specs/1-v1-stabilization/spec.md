# Feature Specification: v1-stabilization

## Overview

**Short Name**: v1-stabilization
**Created**: 2026-01-26
**Status**: Draft

### Summary

Stabilize the v1 release by fixing 3 test failures, restoring test coverage to 85%, and ensuring the implementation checklist accurately reflects the current codebase state.

## Problem Statement

### Current State

The Poetry MCP server has grown from the documented 17 tools to 31 tools, with new features including:
- Chain tools (8 tools) - poems can be organized into ordered sequences
- Venue management tools (3 tools) - sync, list, regenerate venues
- Submission tracking (3 tools) - track poem submissions to venues
- Nexus management (3 tools) - create, delete, validate nexuses

However, this growth has introduced:
1. **3 test failures** in config module (SearchConfig and PoetryMCPConfig)
2. **Coverage regression** from 85% to 63% (-22 percentage points)
3. **Documentation drift** - IMPLEMENTATION_CHECKLIST.md is outdated (lists 17 tools, 343 tests)

### Desired State

1. All 363+ tests pass (100% pass rate)
2. Code coverage restored to 85% minimum
3. IMPLEMENTATION_CHECKLIST.md updated to reflect actual state
4. All 31 tools documented and tested

### User Impact

- Developers can trust the test suite and documentation
- CI/CD pipeline reliably validates changes
- New contributors understand the actual codebase state

---

## User Scenarios & Testing

### Primary User Flow

1. Developer runs `uv run pytest tests/ -q`
2. All tests pass with no failures
3. Coverage report shows 85%+ coverage
4. IMPLEMENTATION_CHECKLIST.md matches reality

### Acceptance Scenarios

#### Scenario 1: All Tests Pass

**Given**: The poetry-mcp codebase with current changes
**When**: Running `uv run pytest tests/`
**Then**: All tests pass with 0 failures

#### Scenario 2: Coverage Target Met

**Given**: The poetry-mcp codebase
**When**: Running `uv run pytest tests/ --cov=poetry_mcp --cov-report=term`
**Then**: Overall coverage is 85% or higher

#### Scenario 3: Documentation Accuracy

**Given**: The IMPLEMENTATION_CHECKLIST.md file
**When**: Comparing documented tools/tests to actual implementation
**Then**: All numbers and statuses match reality

---

## Functional Requirements

### Mandatory (Must Have)

| ID    | Requirement                               | Acceptance Criteria                                            |
|-------|-------------------------------------------|----------------------------------------------------------------|
| FR-1  | Fix SearchConfig test failures            | `test_search_config_defaults` passes                           |
| FR-2  | Fix PoetryMCPConfig test failures         | `test_complete_config_with_defaults` and `test_load_minimal_config_file` pass |
| FR-3  | Add tests for chain_tools.py              | Coverage for chain_tools.py increases from 56% to 80%+         |
| FR-4  | Add tests for venue_writer.py             | Coverage for venue_writer.py increases from 12% to 70%+        |
| FR-5  | Add tests for nexus_writer.py             | Coverage for nexus_writer.py increases from 38% to 70%+        |
| FR-6  | Update IMPLEMENTATION_CHECKLIST.md        | Tool count, test count, and coverage numbers reflect reality   |

### Optional (Nice to Have)

| ID     | Requirement                                | Acceptance Criteria                                           |
|--------|--------------------------------------------|-----------------------------------------------------------------|
| FR-O1  | Add tests for server.py new tools          | Server coverage increases from 38% to 60%+                     |
| FR-O2  | Document new tool categories in README     | README lists all 31 tools with descriptions                    |

---

## Success Criteria

| Criterion               | Target | Measurement Method                          |
|-------------------------|--------|---------------------------------------------|
| Test pass rate          | 100%   | `pytest tests/` output shows 0 failures     |
| Overall coverage        | 85%+   | `pytest --cov` reports 85%+                 |
| Config module coverage  | 70%+   | Per-module coverage report                  |
| Writer module coverage  | 70%+   | Per-module coverage report                  |
| Documentation accuracy  | 100%   | Manual comparison of checklist vs code      |

---

## Key Entities

| Entity           | Description                       | Key Attributes                                |
|------------------|-----------------------------------|-----------------------------------------------|
| SearchConfig     | Configuration for search behavior | max_results, default_limit                    |
| PoetryMCPConfig  | Main configuration model          | vault_path, search_config, logging_config     |
| ChainTools       | Poem sequence management          | create, add, remove, reorder, delete, get, list |

---

## Constraints & Assumptions

### Constraints

- Must maintain backward compatibility with existing tool interfaces
- Cannot change public API signatures of existing tools
- Must work with Python 3.10+

### Assumptions

- The 3 test failures are due to config model changes, not fundamental issues
- Coverage regression is due to new untested code, not removed tests
- Chain tools feature is intentional and should be documented/tested

---

## Out of Scope

- Adding new features beyond what's currently implemented
- Refactoring existing tool implementations
- Performance optimizations
- v2 features (deferred items in checklist)

---

## Dependencies

- Existing test fixtures in tests/fixtures/
- Poetry vault for integration testing

---

## Revision History

| Date       | Author | Changes                                |
|------------|--------|----------------------------------------|
| 2026-01-26 | Claude | Initial draft based on test analysis   |
