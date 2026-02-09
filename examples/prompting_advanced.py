"""Advanced prompting adapter usage examples.

This script demonstrates:
- Context manager usage (automatic cleanup)
- PromptAdapter class instantiation
- Custom configuration with PromptAdapterSettings
- Environment variable configuration
- Error handling and fallbacks
"""

import asyncio
import os
from mcp_common.prompting import (
    PromptAdapter,
    PromptAdapterSettings,
    create_prompt_adapter,
)
from mcp_common.prompting.exceptions import (
    BackendUnavailableError,
    UserCancelledError,
)


async def example_context_manager():
    """Example 1: Using context manager for automatic resource management."""
    print("=== Example 1: Context Manager ===")

    # Context manager automatically calls initialize() and shutdown()
    async with create_prompt_adapter() as adapter:
        print(f"Backend: {adapter.backend_name}")
        await adapter.notify("Hello from context manager!")

    # Resources are automatically cleaned up here
    print("Context manager exited, resources cleaned up\n")


async def example_direct_instantiation():
    """Example 2: Direct class instantiation."""
    print("=== Example 2: Direct Instantiation ===")

    # Create adapter using PromptAdapter class
    adapter = PromptAdapter()
    await adapter.initialize()

    try:
        print(f"Backend: {adapter.backend_name}")
        result = await adapter.confirm("Does direct instantiation work?")
        print(f"Result: {result}")
    finally:
        await adapter.shutdown()

    print()


async def example_custom_settings():
    """Example 3: Custom configuration."""
    print("=== Example 3: Custom Settings ===")

    # Create custom settings
    settings = PromptAdapterSettings(
        backend="prompt-toolkit",  # Force specific backend
        timeout=60,  # Longer timeout
        tui_theme="dark",  # Dark theme for TUI
    )

    adapter = PromptAdapter(settings=settings)
    await adapter.initialize()

    try:
        print(f"Backend: {adapter.backend_name}")
        await adapter.notify("Custom settings applied!")
    finally:
        await adapter.shutdown()

    print()


async def example_environment_variables():
    """Example 4: Configuration via environment variables."""
    print("=== Example 4: Environment Variables ===")

    # Set environment variables
    os.environ["MCP_COMMON_PROMPT_BACKEND"] = "prompt-toolkit"
    os.environ["MCP_COMMON_PROMPT_TIMEOUT"] = "45"

    # Settings automatically load from environment
    settings = PromptAdapterSettings()
    print(f"Backend from env: {settings.backend}")
    print(f"Timeout from env: {settings.timeout}")

    # Clean up
    del os.environ["MCP_COMMON_PROMPT_BACKEND"]
    del os.environ["MCP_COMMON_PROMPT_TIMEOUT"]

    print()


async def example_error_handling():
    """Example 5: Error handling and fallbacks."""
    print("=== Example 5: Error Handling ===")

    # Try to use PyObjC backend (will fail on non-macOS)
    try:
        adapter = create_prompt_adapter(backend="pyobjc")
        await adapter.initialize()
        print("PyObjC backend available!")
        await adapter.shutdown()
    except BackendUnavailableError as e:
        print(f"PyObjC backend unavailable: {e.backend}")
        print(f"Reason: {e.reason}")
        print(f"Falling back to prompt-toolkit...")

        # Fallback to prompt-toolkit
        adapter = create_prompt_adapter(backend="prompt-toolkit")
        await adapter.initialize()
        try:
            print(f"Using fallback backend: {adapter.backend_name}")
            await adapter.notify("Fallback backend working!")
        finally:
            await adapter.shutdown()

    print()


async def example_user_cancellation():
    """Example 6: Handling user cancellation."""
    print("=== Example 6: User Cancellation ===")

    adapter = create_prompt_adapter()
    await adapter.initialize()

    try:
        # Prompt might be cancelled by user
        name = await adapter.prompt_text(
            title="Optional Input",
            message="Enter your name (or press Cancel to skip):",
        )

        if name is None:
            print("User cancelled the prompt")
        else:
            print(f"User entered: {name}")

        # Another way to handle cancellation
        try:
            result = await adapter.prompt_choice(
                title="Choose Option",
                message="Select an option:",
                choices=["A", "B", "C"],
            )
            print(f"Selected: {result}")
        except UserCancelledError:
            print("User cancelled via exception")

    finally:
        await adapter.shutdown()

    print()


async def example_list_backends():
    """Example 7: Check available backends."""
    print("=== Example 7: List Available Backends ===")

    from mcp_common.prompting import list_available_backends

    available = list_available_backends()
    print(f"Available backends: {', '.join(available)}")

    if len(available) == 0:
        print("No backends available! Install prompting support:")
        print("  pip install 'mcp-common[macos-prompts]'      # macOS")
        print("  pip install 'mcp-common[terminal-prompts]'    # Terminal UI")
        print("  pip install 'mcp-common[all-prompts]'         # Everything")

    print()


async def main():
    """Run all advanced examples."""
    print("MCP Common Prompting Adapter - Advanced Examples")
    print("=" * 57)
    print()

    await example_context_manager()
    await example_direct_instantiation()
    await example_custom_settings()
    await example_environment_variables()
    await example_error_handling()
    await example_user_cancellation()
    await example_list_backends()

    print("All advanced examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
