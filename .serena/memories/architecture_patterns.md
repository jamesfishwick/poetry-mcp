# Poetry MCP - Architecture Patterns

## Three Types of Metadata

### 1. Nexus (Binary)
- What does this poem **contain**?
- Example: Contains water imagery (yes/no)
- Categories: Forms (4), Themes (17), Motifs (4)

### 2. Quality (Scalar)  
- What does this poem **achieve**?
- Example: Scores 8/10 on "Surprise"
- 8 Universal Dimensions: Detail, Life, Music, Mystery, Sufficient Thought, Surprise, Syntax, Unity

### 3. Influence (Lineage)
- Where does this poem **come from**?
- Example: Descended from William Bronk
- Tracks writer/movement/aesthetic lineage

## Agent-Based Analysis Pattern

**Server Responsibilities:**
- Catalog management (scan, index, search)
- Data access (poems, nexuses, quality rubrics)
- Data modification (update tags, move files)

**Agent (Claude) Responsibilities:**
- Poetry analysis (theme detection)
- Quality assessment (grading dimensions)
- Batch processing (multiple poem analysis)

**Benefits:**
- No API keys needed in server
- Server stays lightweight and data-focused
- Agent uses natural language understanding
- Transparent analysis (reasoning visible)
- Flexible analysis approaches

## Vault Directory Structure

```
/Poetry/
├── catalog/           # State-based poem organization (381 poems)
│   ├── Completed/     # 49 poems
│   ├── Fledgelings/   # 172 poems
│   ├── Needs Research/# 10 poems
│   ├── Risks/         # 22 poems
│   └── Still Cooking/ # 65 poems
├── nexus/             # Thematic/formal connections
│   ├── themes/        # 17 thematic connections
│   ├── forms/         # 4 structural patterns
│   └── motifs/        # 4 compositional patterns
├── Qualities/         # 8 universal quality dimensions
├── influences/        # Writer/movement lineage
├── techniques/        # Generative methods
├── venues/            # Publication venues (22 venues)
└── Submissions/       # Historical submissions
```

## Data Synchronization

**Current (v1):**
- Server starts → scans catalog/ → parses frontmatter → Pydantic models in RAM
- Models persist in memory during server lifetime
- To see changes: restart server (< 3 seconds)

**Future (v2):**
- Manual reload tool: `reload_catalog()`
- File watching with debouncing
- Real-time synchronization
