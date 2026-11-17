# Test Output Storage Structure

## Overview

Test outputs are stored in **two places** with different purposes:

### 1. **test_cases.xlsx** - Manual Test Documentation
Where you track test execution status manually

### 2. **output/** folder - Automated Test Results
Where pytest stores execution results, reports, and coverage data

---

## Directory Structure

```
tests/
├── test_cases.xlsx              ← Manual test tracking (you update this)
├── pytest.ini                   ← Pytest configuration
├── README.md                    ← Test documentation
├── TEST_SUMMARY.md
├── OUTPUT_STRUCTURE.md          ← This file
├── generate_test_cases.py
├── test_router_sample.py
│
└── output/                      ← Automated test results (pytest generates these)
    ├── reports/
    │   ├── test_report.html     ← Pretty HTML test report
    │   ├── junit.xml            ← XML for CI/CD systems
    │   └── summary.txt          ← Quick summary
    │
    ├── coverage/
    │   ├── html/                ← Interactive coverage report
    │   │   ├── index.html       ← Open this in browser
    │   │   ├── status.json
    │   │   └── ...
    │   ├── coverage.xml         ← For CI/CD/SonarQube
    │   └── coverage.txt         ← Terminal output
    │
    ├── logs/
    │   ├── test_execution.log   ← Detailed test logs
    │   └── failures.log         ← Only failed test logs
    │
    ├── screenshots/             ← For UI test failures
    │   └── *.png
    │
    └── artifacts/               ← Test data artifacts
        ├── test_data.json
        └── debug_outputs/
```

---

## What Gets Stored Where

### Manual Tracking in Excel

**File:** `test_cases.xlsx` → **Sheet: "Test Cases Overview"**

| Column | Stored Information |
|--------|-------------------|
| Test Case ID | TC001, TC002, etc. |
| Status | Pending → In Progress → Pass/Fail |
| Notes | Any manual observations |
| Assignee | Who's running the test |

**You manually update this** as you execute tests.

Example:
```
Status: Pending  →  Status: Pass  (update by hand)
```

### Automated Results in output/ Folder

Generated when you run: `pytest tests/test_router_sample.py`

#### A. HTML Test Report
**Location:** `tests/output/reports/test_report.html`

```html
Test Report
- Test execution summary (passed/failed/skipped)
- Individual test results with timing
- Stack traces for failures
- Execution date and duration
- Browser-viewable interface
```

**Open in browser:**
```bash
# Windows
start tests\output\reports\test_report.html

# Mac
open tests/output/reports/test_report.html

# Linux
firefox tests/output/reports/test_report.html
```

#### B. Coverage Report
**Location:** `tests/output/coverage/html/index.html`

Interactive coverage analysis showing:
- Line-by-line coverage
- Which functions/branches are tested
- Coverage percentage per file
- Missing test coverage

**Open in browser:**
```bash
start tests\output\coverage\html\index.html
```

#### C. XML Reports (for CI/CD)
**Locations:**
- `tests/output/reports/junit.xml` - Standard JUnit format
- `tests/output/coverage/coverage.xml` - Coverage in XML

Used by:
- Jenkins, GitLab CI, GitHub Actions
- SonarQube (code quality)
- Coverage tracking tools

#### D. Test Logs
**Location:** `tests/output/logs/test_execution.log`

Contains:
- Timestamp of each test
- Test name and result
- Assertion details
- Debug information
- Error messages

Example:
```
2026-10-28 18:50:15 INFO Test: test_cost_estimation_accuracy PASSED
2026-10-28 18:50:16 DEBUG Input: input_tokens=1000, output_tokens=500
2026-10-28 18:50:16 DEBUG Expected: 0.0105, Actual: 0.0105
2026-10-28 18:50:17 ERROR Test: test_no_eligible_models_error FAILED
2026-10-28 18:50:17 ERROR Expected NoEligibleModelError but got ValueError
```

---

## Test Execution Flow

```
1. Run Tests
   $ pytest tests/test_router_sample.py -v

2. Pytest Execution
   ├─ Run test functions
   ├─ Capture results
   └─ Generate outputs

3. Outputs Created
   ├─ output/reports/test_report.html      ✓ Generated
   ├─ output/coverage/html/                ✓ Generated
   ├─ output/reports/junit.xml             ✓ Generated
   ├─ output/logs/test_execution.log       ✓ Generated
   └─ Terminal output (console)            ✓ Displayed

4. Manual Tracking
   └─ You update test_cases.xlsx Status column
      (Copy results from HTML report)
```

---

## How to Access Results

### Immediate Viewing (After Test Run)

**Terminal Output:**
```bash
$ pytest tests/test_router_sample.py -v

# Output in terminal:
test_router_sample.py::TestCostEstimation::test_basic_cost_calculation PASSED
test_router_sample.py::TestCostEstimation::test_cost_with_zero_input_tokens PASSED
test_router_sample.py::TestHardFilter::test_quality_floor_filter PASSED
...
```

### Detailed Reports

**HTML Test Report (Interactive):**
```bash
# Open this file in your browser
tests/output/reports/test_report.html
```

Displays:
- ✓ Passed tests (green)
- ✗ Failed tests (red)
- Test execution time
- Stack traces for failures

**Coverage Report (Interactive):**
```bash
# Open this file in your browser
tests/output/coverage/html/index.html
```

Displays:
- Coverage percentage by file
- Line-by-line coverage
- Branch coverage
- Missing coverage areas

### Log Files (Detailed Debugging)

```bash
# View execution logs
cat tests/output/logs/test_execution.log

# View only failures
grep "FAILED\|ERROR" tests/output/logs/test_execution.log
```

---

## Complete Command Examples

