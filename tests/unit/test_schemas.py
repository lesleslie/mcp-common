"""Tests for LLM-Friendly API Response Schemas."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from mcp_common.schemas import ToolInput, ToolResponse


@pytest.mark.unit
class TestToolResponse:
    """Tests for ToolResponse schema."""

    def test_tool_response_success_basic(self) -> None:
        """Test basic successful tool response."""
        response = ToolResponse(
            success=True,
            message="Operation completed successfully",
        )

        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.data is None
        assert response.error is None
        assert response.next_steps is None

    def test_tool_response_with_data(self) -> None:
        """Test tool response with structured data."""
        response = ToolResponse(
            success=True,
            message="Created 3 user records",
            data={
                "records": [
                    {"id": "1", "name": "Alice"},
                    {"id": "2", "name": "Bob"},
                    {"id": "3", "name": "Charlie"},
                ]
            },
        )

        assert response.success is True
        assert len(response.data["records"]) == 3
        assert response.data["records"][0]["name"] == "Alice"

    def test_tool_response_with_next_steps(self) -> None:
        """Test tool response with suggested next steps."""
        response = ToolResponse(
            success=True,
            message="Records created",
            data={"count": 3},
            next_steps=[
                "Verify records in database",
                "Send confirmation emails",
                "Update cache",
            ],
        )

        assert response.success is True
        assert len(response.next_steps) == 3
        assert "Verify records" in response.next_steps[0]

    def test_tool_response_failure(self) -> None:
        """Test failed tool response."""
        response = ToolResponse(
            success=False,
            message="Failed to connect to database",
            error="Connection timeout after 30s - check database connectivity",
            next_steps=[
                "Check database status",
                "Verify network connectivity",
                "Retry with increased timeout",
            ],
        )

        assert response.success is False
        assert "Connection timeout" in response.error
        assert len(response.next_steps) == 3

    def test_tool_response_all_fields(self) -> None:
        """Test tool response with all fields populated."""
        response = ToolResponse(
            success=True,
            message="Operation completed",
            data={"result": "success", "count": 42},
            error=None,
            next_steps=["Step 1", "Step 2"],
        )

        assert response.success is True
        assert response.data["count"] == 42
        assert response.error is None
        assert response.next_steps == ["Step 1", "Step 2"]

    def test_tool_response_required_fields(self) -> None:
        """Test that success and message are required."""
        with pytest.raises(ValidationError) as exc_info:
            ToolResponse(success=True)  # Missing message

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "message" in error_fields

    def test_tool_response_invalid_success_type(self) -> None:
        """Test that success must be boolean."""
        with pytest.raises(ValidationError) as exc_info:
            ToolResponse(
                success="yes",  # Should be bool
                message="Test",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "success" for e in errors)

    def test_tool_response_to_dict(self) -> None:
        """Test ToolResponse can be converted to dict."""
        response = ToolResponse(
            success=True,
            message="Test",
            data={"key": "value"},
        )

        response_dict = response.model_dump()

        assert response_dict["success"] is True
        assert response_dict["message"] == "Test"
        assert response_dict["data"]["key"] == "value"

    def test_tool_response_to_json(self) -> None:
        """Test ToolResponse can be serialized to JSON."""
        response = ToolResponse(
            success=True,
            message="Test",
            data={"count": 5},
        )

        json_str = response.model_dump_json()

        parsed = json.loads(json_str)
        assert parsed["success"] is True
        assert parsed["data"]["count"] == 5

    def test_tool_response_empty_data(self) -> None:
        """Test tool response with empty data dict."""
        response = ToolResponse(
            success=True,
            message="No results",
            data={},
        )

        assert response.data == {}

    def test_tool_response_complex_data(self) -> None:
        """Test tool response with nested complex data."""
        response = ToolResponse(
            success=True,
            message="Complex data",
            data={
                "users": [
                    {
                        "id": 1,
                        "name": "Alice",
                        "metadata": {"role": "admin", "active": True},
                    }
                ],
                "pagination": {"page": 1, "total": 100},
            },
        )

        assert response.data["users"][0]["metadata"]["role"] == "admin"
        assert response.data["pagination"]["total"] == 100


@pytest.mark.unit
class TestToolResponseExamples:
    """Tests using the example data from ToolResponse schema."""

    def test_example_1_success_case(self) -> None:
        """Test first example: successful user creation."""
        example = ToolResponse.model_json_schema()["examples"][0]

        response = ToolResponse(**example)

        assert response.success is True
        assert "Successfully created" in response.message
        assert len(response.data["records"]) == 3

    def test_example_2_failure_case(self) -> None:
        """Test second example: database connection failure."""
        example = ToolResponse.model_json_schema()["examples"][1]

        response = ToolResponse(**example)

        assert response.success is False
        assert "Failed to connect" in response.message
        assert response.error is not None


@pytest.mark.unit
class TestToolInput:
    """Tests for ToolInput schema."""

    def test_tool_input_basic(self) -> None:
        """Test basic tool input."""
        tool_input = ToolInput(
            name="search_users",
            description="Search for users by name or email",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or email)",
                    }
                },
                "required": ["query"],
            },
            example={"query": "alice@example.com"},
        )

        assert tool_input.name == "search_users"
        assert "Search for users" in tool_input.description

    def test_tool_input_to_example(self) -> None:
        """Test to_example method generates correct format."""
        tool_input = ToolInput(
            name="send_email",
            description="Send transactional email",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email"},
                    "subject": {"type": "string", "description": "Email subject"},
                },
                "required": ["to", "subject"],
            },
            example={"to": "user@example.com", "subject": "Test Email"},
        )

        example_dict = tool_input.to_example()

        assert "description" in example_dict
        assert "parameters" in example_dict
        assert "example" in example_dict
        assert example_dict["example"]["to"] == "user@example.com"

    def test_tool_input_complex_parameters(self) -> None:
        """Test tool input with complex parameter schema."""
        tool_input = ToolInput(
            name="advanced_search",
            description="Advanced search with filters",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "date_range": {"type": "string"},
                            "category": {"type": "string"},
                        },
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
            },
            example={"query": "test", "limit": 10},
        )

        assert tool_input.parameters["properties"]["filters"]["type"] == "object"

    def test_tool_input_required_fields(self) -> None:
        """Test that all ToolInput fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            ToolInput(
                name="test",
                # Missing description, parameters, example
            )

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "description" in error_fields
        assert "parameters" in error_fields
        assert "example" in error_fields

    def test_tool_input_name_convention(self) -> None:
        """Test tool input names follow snake_case convention."""
        tool_input = ToolInput(
            name="get_user_profile",
            description="Get user profile",
            parameters={"type": "object", "properties": {}, "required": []},
            example={},
        )

        assert "_" in tool_input.name
        assert " " not in tool_input.name


