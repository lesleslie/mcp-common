"""Tests for Dual-Use Tool Interfaces."""

from __future__ import annotations

import inspect

import pytest

from mcp_common.interfaces import DualUseTool, ensure_dual_use


@pytest.mark.unit
class TestDualUseToolProtocol:
    """Tests for DualUseTool protocol."""

    def test_dual_use_tool_is_protocol(self) -> None:
        """Test that DualUseTool is a runtime-checkable protocol."""
        assert hasattr(DualUseTool, "__protocol_attrs__")
        assert "cli" in DualUseTool.__protocol_attrs__
        assert "mcp" in DualUseTool.__protocol_attrs__

    def test_dual_use_tool_checks_implementations(self) -> None:
        """Test DualUseTool can check if a class implements the protocol."""

        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True}

        assert isinstance(ValidTool(), DualUseTool)

    def test_dual_use_tool_rejects_invalid_implementations(self) -> None:
        """Test DualUseTool rejects classes without required methods."""

        class InvalidTool:
            def some_other_method(self) -> None:
                pass

        assert not isinstance(InvalidTool(), DualUseTool)

    def test_dual_use_tool_requires_cli_method(self) -> None:
        """Test DualUseTool requires cli method."""

        class MissingCLI:
            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

        assert not isinstance(MissingCLI(), DualUseTool)

    def test_dual_use_tool_requires_mcp_method(self) -> None:
        """Test DualUseTool requires mcp method."""

        class MissingMCP:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

        assert not isinstance(MissingMCP(), DualUseTool)


@pytest.mark.unit
class TestEnsureDualUseDecorator:
    """Tests for ensure_dual_use decorator."""

    def test_decorator_passes_valid_tool(self) -> None:
        """Test decorator accepts valid dual-use tool."""

        @ensure_dual_use
        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True, "message": "Done"}

        # Should not raise
        assert ValidTool is not None

    def test_decorator_rejects_missing_cli(self) -> None:
        """Test decorator rejects tool without cli method."""

        with pytest.raises(TypeError) as exc_info:
            @ensure_dual_use
            class MissingCLI:
                @staticmethod
                async def mcp(**kwargs) -> dict:
                    return {}

        assert "must implement 'cli" in str(exc_info.value)

    def test_decorator_rejects_missing_mcp(self) -> None:
        """Test decorator rejects tool without mcp method."""

        with pytest.raises(TypeError) as exc_info:
            @ensure_dual_use
            class MissingMCP:
                @staticmethod
                def cli(args: list[str]) -> str:
                    return "output"

        assert "must implement 'async mcp" in str(exc_info.value)

    def test_decorator_rejects_non_callable_cli(self) -> None:
        """Test decorator rejects non-callable cli attribute."""

        with pytest.raises(TypeError) as exc_info:
            @ensure_dual_use
            class InvalidCLI:
                cli = "not a method"  # type: ignore[assignment]

                @staticmethod
                async def mcp(**kwargs) -> dict:
                    return {}

        assert "cli must be callable" in str(exc_info.value)

    def test_decorator_rejects_non_callable_mcp(self) -> None:
        """Test decorator rejects non-callable mcp attribute."""

        with pytest.raises(TypeError) as exc_info:
            @ensure_dual_use
            class InvalidMCP:
                @staticmethod
                def cli(args: list[str]) -> str:
                    return "output"

                mcp = "not a method"  # type: ignore[assignment]

        assert "mcp must be callable" in str(exc_info.value)

    def test_decorator_requires_async_mcp(self) -> None:
        """Test decorator requires mcp method to be async."""

        with pytest.raises(TypeError) as exc_info:
            @ensure_dual_use
            class SyncMCP:
                @staticmethod
                def cli(args: list[str]) -> str:
                    return "output"

                @staticmethod
                def mcp(**kwargs) -> dict:  # Not async
                    return {}

        assert "must be an async method" in str(exc_info.value)

    def test_decorator_preserves_class(self) -> None:
        """Test decorator returns the same class instance."""

        @ensure_dual_use
        class TestTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

        # Should return the class
        assert TestTool.__name__ == "TestTool"


