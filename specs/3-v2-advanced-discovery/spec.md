# Feature Specification: v2-advanced-discovery

## Overview

**Short Name**: v2-advanced-discovery
**Created**: 2026-01-26
**Status**: Draft (v2 - Future)

### Summary

Advanced AI-powered discovery tools that go beyond individual poem analysis to find patterns across the entire catalog, including emerging themes, influence matching, and motif clustering.

## Problem Statement

### Current State

The v1 Poetry MCP provides:
- `find_nexuses_for_poem`: Analyzes single poems against known nexuses
- `get_poems_for_enrichment`: Batch retrieval for theme suggestions
- Manual tagging based on suggestions

Limitations:
- Cannot discover NEW themes not already in the nexus registry
- Cannot identify recurring patterns (motifs) across poems
- Cannot match poems to literary influences based on style
- Each poem analyzed in isolation, missing cross-catalog insights

### Desired State

Poets can:
- Discover emerging themes that don't match existing nexuses
- Find poems that share stylistic qualities with known influences
- Identify motif clusters (recurring image combinations)
- Make data-driven decisions about expanding their nexus taxonomy

### User Impact

- **Creative insight**: Discover unconscious patterns in their work
- **Taxonomy evolution**: Grow nexus registry based on actual writing patterns
- **Literary lineage**: Understand which influences manifest in specific poems
- **Collection curation**: Group poems by subtle stylistic connections

---

## User Scenarios & Testing

### Primary User Flow

1. Poet wants to understand recurring patterns across 50+ fledgeling poems
2. Runs emerging themes extraction on their untagged work
3. Reviews suggested new themes with supporting evidence
4. Decides which themes to add to nexus registry
5. Auto-applies new nexus tags to matching poems

### Acceptance Scenarios

#### Scenario 1: Extract Emerging Themes

**Given**: 30 poems with minimal/no tagging
**When**: Poet runs extract_emerging_themes with min_poems=3
**Then**: Returns themes appearing in 3+ poems, with poem lists and confidence scores

#### Scenario 2: Match Poems to Influences

**Given**: Poet has defined influences (e.g., "Bronk's austerity", "Beat aesthetic")
**When**: Running suggest_influences_for_poem on a completed poem
**Then**: Returns ranked influence matches with specific stylistic evidence

#### Scenario 3: Detect Motifs

**Given**: Catalog with 100+ poems
**When**: Running detect_motifs with min_poems=5
**Then**: Returns clusters of co-occurring themes (e.g., "Water + Body + Failure" pattern)

---

## Functional Requirements

### Mandatory (Must Have)

| ID    | Requirement                               | Acceptance Criteria                                           |
|-------|-------------------------------------------|---------------------------------------------------------------|
| FR-1  | Extract emerging themes from poem set     | Returns themes with poem lists, confidence, and evidence      |
| FR-2  | Compare to existing nexuses               | Distinguishes new themes from existing ones                   |
| FR-3  | Suggest influences for poem               | Returns ranked influence matches with stylistic reasoning     |
| FR-4  | Detect motifs (theme clusters)            | Returns co-occurring theme patterns with poem groups          |
| FR-5  | Threshold filtering                       | All tools respect min_poems/min_confidence parameters         |
| FR-6  | Evidence citation                         | All suggestions include specific poem excerpts as evidence    |

### Optional (Nice to Have)

| ID     | Requirement                                | Acceptance Criteria                                          |
|--------|--------------------------------------------|-----------------------------------------------------------------|
| FR-O1  | Create nexus from emerging theme           | One-click nexus creation from discovery results               |
| FR-O2  | Motif visualization data                   | Export data for external visualization tools                  |
| FR-O3  | Influence bibliography suggestions         | Suggest reading based on detected influence patterns          |

---

## Success Criteria

| Criterion                          | Target        | Measurement Method                           |
|------------------------------------|---------------|----------------------------------------------|
| Theme extraction accuracy          | 70%+ useful   | User accepts 7+ of 10 suggested themes       |
| Influence matching precision       | 60%+ correct  | User agrees with 6+ of 10 influence matches  |
| Motif detection relevance          | 80%+ coherent | Detected clusters are semantically meaningful |
| Processing time (50 poems)         | Under 2 min   | End-to-end analysis completes quickly        |

---

## Key Entities

| Entity              | Description                                    | Key Attributes                           |
|---------------------|------------------------------------------------|------------------------------------------|
| Emerging Theme      | Newly discovered pattern not in nexus registry | name, description, poems, confidence     |
| Influence Match     | Poem-to-influence stylistic connection         | influence_name, poem_id, evidence, score |
| Motif               | Recurring combination of themes                | theme_set, poems, co-occurrence_strength |

---

## Constraints & Assumptions

### Constraints

- Requires sufficient poem content for meaningful analysis (min ~10 lines per poem)
- Influence matching requires pre-defined influence aesthetic descriptions
- Motif detection requires existing theme tags for co-occurrence analysis

### Assumptions

- Poets have defined at least 5 influences in their vault
- Most poems have 50+ words of content
- Emerging themes will be reviewed before nexus creation
- Analysis uses agent-based pattern (no direct API costs to Poetry MCP)

---

## Out of Scope

- Real-time theme detection during writing
- Automatic nexus creation without human review
- Influence detection for poets not in the vault's influence registry
- Cross-poet comparison or collaboration features

---

## Dependencies

- v1 enrichment tools (find_nexuses_for_poem as baseline)
- Influence parser (load_influence_registry)
- Nexus registry (for comparison and creation)
- LLM integration architecture (prompts, cost tracking)

---

## Resolved Questions

### LLM Integration Pattern
**Decision**: Agent-based pattern (Recommended)
- MCP provides structured data (poems, nexuses, influences)
- Claude (the agent in conversation) performs analysis
- No API keys or direct costs to Poetry MCP
- Aligns with existing v1 architecture

### Cost Structure
**Decision**: No direct costs (Agent-based)
- User bears Claude usage costs as part of normal agent interaction
- Poetry MCP has no per-request API costs
- Simplifies architecture and deployment

---

## Revision History

| Date       | Author | Changes                                           |
|------------|--------|---------------------------------------------------|
| 2026-01-26 | Claude | Initial draft from IMPLEMENTATION_CHECKLIST.md   |
| 2026-01-26 | Claude | Resolved open questions: agent-based, no costs    |
