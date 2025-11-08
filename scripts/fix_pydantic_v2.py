#!/usr/bin/env python3
"""Fix Pydantic V2 deprecations in models."""

import re
from pathlib import Path

def fix_file(file_path: Path):
    """Fix Pydantic V2 deprecations in a single file."""
    content = file_path.read_text()
    original = content

    # Add ConfigDict import if needed
    if "class Config:" in content and "ConfigDict" not in content:
        content = re.sub(
            r'from pydantic import ([^\n]+)',
            lambda m: f'from pydantic import {m.group(1)}, ConfigDict' if 'ConfigDict' not in m.group(1) else m.group(0),
            content
        )

    # Replace class Config: with model_config = ConfigDict(
    content = re.sub(
        r'(\s+)class Config:\s*\n\s*"""[^"]*"""\s*\n\s*\n\s*json_schema_extra = ({[^}]+})',
        r'\1model_config = ConfigDict(\n\1    json_schema_extra=\2\n\1)',
        content,
        flags=re.DOTALL
    )

    if content != original:
        file_path.write_text(content)
        print(f"Fixed: {file_path}")
        return True
    return False

# Fix remaining files
files = [
    Path("src/poetry_mcp/models/influence.py"),
    Path("src/poetry_mcp/models/results.py"),
]

for file_path in files:
    if file_path.exists():
        fix_file(file_path)
