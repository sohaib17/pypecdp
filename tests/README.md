# pypecdp Tests

Comprehensive unit test suite for pypecdp using pytest, pytest-asyncio, and mocking.

## Overview

These tests validate pypecdp functionality **without launching Chrome** using:
- **pytest** - Test framework
- **pytest-asyncio** - Async test support
- **unittest.mock** - Mocking to avoid external dependencies
- **pytest-cov** - Code coverage reporting

## Installation

Install test dependencies:

```bash
# From pypecdp root directory
pip install -e ".[test]"

# Or install dev dependencies (includes test + linting)
pip install -e ".[dev]"
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/test_config.py
pytest tests/test_elem.py
```

### Run specific test
```bash
pytest tests/test_config.py::TestConfig::test_default_config
```

### Run with coverage report
```bash
pytest --cov=src/pypecdp --cov-report=html
```

### Run verbose
```bash
pytest -v
```

### Run with output
```bash
pytest -s
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and pytest config
├── test_browser.py       # Browser class tests
├── test_config.py        # Config class tests
├── test_elem.py          # Elem and Position class tests
├── test_tab.py           # Tab class tests
└── test_util.py          # Utility function tests
```

## Test Coverage

Current test coverage focuses on:

### Config Class (`test_config.py`)
- Default and custom configuration
- User data directory management
- Command-line argument building
- Environment variable handling
- Default argument filtering

### Elem Class (`test_elem.py`)
- Position calculation (center, width, height)
- Element interaction methods (click, type, scroll)
- Attribute and text extraction
- Query selector methods
- Parent element access and DOM tree traversal
- `@tab_attached` decorator integration
- ReferenceError handling

### Tab Class (`test_tab.py`)
- Tab creation and initialization
- Command sending with session management
- Event handler registration and dispatch
- Navigation and evaluation
- DOM element finding and waiting
- Tab lifecycle (attach, close)

### Browser Class (`test_browser.py`)
- Browser initialization
- Configuration handling
- Tab creation and navigation
- Event handling
- Context manager support
- Process ID and first_tab properties

### Util Module (`test_util.py`)
- `@tab_attached` decorator behavior
- ReferenceError raising on None session
- Session not found error catching
- Function metadata preservation

## Mocking Strategy

Tests use mocking to avoid launching Chrome:

### Mock Process
```python
proc = Mock()
proc.pid = 12345
proc.wait = AsyncMock()
```

### Mock Tab
```python
tab = Mock()
tab.session_id = "session-123"
tab.send = AsyncMock()
```

### Mock Elem
```python
node = Mock()
node.node_id = 1
node.backend_node_id = 2
elem = Elem(tab=mock_tab, node=node)
```

## Writing New Tests

### Example async test
```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_my_async_function():
    mock_obj = Mock()
    mock_obj.async_method = AsyncMock(return_value="result")
    
    result = await my_function(mock_obj)
    
    assert result == "result"
    mock_obj.async_method.assert_awaited_once()
```

### Example fixture
```python
@pytest.fixture
def my_fixture():
    """Create test data."""
    return {"key": "value"}

def test_with_fixture(my_fixture):
    assert my_fixture["key"] == "value"
```

## Integration Tests

These unit tests use mocking and don't launch Chrome. For integration tests that actually launch Chrome, see the `example/` directory.

## CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Install test dependencies
  run: pip install -e ".[test]"

- name: Run tests
  run: pytest

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Coverage Goals

- **Target**: 80%+ coverage for non-CDP code
- **Excluded**: `src/pypecdp/cdp/*` (auto-generated)
- **Reports**: HTML coverage report in `htmlcov/`

## Troubleshooting

### Coverage warnings about module not imported
```bash
# Make sure pypecdp is installed in editable mode
pip install -e .

# Then run tests
pytest
```

**Note:** The coverage tool tracks the installed `pypecdp` module, not `src/pypecdp`. The package must be installed in editable mode for coverage to work.

### Import errors
```bash
# Install pypecdp in editable mode
pip install -e .
```

### Async test failures
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio
```

### Missing coverage
```bash
# Install pytest-cov
pip install pytest-cov
```

### "No data was collected" warning
This happens when pypecdp is not installed. Run:
```bash
pip install -e .
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Use mocking to avoid Chrome dependency
3. Aim for 80%+ coverage
4. Run tests before committing: `pytest`
5. Check coverage: `pytest --cov`
