"""Tests for LLM-friendly API schemas."""

from __future__ import annotations

import pytest

from mcp_common.schemas import ToolInput, ToolResponse


class TestToolResponse:
    """Test the ToolResponse model."""

    def test_successful_response(self):
        """Test creating a successful tool response."""
        response = ToolResponse(
            success=True,
            message="Successfully created 3 user records",
            data={
                "records": [
                    {"id": "1", "name": "Alice"},
                    {"id": "2", "name": "Bob"},
                    {"id": "3", "name": "Charlie"}
                ]
            },
            next_steps=["Verify records in database", "Send confirmation emails"]
        )

        assert response.success is True
        assert "Successfully created" in response.message
        assert len(response.data["records"]) == 3
        assert response.error is None
        assert len(response.next_steps) == 2

    def test_failed_response(self):
        """Test creating a failed tool response."""
        response = ToolResponse(
            success=False,
            message="Failed to connect to database",
            error="Connection timeout after 30s - check database connectivity",
            next_steps=[
                "Check database status",
                "Verify network connectivity",
                "Retry with increased timeout"
            ]
        )

        assert response.success is False
        assert "Failed to connect" in response.message
        assert response.data is None
        assert "timeout" in response.error
        assert len(response.next_steps) == 3

    def test_minimal_response(self):
        """Test creating a minimal response (only required fields)."""
        response = ToolResponse(
            success=True,
            message="Operation completed"
        )

        assert response.success is True
        assert response.message == "Operation completed"
        assert response.data is None
        assert response.error is None
        assert response.next_steps is None

    def test_json_serialization(self):
        """Test that ToolResponse serializes to JSON correctly."""
        response = ToolResponse(
            success=True,
            message="Success",
            data={"count": 42},
            next_steps=["Step 1", "Step 2"]
        )

        json_dict = response.model_dump()

        assert json_dict["success"] is True
        assert json_dict["message"] == "Success"
        assert json_dict["data"]["count"] == 42
        assert json_dict["error"] is None
        assert json_dict["next_steps"] == ["Step 1", "Step 2"]

    def test_json_deserialization(self):
        """Test that ToolResponse can be created from JSON dict."""
        json_dict = {
            "success": True,
            "message": "Success",
            "data": {"count": 42},
            "error": None,
            "next_steps": ["Step 1"]
        }

        response = ToolResponse(**json_dict)

        assert response.success is True
        assert response.message == "Success"
        assert response.data["count"] == 42


class TestToolInput:
    """Test the ToolInput model."""

    def test_tool_input_creation(self):
        """Test creating a tool input schema."""
        input_schema = ToolInput(
            name="search_users",
            description="Search for users by name or email",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or email)"
                    }
                },
                "required": ["query"]
            },
            example={"query": "alice@example.com"}
        )

        assert input_schema.name == "search_users"
        assert "Search for users" in input_schema.description
        assert input_schema.parameters["type"] == "object"
        assert "query" in input_schema.parameters["properties"]
        assert input_schema.example["query"] == "alice@example.com"

    def test_to_example_method(self):
        """Test the to_example() method generates proper format."""
        input_schema = ToolInput(
            name="create_user",
            description="Create a new user account",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["name", "email"]
            },
            example={"name": "Alice", "email": "alice@example.com"}
        )

        example = input_schema.to_example()

        assert "description" in example
        assert "parameters" in example
        assert "example" in example
        assert example["description"] == "Create a new user account"
        assert example["example"]["name"] == "Alice"

    def test_json_serialization(self):
        """Test that ToolInput serializes to JSON correctly."""
        input_schema = ToolInput(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            example={"test": "value"}
        )

        json_dict = input_schema.model_dump()

        assert json_dict["name"] == "test_tool"
        assert json_dict["description"] == "Test tool"
        assert json_dict["parameters"]["type"] == "object"
        assert json_dict["example"]["test"] == "value"
