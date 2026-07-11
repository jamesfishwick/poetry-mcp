"""Unit tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from poetry_mcp.models.nexus import Nexus, NexusRegistry
from poetry_mcp.models.poem import Poem
from poetry_mcp.models.quality import Quality, QualityRegistry
from poetry_mcp.models.results import CatalogStats, SearchResult, SyncResult
from poetry_mcp.models.venue import Venue


class TestPoemModel:
    """Test Poem model validation and normalization."""

    def test_valid_poem_creation(self):
        """Test creating a valid poem with all required fields."""
        poem = Poem(
            id="test-poem",
            title="Test Poem",
            file_path="catalog/completed/test-poem.md",
            state="completed",
            form="free_verse",
            tags=["water", "memory"],
            word_count=100,
            line_count=20,
            stanza_count=4,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 6, 1),
        )
        assert poem.id == "test-poem"
        assert poem.state == "completed"
        assert poem.form == "free_verse"
        assert poem.tags == ["water", "memory"]

    def test_poem_with_custom_state(self):
        """Test poem with custom state after setting custom states."""
        Poem.set_custom_states(["archived", "submitted"])
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="archived",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert poem.state == "archived"

    def test_invalid_state(self):
        """Test that invalid state raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="invalid_state",
                form="free_verse",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        assert "Invalid state" in str(exc_info.value)

    def test_invalid_form(self):
        """Test that invalid form raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="completed",
                form="invalid_form",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        assert "literal_error" in str(exc_info.value) or "Invalid" in str(exc_info.value)

    def test_tags_normalization(self):
        """Test that tags are normalized (lowercase, stripped, deduplicated)."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            tags=["Water", " MEMORY ", "water", "Memory  "],
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert poem.tags == ["water", "memory"]

    def test_empty_tags_default(self):
        """Test that empty tags default to empty list."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert poem.tags == []

    def test_qualities_validation_valid(self):
        """Test valid quality scores."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            qualities={
                "detail": 8,
                "life": 7,
                "music": 6,
                "mystery": 9,
                "sufficient thought": 8,
                "surprise": 7,
                "syntax": 8,
                "unity": 9,
            },
        )
        assert poem.qualities["detail"] == 8
        assert poem.qualities["unity"] == 9

    def test_qualities_normalization(self):
        """Test that quality keys are normalized to lowercase."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            qualities={"DETAIL": 8, "Life": 7, "  Music  ": 6},
        )
        assert "detail" in poem.qualities
        assert "life" in poem.qualities
        assert "music" in poem.qualities

    def test_qualities_invalid_dimension(self):
        """Test that invalid quality dimension raises error."""
        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="completed",
                form="free_verse",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                qualities={"invalid_dimension": 8},
            )
        assert "Invalid quality dimension" in str(exc_info.value)

    def test_qualities_invalid_score_range(self):
        """Test that quality score outside 0-10 range raises error."""
        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="completed",
                form="free_verse",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                qualities={"detail": 15},
            )
        assert "must be integer 0-10" in str(exc_info.value)

    def test_qualities_negative_score(self):
        """Test that negative quality score raises error."""
        with pytest.raises(ValidationError) as exc_info:
            Poem(
                id="test",
                title="Test",
                file_path="test.md",
                state="completed",
                form="free_verse",
                word_count=10,
                line_count=5,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                qualities={"detail": -1},
            )
        assert "must be integer 0-10" in str(exc_info.value)

    def test_poem_json_serialization(self):
        """Test that poem can be serialized to JSON."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 6, 1),
        )
        json_data = poem.model_dump_json()
        assert "test-poem" in json_data or "test" in json_data

    def test_poem_with_content(self):
        """Test poem with optional content field."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            content="This is the poem content.",
        )
        assert poem.content == "This is the poem content."


class TestNexusModel:
    """Test Nexus model validation."""

    def test_valid_nexus_creation(self):
        """Test creating a valid nexus."""
        nexus = Nexus(
            name="Water-Liquid Imagery",
            category="theme",
            description="Water, blood, beer, tears - liquids as transformation",
            file_path="vault/nexuses/themes/water-liquid.md",
            canonical_tag="water-liquid",
        )
        assert nexus.name == "Water-Liquid Imagery"
        assert nexus.category == "theme"
        assert nexus.canonical_tag == "water-liquid"

    def test_nexus_json_serialization(self):
        """Test nexus JSON serialization."""
        nexus = Nexus(
            name="Test Nexus",
            category="motif",
            description="Test description",
            file_path="test.md",
            canonical_tag="test-nexus",
        )
        json_data = nexus.model_dump_json()
        assert "Test Nexus" in json_data


class TestNexusRegistry:
    """Test NexusRegistry model."""

    def test_nexus_registry_creation(self):
        """Test creating nexus registry with categorized nexuses."""
        registry = NexusRegistry(
            themes=[
                Nexus(
                    name="Water",
                    category="theme",
                    description="Water imagery",
                    file_path="water.md",
                    canonical_tag="water",
                )
            ],
            motifs=[
                Nexus(
                    name="Failure",
                    category="motif",
                    description="Patterns of failure",
                    file_path="failure.md",
                    canonical_tag="failure",
                )
            ],
            forms=[
                Nexus(
                    name="Catalog",
                    category="form",
                    description="List structure",
                    file_path="catalog.md",
                    canonical_tag="catalog",
                )
            ],
            total_count=3,
        )
        assert len(registry.themes) == 1
        assert len(registry.motifs) == 1
        assert len(registry.forms) == 1
        assert registry.total_count == 3
        assert registry.themes[0].name == "Water"


class TestQualityModel:
    """Test Quality model validation."""

    def test_valid_quality_creation(self):
        """Test creating a valid quality dimension."""
        quality = Quality(
            name="Detail",
            scale_min=0,
            scale_max=10,
            description="Precision and specificity of imagery",
            file_path="vault/qualities/detail.md",
        )
        assert quality.name == "Detail"
        assert quality.scale_min == 0
        assert quality.scale_max == 10

    def test_quality_json_serialization(self):
        """Test quality JSON serialization."""
        quality = Quality(
            name="Life",
            scale_min=0,
            scale_max=10,
            description="Vitality and energy",
            file_path="life.md",
        )
        json_data = quality.model_dump_json()
        assert "Life" in json_data


class TestQualityRegistry:
    """Test QualityRegistry model."""

    def test_quality_registry_creation(self):
        """Test creating quality registry."""
        registry = QualityRegistry(
            qualities=[
                Quality(
                    name="Detail",
                    scale_min=0,
                    scale_max=10,
                    description="Detail level",
                    file_path="detail.md",
                ),
                Quality(
                    name="Life",
                    scale_min=0,
                    scale_max=10,
                    description="Vitality",
                    file_path="life.md",
                ),
            ],
            total_count=2,
        )
        assert len(registry.qualities) == 2
        assert registry.total_count == 2
        assert registry.qualities[0].name == "Detail"


class TestVenueModel:
    """Test Venue model validation."""

    def test_valid_venue_creation(self):
        """Test creating a valid venue."""
        venue = Venue(
            name="The Paris Review",
            payment="paid",
            response_time_days=90,
            simultaneous=False,
            aesthetic="Literary, traditional",
            url="https://theparisreview.org",
            submission_format="Submittable",
        )
        assert venue.name == "The Paris Review"
        assert venue.payment == "paid"
        assert venue.simultaneous is False

    def test_venue_with_optional_fields(self):
        """Test venue with optional fields omitted."""
        venue = Venue(
            name="Small Press",
            payment="token",
            response_time_days=30,
            simultaneous=True,
            aesthetic="Experimental",
        )
        assert venue.url is None
        assert venue.submission_format is None


class TestResultModels:
    """Test result/response models."""

    def test_sync_result_creation(self):
        """Test creating sync result."""
        result = SyncResult(
            total_poems=381,
            new_poems=5,
            updated_poems=12,
            skipped_poems=0,
            warnings=[],
            duration_seconds=2.5,
        )
        assert result.total_poems == 381
        assert result.new_poems == 5
        assert result.updated_poems == 12
        assert result.duration_seconds == 2.5

    def test_search_result_creation(self):
        """Test creating search result."""
        poem = Poem(
            id="test",
            title="Test",
            file_path="test.md",
            state="completed",
            form="free_verse",
            word_count=10,
            line_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        result = SearchResult(
            poems=[poem],
            total_matches=1,
            query_time_ms=15.5,
        )
        assert result.total_matches == 1
        assert result.query_time_ms == 15.5

    def test_catalog_stats_creation(self):
        """Test creating catalog stats."""
        stats = CatalogStats(
            total_poems=381,
            by_state={"completed": 250, "fledgeling": 131},
            by_form={"free_verse": 300, "prose_poem": 81},
            poems_without_tags=100,
            total_word_count=125430,
            avg_word_count=329.2,
            newest_poem="November Rain",
            oldest_poem="First Poem",
        )
        assert stats.total_poems == 381
        assert stats.by_state["completed"] == 250
        assert stats.poems_without_tags == 100
        assert stats.newest_poem == "November Rain"
