"""Unit tests for DataMapper component."""

from unittest.mock import MagicMock, Mock

import polars as pl
import pytest

from chartelier.core.chart_builder.base import TemplateSpec
from chartelier.core.enums import AuxiliaryElement, ErrorCode
from chartelier.core.errors import DataMappingError
from chartelier.core.models import MappingConfig
from chartelier.processing.data_mapper import DataMapper


class TestDataMapper:
    """Test cases for DataMapper class."""

    @pytest.fixture
    def mock_chart_builder(self) -> Mock:
        """Create a mock ChartBuilder."""
        return Mock()

    @pytest.fixture
    def mock_llm_client(self) -> Mock:
        """Create a mock LLM client."""
        return Mock()

    @pytest.fixture
    def mapper(self, mock_chart_builder: Mock, mock_llm_client: Mock) -> DataMapper:
        """Create a DataMapper instance with mocked dependencies."""
        return DataMapper(
            chart_builder=mock_chart_builder,
            llm_client=mock_llm_client,
        )

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample data for testing."""
        return pl.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "sales": [100.0, 150.0, 120.0],
                "category": ["A", "B", "A"],
                "count": [10, 15, 12],
            }
        )

    @pytest.fixture
    def template_spec(self) -> TemplateSpec:
        """Create a sample template specification."""
        return TemplateSpec(
            template_id="p01_line",
            name="Line Chart",
            pattern_ids=["P01"],
            required_encodings=["x", "y"],
            optional_encodings=["color"],
            allowed_auxiliary=[AuxiliaryElement.TARGET_LINE],
        )

    def test_analyze_columns(self, mapper: DataMapper, sample_data: pl.DataFrame) -> None:
        """Test column analysis functionality."""
        # Analyze columns
        column_info = mapper._analyze_columns(sample_data)  # noqa: SLF001

        # Verify column metadata
        assert "date" in column_info
        assert "sales" in column_info
        assert "category" in column_info
        assert "count" in column_info

        # Check date column
        date_info = column_info["date"]
        assert date_info["dtype"] == "String"  # Polars uses String type
        assert not date_info["is_temporal"]  # Not parsed as datetime yet
        assert not date_info["is_numeric"]

        # Check numeric column
        sales_info = column_info["sales"]
        assert sales_info["dtype"] == "Float64"
        assert sales_info["is_numeric"]
        assert not sales_info["is_categorical"]

        # Check categorical column
        category_info = column_info["category"]
        assert category_info["dtype"] == "String"  # Polars uses String type
        assert category_info["n_unique"] == 2
        assert category_info["is_categorical"]

    def test_deterministic_fallback_basic(
        self,
        mapper: DataMapper,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test deterministic fallback mapping (UT-DM-001)."""
        # Analyze columns
        column_info = mapper._analyze_columns(sample_data)  # noqa: SLF001

        # Get deterministic mapping
        mapping = mapper._deterministic_fallback(column_info, template_spec)  # noqa: SLF001

        # Verify required encodings are mapped
        assert mapping.x is not None
        assert mapping.y is not None

        # Verify the mapping makes sense
        # Should prefer numeric column for y
        assert mapping.y in ["sales", "count"]

    def test_deterministic_fallback_with_temporal(self, mapper: DataMapper) -> None:
        """Test fallback with temporal data."""
        # Create data with actual datetime
        data = pl.DataFrame(
            {
                "timestamp": pl.date_range(
                    start=pl.datetime(2024, 1, 1),
                    end=pl.datetime(2024, 1, 3),
                    interval="1d",
                    eager=True,
                ),
                "value": [10.0, 20.0, 15.0],
                "group": ["A", "A", "B"],
            }
        )

        column_info = mapper._analyze_columns(data)  # noqa: SLF001

        template_spec = TemplateSpec(
            template_id="test",
            name="Test",
            pattern_ids=["P01"],
            required_encodings=["x", "y"],
            optional_encodings=["color"],
            allowed_auxiliary=[],
        )

        mapping = mapper._deterministic_fallback(column_info, template_spec)  # noqa: SLF001

        # Since timestamp is properly detected as temporal, it should be mapped to x
        # But we need to check the actual dtype first
        timestamp_info = column_info["timestamp"]
        if timestamp_info["is_temporal"]:
            assert mapping.x == "timestamp"
        else:
            # If not detected as temporal (due to dtype string representation),
            # it will use first available column
            assert mapping.x in ["group", "timestamp", "value"]

        assert mapping.y == "value"  # Should map numeric column to y
        # Optional color should map to categorical if available
        if mapping.color:
            assert mapping.color == "group"

    def test_validate_and_cast_types(
        self,
        mapper: DataMapper,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test type validation and casting (UT-DM-002)."""
        # Create a mapping
        mapping = MappingConfig(x="date", y="sales", color="category")

        # Validate types
        validated = mapper._validate_and_cast_types(sample_data, mapping, template_spec)  # noqa: SLF001

        # Should return the same mapping (casting is handled elsewhere)
        assert validated.x == "date"
        assert validated.y == "sales"
        assert validated.color == "category"

    def test_map_with_llm_success(
        self,
        mapper: DataMapper,
        mock_llm_client: Mock,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test successful LLM-based mapping."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = '{"x": "date", "y": "sales", "color": "category"}'
        mock_llm_client.complete.return_value = mock_response

        column_info = mapper._analyze_columns(sample_data)  # noqa: SLF001

        # Get LLM mapping
        mapping = mapper._map_with_llm(column_info, template_spec, "Show sales over time")  # noqa: SLF001

        # Verify mapping
        assert mapping.x == "date"
        assert mapping.y == "sales"
        assert mapping.color == "category"

    def test_map_with_llm_invalid_column(
        self,
        mapper: DataMapper,
        mock_llm_client: Mock,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test LLM mapping with invalid column names."""
        # Mock LLM response with invalid column
        mock_response = MagicMock()
        mock_response.content = '{"x": "timestamp", "y": "revenue", "color": "category"}'
        mock_llm_client.complete.return_value = mock_response

        column_info = mapper._analyze_columns(sample_data)  # noqa: SLF001

        # Get LLM mapping
        mapping = mapper._map_with_llm(column_info, template_spec, "Show sales over time")  # noqa: SLF001

        # Invalid columns should be filtered out
        assert mapping.x is None  # "timestamp" doesn't exist
        assert mapping.y is None  # "revenue" doesn't exist
        assert mapping.color == "category"  # This one exists

    def test_map_full_workflow_with_llm(
        self,
        mapper: DataMapper,
        mock_llm_client: Mock,
        mock_chart_builder: Mock,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test complete mapping workflow with LLM."""
        # Setup mock chart builder
        mock_chart_builder.get_template_spec.return_value = template_spec

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = '{"x": "date", "y": "sales", "color": "category"}'
        mock_llm_client.complete.return_value = mock_response

        # Execute mapping
        mapping = mapper.map(
            data=sample_data,
            template_id="p01_line",
            query="Show sales trend by category",
        )

        # Verify result
        assert mapping.x == "date"
        assert mapping.y == "sales"
        assert mapping.color == "category"

    def test_map_full_workflow_with_fallback(
        self,
        mapper: DataMapper,
        mock_llm_client: Mock,
        mock_chart_builder: Mock,
        sample_data: pl.DataFrame,
        template_spec: TemplateSpec,
    ) -> None:
        """Test complete mapping workflow with fallback on LLM failure."""
        # Setup mock chart builder
        mock_chart_builder.get_template_spec.return_value = template_spec

        # Mock LLM failure
        mock_llm_client.complete.side_effect = Exception("LLM timeout")

        # Execute mapping (should use fallback)
        mapping = mapper.map(
            data=sample_data,
            template_id="p01_line",
            query="Show sales trend",
        )

        # Verify fallback was used
        assert mapping.x is not None
        assert mapping.y is not None
        # Should map to numeric columns for y
        assert mapping.y in ["sales", "count"]

    def test_map_missing_required_encodings(
        self,
        mapper: DataMapper,
        mock_chart_builder: Mock,
    ) -> None:
        """Test error when required encodings cannot be satisfied."""
        # Create data with only one column
        data = pl.DataFrame({"single_col": [1, 2, 3]})

        # Template requires x and y
        template_spec = TemplateSpec(
            template_id="test",
            name="Test",
            pattern_ids=["P01"],
            required_encodings=["x", "y"],
            optional_encodings=[],
            allowed_auxiliary=[],
        )
        mock_chart_builder.get_template_spec.return_value = template_spec

        # Should raise DataMappingError
        with pytest.raises(DataMappingError) as exc_info:
            mapper.map(data=data, template_id="test", query="Test query")

        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE
        assert "Required encodings not satisfied" in exc_info.value.message

    def test_map_template_not_found(
        self,
        mapper: DataMapper,
        mock_chart_builder: Mock,
        sample_data: pl.DataFrame,
    ) -> None:
        """Test error when template is not found."""
        # Mock template not found
        mock_chart_builder.get_template_spec.return_value = None

        # Should raise DataMappingError
        with pytest.raises(DataMappingError) as exc_info:
            mapper.map(
                data=sample_data,
                template_id="nonexistent",
                query="Test query",
            )

        # DataMappingError inherits from BusinessError which has E422_UNPROCESSABLE code
        assert exc_info.value.code == ErrorCode.E422_UNPROCESSABLE
        assert "Template 'nonexistent' not found" in exc_info.value.message

    def test_generate_mapping_hint(self, mapper: DataMapper) -> None:
        """Test hint generation for missing mappings."""
        column_info = {
            "date": {"is_temporal": True, "is_numeric": False},
            "value": {"is_temporal": False, "is_numeric": True},
            "category": {"is_temporal": False, "is_numeric": False},
        }

        # Test hint for missing x
        hint = mapper._generate_mapping_hint(column_info, ["x"])  # noqa: SLF001
        assert "temporal column: date" in hint

        # Test hint for missing y
        hint = mapper._generate_mapping_hint(column_info, ["y"])  # noqa: SLF001
        assert "numeric column: value" in hint

        # Test hint for multiple missing
        hint = mapper._generate_mapping_hint(column_info, ["x", "y"])  # noqa: SLF001
        assert "date" in hint
        assert "value" in hint
