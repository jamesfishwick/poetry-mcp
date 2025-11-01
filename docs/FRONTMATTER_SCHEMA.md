# Poetry Frontmatter Schema

**Version:** 2.0
**Last Updated:** 2025-01-31

## Overview

All poems in the catalog should have YAML frontmatter with consistent properties to enable querying via Obsidian BASE views and future MCP server tools.

## Standard Schema

### Required Properties

```yaml
---
state: completed
form: free_verse
---
```

#### `state` (required)
**Type:** String enum
**Values:** `completed | fledgeling | still_cooking | needs_research | risk | phone_poetry`

Indicates the production state of the poem. Should generally align with the directory structure:
- `completed` - Finished, polished poems ready for submission/publication
- `fledgeling` - Early drafts with potential, needs development
- `still_cooking` - Active work in progress
- `needs_research` - Requires fact-checking, research, or reference verification
- `risk` - Experimental poems with uncertain value
- `phone_poetry` - Transitional state for poems drafted on mobile devices (46 poems currently use this)

**Note:** State should generally match the directory the poem is in. The `phone_poetry` state is used for poems in the `phone-poetry/` directory and represents a parallel workflow for mobile-drafted poems that will eventually move to other states.

**Personal workflow directories** (like `journal/`) are allowed, and poems in them should use whichever state best fits their current status.

#### `form` (required)
**Type:** String enum
**Values:** `free_verse | prose_poem | american_sentence | catalog_poem`

Indicates the structural/formal pattern of the poem:
- `free_verse` - No consistent meter or rhyme (most common)
- `prose_poem` - Paragraph formatting, maintains poetic density
- `american_sentence` - Single line, exactly 17 syllables (Ginsberg's form)
- `catalog_poem` - List/accumulation structure with anaphora

**Detection heuristics:**
- Single line ~17 syllables → `american_sentence`
- Paragraph format, no stanzas → `prose_poem`
- Anaphora patterns (3+ lines starting with "and", "or", "the") → `catalog_poem`
- Default → `free_verse`

### Optional Properties

```yaml
---
state: completed
form: free_verse
tags: [water, body, memory, loss]
---
```

#### `tags` (optional)
**Type:** Array of strings
**Format:** `tags: [tag1, tag2, tag3]`

Thematic tags for connecting poems to nexuses and marking workflow status. Two types of tags are used:

**1. Canonical Nexus Tags** - Match the `canonical_tag` values from nexus files:
- Theme tags: `water-liquid`, `body-bones`, `childhood`, `memory`, etc.
- Form tags: `free-verse`, `prose-poem`, `american-sentence`, `catalog-poem`
- Motif tags: `american-grotesque`, `failed-transcendence`, etc.

**2. Ad-Hoc Workflow Tags** - Personal markers and legacy values:
- `favs` - Personal favorites, submission-ready (most common: 58 poems)
- `Completed` - Legacy state marker (7 poems, duplicates state field)
- Custom thematic tags: `regret`, `violence`, `poetry`, etc.

**See also:** docs/CANONICAL_TAGS.md for complete list of nexus tags

### Additional Optional Properties

Rarely used metadata for specific workflow needs:

#### `version` (optional)
**Type:** String
**Format:** `version: 1.5 opening + cleaned up formatting`

Revision notes for tracking poem changes (1 poem uses this).

#### `deadline` (optional)
**Type:** String
**Format:** `deadline: End of November`

Submission deadline tracking (1 poem uses this).

#### `contest` (optional)
**Type:** String
**Format:** `contest: Monsters of Our Own Making`

Venue or contest name for submission tracking (1 poem uses this).

## Current Status

**Frontmatter coverage:** 370/381 poems (97%) ✓

**Property usage:**
- `state`: 364/381 (95.5%) - Nearly complete coverage
- `form`: 363/381 (95.3%) - Nearly complete coverage
- `tags`: 96/381 (25.2%) - Growing through enrichment efforts

## Enrichment Opportunities

### Complete Frontmatter Coverage (97% → 100%)
- Add frontmatter to 11 remaining poems (3%)
- Use directory structure to infer state and form
- Safe operation: purely additive

### Tag Enrichment (25% → 90%+)
Current: 96/381 poems have tags (25.2%)
Goal: 340+/381 poems with canonical nexus tags (90%)

**Approaches:**
1. **Agent-based analysis** - Use MCP tools (`find_nexuses_for_poem`) for theme detection
2. **Batch enrichment** - Process multiple poems with `get_poems_for_enrichment`
3. **Manual tagging** - Add tags during revision workflow in Obsidian

**Priority order:**
1. Completed poems (49 poems) - publication-ready work
2. Risks (22 poems) - experimental work worth preserving
3. Still Cooking (65 poems) - active development
4. Fledgelings (172 poems) - largest group, process gradually

### Cleanup Ad-Hoc Tags (optional)
- Migrate `Completed` tag → verify state field matches (7 poems)
- Standardize `favs` workflow (58 poems) - consider moving to quality scores
- Convert custom thematic tags to canonical nexus tags where applicable

## Examples

### Minimal frontmatter (required only)
```yaml
---
state: fledgeling
form: free_verse
---
```

### Complete frontmatter (with canonical nexus tags)
```yaml
---
state: completed
form: prose_poem
tags: [water-liquid, body-bones, memory, death]
---
```

### Phone-poetry workflow example
```yaml
---
state: phone_poetry
form: prose_poem
tags: [favs]
---
```

### Submission tracking example
```yaml
---
state: completed
form: free_verse
tags: [industrial-mechanical, age, despair]
contest: Monsters of Our Own Making
deadline: End of November
version: 1.5 opening + cleaned up formatting
---
```

## Schema Validation

**BASE view queries rely on:**
- `file.inFolder("Poetry/catalog")` - finds all poems
- Frontmatter properties for filtering/sorting
- `state`, `form`, `tags` for categorical queries

**MCP server requirements:**
- Parse YAML frontmatter from markdown files
- Handle missing optional properties gracefully
- Use `state` for catalog organization
- Use `tags` for nexus connections
- Use `form` for structural analysis

## Notes

- **Frontmatter Coverage** - 370/381 poems (97%) have frontmatter; 11 poems still need frontmatter added
- **State/Directory Alignment** - State should generally match directory, except for `phone_poetry` which is a parallel workflow
- **Form detection is automatic** - MCP server uses heuristics to detect form, but can be manually overridden
- **Tag Types** - Mix canonical nexus tags (from CANONICAL_TAGS.md) with ad-hoc workflow tags (`favs`, etc.)
- **Frontmatter must be valid YAML** - Obsidian's parser is strict, ensure proper formatting

---

**See also:**
- README.md - Architectural Philosophy and frontmatter-first architecture
- IMPLEMENTATION_CHECKLIST.md - Technical Reference for frontmatter parsing strategy
- CANONICAL_TAGS.md - Complete list of canonical nexus tags
- catalog/catalog.base - BASE view definition for Obsidian queries
