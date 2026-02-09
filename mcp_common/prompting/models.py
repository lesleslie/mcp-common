"""Data models for prompting adapter."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationLevel(str, Enum):
    """Notification severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class PromptStyle(str, Enum):
    """Predefined prompt styles."""

    DEFAULT = "default"
    DANGER = "danger"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class ButtonConfig(BaseModel):
    """Configuration for a dialog button."""

    label: str = Field(..., description="Button label text")
    is_default: bool = Field(False, description="Whether this is the default button")
    is_cancel: bool = Field(False, description="Whether this is the cancel button")


class DialogResult(BaseModel):
    """Result from a dialog interaction."""

    button_clicked: str | None = Field(
        None, description="Label of button that was clicked"
    )
    text_input: str | None = Field(None, description="Text input from user")
    cancelled: bool = Field(False, description="Whether user cancelled the dialog")
    selected_choice: str | None = Field(None, description="Selected choice from list")
    selected_files: list[str] | None = Field(None, description="Selected file paths")
    selected_directory: str | None = Field(None, description="Selected directory path")


class PromptAdapterSettings(BaseSettings):
    """Settings for prompting adapter following Oneiric patterns."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_COMMON_PROMPT_",
        env_file=".env",
        extra="allow",
    )

    # Backend selection
    backend: str = Field(
        default="auto",
        description="Backend to use: auto, pyobjc, prompt-toolkit",
    )

    # Dialog behavior
    timeout: int | None = Field(
        default=None, description="Timeout in seconds (None = no timeout)"
    )

    # macOS-specific settings
    macos_icon: str | None = Field(default=None, description="Path to icon file for macOS dialogs")
    macos_sound: str = Field(
        default="default", description="macOS notification sound name"
    )

    # Terminal UI settings
    tui_theme: str = Field(
        default="default", description="prompt-toolkit theme name"
    )

    # Styling
    default_style: PromptStyle = Field(
        default=PromptStyle.DEFAULT, description="Default prompt style"
    )

    @classmethod
    def from_settings(cls) -> "PromptAdapterSettings":
        """Load from Oneiric settings with environment overrides.

        Loads configuration from:
        1. settings/mcp-common.yaml (if exists)
        2. Environment variables (MCP_COMMON_PROMPT_*)
        3. Default values

        Returns:
            Configured settings instance
        """
        try:
            from oneiric import load_config

            oneiric_config = load_config()
            prompt_config = oneiric_config.get("prompting", {})
            return cls(**prompt_config)
        except ImportError:
            # Oneiric not available, use defaults
            return cls()


# Backward compatibility alias
PromptConfig = PromptAdapterSettings


class PromptRequest(BaseModel):
    """Request for a prompt operation."""

    title: str = Field(..., description="Dialog title")
    message: str = Field(..., description="Primary message")
    detail: str | None = Field(None, description="Additional details")
    default: str | None = Field(None, description="Default value")
    placeholder: str | None = Field(None, description="Placeholder text")
    choices: list[str] | None = Field(None, description="List of choices")
    buttons: list[str] | None = Field(None, description="Button labels")
    secure: bool = Field(False, description="Whether to mask input")
    style: str | None = Field(None, description="Dialog style")

    # File selection options
    allowed_types: list[str] | None = Field(None, description="Allowed file extensions")
    multiple_files: bool = Field(False, description="Allow multiple file selection")

    # Notification options
    level: NotificationLevel = Field(NotificationLevel.INFO, description="Notification level")
    sound: bool = Field(True, description="Play notification sound")
