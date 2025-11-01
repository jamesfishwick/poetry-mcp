# Poetry MCP Templates

## Important: BASE File Format

Obsidian BASE files **must be created and populated through the Obsidian UI**. 

The template BASE files provided here contain only the `views:` configuration. They define the table structure but contain no data entries.

## Setup Process

1. **Initialize directory structure** (automated):
   ```bash
   poetry-mcp init ~/Documents/Poetry --template=comprehensive
   ```
   This creates folders and empty BASE files.

2. **Open in Obsidian** (manual):
   - Open your Poetry directory in Obsidian
   - Navigate to each BASE file
   - Click "Add row" to populate entries

3. **Run form detection** (automated):
   ```bash
   cd ~/Documents/Poetry
   python3 scripts/add_poem_frontmatter.py --dry-run  # Preview
   python3 scripts/add_poem_frontmatter.py            # Run
   ```

## Templates

### Comprehensive
Full system with all BASE files:
- `nexus.base` - Themes, motifs, forms
- `qualities.base` - 12 quality dimensions
- `venues.base` - Submission venues
- `influences.base` - Writers, movements
- `techniques.base` - Generative methods
- `catalog.base` - Poem registry

### Starter
Minimal system for learning:
- 5 core themes
- 5 essential qualities
- Empty venues/influences/techniques

### Custom
Blank slate with guidance comments.

## Why Manual Population?

Obsidian BASE has a strict YAML parser that doesn't accept programmatically generated data entries. The `---` separator format must be created through the Obsidian UI to ensure proper formatting.

Once populated, the MCP server can read and query these BASE files programmatically.
