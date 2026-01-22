"""Tests for dual-use tool interfaces."""

from __future__ import annotations

import pytest

from mcp_common.interfaces import DualUseTool, ensure_dual_use


class TestDualUseTool:
    """Test the DualUseTool protocol."""

    def test_valid_dual_use_tool(self):
        """Valid tool implements both cli and mcp methods."""

        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True}

        # Should not raise TypeError
        assert isinstance(ValidTool(), DualUseTool)

    def test_missing_cli_method(self):
        """Tool without cli method should fail protocol check."""

        class InvalidToolNoCLI:
            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True}

        tool = InvalidToolNoCLI()
        assert not isinstance(tool, DualUseTool)

    def test_missing_mcp_method(self):
        """Tool without mcp method should fail protocol check."""

        class InvalidToolNoMCP:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

        tool = InvalidToolNoMCP()
        assert not isinstance(tool, DualUseTool)


class TestEnsureDualUse:
    """Test the ensure_dual_use decorator."""

    def test_decorator_with_valid_tool(self):
        """Decorator should pass valid tool."""

        @ensure_dual_use
        class ValidTool:
            @staticmethod
            def cli(args: list[str]) -> str:
                return "CLI output"

            @staticmethod
            async def mcp(**kwargs) -> dict:
                return {"success": True}

        # Should not raise
        assert ValidTool is not None

    def test_decorator_missing_cli(self):
        """Decorator should raise TypeError when cli method missing."""

        def create_invalid_tool():
            @ensure_dual_use
            class InvalidTool:
                @staticmethod
                async def mcp(**kwargs) -> dict:
                    return {"success": True}
            return InvalidTool

        with pytest.raises(TypeError, match="must implement 'cli"):
            create_invalid_tool()

    def test_decorator_missing_mcp(self):
        """Decorator should raise TypeError when mcp method missing."""

        def create_invalid_tool():
            @ensure_dual_use
            class InvalidTool:
                @staticmethod
                def cli(args: list[str]) -> str:
                    return "CLI output"
            return InvalidTool

        with pytest.raises(TypeError, match=r"must implement 'async mcp"):
            create_invalid_tool()

    def test_decorator_non_async_mcp(self):
        """Decorator should raise TypeError when mcp is not async."""

        def create_invalid_tool():
            @ensure_dual_use
            class InvalidTool:
                @staticmethod
                def cli(args: list[str]) -> str:
                    return "CLI output"

                @staticmethod
                def mcp(**kwargs) -> dict:
                    # Not async!
                    return {"success": True}
            return InvalidTool

        with pytest.raises(TypeError, match="must be an async method"):
            create_invalid_tool()

    def test_realistic_dual_use_tool(self):
        """Test a realistic dual-use tool implementation."""

        @ensure_dual_use
        class SearchTool:
            """Search tool that works via CLI and MCP."""

            @staticmethod
            def cli(args: list[str]) -> str:
                """Execute search via CLI."""
                query = " ".join(args)
                # Simulate search
                results = [f"Result {i+1} for '{query}'" for i in range(3)]
                return "\n".join(results)

            @staticmethod
            async def mcp(**kwargs) -> dict:
                """Execute search via MCP."""
                query = kwargs.get("query", "")
                # Simulate search
                results = [{"id": i, "text": f"Result {i+1} for '{query}'"} for i in range(3)]
                return {
                    "success": True,
                    "message": f"Found {len(results)} results",
                    "data": {"results": results},
                    "next_steps": ["View detailed results"]
                }

        # Test CLI interface
        tool = SearchTool()
        cli_output = tool.cli(["test", "query"])
        assert "Result 1 for 'test query'" in cli_output
        assert "Result 2 for 'test query'" in cli_output

        # Test MCP interface
        import asyncio

        async def test_mcp():
            mcp_output = await tool.mcp(query="test query")
            assert mcp_output["success"] is True
            assert "Found 3 results" in mcp_output["message"]
            assert len(mcp_output["data"]["results"]) == 3

        asyncio.run(test_mcp())
