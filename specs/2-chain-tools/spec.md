# Feature Specification: chain-tools

## Overview

**Short Name**: chain-tools
**Created**: 2026-01-26
**Status**: Complete ✅ (documented, tested at 89% coverage)

### Summary

Enable poets to organize poems into ordered sequences or themed collections called "chains", with chain membership stored directly in poem frontmatter following the project's frontmatter-first architecture.

## Problem Statement

### Current State

Poets have individual poems in their vault but no way to:
- Group related poems into coherent sequences (e.g., a chapbook order)
- Track themed collections (e.g., "all water poems")
- Maintain reading order for poem series
- Export poems in a specific sequence

### Desired State

Poets can:
- Create named chains of poems with optional ordering
- Add/remove poems from chains
- Reorder poems within chains
- View chain contents with full poem details
- Query chains across their catalog

### User Impact

- **Manuscript preparation**: Order poems for chapbook/collection submission
- **Thematic exploration**: Group poems by recurring imagery or theme
- **Reading sequences**: Create curated reading paths through the vault
- **Export preparation**: Prepare poems in specific order for publication

---

## User Scenarios & Testing

### Primary User Flow

1. Poet identifies poems that belong together (e.g., water imagery sequence)
2. Creates a chain with an identifying name
3. Adds poems in desired order
4. Reviews chain to verify order and completeness
5. Reorders or adds/removes poems as needed
6. Uses chain for manuscript preparation or export

### Acceptance Scenarios

#### Scenario 1: Create Ordered Sequence

**Given**: Three poems exist: "antlion", "second-bridge", "river-poem"
**When**: Poet creates chain "water-sequence" with ordered=true
**Then**: Each poem receives position (1, 2, 3) and chain membership in frontmatter

#### Scenario 2: Create Themed Collection

**Given**: Five poems with water imagery exist
**When**: Poet creates chain "water-imagery" with ordered=false
**Then**: Poems are grouped together without position numbers (loose collection)

#### Scenario 3: Reorder Within Chain

**Given**: Chain "water-sequence" exists with poems in positions 1, 2, 3
**When**: Poet moves poem at position 3 to position 1
**Then**: All positions update: former #3 becomes #1, others shift accordingly

#### Scenario 4: View Chain Contents

**Given**: Chain "water-sequence" exists with 3 poems
**When**: Poet requests chain details with include_content=true
**Then**: Returns all poems with full content, ordered by position

---

## Functional Requirements

### Mandatory (Must Have)

| ID    | Requirement                        | Acceptance Criteria                                             |
|-------|------------------------------------|-----------------------------------------------------------------|
| FR-1  | Create chain with initial poems    | Chain created with normalized ID, poems updated                 |
| FR-2  | Support ordered and unordered chains | Position tracking for ordered; loose membership for unordered  |
| FR-3  | Add poems to existing chain        | Poems receive chain membership, optional position assignment    |
| FR-4  | Remove poems from chain            | Chain membership removed, positions recalculated                |
| FR-5  | Reorder poems in chain             | Position updates propagate correctly                            |
| FR-6  | Delete entire chain                | All chain membership removed from affected poems                |
| FR-7  | Get chain details                  | Returns poems in order with optional content                    |
| FR-8  | List all chains                    | Returns all chains with poem counts                             |

### Optional (Nice to Have)

| ID     | Requirement                         | Acceptance Criteria                                            |
|--------|-------------------------------------|----------------------------------------------------------------|
| FR-O1  | Chain metadata (description, notes) | Chains can have descriptive metadata                           |
| FR-O2  | Export chain to file                | Export ordered poems to single file for submission             |
| FR-O3  | Chain templates                     | Pre-defined chain structures (e.g., "chapbook-30")             |

---

## Success Criteria

| Criterion                       | Target        | Measurement Method                          |
|---------------------------------|---------------|---------------------------------------------|
| Chain creation success rate     | 100%          | All valid chain operations succeed          |
| Position consistency            | 100%          | No gaps or duplicates in ordered chains     |
| Frontmatter integrity           | 100%          | Chain updates don't corrupt other fields    |
| Query performance               | Under 1 second | Chain listing and retrieval fast            |

---

## Key Entities

| Entity          | Description                                | Key Attributes                            |
|-----------------|--------------------------------------------|-------------------------------------------|
| Chain           | Named grouping of poems                    | chain_id, ordered (bool), poem_count      |
| Chain Membership| A poem's membership in a chain             | chain_id, position (optional)             |
| Chain Position  | Order within an ordered chain              | 1-based integer, unique within chain      |

---

## Constraints & Assumptions

### Constraints

- Chain membership stored in poem frontmatter (no separate database)
- Chain IDs normalized to lowercase-with-dashes format
- Poems can belong to multiple chains simultaneously
- Positions must be unique within an ordered chain

### Assumptions

- Poets understand the difference between ordered sequences and loose collections
- Chain IDs will be meaningful (e.g., "water-sequence", not "chain-1")
- Most chains will have fewer than 50 poems
- Reordering will be infrequent compared to viewing

---

## Out of Scope

- Visual chain builder/editor UI
- Automatic chain suggestions based on content
- Chain versioning or history
- Cross-vault chain sharing
- Chain export to specific formats (Word, PDF)

---

## Dependencies

- frontmatter_writer.py (update_poem_chains function)
- Catalog index (get_by_id_or_title lookups)
- Poem model (chains field in frontmatter)

---

## Revision History

| Date       | Author | Changes                                              |
|------------|--------|------------------------------------------------------|
| 2026-01-26 | Claude | Initial specification from implemented chain_tools.py |
