"""Tests for structured output validation utilities."""

from __future__ import annotations

import pytest

from pydantic import BaseModel, Field, ValidationError

from mcp_common.schemas import ToolResponse
from mcp_common.validation import validate_input, validate_output


class TestValidateOutput:
    """Test the validate_output function."""

    def test_valid_output(self):
        """Test validation with valid output."""
        output = {
            "success": True,
            "message": "Operation completed",
            "data": {"count": 42}
        }

        validated = validate_output(output, ToolResponse)

        assert validated.success is True
        assert validated.message == "Operation completed"
        assert validated.data["count"] == 42

    def test_missing_required_field(self):
        """Test validation fails when required field missing."""
        output = {
            "data": {"count": 42}
            # Missing 'success' and 'message'
        }

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_message = str(exc_info.value)
        assert "Tool output validation failed" in error_message
        assert "success" in error_message or "message" in error_message

    def test_wrong_type_for_field(self):
        """Test validation fails when field has wrong type."""
        output = {
            "success": "not a boolean",  # Should be bool
            "message": "Test"
        }

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_message = str(exc_info.value)
        assert "validation failed" in error_message.lower()

    def test_helpful_error_message(self):
        """Test that error message includes received output and expected schema."""
        output = {"invalid": "field"}

        with pytest.raises(ValueError) as exc_info:
            validate_output(output, ToolResponse)

        error_message = str(exc_info.value)
        assert "Received output:" in error_message
        assert "Expected schema:" in error_message

    def test_successful_validation_returns_model_instance(self):
        """Test that successful validation returns proper model instance."""
        output = {
            "success": True,
            "message": "Success",
            "data": {"items": [1, 2, 3]},
            "error": None,
            "next_steps": ["Step 1"]
        }

        validated = validate_output(output, ToolResponse)

        # Should be ToolResponse instance
        assert isinstance(validated, ToolResponse)
        assert isinstance(validated.data, dict)
        assert isinstance(validated.next_steps, list)


class TestValidateInput:
    """Test the validate_input function."""

    def test_valid_input(self):
        """Test validation with valid input."""
        from pydantic import BaseModel, Field

        class SearchInput(BaseModel):
            query: str = Field(..., min_length=1)
            limit: int = Field(default=10, ge=1, le=100)

        input_data = {"query": "test", "limit": 5}

        validated = validate_input(input_data, SearchInput)

        assert validated.query == "test"
        assert validated.limit == 5

    def test_missing_required_field(self):
        """Test validation fails when required field missing."""
        from pydantic import BaseModel, Field

        class SearchInput(BaseModel):
            query: str = Field(..., min_length=1)
            limit: int = Field(default=10, ge=1, le=100)

        input_data = {"limit": 5}  # Missing 'query'

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SearchInput)

        error_message = str(exc_info.value)
        assert "Tool input validation failed" in error_message

    def test_validation_constraint_violation(self):
        """Test validation fails when constraints violated."""
        from pydantic import BaseModel, Field

        class SearchInput(BaseModel):
            query: str = Field(..., min_length=1)
            limit: int = Field(default=10, ge=1, le=100)

        input_data = {"query": "test", "limit": 200}  # Exceeds max

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SearchInput)

        error_message = str(exc_info.value)
        assert "validation failed" in error_message.lower()

    def test_helpful_error_message_includes_schema(self):
        """Test that error message includes expected schema."""
        from pydantic import BaseModel, Field

        class SearchInput(BaseModel):
            query: str = Field(..., min_length=1)

        input_data = {}  # Missing required field

        with pytest.raises(ValueError) as exc_info:
            validate_input(input_data, SearchInput)

        error_message = str(exc_info.value)
        assert "Received input:" in error_message
        assert "Expected schema:" in error_message

    def test_default_values_applied(self):
        """Test that default values are properly applied."""
        from pydantic import BaseModel, Field

        class SearchInput(BaseModel):
            query: str = Field(..., min_length=1)
            limit: int = Field(default=10, ge=1, le=100)
            sort: str = Field(default="relevance")

        input_data = {"query": "test"}

        validated = validate_input(input_data, SearchInput)

        assert validated.limit == 10  # Default applied
        assert validated.sort == "relevance"  # Default applied


class TestValidationIntegration:
    """Integration tests combining schemas and validation."""

    def test_roundtrip_validation(self):
        """Test output -> validate -> serialize -> validate workflow."""
        # Create response
        response = ToolResponse(
            success=True,
            message="Test",
            data={"items": [1, 2, 3]}
        )

        # Serialize to dict (as MCP protocol would)
        output_dict = response.model_dump()

        # Validate output
        validated = validate_output(output_dict, ToolResponse)

        # Should match original
        assert validated.success == response.success
        assert validated.message == response.message
        assert validated.data == response.data

    def test_complex_nested_data_validation(self):
        """Test validation with complex nested data structures."""
        complex_output = {
            "success": True,
            "message": "Complex operation successful",
            "data": {
                "users": [
                    {"id": "1", "name": "Alice", "roles": ["admin", "user"]},
                    {"id": "2", "name": "Bob", "roles": ["user"]}
                ],
                "metadata": {
                    "total": 2,
                    "page": 1,
                    "per_page": 10
                }
            },
            "next_steps": [
                "View user details",
                "Export results",
                "Apply filters"
            ]
        }

        validated = validate_output(complex_output, ToolResponse)

        assert validated.success is True
        assert len(validated.data["users"]) == 2
        assert validated.data["metadata"]["total"] == 2
        assert len(validated.next_steps) == 3
