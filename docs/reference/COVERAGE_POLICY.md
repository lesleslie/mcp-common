# Coverage Policy

This document outlines the code coverage policy for the project.

## Goals

- Maintain and improve test coverage incrementally
- Target 42% overall coverage milestone
- Focus on meaningful tests that verify functionality

## Guidelines

- Always improve coverage when working on projects with low pytest coverage
- Run `uv run pytest --cov=<package_name> --cov-report=term-missing` to check current status
- Aim for 2-5% improvement per development session
- Add focused tests that cover uncovered lines effectively