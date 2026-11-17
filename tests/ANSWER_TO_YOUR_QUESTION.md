# ✅ Answer: Where Test Output is Stored

## Your Question:
> "Where will the output be stored for the test scenarios?"

## The Answer:

Test outputs are stored in **TWO distinct places**:

---

## 1️⃣ Manual Test Tracking (You Update This)

**File:** `tests/test_cases.xlsx`

**What it contains:**
- 58 test case specifications across 6 sheets
- Status column where you manually enter: Pending → In Progress → Pass/Fail
- Priority levels, descriptions, expected results

**How it works:**
```
You run: pytest test_router_sample.py -v
         ↓
Results appear in terminal + output/ folder
         ↓
You open test_cases.xlsx
         ↓
Update Status column manually:
  TC001: Pending → Pass ✓
  TC002: Pending → Fail ✗
         ↓
Save file to version control
```

**Location:** `C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\test_cases.xlsx`

---

## 2️⃣ Automated Test Results (Pytest Generates These)

**Folder:** `tests/output/`

When you run `pytest test_router_sample.py -v`, these files are automatically created:

### A. Test Report
```
output/reports/test_report.html

What: Pretty HTML report showing all test results
Open in: Browser
Shows:
  ✓ Passed tests (green)
  ✗ Failed tests (red)
  ⏭️  Skipped tests
  Execution time
  Failure stack traces
```

### B. Code Coverage Report
```
output/coverage/html/index.html

What: Interactive coverage analysis
Open in: Browser
Shows:
  Coverage percentage by file
  Line-by-line coverage
  Which branches tested
  Missing coverage
```

### C. Execution Logs
```
output/logs/test_execution.log

What: Detailed test execution log
Open in: Text editor or terminal
Shows:
  Timestamp of each test
  Test name and result
  Debug information
  Error messages
```

### D. CI/CD Reports
```
output/reports/junit.xml
output/coverage/coverage.xml

What: Machine-readable formats
Use for: Jenkins, GitLab CI, GitHub Actions, SonarQube
Format: XML
```

---

## 📊 Storage Comparison

| Aspect | Manual (Excel) | Automated (output/) |
|--------|---|---|
| **File** | test_cases.xlsx | output/reports/*.html |
| **Format** | Excel | HTML/XML/Text |
| **Created by** | You (manually) | Pytest (automatic) |
| **Updated when** | After test run | During test run |
| **Purpose** | Track status | View detailed results |
| **Persistence** | Version control | Temporary (can delete) |
| **Audience** | Project team | Developers/CI systems |

---

## 🚀 Complete Workflow

```
Step 1: Write Test Code
   └─ test_router_sample.py

Step 2: Run Tests
   Command: pytest test_router_sample.py -v
   
Step 3: Outputs Created (Automatic)
   ├─ Console: Summary (10 passed, 1 failed)
   ├─ output/reports/test_report.html
   ├─ output/coverage/html/index.html
   ├─ output/logs/test_execution.log
   └─ output/reports/junit.xml

Step 4: View Results
   Option A: Browser - open output/reports/test_report.html
   Option B: Terminal - cat output/logs/test_execution.log
   Option C: Text - view console output

Step 5: Manual Tracking (Optional)
   └─ Open test_cases.xlsx
   └─ Update Status column with Pass/Fail
   └─ Save to version control
```

---

## 📁 Directory Layout

```
tests/
│
├── test_cases.xlsx                 ← YOU UPDATE THIS (manual status)
├── test_router_sample.py           ← Test code
│
└── output/                         ← PYTEST CREATES THESE (automatic)
    ├── reports/
    │   ├── test_report.html        ← Open in browser
    │   ├── junit.xml               ← For CI/CD
    │   └── summary.txt
    │
    ├── coverage/
    │   ├── html/index.html         ← Open in browser
    │   ├── coverage.xml            ← For SonarQube
    │   └── coverage.txt
    │
    └── logs/
        ├── test_execution.log      ← View in terminal
        └── failures.log
```

---

## 🎯 Quick Commands

```bash
# Run tests (creates output/)
cd tests
pytest test_router_sample.py -v

# View test results in browser
start output\reports\test_report.html

# View code coverage in browser
start output\coverage\html\index.html

# View execution logs
cat output\logs\test_execution.log

# Update manual tracking
open test_cases.xlsx
# Update Status column
# Save file
```

---

## 📍 File Locations

### Absolute Paths
```
C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\test_cases.xlsx
C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\output\reports\test_report.html
C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\output\coverage\html\index.html
C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\tests\output\logs\test_execution.log
```

### Relative Paths (from tests/ folder)
```
.\test_cases.xlsx
.\output\reports\test_report.html
.\output\coverage\html\index.html
.\output\logs\test_execution.log
```

---

## 💡 Key Points

✅ **Manual Tracking:** test_cases.xlsx (you update it)
✅ **Automated Results:** output/ folder (pytest creates it)
✅ **Reports:** HTML format (open in browser)
✅ **CI/CD:** XML format (junit.xml, coverage.xml)
✅ **Logs:** Text format (view in terminal)
✅ **Permanent:** Keep test_cases.xlsx in version control
✅ **Temporary:** Delete output/ folder anytime (regenerated)

---

## Example: After Running Tests

```bash
$ pytest test_router_sample.py -v

test_router_sample.py::TestCostEstimation::test_basic_cost_calculation PASSED
test_router_sample.py::TestCostEstimation::test_cost_with_zero_input_tokens PASSED
test_router_sample.py::TestHardFilter::test_quality_floor_filter PASSED
...
=============== 10 passed, 1 failed in 2.45s ===============
```

**Then these files exist:**

✓ `output/reports/test_report.html` - View full results in browser
✓ `output/coverage/html/index.html` - View coverage in browser
✓ `output/logs/test_execution.log` - View detailed logs
✓ `output/reports/junit.xml` - For CI/CD systems

**Then you optionally:**

Edit `test_cases.xlsx` → Update Status column → Save

---

## 📖 For More Details

- **QUICK_START.md** - 5 minute overview
- **OUTPUT_STRUCTURE.md** - Detailed storage explanation
- **README.md** - Complete test suite guide
- **INDEX.md** - Navigation guide

---

## ✨ Summary

**Test outputs are stored in:**

1. **test_cases.xlsx** - Manual tracking (you update it)
2. **output/** - Automated results (pytest creates it)

Everything is organized, documented, and ready to use!

---

**Created:** October 28, 2026  
**Status:** Complete ✓