### Run All Tests with Full Output

```bash
cd tests
pytest test_router_sample.py -v
```

Generates:
- `output/reports/test_report.html`
- `output/coverage/html/`
- `output/logs/test_execution.log`

### Run Specific Test Category

```bash
# Only cost estimation tests
pytest test_router_sample.py::TestCostEstimation -v

# Only hard filter tests
pytest test_router_sample.py::TestHardFilter -v

# Only edge case tests
pytest test_router_sample.py::TestEdgeCases -v
```

### Run with Specific Output Options

```bash
# Verbose output with slow tests
pytest test_router_sample.py -v --durations=10

# Stop on first failure
pytest test_router_sample.py -x

# Run failed tests only
pytest test_router_sample.py --lf

# Show local variables in failures
pytest test_router_sample.py -l
```

### Generate Only Coverage Report

```bash
pytest test_router_sample.py --cov=cli_tools.tools.image_model_routing --cov-report=html
```

### Generate Only JUnit Report (for CI/CD)

```bash
pytest test_router_sample.py --junitxml=output/reports/junit.xml
```

---

## Updating test_cases.xlsx with Results

### Process:

1. **Run tests and get results:**
   ```bash
   pytest tests/test_router_sample.py -v
   ```

2. **Open HTML report:**
   ```bash
   start tests\output\reports\test_report.html
   ```

3. **Open test_cases.xlsx:**
   ```bash
   start tests\test_cases.xlsx
   ```

4. **Update Status Column:**
   | Test ID | Previous Status | New Status | Notes |
   |---------|-----------------|-----------|-------|
   | TC008 | Pending | Pass | Cost calculation accurate |
   | TC009 | Pending | Pass | Min-max scaling correct |
   | TC010 | Pending | Fail | Cost inversion not working |

5. **Add Notes:**
   - What passed
   - What failed
   - Any issues encountered

6. **Save updated file**

---

## Automated Reporting (CI/CD Integration)

### JUnit XML Format

**File:** `output/reports/junit.xml`

Used by Jenkins, GitLab CI, GitHub Actions:

```xml
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
    <testsuite name="test_router_sample.py" tests="10" failures="1" skipped="0">
        <testcase classname="TestCostEstimation" name="test_basic_cost_calculation" time="0.125">
        </testcase>
        <testcase classname="TestHardFilter" name="test_quality_floor_filter" time="0.234">
            <failure message="assertion failed">
                AssertionError: assert 2 == 3
            </failure>
        </testcase>
    </testsuite>
</testsuites>
```

### Coverage XML Format

**File:** `output/coverage/coverage.xml`

Used by SonarQube, Codecov:

```xml
<?xml version="1.0" ?>
<coverage version="5.5">
    <sources>
        <source>/path/to/cli_tools</source>
    </sources>
    <packages>
        <package name="image_model_routing" line-rate="0.82">
            <classes>
                <class name="router.py" line-rate="0.85">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
```

---

## Storage Summary

| Output Type | File Location | Format | Usage |
|------------|---------------|--------|-------|
| **Manual Test Status** | test_cases.xlsx | Excel | Track test execution by hand |
| **Test Results** | output/reports/test_report.html | HTML | View pretty test results |
| **Code Coverage** | output/coverage/html/index.html | HTML | View code coverage details |
| **CI/CD Results** | output/reports/junit.xml | XML | Integrate with CI/CD |
| **Coverage Metrics** | output/coverage/coverage.xml | XML | Code quality tools |
| **Logs** | output/logs/test_execution.log | Text | Debug test failures |
| **Screenshots** | output/screenshots/ | PNG | UI test failures (when added) |
| **Artifacts** | output/artifacts/ | JSON/misc | Test data outputs |

---

## Retention Policy

### Keep in Version Control:
- ✓ `test_cases.xlsx` - Test documentation
- ✓ `pytest.ini` - Configuration
- ✓ `test_*.py` - Test code

### Ignore (in .gitignore):
- ✗ `output/` - Generated reports
- ✗ `.pytest_cache/` - Pytest cache
- ✗ `.coverage` - Coverage data
- ✗ `*.log` - Log files

### Local Cleanup:
```bash
# Clean test outputs
rm -rf tests/output

# Clean pytest cache
rm -rf tests/.pytest_cache

# Clean coverage cache
rm -rf tests/.coverage*

# Or use cleanup script
pytest --cache-clear
```

---

## Example: Complete Test Run Flow

```bash
# 1. Navigate to tests directory
cd tests

# 2. Run all tests
pytest test_router_sample.py -v

# 3. View results in terminal (immediate)
# ✓ PASSED
# ✗ FAILED
# Output: 10 passed, 1 failed

# 4. View detailed HTML report
start output/reports/test_report.html

# 5. View coverage report
start output/coverage/html/index.html

# 6. Check logs for debugging
cat output/logs/test_execution.log

# 7. Update test_cases.xlsx with results
# Open test_cases.xlsx
# Update Status column: Pending → Pass/Fail
# Add notes and save

# 8. Commit results (if needed)
git add test_cases.xlsx
git commit -m "Test results: 10 passed, 1 failed"
```

---

## Questions?

**Where is [X] stored?**

| What | Location | Format |
|-----|----------|--------|
| Test cases? | test_cases.xlsx | Excel |
| Test code? | test_router_sample.py | Python |
| Test results? | output/reports/test_report.html | HTML |
| Coverage? | output/coverage/html/index.html | HTML |
| Logs? | output/logs/test_execution.log | Text |
| For CI/CD? | output/reports/junit.xml | XML |

---

**Last Updated:** October 28, 2026  
**Relevant Test Files:** pytest.ini, test_router_sample.py, output/
