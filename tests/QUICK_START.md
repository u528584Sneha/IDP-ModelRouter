# Quick Start: Test Output Storage

## TL;DR - Two Types of Storage

### 1️⃣ Manual Tracking in Excel
**File:** `test_cases.xlsx`
- You update the "Status" column manually
- Tracks: Pending → In Progress → Pass/Fail
- Where: Rows 2+ in "Test Cases Overview" sheet

### 2️⃣ Automated Results from Pytest
**Folder:** `output/`
- Generated automatically when tests run
- Where: `output/reports/`, `output/coverage/`, `output/logs/`

---

## Quick Command Reference

### Run Tests
```bash
cd tests
pytest test_router_sample.py -v
```

### View Results

**Option 1: HTML Report (Pretty)**
```bash
# Windows
start output\reports\test_report.html

# Mac
open output/reports/test_report.html

# Linux
firefox output/reports/test_report.html
```

**Option 2: Coverage Report**
```bash
start output\coverage\html\index.html
```

**Option 3: Logs (Debugging)**
```bash
cat output/logs/test_execution.log
```

---

## Output Storage Map

```
After: pytest test_router_sample.py -v

tests/output/
│
├── reports/
│   ├── test_report.html          ← Open this for test results
│   └── junit.xml                 ← For CI/CD systems
│
├── coverage/
│   ├── html/index.html           ← Open this for coverage
│   └── coverage.xml              ← For SonarQube
│
└── logs/
    └── test_execution.log        ← For debugging

+ Also update:
  test_cases.xlsx                 ← Manual status tracking
```

---

## Step-by-Step Example

### Step 1: Run Tests
```bash
cd tests
pytest test_router_sample.py -v
```

✅ Creates:
- `output/reports/test_report.html`
- `output/coverage/html/`
- `output/logs/test_execution.log`

### Step 2: View Test Report
```bash
start output\reports\test_report.html
```

Shows:
- ✓ Passed tests (green)
- ✗ Failed tests (red)
- Execution time
- Failure details

### Step 3: View Coverage Report
```bash
start output\coverage\html\index.html
```

Shows:
- Coverage percentage
- Which lines tested
- Missing coverage

### Step 4: Update Excel File
```bash
# Open test_cases.xlsx
# Update Status column:
# TC001: Pending → Pass
# TC002: Pending → Fail (add note)
# TC003: Pending → Pass
```

---

## File Locations Reference

| Need | Command | Result |
|------|---------|--------|
| **See test results** | `start output\reports\test_report.html` | HTML report |
| **See code coverage** | `start output\coverage\html\index.html` | Interactive coverage |
| **See test logs** | `cat output/logs/test_execution.log` | Debug info |
| **See XML (CI/CD)** | `cat output/reports/junit.xml` | XML format |
| **Update test status** | `open test_cases.xlsx` | Excel file |

---

## What Gets Generated Where

### When You Run: `pytest tests/test_router_sample.py -v`

| Output | Location | What It Shows |
|--------|----------|---------------|
| 📊 HTML Report | `output/reports/test_report.html` | Pretty test results |
| 📈 Coverage | `output/coverage/html/index.html` | Code coverage % |
| 📝 Logs | `output/logs/test_execution.log` | Test execution log |
| 🤖 CI/CD XML | `output/reports/junit.xml` | For Jenkins/GitHub |
| 📋 Coverage XML | `output/coverage/coverage.xml` | For SonarQube |

---

## Example: Full Workflow

```bash
# 1. Run tests
cd C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests
pytest test_router_sample.py -v

# 2. See summary in terminal (immediate)
# ✓ 10 passed, 1 failed in 2.45s

# 3. View detailed report
start output\reports\test_report.html
# Shows: Which tests passed/failed with details

# 4. Check coverage
start output\coverage\html\index.html
# Shows: 82% coverage, which lines untested

# 5. Open test_cases.xlsx and update:
# TC008: Pending → Pass ✓
# TC009: Pending → Fail ✗
# Add notes about failures

# 6. Save and commit
git add test_cases.xlsx
git commit -m "Updated test results"
```

---

## Paths Explained

### Absolute Paths
```
C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\
├── test_cases.xlsx                    (you update this)
├── output\                            (pytest creates these)
│   ├── reports\test_report.html
│   ├── coverage\html\index.html
│   └── logs\test_execution.log
└── test_router_sample.py              (test code)
```

### Relative Paths (from tests/ folder)
```bash
cd tests

# View results
start output\reports\test_report.html

# View coverage
start output\coverage\html\index.html

# View logs
cat output\logs\test_execution.log
```

---

## Common Questions

**Q: Where do test results go?**
A: `output/reports/test_report.html` (open in browser)

**Q: How do I track test status?**
A: Update `test_cases.xlsx` Status column manually

**Q: Where are the logs?**
A: `output/logs/test_execution.log`

**Q: How do I see coverage?**
A: `output/coverage/html/index.html` (open in browser)

**Q: For CI/CD integration?**
A: Use `output/reports/junit.xml` (JUnit format)

**Q: Are results deleted after?**
A: No, they persist until you manually delete `output/` folder

---

## One-Liner Cheat Sheet

```bash
# Run tests
pytest tests/test_router_sample.py -v

# Open test report
start tests\output\reports\test_report.html

# Open coverage
start tests\output\coverage\html\index.html

# See logs
cat tests\output\logs\test_execution.log

# Update tracking
open tests\test_cases.xlsx
```

---

**Document:** tests/QUICK_START.md  
**Updated:** October 28, 2026
