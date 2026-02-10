#!/usr/bin/env python3
"""Demo script for prompting adapter.

This script demonstrates the unified prompting adapter with automatic backend detection.
Run with: python examples/prompt_demo.py
"""

import asyncio
from mcp_common.prompting import create_prompt_adapter, NotificationLevel


async def main():
    """Run prompting adapter demonstrations."""

    # Create adapter with auto-detection
    adapter = create_prompt_adapter()
    print(f"Using backend: {adapter.backend_name}\n")

    # 1. Simple alert
    print("=== 1. Alert Dialog ===")
    result = await adapter.alert(
        title="Welcome",
        message="This is a demonstration of the prompting adapter.",
        buttons=["Got it!", "Tell me more"],
        default_button="Got it!",
    )
    print(f"Button clicked: {result.button_clicked}\n")

    # 2. Confirmation dialog
    print("=== 2. Confirmation Dialog ===")
    confirmed = await adapter.confirm(
        title="Continue Demo",
        message="Would you like to see more examples?",
        default=True,
    )
    print(f"Confirmed: {confirmed}\n")

    if not confirmed:
        print("Demo cancelled by user.")
        return

    # 3. Text input
    print("=== 3. Text Input ===")
    name = await adapter.prompt_text(
        title="Personalization",
        message="What should we call you?",
        default="Claude User",
        placeholder="Enter your name",
    )
    print(f"Name: {name}\n")

    # 4. Choice selection
    print("=== 4. Choice Selection ===")
    choice = await adapter.prompt_choice(
        title="Favorite Color",
        message="What's your favorite color?",
        choices=["Red", "Green", "Blue", "Other"],
        default="Blue",
    )
    print(f"Selected: {choice}\n")

    # 5. Notification
    print("=== 5. Notification ===")
    await adapter.notify(
        title="Demo Complete",
        message="All demonstrations finished successfully!",
        level=NotificationLevel.SUCCESS,
        sound=True,
    )
    print("Notification sent!\n")

    # 6. File selection (optional, can skip in CI)
    print("=== 6. File Selection (Optional) ===")
    try:
        file_result = await adapter.select_file(
            title="Select a file to inspect",
            allowed_types=["py", "md", "txt"],
            multiple=False,
        )
        if file_result:
            print(f"Selected file: {file_result[0]}\n")
        else:
            print("No file selected (cancelled)\n")
    except Exception as e:
        print(f"File selection skipped: {e}\n")

    # 7. Directory selection (optional)
    print("=== 7. Directory Selection (Optional) ===")
    try:
        dir_result = await adapter.select_directory(
            title="Select a working directory",
        )
        if dir_result:
            print(f"Selected directory: {dir_result}\n")
        else:
            print("No directory selected (cancelled)\n")
    except Exception as e:
        print(f"Directory selection skipped: {e}\n")

    print("=== Demo Complete ===")
    print(f"Thanks, {name}!")


if __name__ == "__main__":
    asyncio.run(main())
