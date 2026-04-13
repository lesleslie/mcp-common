"""Shared LLM types for the Bodai ecosystem."""

from __future__ import annotations

from enum import StrEnum


class TaskType(StrEnum):
    """Task categories for model routing."""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TESTING = "testing"
    REASONING = "reasoning"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    GENERAL = "general"
    SWARM = "swarm"
    VISION = "vision"
    QUICK = "quick"
    EMBEDDING = "embedding"
    CREATIVE = "creative"
