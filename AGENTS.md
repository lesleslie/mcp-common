# Repository Guidelines

## Project Structure & Module Organization

The production code lives under `mcp_common/` with subpackages for `adapters`, `config`, `security`, `ui`, and `cli`. Shared type hints ship via `py.typed`. Tests sit in `tests/`, mixing unit coverage (`test_http_client.py`, `test_config_*`) with scenario suites such as `tests/performance/`. Example servers for manual validation are under `examples/`, while architecture notes and implementation guides live in `docs/`. Build artifacts (`dist/`, `htmlcov/`) should stay out of PRs.

## Build, Test, and Development Commands

Install dev tooling with `uv pip install -e ".[dev]"` to match the lockfile. Key commands (run with `uv run`):

- `pytest --cov=mcp_common --cov-report=html` for the full test matrix.
- `ruff check` and `ruff format` for linting and auto-format.
- `mypy mcp_common tests` for static typing.
- `crackerjack --all` to execute the quality gate used in CI.
  Use `uv run pre-commit run --all-files` before pushing; hooks invoke bandit, codespell, and other safety nets.

## Coding Style & Naming Conventions

Follow PEP 8 with 4-space indents and 100-character line limits (configured in Ruff). Prefer explicit type hints and async-first patterns; new adapters should follow the Oneiric pattern with direct instantiation and lifecycle methods. Modules and packages use snake_case; classes stick to PascalCase; async tools keep `*_tool` or `_adapter` suffixes for clarity. Use global instance patterns with proper initialization in `main()`.

## Testing Guidelines

Pytest powers the suite; name files `test_*.py` and async tests `async def test_*`. Maintain ≥90% coverage, extending fixtures in `tests/conftest.py` when possible. For performance-sensitive features, mirror the structure in `tests/performance/`. Generate local coverage reports with `uv run pytest --cov ...` and ensure Rich UI assertions remain stable by using the helper utilities in `tests/test_ui_panels.py`.

## Commit & Pull Request Guidelines

Commit history follows Conventional Commits (e.g., `feat: add redis adapter`, `fix(test): adjust rate limit assertion`). Each PR should describe scope, link relevant issues, list new adapters/settings, and note test commands executed. Include screenshots or terminal captures when UI panels change. Verify pre-commit hooks pass before requesting review.

## Security & Configuration Notes

Guard secrets by using MCPBaseSettings with YAML + environment variables—never hard-code keys. Validate new regexes with `uv run python -m crackerjack.tools.validate_regex_patterns`. Update `docs/` when configuration surfaces change so downstream MCP servers stay in sync.
