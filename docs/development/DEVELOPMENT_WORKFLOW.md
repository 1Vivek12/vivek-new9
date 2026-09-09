# Development Workflow & Engineering Standards

## 1. Branching & Git Strategy

1. **Main Branch Protection**: Direct commits to `main` are strictly prohibited.
2. **Feature Branches**: All work occurs on descriptive feature branches (e.g., `feature/project-foundation`).
3. **No Automatic Merges**: Merges to `main` require code review, pass of all test suites, linting, type checks, and security scans.

---

## 2. Pre-Commit Quality Checklist

Before committing any code, developers must run the following checks:
```bash
# 1. Format and Linting
ruff check backend/
ruff format --check backend/

# 2. Static Type Checks
mypy backend/app

# 3. Unit & Integration Tests
pytest -v backend/tests

# 4. Frontend Type Checking & Build
cd frontend
npm run build

# 5. Git Diff Review (No secrets, no hardcoded tenant names in business logic)
git diff
```

---

## 3. Dependency Management Rules

1. **Pin Versions**: All dependencies in `pyproject.toml` and `package.json` must be pinned to major/minor versions.
2. **License Vetting**: Only permissive licenses (MIT, Apache 2.0, BSD) are allowed. AGPL, GPL, and proprietary licenses without legal review are prohibited.
3. **Minimal Dependencies**: Never introduce a third-party library if the functionality can be cleanly implemented in under 50 lines of standard library code.