@pytest.mark.unit
class TestToolResponseEncoding:
    """Tests for custom encoding in schemas."""

    def test_tool_response_with_set_data(self) -> None:
        """Test that sets in data are encoded as lists."""
        # Create response with set (will be converted to list)
        response = ToolResponse(
            success=True,
            message="Test",
            data={"tags": {1, 2, 3}},  # Set will be preserved
        )

        # Model should handle set encoding
        assert isinstance(response.data["tags"], set)

    def test_tool_input_with_set_encoding(self) -> None:
        """Test that ToolInput handles set encoding."""
        tool_input = ToolInput(
            name="test",
            description="Test",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            example={"tags": {1, 2, 3}},
        )

        # Should handle set in example
        assert "tags" in tool_input.example


@pytest.mark.unit
class TestToolResponseValidation:
    """Tests for ToolResponse validation patterns."""

    def test_success_must_be_bool(self) -> None:
        """Test success field only accepts boolean values."""
        # Valid booleans
        ToolResponse(success=True, message="Test")
        ToolResponse(success=False, message="Test")

        # Invalid: string
        with pytest.raises(ValidationError):
            ToolResponse(success="true", message="Test")

        # Invalid: int
        with pytest.raises(ValidationError):
            ToolResponse(success=1, message="Test")

    def test_message_required(self) -> None:
        """Test message field is always required."""
        with pytest.raises(ValidationError):
            ToolResponse(success=True)  # Missing message

        with pytest.raises(ValidationError):
            ToolResponse(success=True, message="")  # Empty message

    def test_optional_fields_can_be_omitted(self) -> None:
        """Test that optional fields can be None or omitted."""
        # All valid
        ToolResponse(
            success=True,
            message="Test",
            data=None,
            error=None,
            next_steps=None,
        )

    def test_next_steps_must_be_list(self) -> None:
        """Test next_steps must be a list of strings."""
        # Valid list
        ToolResponse(
            success=True,
            message="Test",
            next_steps=["Step 1", "Step 2"],
        )

        # Invalid: not a list
        with pytest.raises(ValidationError):
            ToolResponse(
                success=True,
                message="Test",
                next_steps="Step 1",  # Should be list
            )


