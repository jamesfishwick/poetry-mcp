"""Quality-scoring tool implementations.

Extracted from server.py. Each impl takes an explicit `catalog` (keyword-only)
so it stays testable and free of module globals / circular imports; the server
wrappers pass get_catalog().
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from ..parsers.frontmatter_parser import extract_frontmatter
from ..writers.frontmatter_writer import create_backup

logger = logging.getLogger(__name__)

VALID_DIMENSIONS = {
    "detail",
    "life",
    "music",
    "mystery",
    "sufficient thought",
    "surprise",
    "syntax",
    "unity",
}


def commit_quality_scores_impl(
    poem_id: str,
    scores: dict,
    notes: str | None = None,
    *,
    catalog: Any,
) -> dict:
    """Validate and write quality scores to a poem's frontmatter."""
    cat = catalog

    poem = cat.index.get_by_id_or_title(poem_id)
    if not poem:
        return {"success": False, "error": f"Poem not found: {poem_id}"}

    normalized_scores = {}
    for dimension, score in scores.items():
        dim_lower = dimension.lower().strip()
        if dim_lower not in VALID_DIMENSIONS:
            return {
                "success": False,
                "error": f"Invalid dimension '{dimension}'. Valid: {sorted(VALID_DIMENSIONS)}",
            }
        if not isinstance(score, int) or score < 0 or score > 10:
            return {
                "success": False,
                "error": f"Score for '{dimension}' must be integer 0-10, got: {score}",
            }
        normalized_scores[dim_lower] = score

    vault_root = Path(cat.vault_root)
    file_path = vault_root / poem.file_path
    if not file_path.exists():
        return {"success": False, "error": f"Poem file not found: {file_path}"}

    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content, file_path)

    frontmatter["qualities"] = normalized_scores
    if notes:
        frontmatter["quality_notes"] = notes

    fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    new_content = f"---\n{fm_yaml}---\n{body}"

    create_backup(file_path)
    file_path.write_text(new_content, encoding="utf-8")

    cat.sync()
    logger.info(f"Committed quality scores for '{poem.title}': {normalized_scores}")

    return {
        "success": True,
        "poem_id": poem.id,
        "scores_committed": normalized_scores,
        "notes": notes,
        "file_path": str(file_path),
    }


def get_quality_scores_impl(poem_id: str, *, catalog: Any) -> dict:
    """Read quality scores + notes from a poem's frontmatter."""
    cat = catalog

    poem = cat.index.get_by_id_or_title(poem_id)
    if not poem:
        return {"success": False, "error": f"Poem not found: {poem_id}"}

    scores = poem.qualities if poem.qualities else {}

    vault_root = Path(cat.vault_root)
    file_path = vault_root / poem.file_path

    notes = None
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        frontmatter, _ = extract_frontmatter(content, file_path)
        notes = frontmatter.get("quality_notes")

    return {
        "success": True,
        "poem_id": poem.id,
        "poem_title": poem.title,
        "scores": scores,
        "notes": notes,
        "has_scores": len(scores) > 0,
    }


def find_high_scoring_poems_impl(
    qualities: list[str],
    min_score: int = 8,
    states: list[str] | None = None,
    limit: int = 20,
    *,
    catalog: Any,
) -> dict:
    """Find poems scoring >= min_score on all requested quality dimensions."""
    cat = catalog

    normalized_qualities = []
    for q in qualities:
        q_lower = q.lower().strip()
        if q_lower not in VALID_DIMENSIONS:
            return {
                "success": False,
                "error": f"Invalid quality dimension '{q}'. Valid: {sorted(VALID_DIMENSIONS)}",
            }
        normalized_qualities.append(q_lower)

    matching_poems = []
    for poem in cat.index.all_poems:
        if states and poem.state not in states:
            continue
        if not poem.qualities:
            continue

        matches_all = True
        dimension_scores = {}
        for quality in normalized_qualities:
            score = poem.qualities.get(quality)
            if score is None or score < min_score:
                matches_all = False
                break
            dimension_scores[quality] = score

        if matches_all:
            avg_score = sum(dimension_scores.values()) / len(dimension_scores)
            matching_poems.append(
                {
                    "id": poem.id,
                    "title": poem.title,
                    "state": poem.state,
                    "form": poem.form,
                    "scores": dimension_scores,
                    "avg_score": round(avg_score, 1),
                    "all_scores": poem.qualities,
                }
            )

    matching_poems.sort(key=lambda p: p["avg_score"], reverse=True)  # type: ignore[arg-type,return-value]
    limited_poems = matching_poems[:limit]
    logger.info(f"Found {len(matching_poems)} poems scoring {min_score}+ on {normalized_qualities}")

    return {
        "success": True,
        "poems": limited_poems,
        "total_matches": len(matching_poems),
        "returned": len(limited_poems),
        "query": {
            "qualities": normalized_qualities,
            "min_score": min_score,
            "states": states,
            "limit": limit,
        },
    }
