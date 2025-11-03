"""Integration tests for quality scoring MCP tools."""

import pytest
from pathlib import Path
import tempfile

from poetry_mcp.catalog.catalog import Catalog


@pytest.fixture
def temp_vault():
    """Create a temporary vault with test poems."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create completed directory with scored poem
        completed_dir = vault_path / "catalog" / "completed"
        completed_dir.mkdir(parents=True)

        scored_poem = completed_dir / "scored-poem.md"
        scored_poem.write_text(
            """---
title: Scored Poem
state: completed
form: free_verse
qualities:
  detail: 8
  life: 7
  music: 6
  mystery: 9
  sufficient thought: 8
  surprise: 7
  syntax: 8
  unity: 9
quality_notes: Strong imagery and mystery, adequate music
---

This is a poem with quality scores.
Multiple stanzas here.

Second stanza content.
""",
            encoding="utf-8",
        )

        # Create poem without scores
        unscored_poem = completed_dir / "unscored-poem.md"
        unscored_poem.write_text(
            """---
title: Unscored Poem
state: completed
form: prose_poem
---

This poem has no quality scores yet.
""",
            encoding="utf-8",
        )

        # Create fledgeling poem with partial scores
        fledge_dir = vault_path / "catalog" / "fledgeling"
        fledge_dir.mkdir(parents=True)

        partial_poem = fledge_dir / "partial-scores.md"
        partial_poem.write_text(
            """---
title: Partial Scores
state: fledgeling
form: free_verse
qualities:
  detail: 5
  mystery: 6
---