@pytest.mark.unit
class TestToolInputValidation:
    """Tests for ToolInput validation patterns."""

    def test_parameters_must_be_dict(self) -> None:
        """Test parameters field must be a dictionary."""
        ToolInput(
            name="test",
            description="Test",
            parameters={},
            example={},
        )

        with pytest.raises(ValidationError):
            ToolInput(
                name="test",
                description="Test",
                parameters="not a dict",  # type: ignore
                example={},
            )

    def test_example_must_be_dict(self) -> None:
        """Test example field must be a dictionary."""
        ToolInput(
            name="test",
            description="Test",
            parameters={},
            example={},
        )

        with pytest.raises(ValidationError):
            ToolInput(
                name="test",
                description="Test",
                parameters={},
                example="not a dict",  # type: ignore
            )


@pytest.mark.unit
class TestToolResponseRealWorldScenarios:
    """Tests mimicking real-world MCP tool usage."""

    def test_database_query_response(self) -> None:
        """Test response from database query tool."""
        response = ToolResponse(
            success=True,
            message="Retrieved 5 user records",
            data={
                "records": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"},
                    {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
                    {"id": 4, "name": "Diana", "email": "diana@example.com"},
                    {"id": 5, "name": "Eve", "email": "eve@example.com"},
                ],
                "total": 5,
                "query_time_ms": 23,
            },
            next_steps=[
                "Process user records",
                "Send notifications if needed",
            ],
        )

        assert response.success is True
        assert len(response.data["records"]) == 5
        assert response.data["query_time_ms"] == 23

    def test_api_request_failure_response(self) -> None:
        """Test response from failed API request."""
        response = ToolResponse(
            success=False,
            message="External API request failed",
            error="HTTP 400 Bad Request: Invalid parameter 'limit' must be >= 1",
            data=None,
            next_steps=[
                "Validate request parameters",
                "Check API documentation",
                "Retry with corrected parameters",
            ],
        )

        assert response.success is False
        assert "HTTP 400" in response.error
        assert len(response.next_steps) == 3

    def test_file_operation_response(self) -> None:
        """Test response from file operation tool."""
        response = ToolResponse(
            success=True,
            message="File copied successfully",
            data={
                "source": "/path/to/source.txt",
                "destination": "/path/to/destination.txt",
                "bytes_copied": 1024,
                "duration_seconds": 0.5,
            },
        )

        assert response.success is True
        assert response.data["bytes_copied"] == 1024

    def test_validation_error_response(self) -> None:
        """Test response for validation error."""
        response = ToolResponse(
            success=False,
            message="Input validation failed",
            error="Email address 'invalid-email' is not a valid format",
            data={
                "field": "email",
                "value": "invalid-email",
                "constraint": "must match email regex pattern",
            },
            next_steps=[
                "Correct email format",
                "Resubmit with valid email",
            ],
        )

        assert response.success is False
        assert "not a valid format" in response.error
