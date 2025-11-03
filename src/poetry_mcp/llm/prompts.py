"""Prompt templates for LLM-powered poetry analysis."""

from typing import List
from ..models.nexus import Nexus


SYSTEM_PROMPT = """You are a poetry analysis expert specializing in identifying thematic connections.

Your task is to analyze poems and identify which themes (nexuses) they engage with.
You should look for:
- Direct imagery and references
- Underlying thematic concerns
- Emotional and psychological patterns
- Symbolic connections

Be precise and evidence-based. Only suggest themes with clear textual support.
Assign confidence scores (0.0-1.0) based on how strongly the theme appears."""


def build_theme_detection_prompt(
    poem_title: str,
    poem_content: str,
    available_nexuses: List[Nexus],
    max_suggestions: int = 5,
) -> str:
    """
    Build prompt for detecting themes in a poem.

    Args:
        poem_title: Title of the poem
        poem_content: Full text of the poem
        available_nexuses: List of available theme nexuses to choose from
        max_suggestions: Maximum number of themes to suggest

    Returns:
        Formatted prompt string
    """
    # Build nexus descriptions
    nexus_descriptions = []
    for nexus in available_nexuses:
        # Extract key description from full markdown
        # (For now, just use first few lines of description)
        desc_lines = nexus.description.split("\n")
        brief_desc = []
        for line in desc_lines:
            if line.strip() and not line.startswith("#"):
                brief_desc.append(line.strip())
                if len(brief_desc) >= 3:  # Limit to 3 lines
                    break

        brief_text = " ".join(brief_desc)[:200]  # Max 200 chars

        nexus_descriptions.append(f"**{nexus.name}** (tag: #{nexus.canonical_tag}): {brief_text}")

    nexuses_text = "\n".join(nexus_descriptions)

    prompt = f"""Analyze this poem and identify which themes it engages with.

# Poem to Analyze

**Title**: {poem_title}

**Content**:
```
{poem_content.strip()}
```

# Available Themes

{nexuses_text}

# Task

Identify up to {max_suggestions} themes that appear in this poem.
For each theme, provide:
1. **name**: The theme name (exactly as shown above)
2. **canonical_tag**: The tag to use (exactly as shown above, with #)
3. **confidence**: Float 0.0-1.0 indicating how strongly this theme appears
4. **evidence**: Brief quote or description of why this theme is present

Only suggest themes with clear textual evidence. Higher confidence (>0.7) means the theme is central to the poem. Lower confidence (0.4-0.7) means the theme is present but not dominant.

# Output Format

Respond with **only** valid JSON in this exact structure:

```json
{{
  "themes": [
    {{
      "name": "Water-Liquid",
      "canonical_tag": "water-liquid",
      "confidence": 0.85,
      "evidence": "The poem repeatedly uses water imagery: 'river flows', 'ancient stones', 'mountain to sea'"
    }}
  ]
}}
```

If no themes match, return: `{{"themes": []}}`

Respond now with JSON only:"""

    return prompt


def build_batch_enrichment_prompt(
    poems_data: List[dict],
    available_nexuses: List[Nexus],
) -> str:
    """
    Build prompt for batch enrichment of multiple poems.

    Args:
        poems_data: List of dicts with 'title' and 'content' keys
        available_nexuses: List of available theme nexuses

    Returns:
        Formatted prompt string for batch analysis
    """
    # Build compact nexus reference
    nexus_refs = []
    for nexus in available_nexuses:
        # Very brief description for batch mode
        desc_lines = nexus.description.split("\n")
        brief = next(
            (line.strip() for line in desc_lines if line.strip() and not line.startswith("#")), ""
        )[:100]
        nexus_refs.append(f"#{nexus.canonical_tag}: {brief}")

    nexuses_text = "\n".join(nexus_refs)

    # Build poems list
    poems_text = []
    for i, poem_data in enumerate(poems_data, 1):
        poems_text.append(
            f"""
## Poem {i}: {poem_data['title']}
```
{poem_data['content'].strip()[:500]}...
```
"""
        )

    poems_section = "\n".join(poems_text)

    prompt = f"""Analyze these {len(poems_data)} poems and suggest theme tags for each.

# Available Themes
{nexuses_text}

# Poems to Analyze
{poems_section}

# Task
For each poem, identify 1-3 most relevant themes with confidence scores.

# Output Format
```json
{{
  "results": [
    {{
      "poem_title": "Exact title",
      "themes": [
        {{
          "canonical_tag": "water-liquid",
          "confidence": 0.8
        }}
      ]
    }}
  ]
}}
```

Respond with JSON only:"""

    return prompt
