# GEMINI.md

## Project Overview

`mcp-common` is a foundational Python library for building production-grade MCP (Model Context Protocol) servers. It is built on the Asynchronous Component Base (ACB) framework and provides a set of battle-tested patterns and components for building robust and scalable MCP servers.

**Main Technologies:**

- Python 3.13+
- Asynchronous Component Base (ACB)
- Optional: FastMCP (install separately)
- Pydantic
- Httpx

**Architecture:**

The library follows a modular and extensible architecture based on the ACB framework. It provides a set of core components (adapters) for common functionalities like HTTP client, rate limiting, and security. These components are designed to be easily integrated into any ACB-based application.

## Building and Running

**Installation:**

```bash
pip install -e ".[dev]"
```

**Running Tests:**

```bash
pytest
```

**Running Linters and Formatters:**

```bash
ruff format
ruff check
mypy mcp_common tests
```

## Development Conventions

- **Coding Style:** The project uses `ruff` for code formatting and linting. The configuration is defined in the `pyproject.toml` file.
- **Testing:** The project uses `pytest` for testing. The tests are located in the `tests` directory. The project aims for a high test coverage (90% minimum).
- **Type Hinting:** The project uses type hints and `mypy` for static type checking.
- **Dependency Management:** The project uses `hatch` for dependency management and task running.
