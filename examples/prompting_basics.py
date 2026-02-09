"""Basic prompting adapter usage examples.

This script demonstrates the fundamental features of the prompting adapter:
- Auto-detection of best backend
- Sending notifications
- Confirmation dialogs
- Text input prompts
"""

import asyncio
from mcp_common.prompting import create_prompt_adapter


async def main():
    """Run basic prompting examples."""
    # Create adapter with auto-detection
    adapter = create_prompt_adapter()

    # Initialize the adapter
    await adapter.initialize()
    print(f"Using backend: {adapter.backend_name}\n")

    try:
        # Example 1: Send notification
        print("=== Example 1: Notification ===")
        await adapter.notify(
            title="Build Complete",
            message="All tests passed successfully!",
        )
        print("Notification sent!\n")

        # Example 2: Confirmation dialog
        print("=== Example 2: Confirmation ===")
        result = await adapter.confirm(
            title="Continue",
            message="Do you want to proceed to the next example?",
            default=True,
        )
        print(f"User selected: {result}\n")
        if not result:
            print("User cancelled. Exiting...")
            return

        # Example 3: Text input
        print("=== Example 3: Text Input ===")
        name = await adapter.prompt_text(
            title="User Information",
            message="Enter your name:",
            placeholder="John Doe",
        )
        if name:
            print(f"Hello, {name}!\n")
        else:
            print("No name provided.\n")

        # Example 4: Secure input
        print("=== Example 4: Secure Input ===")
        password = await adapter.prompt_text(
            title="Authentication",
            message="Enter your password:",
            secure=True,
        )
        if password:
            print(f"Password received ({len(password)} characters)\n")
        else:
            print("No password provided.\n")

        # Example 5: Choice selection
        print("=== Example 5: Choice Selection ===")
        choice = await adapter.prompt_choice(
            title="Select Environment",
            message="Choose deployment environment:",
            choices=["development", "staging", "production"],
            default="staging",
        )
        if choice:
            print(f"Selected environment: {choice}\n")
        else:
            print("No selection made.\n")

        # Example 6: Alert with buttons
        print("=== Example 6: Alert with Buttons ===")
        from mcp_common.prompting.models import DialogResult

        result: DialogResult = await adapter.alert(
            title="Deployment Options",
            message="Choose deployment strategy:",
            buttons=["Deploy Now", "Schedule", "Cancel"],
            default_button="Schedule",
        )
        print(f"User clicked: {result.button_clicked}")
        if result.cancelled:
            print("User cancelled the dialog\n")
        else:
            print(f"Action: {result.button_clicked}\n")

    finally:
        # Cleanup resources
        await adapter.shutdown()
        print("Adapter shutdown complete.")


if __name__ == "__main__":
    print("MCP Common Prompting Adapter - Basic Examples")
    print("=" * 50)
    print()
    asyncio.run(main())
