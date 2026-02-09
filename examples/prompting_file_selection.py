"""File selection examples for the prompting adapter.

This script demonstrates:
- Single file selection
- Multiple file selection
- Directory selection
- File type filtering
"""

import asyncio
from pathlib import Path
from mcp_common.prompting import create_prompt_adapter


async def main():
    """Run file selection examples."""
    adapter = create_prompt_adapter()
    await adapter.initialize()
    print(f"Using backend: {adapter.backend_name}\n")

    try:
        # Example 1: Single file selection
        print("=== Example 1: Single File Selection ===")
        files = await adapter.select_file(
            title="Select Configuration File",
            allowed_types=["yaml", "yml", "json"],
        )
        if files:
            print(f"Selected file: {files[0]}")
            print(f"File exists: {files[0].exists()}")
        else:
            print("No file selected")
        print()

        # Example 2: Multiple file selection
        print("=== Example 2: Multiple File Selection ===")
        files = await adapter.select_file(
            title="Select Log Files",
            allowed_types=["log", "txt"],
            multiple=True,
        )
        if files:
            print(f"Selected {len(files)} files:")
            for file in files:
                print(f"  - {file}")
        else:
            print("No files selected")
        print()

        # Example 3: Directory selection
        print("=== Example 3: Directory Selection ===")
        directory = await adapter.select_directory(
            title="Select Project Directory",
        )
        if directory:
            print(f"Selected directory: {directory}")
            print(f"Directory exists: {directory.exists()}")
            # List contents
            if directory.exists():
                items = list(directory.iterdir())[:5]  # First 5 items
                print(f"Contents (first 5): {[i.name for i in items]}")
        else:
            print("No directory selected")
        print()

        # Example 4: File selection without filtering
        print("=== Example 4: Any File Type ===")
        files = await adapter.select_file(
            title="Select Any File",
            # No allowed_types specified - allows any file
        )
        if files:
            print(f"Selected file: {files[0]}")
            print(f"File extension: {files[0].suffix}")
        else:
            print("No file selected")
        print()

    finally:
        await adapter.shutdown()


if __name__ == "__main__":
    print("MCP Common Prompting Adapter - File Selection Examples")
    print("=" * 55)
    print()
    asyncio.run(main())
