"""
Nexus file writer.

Generates nexus markdown files for themes, motifs, and forms.
"""

from pathlib import Path
from typing import Literal

import yaml

from poetry_mcp.models.nexus import Nexus


class NexusWriter:
    """
    Generates nexus markdown files from nexus metadata.

    Nexus files contain:
    1. Frontmatter with canonical_tag
    2. Markdown content with description and structure
    """

    def generate_nexus_file(
        self,
        nexus: Nexus,
        output_path: Path,
        template: str | None = None,
    ) -> None:
        """
        Generate a nexus markdown file.

        Args:
            nexus: Nexus metadata
            output_path: Where to write the file
            template: Optional custom markdown template (uses default if None)
        """
        # Generate frontmatter
        frontmatter = self._generate_frontmatter(nexus)

        # Generate markdown content
        content = template or self._generate_default_template(nexus)

        # Combine into full file
        full_content = f"{frontmatter}\n\n{content}"

        # Write file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_content, encoding="utf-8")

    def _generate_frontmatter(self, nexus: Nexus) -> str:
        """Generate YAML frontmatter from nexus metadata."""
        frontmatter_dict = {
            "canonical_tag": nexus.canonical_tag,
        }

        # Serialize to YAML
        yaml_str = yaml.dump(
            frontmatter_dict,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        return f"---\n{yaml_str}---"

    def _generate_default_template(self, nexus: Nexus) -> str:
        """Generate default markdown template for new nexus."""
        category_title = {
            "theme": "Theme",
            "motif": "Motif",
            "form": "Form",
        }[nexus.category]

        template = f"""# {nexus.name}

## Overview

{nexus.description}

## Key Appearances

### Poems
- _To be filled as poems are tagged_

## Analysis

### Characteristics
1. **Element 1** - description
2. **Element 2** - description
3. **Element 3** - description

### Connection to Other {category_title}s
- _To be filled_

## Related Poems
- _To be filled_

---
Tags: #poetry-analysis #{nexus.category}
Created: {self._get_today_iso()}
"""
        return template

    def _get_today_iso(self) -> str:
        """Get today's date in ISO format."""
        from datetime import date

        return date.today().isoformat()

    def get_nexus_filename(self, name: str, category: Literal["theme", "motif", "form"]) -> str:
        """
        Generate canonical filename for a nexus.

        Args:
            name: Nexus name
            category: Nexus category

        Returns:
            Filename string (e.g., "Water-Liquid Imagery.md")
        """
        # For themes, add " Imagery" suffix if not present
        if category == "theme" and not name.endswith(" Imagery"):
            return f"{name} Imagery.md"
        else:
            return f"{name}.md"
