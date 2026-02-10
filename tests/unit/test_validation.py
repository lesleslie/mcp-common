"""Tests for validation utilities."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field, ValidationError

from mcp_common.schemas import ToolResponse
from mcp_common.validation import validate_input, validate_output


# Test Models
class SimpleInput(BaseModel):
    """Simple input model for testing."""

    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=150)


class ComplexInput(BaseModel):
    """Complex input model for testing."""

    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: dict[str, str] | None = Field(default=None)


class NestedOutput(BaseModel):
    """Nested output model for testing."""

    success: bool
    data: dict[str, int]
    metadata: dict[str, str] | None = None


@pytest.mark.unit
class TestValidateOutput:
    """Tests for validate_output function."""

    def test_validate_output_success(self) -> None:
        """Test successful output validation."""
        output = {
            "success": True,
            "message": "Operation completed",
            "data": {"result": "value"},
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is True
        assert validated.message == "Operation completed"
        assert validated.data == {"result": "value"}

    def test_validate_output_with_all_fields(self) -> None:
        """Test validation with all fields populated."""
        output = {
            "success": True,
            "message": "Success",
            "data": {"count": 5},
            "error": None,
            "next_steps": ["Step 1", "Step 2"],
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is True
        assert validated.data == {"count": 5}
        assert validated.error is None
        assert validated.next_steps == ["Step 1", "Step 2"]

    def test_validate_output_failure_case(self) -> None:
        """Test validation with failure case."""
        output = {
            "success": False,
            "message": "Operation failed",
            "error": "Database connection timeout",
            "next_steps": ["Check database", "Retry"],
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is False
        assert validated.error == "Database connection timeout"
        assert validated.next_steps == ["Check database", "Retry"]

    def test_validate_output_missing_required_field(self) -> None:
        """Test validation fails with missing required field."""
        output = {"data": {"result": "value"}}  # Missing 'success' and 'message'

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_msg = str(exc_info.value)
        assert "Tool output validation failed" in error_msg
        assert "ToolResponse" in error_msg
        assert "validation errors" in error_msg.lower()

    def test_validate_output_wrong_type(self) -> None:
        """Test validation fails with wrong type."""
        output = {
            "success": "not a boolean",  # Should be bool
            "message": "Test",
        }

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()

    def test_validate_output_error_message_includes_received(self) -> None:
        """Test error message includes received output."""
        output = {"invalid": "data"}

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_msg = str(exc_info.value)
        assert "Received output:" in error_msg
        assert str(output) in error_msg

    def test_validate_output_error_message_includes_schema(self) -> None:
        """Test error message includes expected schema."""
        output = {"invalid": "data"}

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_msg = str(exc_info.value)
        assert "Expected schema:" in error_msg
        # Schema should be JSON
        assert "{" in error_msg

    def test_validate_output_with_custom_model(self) -> None:
        """Test validate_output with custom Pydantic model."""
        output = {
            "success": True,
            "data": {"count": 10, "total": 20},
            "metadata": {"version": "1.0"},
        }

        validated = validate_output(output, NestedOutput)

        assert validated.success is True
        assert validated.data == {"count": 10, "total": 20}
        assert validated.metadata == {"version": "1.0"}

    def test_validate_output_optional_fields(self) -> None:
        """Test validation with optional fields omitted."""
        output = {
            "success": True,
            "message": "Success",
            # data and next_steps omitted
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is True
        assert validated.data is None
        assert validated.next_steps is None


@pytest.mark.unit
class TestValidateInput:
    """Tests for validate_input function."""

    def test_validate_input_success(self) -> None:
        """Test successful input validation."""
        input_data = {"name": "Alice", "age": 30}

        validated = validate_input(input_data, SimpleInput)

        assert validated.name == "Alice"
        assert validated.age == 30

    def test_validate_input_with_defaults(self) -> None:
        """Test validation uses default values."""
        input_data = {"query": "search term"}

        validated = validate_input(input_data, ComplexInput)

        assert validated.query == "search term"
        assert validated.limit == 10  # Default value
        assert validated.filters is None

    def test_validate_input_missing_required_field(self) -> None:
        """Test validation fails with missing required field."""
        input_data = {"age": 30}  # Missing 'name'

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SimpleInput)

        error_msg = str(exc_info.value)
        assert "Tool input validation failed" in error_msg
        assert "SimpleInput" in error_msg

    def test_validate_input_validation_error(self) -> None:
        """Test validation fails with constraint violation."""
        input_data = {"name": "Bob", "age": 200}  # Age exceeds max

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SimpleInput)

        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()

    def test_validate_input_wrong_type(self) -> None:
        """Test validation fails with wrong type."""
        input_data = {"name": "Charlie", "age": "thirty"}  # Should be int

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SimpleInput)

        error_msg = str(exc_info.value)
        assert "validation failed" in error_msg.lower()

    def test_validate_input_error_formatting(self) -> None:
        """Test error message is properly formatted."""
        input_data = {"invalid": "field"}

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SimpleInput)

        error_msg = str(exc_info.value)
        assert "Received input:" in error_msg
        assert "Validation errors:" in error_msg
        assert "Expected schema:" in error_msg

    def test_validate_input_with_complex_data(self) -> None:
        """Test validation with complex nested data."""
        input_data = {
            "query": "test",
            "limit": 50,
            "filters": {"status": "active", "type": "user"},
        }

        validated = validate_input(input_data, ComplexInput)

        assert validated.query == "test"
        assert validated.limit == 50
        assert validated.filters == {"status": "active", "type": "user"}

    def test_validate_input_boundary_values(self) -> None:
        """Test validation with boundary values."""
        # Test minimum age
        validated = validate_input({"name": "Baby", "age": 0}, SimpleInput)
        assert validated.age == 0

        # Test maximum age
        validated = validate_input({"name": "Elder", "age": 150}, SimpleInput)
        assert validated.age == 150

    def test_validate_input_string_constraints(self) -> None:
        """Test validation with string constraints."""
        # Empty string should fail
        with pytest.raises(ValueError):
            validate_input({"name": "", "age": 30}, SimpleInput)

        # Whitespace only should fail
        with pytest.raises(ValueError):
            validate_input({"name": "   ", "age": 30}, SimpleInput)

        # Valid string should pass
        validated = validate_input({"name": "Valid Name", "age": 30}, SimpleInput)
        assert validated.name == "Valid Name"


@pytest.mark.unit
class TestValidationIntegration:
    """Integration tests for validation utilities."""

    def test_round_trip_validation(self) -> None:
        """Test validation through input->process->output flow."""
        # Input validation
        input_data = {"query": "test", "limit": 20}
        validated_input = validate_input(input_data, ComplexInput)

        # Simulate processing
        output_data = {
            "success": True,
            "message": f"Processed {validated_input.limit} results",
            "data": {"query": validated_input.query, "count": validated_input.limit},
        }

        # Output validation
        validated_output = validate_output(output_data, ToolResponse)

        assert validated_output.success is True
        assert "20 results" in validated_output.message

    def test_validation_in_tool_context(self) -> None:
        """Test validation as used in MCP tool context."""
        # Simulate tool input from MCP protocol
        raw_input = {"name": "Alice", "age": 25}
        validated_input = validate_input(raw_input, SimpleInput)

        # Simulate tool processing
        result = f"User {validated_input.name} is {validated_input.age} years old"

        # Validate output format
        raw_output = {
            "success": True,
            "message": result,
            "data": {"user": validated_input.name, "age": validated_input.age},
        }
        validated_output = validate_output(raw_output, ToolResponse)

        assert validated_output.success is True
        assert validated_output.data["user"] == "Alice"

    def test_validation_error_propagation(self) -> None:
        """Test that validation errors are properly propagated."""
        invalid_input = {"name": "", "age": -1}

        with pytest.raises(ValueError) as exc_info:
            validate_input(invalid_input, SimpleInput)

        # Error should contain details about both validation failures
        error_msg = str(exc_info.value)
        assert "validation errors" in error_msg.lower()


@pytest.mark.unit
class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    def test_validate_output_with_empty_data(self) -> None:
        """Test validation with empty data dict."""
        output = {
            "success": True,
            "message": "Success",
            "data": {},
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is True
        assert validated.data == {}

    def test_validate_output_with_large_data(self) -> None:
        """Test validation with large data structures."""
        large_data = {f"key_{i}": f"value_{i}" for i in range(100)}

        output = {
            "success": True,
            "message": "Large data",
            "data": large_data,
        }

        validated = validate_output(output, ToolResponse)

        assert validated.data == large_data

    def test_validate_input_with_unicode(self) -> None:
        """Test validation with unicode characters."""
        input_data = {"name": "日本語", "age": 25}

        validated = validate_input(input_data, SimpleInput)

        assert validated.name == "日本語"

    def test_validate_output_with_special_characters(self) -> None:
        """Test validation with special characters in strings."""
        output = {
            "success": True,
            "message": "Test with special chars: <>&\"'",
            "data": {"special": "🎉 emojis too!"},
        }

        validated = validate_output(output, ToolResponse)

        assert "special chars" in validated.message
        assert validated.data["special"] == "🎉 emojis too!"

    def test_validate_input_with_null_values(self) -> None:
        """Test validation handles null values correctly."""
        input_data = {
            "query": "test",
            "limit": 10,
            "filters": None,  # Explicit null
        }

        validated = validate_input(input_data, ComplexInput)

        assert validated.filters is None

    def test_validate_output_error_detail_access(self) -> None:
        """Test that validation error details are accessible."""
        output = {"success": "invalid"}

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        # Check that error message is structured
        error_msg = str(exc_info.value)
        lines = error_msg.split("\n")

        # Should have multiple sections
        assert any("validation failed" in line.lower() for line in lines)
        assert any("Received output:" in line for line in lines)
        assert any("Validation errors:" in line for line in lines)
