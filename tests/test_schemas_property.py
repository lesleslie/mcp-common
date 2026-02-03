"""Property-based tests for MCP protocol types using Hypothesis.

Tests ToolResponse and ToolInput schemas with various inputs to ensure
robust serialization, validation, and edge case handling.
"""

from typing import Any

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from mcp_common.schemas import ToolInput, ToolResponse


class TestToolResponseProperties:
    """Property-based tests for ToolResponse."""

    @given(
        success=st.booleans(),
        message=st.text(min_size=1, max_size=200),
        data=st.one_of(
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=50),
                values=st.one_of(
                    st.none(),
                    st.text(min_size=0, max_size=100),
                    st.integers(min_value=-1000, max_value=1000),
                    st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
                    st.lists(st.text(min_size=0, max_size=50)),
                ),
                max_size=10,
            ),
        ),
        error=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
        next_steps=st.one_of(
            st.none(),
            st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
        ),
    )
    def test_tool_response_serialization_roundtrip(
        self,
        success: bool,
        message: str,
        data: dict[str, Any] | None,
        error: str | None,
        next_steps: list[str] | None,
    ) -> None:
        """Test that ToolResponse serializes and deserializes correctly."""
        # Create response
        response = ToolResponse(
            success=success,
            message=message,
            data=data,
            error=error,
            next_steps=next_steps,
        )

        # Serialize to dict
        response_dict = response.model_dump()

        # Deserialize back
        restored = ToolResponse(**response_dict)

        # Verify all fields match
        assert restored.success == success
        assert restored.message == message
        assert restored.data == data
        assert restored.error == error
        assert restored.next_steps == next_steps

    @given(
        success=st.booleans(),
        message=st.text(min_size=1, max_size=100),
    )
    def test_tool_response_json_serialization(self, success: bool, message: str) -> None:
        """Test JSON serialization of ToolResponse."""
        response = ToolResponse(success=success, message=message)

        # Serialize to JSON
        json_str = response.model_dump_json()

        # Deserialize from JSON
        restored = ToolResponse.model_validate_json(json_str)

        assert restored.success == success
        assert restored.message == message

    @given(
        data_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=30),
            values=st.one_of(
                st.integers(min_value=0, max_value=100),
                st.text(min_size=0, max_size=50),
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_tool_response_with_various_data(self, data_dict: dict[str, Any]) -> None:
        """Test ToolResponse handles various data structures."""
        response = ToolResponse(
            success=True,
            message="Test with data",
            data=data_dict,
        )

        assert response.data == data_dict
        assert response.model_dump()["data"] == data_dict

    @given(
        next_steps_list=st.lists(
            st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
            min_size=0,
            max_size=20,
        )
    )
    def test_tool_response_next_steps(self, next_steps_list: list[str]) -> None:
        """Test ToolResponse handles next_steps correctly."""
        response = ToolResponse(
            success=True,
            message="Test",
            next_steps=next_steps_list if next_steps_list else None,
        )

        expected = next_steps_list if next_steps_list else None
        assert response.next_steps == expected

    def test_tool_response_set_encoding(self) -> None:
        """Test that sets in data are encoded as lists."""
        # Note: Pydantic's custom encoder only works with model_dump_json(),
        # not model_dump(). Sets remain as sets in model_dump().
        response = ToolResponse(
            success=True,
            message="Test with set",
            data={"tags": {1, 2, 3}, "names": {"alice", "bob"}},
        )

        # model_dump() keeps sets as sets
        response_dict = response.model_dump()
        assert isinstance(response_dict["data"]["tags"], set)

        # model_dump_json() converts sets to lists via custom encoder
        json_str = response.model_dump_json()
        restored = ToolResponse.model_validate_json(json_str)
        # After JSON roundtrip, sets become lists
        assert isinstance(restored.data["tags"], list)
        assert sorted(restored.data["tags"]) == [1, 2, 3]

    @given(
        message=st.text(min_size=0, max_size=10),
    )
    def test_tool_response_message_validation(self, message: str) -> None:
        """Test that ToolResponse accepts any message including empty strings."""
        # ToolResponse.message field doesn't have validation that rejects empty strings
        # It only has max_length=500 in the schema, so empty strings are valid
        response = ToolResponse(success=True, message=message)
        assert response.message == message


class TestToolInputProperties:
    """Property-based tests for ToolInput."""

    @given(
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        description=st.text(min_size=10, max_size=200),
        param_count=st.integers(min_value=0, max_value=5),
    )
    def test_tool_input_creation(self, name: str, description: str, param_count: int) -> None:
        """Test ToolInput creation with various parameter counts."""
        # Build parameters dynamically
        properties = {}
        required = []

        for i in range(param_count):
            param_name = f"param_{i}"
            properties[param_name] = {
                "type": "string",
                "description": f"Parameter {i}",
            }
            if i % 2 == 0:  # Make half required
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        example = {f"param_{i}": f"value_{i}" for i in range(param_count)}

        tool_input = ToolInput(
            name=name,
            description=description,
            parameters=parameters,
            example=example,
        )

        assert tool_input.name == name
        assert tool_input.description == description
        assert tool_input.parameters == parameters
        assert tool_input.example == example

    @given(
        name=st.text(min_size=1, max_size=30),
        description=st.text(min_size=10, max_size=100),
    )
    def test_tool_input_to_example(self, name: str, description: str) -> None:
        """Test ToolInput.to_example() method."""
        parameters = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        }
        example = {"query": "test"}

        tool_input = ToolInput(
            name=name,
            description=description,
            parameters=parameters,
            example=example,
        )

        result = tool_input.to_example()

        assert result["description"] == description
        assert result["parameters"] == parameters
        assert result["example"] == example

    @given(
        params=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
            values=st.dictionaries(
                keys=st.text(min_size=1, max_size=10),
                values=st.text(min_size=1, max_size=50),
                min_size=1,
                max_size=5,
            ),
            min_size=0,
            max_size=10,
        )
    )
    def test_tool_input_with_various_parameters(self, params: dict[str, Any]) -> None:
        """Test ToolInput with various parameter schemas."""
        parameters = {
            "type": "object",
            "properties": params,
            "required": list(params.keys()) if params else [],
        }

        tool_input = ToolInput(
            name="test_tool",
            description="Test tool",
            parameters=parameters,
            example=params.copy() if params else {},
        )

        assert tool_input.parameters == parameters

    def test_tool_input_serialization(self) -> None:
        """Test ToolInput serialization."""
        tool_input = ToolInput(
            name="test_tool",
            description="Test description",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
                "required": ["input"],
            },
            example={"input": "test"},
        )

        # Serialize and deserialize
        data = tool_input.model_dump()
        restored = ToolInput(**data)

        assert restored.name == tool_input.name
        assert restored.description == tool_input.description
        assert restored.parameters == tool_input.parameters
        assert restored.example == tool_input.example


