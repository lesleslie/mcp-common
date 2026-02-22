"""Grammar loader for tree-sitter languages.

Provides lazy loading of tree-sitter grammars to avoid import errors
when tree-sitter is not installed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_common.parsing.tree_sitter.core import LanguageRegistry
from mcp_common.parsing.tree_sitter.models import SupportedLanguage

if TYPE_CHECKING:
    import tree_sitter

logger = logging.getLogger(__name__)

# Track loaded languages
_loaded_languages: set[SupportedLanguage] = set()


def load_python_grammar() -> tree_sitter.Language | None:
    """Load Python grammar.

    Returns:
        Language object or None if loading failed
    """
    try:
        # Use the language() function from tree_sitter_python
        from tree_sitter import Language
        from tree_sitter_python import language as python_language

        language = Language(python_language())
        LanguageRegistry.set_grammar(SupportedLanguage.PYTHON, language)

        # Register handler
        from mcp_common.parsing.tree_sitter.handlers.python import PythonHandler

        LanguageRegistry.register(PythonHandler())

        _loaded_languages.add(SupportedLanguage.PYTHON)
        logger.debug("Loaded Python tree-sitter grammar")
        return language

    except ImportError as e:
        logger.warning(f"Failed to load Python grammar: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading Python grammar: {e}")
        return None


def load_go_grammar() -> tree_sitter.Language | None:
    """Load Go grammar.

    Returns:
        Language object or None if loading failed
    """
    try:
        from tree_sitter import Language
        from tree_sitter_go import language as go_language

        language = Language(go_language())
        LanguageRegistry.set_grammar(SupportedLanguage.GO, language)

        # Go handler would be registered here
        # from mcp_common.parsing.tree_sitter.handlers.go import GoHandler
        # LanguageRegistry.register(GoHandler())

        _loaded_languages.add(SupportedLanguage.GO)
        logger.debug("Loaded Go tree-sitter grammar")
        return language

    except ImportError as e:
        logger.warning(f"Failed to load Go grammar: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading Go grammar: {e}")
        return None


def load_all_grammars() -> dict[SupportedLanguage, tree_sitter.Language | None]:
    """Load all available grammars.

    Returns:
        Dict mapping language to loaded grammar (or None if failed)
    """
    return {
        SupportedLanguage.PYTHON: load_python_grammar(),
        SupportedLanguage.GO: load_go_grammar(),
    }


def is_language_loaded(language: SupportedLanguage) -> bool:
    """Check if a language grammar is loaded.

    Args:
        language: Language to check

    Returns:
        True if grammar is loaded
    """
    return language in _loaded_languages


def get_loaded_languages() -> set[SupportedLanguage]:
    """Get set of loaded languages.

    Returns:
        Set of successfully loaded languages
    """
    return _loaded_languages.copy()


def ensure_language_loaded(language: SupportedLanguage) -> bool:
    """Ensure a language grammar is loaded.

    Loads the grammar if not already loaded.

    Args:
        language: Language to ensure is loaded

    Returns:
        True if language is available
    """
    if language in _loaded_languages:
        return True

    loaders = {
        SupportedLanguage.PYTHON: load_python_grammar,
        SupportedLanguage.GO: load_go_grammar,
    }

    loader = loaders.get(language)
    if loader is None:
        return False

    result = loader()
    return result is not None
