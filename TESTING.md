# Testing Guide

This repository uses `pytest` for automated testing. Tests are categorized into three levels:

1.  **Unit Tests (`testing/unit/`)**: Fast, isolated tests for logic (parsers, formatters, routers). No external dependencies.
2.  **Integration Tests (`testing/integration/`)**: Tests that verify interaction between components, often using mocks for external APIs (Square, Gemini, etc.).
3.  **End-to-End Tests (`testing/e2e/`)**: Full workflow tests that may hit live APIs or the local filesystem. These require environment variables and may cost money (API credits).

## Prerequisites

Ensure you have `pytest` installed in your environment:

```bash
uv pip install pytest pytest-mock
```

## Running Tests

### Run All Tests
```bash
uv run --project ~/.claude/skills pytest testing/
```

### Run Only Unit Tests (Fast)
```bash
uv run --project ~/.claude/skills pytest testing/unit/
```

### Run E2E Tests (Slow, requires API keys)
```bash
uv run --project ~/.claude/skills pytest testing/e2e/
```

## Writing Tests

### Unit Tests
- Import the module you want to test.
- Use `sys.path.append` or the `conftest.py` path manipulation if needed to reach `scripts/` directories.
- Mock any file I/O or system calls.

### Integration/E2E Tests
- Use `pytest.mark.skipif` to skip tests if API keys are missing.
- Use `tmp_path` fixture for file operations to avoid cluttering the repo.

## Directory Structure

```
testing/
├── conftest.py            # Shared configuration & fixtures
├── unit/                  # Fast logic tests
├── integration/           # Mocked interaction tests
├── e2e/                   # Live system tests
└── resources/             # Test artifacts (images, logs)
```