class TestSchemaEdgeCases:
    """Edge case tests for protocol schemas."""

    def test_tool_response_minimal(self) -> None:
        """Test ToolResponse with only required fields."""
        response = ToolResponse(success=True, message="OK")

        assert response.success is True
        assert response.message == "OK"
        assert response.data is None
        assert response.error is None
        assert response.next_steps is None

    def test_tool_response_complete(self) -> None:
        """Test ToolResponse with all fields populated."""
        response = ToolResponse(
            success=True,
            message="Operation complete",
            data={"result": 42},
            error=None,
            next_steps=["Step 1", "Step 2"],
        )

        assert response.success is True
        assert response.data["result"] == 42
        assert len(response.next_steps) == 2

    def test_tool_response_failure(self) -> None:
        """Test ToolResponse for failure case."""
        response = ToolResponse(
            success=False,
            message="Operation failed",
            error="Connection timeout",
            next_steps=["Retry", "Check logs"],
        )

        assert response.success is False
        assert response.error == "Connection timeout"
        assert response.next_steps is not None

    @pytest.mark.parametrize(
        ("value", "should_be_valid"),
        [
            ({"valid": "dict"}, True),
            ({"nested": {"dict": {"with": "values"}}}, True),
            ({"list": [1, 2, 3]}, True),
            ({"mixed": {"types": [1, "two", {"three": 3}]}}, True),
            (None, True),  # None is valid (default)
        ],
    )
    def test_tool_response_data_validation(self, value: Any, should_be_valid: bool) -> None:
        """Test ToolResponse data field validation."""
        if should_be_valid:
            response = ToolResponse(success=True, message="Test", data=value)
            assert response.data == value

    def test_tool_response_data_rejects_invalid_types(self) -> None:
        """Test that data field rejects non-dict/non-None values."""
        import pytest
        from pydantic import ValidationError

        # These should raise ValidationError
        for invalid_value in [[], "string", 123, True]:
            with pytest.raises(ValidationError):
                ToolResponse(success=True, message="Test", data=invalid_value)

    def test_tool_input_minimal(self) -> None:
        """Test ToolInput with minimal valid parameters."""
        tool_input = ToolInput(
            name="minimal_tool",
            description="Minimal tool",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            example={},
        )

        assert tool_input.name == "minimal_tool"
        assert tool_input.parameters["properties"] == {}

    def test_json_schema_examples(self) -> None:
        """Test that JSON schema examples are valid."""
        # Verify the examples in the model_config are valid
        schema = ToolResponse.model_json_schema()
        assert "examples" in schema

        for example in schema["examples"]:
            # Should be able to create ToolResponse from example
            response = ToolResponse(**example)
            assert isinstance(response, ToolResponse)
