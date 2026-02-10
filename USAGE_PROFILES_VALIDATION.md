#!/usr/bin/env python3
"""Validation script for MCP Common Usage Profiles implementation.

This script validates that all usage profiles are correctly implemented and working.
"""

from __future__ import annotations

import sys


def test_imports() -> bool:
    """Test that all profiles can be imported."""
    try:
        from mcp_common.profiles import MinimalServer, StandardServer, FullServer
        print("✅ All profiles imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_minimal_server() -> bool:
    """Test MinimalServer functionality."""
    try:
        from mcp_common.profiles import MinimalServer

        server = MinimalServer(name="test-minimal")

        @server.tool()
        def add(a: int, b: int) -> int:
            return a + b

        @server.tool()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        # Test tool listing
        tools = server.list_tools()
        assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}"
        assert "add" in tools, "add tool not found"
        assert "greet" in tools, "greet tool not found"

        # Test health check
        health = server.health_check()
        assert health["status"] == "healthy", f"Expected healthy status, got {health['status']}"
        assert health["server"] == "test-minimal", f"Expected server name test-minimal, got {health['server']}"
        assert health["tools"] == 2, f"Expected 2 tools in health, got {health['tools']}"

        # Test tool retrieval
        add_tool = server.get_tool("add")
        assert add_tool is not None, "add tool retrieval failed"
        result = add_tool(3, 5)
        assert result == 8, f"Expected add(3, 5) = 8, got {result}"

        print("✅ MinimalServer: All tests passed")
        return True
    except Exception as e:
        print(f"❌ MinimalServer test failed: {e}")
        return False


def test_standard_server() -> bool:
    """Test StandardServer functionality."""
    try:
        from mcp_common.profiles import StandardServer

        server = StandardServer(
            name="test-standard",
            description="Test Standard Server"
        )

        @server.tool()
        def search(query: str) -> dict:
            return {"query": query, "results": []}

        @server.resource("config://{name}")
        def get_config(name: str) -> str:
            return f"config-{name}"

        @server.resource("data://{table}")
        def get_data(table: str) -> str:
            return f"data-{table}"

        # Test tool listing
        tools = server.list_tools()
        assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
        assert "search" in tools, "search tool not found"

        # Test resource listing
        resources = server.list_resources()
        assert len(resources) == 2, f"Expected 2 resources, got {len(resources)}"
        assert "config://{name}" in resources, "config resource not found"
        assert "data://{table}" in resources, "data resource not found"

        # Test health check
        health = server.health_check()
        assert health["status"] == "healthy", f"Expected healthy status, got {health['status']}"
        assert health["tools"] == 1, f"Expected 1 tool in health, got {health['tools']}"
        assert health["resources"] == 2, f"Expected 2 resources in health, got {health['resources']}"
        assert health["description"] == "Test Standard Server", f"Description mismatch"

        print("✅ StandardServer: All tests passed")
        return True
    except Exception as e:
        print(f"❌ StandardServer test failed: {e}")
        return False


def test_full_server() -> bool:
    """Test FullServer functionality."""
    try:
        from mcp_common.profiles import FullServer

        # Mock auth and telemetry
        class MockAuth:
            pass

        class MockTelemetry:
            pass

        server = FullServer(
            name="test-full",
            description="Test Full Server",
            auth=MockAuth(),
            telemetry=MockTelemetry()
        )

        @server.tool()
        def process(data: dict) -> dict:
            return {"processed": True, "data": data}

        @server.resource("resource://{id}")
        def get_resource(id: str) -> str:
            return f"resource-{id}"

        @server.prompt("analyze")
        def analyze_prompt(data: str) -> str:
            return f"Analyze: {data}"

        @server.prompt("summarize")
        def summarize_prompt(content: str) -> str:
            return f"Summarize: {content}"

        # Test tool listing
        tools = server.list_tools()
        assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"

        # Test resource listing
        resources = server.list_resources()
        assert len(resources) == 1, f"Expected 1 resource, got {len(resources)}"

        # Test prompt listing
        prompts = server.list_prompts()
        assert len(prompts) == 2, f"Expected 2 prompts, got {len(prompts)}"
        assert "analyze" in prompts, "analyze prompt not found"
        assert "summarize" in prompts, "summarize prompt not found"

        # Test health check
        health = server.health_check()
        assert health["status"] == "healthy", f"Expected healthy status, got {health['status']}"
        assert health["tools"] == 1, f"Expected 1 tool in health, got {health['tools']}"
        assert health["resources"] == 1, f"Expected 1 resource in health, got {health['resources']}"
        assert health["prompts"] == 2, f"Expected 2 prompts in health, got {health['prompts']}"
        assert health["auth"]["enabled"] is True, "Expected auth enabled"
        assert health["telemetry"]["enabled"] is True, "Expected telemetry enabled"

        print("✅ FullServer: All tests passed")
        return True
    except Exception as e:
        print(f"❌ FullServer test failed: {e}")
        return False


def test_examples_exist() -> bool:
    """Test that example files exist and are runnable."""
    import os

    examples_dir = "/Users/les/Projects/mcp-common/examples"
    required_files = [
        "minimal_server.py",
        "standard_server.py",
        "full_server.py",
    ]

    all_exist = True
    for filename in required_files:
        filepath = os.path.join(examples_dir, filename)
        if os.path.exists(filepath):
            print(f"✅ Example file exists: {filename}")
        else:
            print(f"❌ Example file missing: {filename}")
            all_exist = False

    return all_exist


def test_documentation_exists() -> bool:
    """Test that documentation exists."""
    import os

    docs_dir = "/Users/les/Projects/mcp-common/docs/guides"
    required_files = [
        "usage-profiles.md",
    ]

    all_exist = True
    for filename in required_files:
        filepath = os.path.join(docs_dir, filename)
        if os.path.exists(filepath):
            print(f"✅ Documentation exists: {filename}")
        else:
            print(f"❌ Documentation missing: {filename}")
            all_exist = False

    # Check QUICKSTART
    quickstart_path = "/Users/les/Projects/mcp-common/QUICKSTART.md"
    if os.path.exists(quickstart_path):
        with open(quickstart_path) as f:
            content = f.read()
            if "MinimalServer" in content and "StandardServer" in content and "FullServer" in content:
                print("✅ QUICKSTART.md updated with profile information")
            else:
                print("❌ QUICKSTART.md missing profile information")
                all_exist = False
    else:
        print("❌ QUICKSTART.md not found")
        all_exist = False

    return all_exist


def main() -> int:
    """Run all validation tests."""
    print("=" * 80)
    print("MCP Common Usage Profiles Validation")
    print("=" * 80)
    print()

    tests = [
        ("Import Tests", test_imports),
        ("MinimalServer Tests", test_minimal_server),
        ("StandardServer Tests", test_standard_server),
        ("FullServer Tests", test_full_server),
        ("Example Files", test_examples_exist),
        ("Documentation", test_documentation_exists),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        print("-" * 80)
        result = test_func()
        results.append((name, result))

    # Summary
    print()
    print("=" * 80)
    print("Validation Summary")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Results: {passed}/{total} test suites passed")

    if passed == total:
        print()
        print("🎉 All validation tests passed!")
        print()
        print("Usage Profiles Implementation: COMPLETE ✅")
        return 0
    else:
        print()
        print("⚠️  Some validation tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
