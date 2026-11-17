# Image Model Router - Test Suite

## Overview
Comprehensive test suite for the HALO Image Model Routing system. This test suite covers unit tests, integration tests, edge cases, and performance tests for all components of the routing engine.

## Test Documentation

### test_cases.xlsx
Complete test case documentation in Excel format with the following sheets:

1. **Test Cases Overview** (58 test cases)
   - Complete test case catalog with IDs, descriptions, steps, and expected results
   - Priority levels: Critical, High, Medium, Low
   - Categories: Router Core, Complexity, Benchmarks, Model Cards, Configuration, Integration, Edge Cases, Performance

2. **Unit Tests Details**
   - Detailed specifications for unit tests
   - Function-level test cases with code snippets
   - Input parameters and expected outputs
   - Mock requirements

3. **Integration Tests**
   - End-to-end test scenarios
   - Component interaction tests
   - Multi-step validation procedures

4. **Edge Cases & Errors**
   - Boundary conditions
   - Error handling scenarios
   - Recovery procedures

5. **Test Data**
   - Sample input data sets
   - Expected outcomes for each data set
   - Various document types and complexity levels

6. **Coverage Matrix**
   - Function-by-function coverage tracking
   - Current coverage percentages
   - Status indicators

## Test Categories

### Router Core (13 tests)
- Basic routing with different profiles (balanced, quality-focused, cost-optimized)
- Hard filtering (quality floor, context window, max output tokens, vision support)
- Cost estimation and accuracy
- Normalization (min-max scaling, inversion for cost/latency)
- Weighted scoring
- Top model selection and provider diversity

### Complexity Handling (11 tests)
- Complexity normalization (min, max, midpoint values)
- Out-of-bounds clamping
- Quality degradation based on complexity
- Weight adaptation for hard/easy documents
- None/null complexity handling

### Benchmarks Module (11 tests)
- Loading benchmark data for different document types (BOL, AWB, ACCORD)
- Model name slugification
- Accuracy to quality conversion
- Latency conversion (seconds to milliseconds)
- Missing data handling
- Unlimited capacity handling (context window, max output tokens)
- Invalid document type and missing file errors

### Model Cards (4 tests)
- Cost override application
- Fallback to benchmark costs
- Cost placeholder flagging
- Override clearing placeholder flag

### Configuration (6 tests)
- Default profile loading
- Custom profile loading
- Missing profile fallback
- Quality floor configuration
- Default expected output tokens
- Context headroom factor

### Integration Tests (5 tests)
- End-to-end routing for BOL, AWB documents
- Routing with complexity adjustment
- Multi-profile comparison
- Cost override integration
- Top 3 models with diversity constraint

### Edge Cases (8 tests)
- No eligible models error
- Single model candidate
- Zero/negative token counts
- Extreme token counts
- All models same score
- Missing/corrupted benchmark files
- Division by zero in normalization

### Performance Tests (3 tests)
- Benchmark loading time
- Routing execution time with many models
- Memory usage profiling

## Priority Breakdown
- **Critical**: 2 tests (Cost estimation accuracy, End-to-end routing)
- **High**: 35 tests (Core functionality, major features)
- **Medium**: 18 tests (Supporting features, configuration)
- **Low**: 3 tests (Optimization, nice-to-have)

## Test Coverage
Current overall coverage: **82%**

### Coverage by Component
- `router.py`: 85% (Good)
  - Core functions well covered
  - Need more edge case tests for _build_reasoning
- `benchmarks.py`: 85% (Good)
  - Need more tests for _find_column helper
- `model_cards.py`: 90% (Good)
- `complexity.py`: 95% (Good)
  - Need tests for describe_complexity
- `config_loader.py`: 70% (Partial)
  - Need more edge case tests

## Running Tests

### Prerequisites
```bash
pip install pytest pytest-cov openpyxl
```

### Unit Tests
```bash
pytest tests/unit/ -v
```

### Integration Tests
```bash
pytest tests/integration/ -v
```

### All Tests with Coverage
```bash
pytest tests/ --cov=cli_tools.tools.image_model_routing --cov-report=html
```

### Specific Test Categories
```bash
# Router tests
pytest tests/unit/test_router.py -v

# Benchmarks tests
pytest tests/unit/test_benchmarks.py -v

# Complexity tests
pytest tests/unit/test_complexity.py -v

# Edge cases
pytest tests/edge_cases/ -v

# Performance tests
pytest tests/performance/ -v
```

## Test Data
Test data files are located in `tests/data/`:
- Sample benchmark files for BOL, AWB, ACCORD
- Mock configuration files
- Test fixtures for various scenarios

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test functions: `test_<functionality>_<scenario>`
- Test classes: `Test<ComponentName>`

### Test Structure
```python
def test_function_name_scenario():
    """Test description."""
    # Arrange
    input_data = ...
    expected_output = ...
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```

### Fixtures
Use pytest fixtures for common setup:
```python
@pytest.fixture
def sample_model_card():
    """Create a sample ModelCard for testing."""
    return ModelCard(
        model_id="test-model",
        provider="TestProvider",
        supports_vision=True,
        quality=0.85,
        cost_per_1m_input_tokens_usd=3.0,
        cost_per_1m_output_tokens_usd=15.0,
        cost_is_placeholder=False,
        latency_ms=1500.0,
        context_window=128000,
        max_output_tokens=4096,
        reliability=0.98
    )
```

## Test Implementation Plan

### Phase 1: Unit Tests (Priority: High)
- [ ] TC001-TC013: Router core functionality
- [ ] TC015-TC025: Complexity handling
- [ ] TC031-TC036: Benchmarks module
- [ ] TC037-TC040: Model cards

### Phase 2: Integration Tests (Priority: High)
- [ ] TC026-TC028: Benchmark loading
- [ ] TC047-TC050: End-to-end routing
- [ ] TC041-TC046: Configuration

### Phase 3: Edge Cases (Priority: Medium)
- [ ] TC014: No eligible models
- [ ] TC029-TC030: Invalid inputs
- [ ] TC051-TC055: Boundary conditions

### Phase 4: Performance Tests (Priority: Low)
- [ ] TC056: Benchmark loading performance
- [ ] TC057: Routing performance
- [ ] TC058: Memory profiling

## Continuous Integration
Tests should be run on:
- Every commit (unit tests)
- Pull requests (all tests)
- Nightly builds (all tests + performance)

### CI Configuration Example (.github/workflows/tests.yml)
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=cli_tools --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Test Maintenance
- Review test coverage monthly
- Update tests when features change
- Add regression tests for bugs
- Remove obsolete tests
- Keep test data synchronized with production data structure

## Contributing
When adding new features:
1. Write tests first (TDD approach)
2. Ensure new code has >80% coverage
3. Update test documentation
4. Add integration tests for new workflows
5. Update coverage matrix

## Contact
For questions about testing:
- Review test_cases.xlsx for detailed specifications
- Check existing test implementations in tests/ directory
- Refer to inline comments in test files

## License
Same as parent project