@pytest.mark.unit
class TestDualUseToolExamples:
    """Tests with realistic dual-use tool examples."""

    def test_search_tool_implementation(self) -> None:
        """Test realistic search tool implementation."""

        class SearchTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                query = " ".join(args)
                # Simulate search
                results = [f"Result {i} for '{query}'" for i in range(1, 4)]
                return "\n".join(results)

            @staticmethod
            async def mcp(**kwargs) -> dict:
                query = kwargs.get("query", "")
                results = [f"Result {i} for '{query}'" for i in range(1, 4)]
                return {
                    "success": True,
                    "message": f"Found {len(results)} results",
                    "data": {"results": results, "query": query},
                }

        tool = SearchTool()

        # Test CLI interface
        cli_output = tool.cli(["test", "query"])
        assert "Result 1" in cli_output
        assert "test query" in cli_output

        # Test MCP interface
        import asyncio

        mcp_output = asyncio.run(tool.mcp(query="test query"))
        assert mcp_output["success"] is True
        assert mcp_output["data"]["query"] == "test query"

    def test_file_operation_tool(self) -> None:
        """Test realistic file operation tool."""

        class FileCopyTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                if len(args) < 2:
                    return "Usage: copy <source> <destination>"
                source, dest = args[0], args[1]
                return f"Copied {source} to {dest}"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                source = kwargs.get("source")
                destination = kwargs.get("destination")

                if not source or not destination:
                    return {
                        "success": False,
                        "message": "Missing required parameters",
                        "error": "Both 'source' and 'destination' are required",
                    }

                return {
                    "success": True,
                    "message": f"Copied {source} to {destination}",
                    "data": {"source": source, "destination": destination},
                }

        tool = FileCopyTool()

        # Test CLI
        cli_output = tool.cli(["file1.txt", "file2.txt"])
        assert "file1.txt" in cli_output
        assert "file2.txt" in cli_output

        # Test MCP
        import asyncio

        mcp_output = asyncio.run(
            tool.mcp(source="file1.txt", destination="file2.txt")
        )
        assert mcp_output["success"] is True

    def test_tool_with_decorator(self) -> None:
        """Test tool using ensure_dual_use decorator."""

        @ensure_dual_use
        class ValidatedTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                if not args:
                    return "Error: No query provided"
                return f"Searching for: {' '.join(args)}"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                query = kwargs.get("query", "")
                if not query:
                    return {
                        "success": False,
                        "message": "Query parameter is required",
                        "error": "Missing 'query' in request",
                    }

                return {
                    "success": True,
                    "message": f"Processed query: {query}",
                    "data": {"query": query},
                }

        tool = ValidatedTool()

        # CLI
        assert "Searching for:" in tool.cli(["test"])

        # MCP
        import asyncio

        result = asyncio.run(tool.mcp(query="test"))
        assert result["success"] is True


@pytest.mark.unit
class TestDualUseToolProtocolCompliance:
    """Tests for protocol compliance details."""

    def test_cli_method_signature(self) -> None:
        """Test CLI method has correct signature."""

        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

        tool = ValidTool()
        assert callable(tool.cli)

        # Check signature
        sig = inspect.signature(tool.cli)
        assert "args" in sig.parameters

    def test_mcp_method_signature(self) -> None:
        """Test MCP method has correct signature."""

        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

        tool = ValidTool()
        assert callable(tool.mcp)

        # Check it's async
        assert inspect.iscoroutinefunction(tool.mcp)

        # Check signature
        sig = inspect.signature(tool.mcp)
        # Should accept kwargs
        assert sig.parameters.get("kwargs") or any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )

    def test_both_methods_produce_equivalent_results(self) -> None:
        """Test both methods produce logically equivalent results."""

        class CalculatorTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                a, b = int(args[0]), int(args[1])
                result = a + b
                return f"Sum: {result}"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                a = kwargs.get("a", 0)
                b = kwargs.get("b", 0)
                result = a + b
                return {
                    "success": True,
                    "message": f"Calculated sum",
                    "data": {"a": a, "b": b, "result": result},
                }

        tool = CalculatorTool()

        # CLI output (formatted for humans)
        cli_output = tool.cli(["5", "3"])
        assert "8" in cli_output

        # MCP output (structured for agents)
        import asyncio

        mcp_output = asyncio.run(tool.mcp(a=5, b=3))
        assert mcp_output["data"]["result"] == 8


@pytest.mark.unit
class TestDualUseToolEdgeCases:
    """Tests for edge cases in dual-use tools."""

    def test_tool_with_instance_methods(self) -> None:
        """Test tool can use instance methods instead of static methods."""

        class InstanceTool:
            def cli(self, args: list[str]) -> str:
                return f"Instance CLI: {' '.join(args)}"

            async def mcp(self, **kwargs) -> dict:
                return {
                    "success": True,
                    "message": "Instance MCP",
                    "data": kwargs,
                }

        tool = InstanceTool()

        # Should still satisfy protocol
        assert isinstance(tool, DualUseTool)

    def test_tool_with_additional_methods(self) -> None:
        """Test tool can have other methods beyond cli/mcp."""

        class ExtendedTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

            @staticmethod
            def helper_function() -> str:
                return "helper"

        tool = ExtendedTool()

        # Should still satisfy protocol
        assert isinstance(tool, DualUseTool)
        assert tool.helper_function() == "helper"

    def test_decorator_with_additional_methods(self) -> None:
        """Test decorator doesn't interfere with other methods."""

        @ensure_dual_use
        class ExtendedTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {}

            @staticmethod
            def validate(value: str) -> bool:
                return len(value) > 0

        tool = ExtendedTool()

        # Additional method should work
        assert tool.validate("test") is True

    def test_cli_handles_empty_args(self) -> None:
        """Test CLI method handles empty argument list gracefully."""

        class RobustTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                if not args:
                    return "No arguments provided"
                return " ".join(args)

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True, "data": kwargs}

        tool = RobustTool()
        output = tool.cli([])
        assert "No arguments" in output

    def test_mcp_handles_empty_kwargs(self) -> None:
        """Test MCP method handles empty kwargs gracefully."""

        class RobustTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {
                    "success": True,
                    "message": "Processed",
                    "data": kwargs if kwargs else {"empty": True},
                }

        tool = RobustTool()

        import asyncio

        output = asyncio.run(tool.mcp())
        assert output["data"]["empty"] is True