Work in progress poem.
""",
            encoding="utf-8",
        )

        yield vault_path


@pytest.fixture
def catalog(temp_vault):
    """Initialize catalog with temp vault."""
    cat = Catalog(vault_root=str(temp_vault))
    cat.sync()
    return cat


class TestCommitQualityScores:
    """Test commit_quality_scores() tool."""

    def test_commit_valid_scores(self, catalog, temp_vault):
        """Test committing valid quality scores to unscored poem."""
        scores = {
            "detail": 7,
            "life": 8,
            "music": 6,
            "mystery": 9,
            "sufficient thought": 7,
            "surprise": 8,
            "syntax": 7,
            "unity": 8,
        }

        # Commit scores
        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(
            poem_id="unscored-poem", scores=scores, notes="Test scoring notes", catalog=catalog
        )

        assert result["success"] is True
        assert result["scores_committed"] == scores

        # Verify backup was created
        poem_path = temp_vault / "catalog" / "completed" / "unscored-poem.md"
        backup_path = Path(str(poem_path) + ".bak")
        assert backup_path.exists()

        # Verify scores written to frontmatter
        content = poem_path.read_text(encoding="utf-8")
        assert "detail: 7" in content
        assert "mystery: 9" in content
        assert "quality_notes: Test scoring notes" in content

    def test_commit_normalizes_dimension_names(self, catalog):
        """Test that dimension names are normalized to lowercase."""
        scores = {"DETAIL": 8, "Life": 7, "  Music  ": 6}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        assert result["success"] is True
        assert "detail" in result["scores_committed"]
        assert "life" in result["scores_committed"]
        assert "music" in result["scores_committed"]

    def test_commit_invalid_dimension_name(self, catalog):
        """Test that invalid dimension names are rejected."""
        scores = {"invalid_dimension": 8}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        assert result["success"] is False
        assert "Invalid dimension" in result["error"]

    def test_commit_score_out_of_range(self, catalog):
        """Test that scores outside 0-10 range are rejected."""
        scores = {"detail": 15}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        assert result["success"] is False
        assert "must be integer 0-10" in result["error"]

    def test_commit_negative_score(self, catalog):
        """Test that negative scores are rejected."""
        scores = {"detail": -1}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        assert result["success"] is False
        assert "must be integer 0-10" in result["error"]

    def test_commit_non_integer_score(self, catalog):
        """Test that non-integer scores are rejected."""
        scores = {"detail": 7.5}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        assert result["success"] is False
        assert "must be integer 0-10" in result["error"]

    def test_commit_poem_not_found(self, catalog):
        """Test error when poem doesn't exist."""
        scores = {"detail": 8}

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(
            poem_id="nonexistent-poem", scores=scores, catalog=catalog
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_commit_overwrites_existing_scores(self, catalog, temp_vault):
        """Test that committing scores overwrites existing ones."""
        new_scores = {
            "detail": 10,
            "life": 9,
            "music": 8,
            "mystery": 10,
            "sufficient thought": 9,
            "surprise": 8,
            "syntax": 9,
            "unity": 10,
        }

        from poetry_mcp.server import commit_quality_scores_impl

        result = commit_quality_scores_impl(
            poem_id="scored-poem", scores=new_scores, notes="Updated scores", catalog=catalog
        )

        assert result["success"] is True

        # Verify new scores in file
        poem_path = temp_vault / "catalog" / "completed" / "scored-poem.md"
        content = poem_path.read_text(encoding="utf-8")
        assert "detail: 10" in content
        assert "quality_notes: Updated scores" in content


class TestGetQualityScores:
    """Test get_quality_scores() tool."""

    def test_get_scores_for_scored_poem(self, catalog):
        """Test retrieving scores from poem with quality scores."""
        from poetry_mcp.server import get_quality_scores_impl

        result = get_quality_scores_impl(poem_id="scored-poem", catalog=catalog)

        assert result["success"] is True
        assert result["poem_id"] == "scored-poem"
        assert result["has_scores"] is True
        assert result["scores"]["detail"] == 8
        assert result["scores"]["mystery"] == 9
        assert result["notes"] == "Strong imagery and mystery, adequate music"

    def test_get_scores_for_unscored_poem(self, catalog):
        """Test retrieving scores from poem without quality scores."""
        from poetry_mcp.server import get_quality_scores_impl

        result = get_quality_scores_impl(poem_id="unscored-poem", catalog=catalog)

        assert result["success"] is True
        assert result["poem_id"] == "unscored-poem"
        assert result["has_scores"] is False
        assert result["scores"] == {}
        assert result["notes"] is None

    def test_get_scores_for_partial_poem(self, catalog):
        """Test retrieving partial scores."""
        from poetry_mcp.server import get_quality_scores_impl

        result = get_quality_scores_impl(poem_id="partial-scores", catalog=catalog)

        assert result["success"] is True
        assert result["has_scores"] is True
        assert result["scores"]["detail"] == 5
        assert result["scores"]["mystery"] == 6
        assert len(result["scores"]) == 2

    def test_get_scores_poem_not_found(self, catalog):
        """Test error when poem doesn't exist."""
        from poetry_mcp.server import get_quality_scores_impl

        result = get_quality_scores_impl(poem_id="nonexistent-poem", catalog=catalog)

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestFindHighScoringPoems:
    """Test find_high_scoring_poems() tool."""

    def test_find_by_single_quality(self, catalog):
        """Test finding poems with high score on single dimension."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(qualities=["mystery"], min_score=8, catalog=catalog)

        assert result["success"] is True
        assert result["total_matches"] == 1
        assert result["poems"][0]["id"] == "scored-poem"
        assert result["poems"][0]["scores"]["mystery"] == 9

    def test_find_by_multiple_qualities(self, catalog):
        """Test finding poems with high scores on multiple dimensions."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(
            qualities=["detail", "mystery"], min_score=8, catalog=catalog
        )

        assert result["success"] is True
        assert result["total_matches"] == 1
        assert result["poems"][0]["scores"]["detail"] == 8
        assert result["poems"][0]["scores"]["mystery"] == 9

    def test_find_with_state_filter(self, catalog):
        """Test filtering by poem state."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(
            qualities=["detail"], min_score=5, states=["completed"], catalog=catalog
        )

        assert result["success"] is True
        # Should only include completed poems
        for poem in result["poems"]:
            poem_obj = catalog.index.get_by_id(poem["id"])
            assert poem_obj.state == "completed"

    def test_find_with_limit(self, catalog):
        """Test result limit parameter."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(
            qualities=["detail"], min_score=5, limit=1, catalog=catalog
        )

        assert result["success"] is True
        assert len(result["poems"]) <= 1

    def test_find_no_matches(self, catalog):
        """Test when no poems meet criteria."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(qualities=["detail"], min_score=10, catalog=catalog)

        assert result["success"] is True
        assert result["total_matches"] == 0
        assert result["poems"] == []

    def test_find_invalid_quality_name(self, catalog):
        """Test error with invalid quality dimension."""
        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(
            qualities=["invalid_dimension"], min_score=8, catalog=catalog
        )

        assert result["success"] is False
        assert "Invalid quality dimension" in result["error"]

    def test_find_sorts_by_average_score(self, catalog, temp_vault):
        """Test that results are sorted by average score descending."""
        # Add another scored poem with lower average
        completed_dir = temp_vault / "catalog" / "completed"
        lower_poem = completed_dir / "lower-scored.md"
        lower_poem.write_text(
            """---
