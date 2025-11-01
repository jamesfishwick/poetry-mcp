#!/usr/bin/env python3
"""
Add/update form property to all poem files.
Obsidian BASE will automatically index this property.

This script:
1. Scans all .md files in catalog directories
2. Detects poem form (free_verse, prose_poem, american_sentence, catalog_poem)
3. Adds/updates 'form' in frontmatter
4. Preserves all existing frontmatter properties
"""

import os
import re
from pathlib import Path
import yaml

# Files to skip
SKIP_FILES = {
    'complete_chapbook.md', 
    'reading_copy.md', 
    'spiel.md',
    '.DS_Store'
}

def parse_frontmatter(content):
    """Extract existing frontmatter and content"""
    match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
            body = match.group(2)
            return fm, body
        except:
            return {}, content
    return {}, content

def detect_form(body, title=""):
    """Detect poem form using heuristics"""
    # Remove title heading if present
    clean = re.sub(r'^#.*?\n', '', body, count=1).strip()
    
    # American sentence: single non-empty line, or "american sentence" in title/text
    non_empty_lines = [l for l in clean.split('\n') if l.strip()]
    if (len(non_empty_lines) == 1 or 
        'american sentence' in body.lower() or 
        'american sentence' in title.lower()):
        return 'american_sentence'
    
    # Catalog poem: repeated "and" or anaphora patterns (3+ lines starting with "And [Capital]")
    and_pattern_count = len(re.findall(r'\n[Aa]nd [A-Z]', body))
    if and_pattern_count >= 3:
        return 'catalog_poem'
    
    # Prose poem: no stanzas (no paragraph breaks)
    paragraphs = [p for p in clean.split('\n\n') if p.strip()]
    if len(paragraphs) <= 1 and len(non_empty_lines) > 1:
        return 'prose_poem'
    
    return 'free_verse'

def process_poem(filepath, dry_run=False):
    """Add/update form property in frontmatter"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        print(f"❌ Error reading {filepath.name}: {e}")
        return False
    
    # Parse existing frontmatter
    existing_fm, body = parse_frontmatter(content)
    
    # Detect form
    form = detect_form(body, filepath.stem)
    
    # Skip if form already exists and matches
    if 'form' in existing_fm and existing_fm['form'] == form:
        return True
    
    # Build updated frontmatter
    updated_fm = existing_fm.copy()
    updated_fm['form'] = form
    
    # Generate new frontmatter YAML
    fm_yaml = yaml.dump(updated_fm, default_flow_style=False, sort_keys=False)
    
    # Construct new content
    new_content = f"---\n{fm_yaml}---\n{body}"
    
    if dry_run:
        if 'form' in existing_fm:
            print(f"  Would update: {filepath.name}")
            print(f"    {existing_fm['form']} → {form}")
        else:
            print(f"  Would add: {filepath.name}")
            print(f"    form={form}")
        return True
    
    # Write updated content
    try:
        filepath.write_text(new_content, encoding='utf-8')
        return True
    except Exception as e:
        print(f"❌ Error writing {filepath.name}: {e}")
        return False

def main(poetry_dir, dry_run=False):
    """Process all poems in catalog directories"""
    poetry_dir = Path(poetry_dir).expanduser().resolve()
    catalog_dir = poetry_dir / "catalog"
    
    state_dirs = ['Completed', 'Fledgelings', 'Needs Research', 'Risks', 'Still Cooking']
    
    # Collect all poem files
    poems = []
    for state_dir in state_dirs:
        dir_path = catalog_dir / state_dir
        if dir_path.exists():
            for md_file in dir_path.rglob('*.md'):
                if md_file.name not in SKIP_FILES:
                    poems.append(md_file)
    
    print(f"Found {len(poems)} poems to process...")
    if dry_run:
        print("DRY RUN - no files will be modified\n")
    else:
        print("LIVE RUN - files will be modified\n")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Process each poem
    success_count = 0
    for i, poem_path in enumerate(poems, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(poems)}...")
        if process_poem(poem_path, dry_run=dry_run):
            success_count += 1
    
    print(f"\n✓ Successfully processed {success_count}/{len(poems)} poems")
    if not dry_run:
        print(f"\nObsidian BASE will now automatically index the 'form' property.")

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Add form property to poem frontmatter')
    parser.add_argument('poetry_dir', nargs='?', default=os.getcwd(),
                       help='Poetry directory path')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without modifying files')
    
    args = parser.parse_args()
    main(args.poetry_dir, dry_run=args.dry_run)
