"""
Tests for parsing utilities - dates and embeddings.

Following clean code best practices:
- Arrange-Act-Assert pattern
- Descriptive test names
- Edge case coverage
- No magic numbers
"""
import pytest
from datetime import date

from app.services.authority.components import parse_neo4j_date, parse_embedding


class TestDateParsing:
    """Test suite for Neo4j date parsing."""

    def test_parse_none_returns_none(self):
        """None input should return None."""
        assert parse_neo4j_date(None) is None

    def test_parse_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_neo4j_date("") is None
        assert parse_neo4j_date("   ") is None

    def test_parse_date_object_passthrough(self):
        """Python date objects should pass through unchanged."""
        expected = date(2024, 1, 15)
        result = parse_neo4j_date(expected)
        assert result == expected

    def test_parse_format_dd_mm_yyyy(self):
        """Parse DD/MM/YYYY format."""
        result = parse_neo4j_date("15/01/2024")
        assert result == date(2024, 1, 15)

    def test_parse_format_yyyy_mm_dd(self):
        """Parse YYYY-MM-DD (ISO) format."""
        result = parse_neo4j_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_format_dd_mm_yyyy_dashes(self):
        """Parse DD-MM-YYYY format."""
        result = parse_neo4j_date("15-01-2024")
        assert result == date(2024, 1, 15)

    def test_parse_format_yyyymmdd(self):
        """Parse YYYYMMDD format (common in Neo4j)."""
        result = parse_neo4j_date("20231114")
        assert result == date(2023, 11, 14)

    def test_parse_invalid_format_returns_none(self):
        """Invalid date formats should return None."""
        assert parse_neo4j_date("invalid") is None
        assert parse_neo4j_date("01-15-2024") is None  # MM-DD-YYYY
        assert parse_neo4j_date("2024/01/15") is None  # Wrong separator for ISO

    def test_parse_neo4j_date_object(self):
        """Neo4j Date objects with to_native() should be converted."""
        class MockNeo4jDate:
            def to_native(self):
                return date(2024, 3, 20)

        result = parse_neo4j_date(MockNeo4jDate())
        assert result == date(2024, 3, 20)

    def test_parse_boundary_dates(self):
        """Test boundary dates."""
        # First day of year
        assert parse_neo4j_date("01/01/2024") == date(2024, 1, 1)
        # Last day of year
        assert parse_neo4j_date("31/12/2024") == date(2024, 12, 31)
        # Leap year
        assert parse_neo4j_date("29/02/2024") == date(2024, 2, 29)

    def test_parse_float_yyyymmdd(self):
        """Parse float values like 20250612.0 (from Neo4j)."""
        result = parse_neo4j_date(20250612.0)
        assert result == date(2025, 6, 12)

    def test_parse_int_yyyymmdd(self):
        """Parse integer values like 20250612."""
        result = parse_neo4j_date(20250612)
        assert result == date(2025, 6, 12)

    def test_parse_string_with_decimal(self):
        """Parse string with decimal like '20250612.0'."""
        result = parse_neo4j_date("20250612.0")
        assert result == date(2025, 6, 12)


class TestEmbeddingParsing:
    """Test suite for embedding parsing."""

    def test_parse_none_returns_none(self):
        """None input should return None."""
        assert parse_embedding(None) is None

    def test_parse_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_embedding("") is None
        assert parse_embedding("   ") is None

    def test_parse_list_of_floats(self):
        """List of floats should pass through."""
        input_list = [1.0, 2.0, 3.0]
        result = parse_embedding(input_list)
        assert result == [1.0, 2.0, 3.0]

    def test_parse_list_of_ints(self):
        """List of ints should be converted to floats."""
        input_list = [1, 2, 3]
        result = parse_embedding(input_list)
        assert result == [1.0, 2.0, 3.0]

    def test_parse_json_string(self):
        """JSON string representation should be parsed."""
        json_str = "[1.0, 2.0, 3.0]"
        result = parse_embedding(json_str)
        assert result == [1.0, 2.0, 3.0]

    def test_parse_json_string_with_ints(self):
        """JSON string with ints should be converted to floats."""
        json_str = "[1, 2, 3]"
        result = parse_embedding(json_str)
        assert result == [1.0, 2.0, 3.0]

    def test_parse_high_dimensional_embedding(self):
        """Test parsing of realistic embedding size (1536 dims)."""
        embedding = [0.001 * i for i in range(1536)]
        result = parse_embedding(embedding)
        assert len(result) == 1536
        assert result[0] == 0.0
        assert abs(result[1535] - 1.535) < 0.001

    def test_parse_numpy_array(self):
        """NumPy arrays should be converted to lists."""
        import numpy as np
        arr = np.array([1.0, 2.0, 3.0])
        result = parse_embedding(arr)
        assert result == [1.0, 2.0, 3.0]

    def test_parse_invalid_string_returns_none(self):
        """Invalid strings should return None."""
        assert parse_embedding("not an embedding") is None
        assert parse_embedding("{invalid: json}") is None


class TestCosineSimularity:
    """Test suite for cosine similarity calculation."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        from app.services.authority.components import cosine_similarity
        vec = [1.0, 2.0, 3.0]
        result = cosine_similarity(vec, vec)
        assert abs(result - 1.0) < 0.0001

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        from app.services.authority.components import cosine_similarity
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        result = cosine_similarity(vec1, vec2)
        assert abs(result) < 0.0001

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        from app.services.authority.components import cosine_similarity
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        result = cosine_similarity(vec1, vec2)
        assert abs(result + 1.0) < 0.0001

    def test_empty_vector_returns_zero(self):
        """Empty vectors should return 0.0."""
        from app.services.authority.components import cosine_similarity
        result = cosine_similarity([], [1.0, 2.0])
        assert result == 0.0

    def test_none_vector_returns_zero(self):
        """None vectors should return 0.0."""
        from app.services.authority.components import cosine_similarity
        result = cosine_similarity(None, [1.0, 2.0])
        assert result == 0.0

    def test_string_embedding_parsing(self):
        """String embeddings should be parsed before calculation."""
        from app.services.authority.components import cosine_similarity
        vec1 = "[1.0, 0.0, 0.0]"
        vec2 = [1.0, 0.0, 0.0]
        result = cosine_similarity(vec1, vec2)
        assert abs(result - 1.0) < 0.0001


class TestTimeDcay:
    """Test suite for time decay calculation."""

    def test_zero_days_returns_one(self):
        """Zero days ago should return 1.0."""
        from app.services.authority.components import time_decay
        result = time_decay(0, 365)
        assert result == 1.0

    def test_half_life_returns_half(self):
        """Days equal to half-life should return ~0.5."""
        from app.services.authority.components import time_decay
        result = time_decay(365, 365)  # 365 days, 365-day half-life
        assert abs(result - 0.5) < 0.01

    def test_negative_days_returns_one(self):
        """Negative days (future) should return 1.0."""
        from app.services.authority.components import time_decay
        result = time_decay(-10, 365)
        assert result == 1.0

    def test_very_old_returns_near_zero(self):
        """Very old activities should return near zero."""
        from app.services.authority.components import time_decay
        result = time_decay(3650, 365)  # 10 years old
        assert result < 0.01

    def test_double_half_life_returns_quarter(self):
        """Double the half-life should return ~0.25."""
        from app.services.authority.components import time_decay
        result = time_decay(730, 365)  # 2 years, 1-year half-life
        assert abs(result - 0.25) < 0.01