title: Lower Scored
state: completed
form: free_verse
qualities:
  detail: 5
  mystery: 6
---

Lower scoring poem.
""",
            encoding="utf-8",
        )

        catalog.sync()

        from poetry_mcp.server import find_high_scoring_poems_impl

        result = find_high_scoring_poems_impl(
            qualities=["detail", "mystery"], min_score=5, catalog=catalog
        )

        assert result["success"] is True
        assert len(result["poems"]) >= 2

        # Verify descending order by average score
        avg_scores = [poem["avg_score"] for poem in result["poems"]]
        assert avg_scores == sorted(avg_scores, reverse=True)


class TestQualityScoringIntegration:
    """Test complete quality scoring workflow."""

    def test_complete_workflow(self, catalog, temp_vault):
        """Test complete workflow: commit → get → find."""
        # Step 1: Commit quality scores
        scores = {
            "detail": 9,
            "life": 8,
            "music": 7,
            "mystery": 10,
            "sufficient thought": 9,
            "surprise": 8,
            "syntax": 8,
            "unity": 9,
        }

        from poetry_mcp.server import (
            commit_quality_scores_impl,
            get_quality_scores_impl,
            find_high_scoring_poems_impl,
        )

        commit_result = commit_quality_scores_impl(
            poem_id="unscored-poem", scores=scores, notes="Complete workflow test", catalog=catalog
        )
        assert commit_result["success"] is True

        # Step 2: Retrieve scores
        get_result = get_quality_scores_impl(poem_id="unscored-poem", catalog=catalog)
        assert get_result["success"] is True
        assert get_result["scores"]["mystery"] == 10
        assert get_result["notes"] == "Complete workflow test"

        # Step 3: Find high-scoring poems
        find_result = find_high_scoring_poems_impl(
            qualities=["mystery"], min_score=9, catalog=catalog
        )
        assert find_result["success"] is True
        assert any(p["id"] == "unscored-poem" for p in find_result["poems"])

    def test_catalog_resync_after_commit(self, catalog, temp_vault):
        """Test that catalog is resynced after committing scores."""
        scores = {"detail": 8, "mystery": 9}

        from poetry_mcp.server import commit_quality_scores_impl

        commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        # Retrieve poem from catalog - should have updated scores
        poem = catalog.index.get_by_id("unscored-poem")
        assert poem is not None
        assert poem.qualities.get("detail") == 8
        assert poem.qualities.get("mystery") == 9

    def test_backup_creation(self, catalog, temp_vault):
        """Test that backup files are created before modification."""
        scores = {"detail": 7}

        from poetry_mcp.server import commit_quality_scores_impl

        commit_quality_scores_impl(poem_id="unscored-poem", scores=scores, catalog=catalog)

        poem_path = temp_vault / "catalog" / "completed" / "unscored-poem.md"
        backup_path = Path(str(poem_path) + ".bak")

        assert backup_path.exists()

        # Backup should contain original content without scores
        backup_content = backup_path.read_text(encoding="utf-8")
        assert "detail:" not in backup_content
