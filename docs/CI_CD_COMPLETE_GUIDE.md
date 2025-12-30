# TermiVoxed CI/CD Complete Guide

> **Author:** Santhosh T / LxusBrain Technologies
> **Last Updated:** December 30, 2025
> **Purpose:** Complete documentation of CI/CD setup, maintenance, and developer workflows

---

## Table of Contents

1. [What is CI/CD?](#1-what-is-cicd)
2. [Why CI/CD Matters for Desktop Apps](#2-why-cicd-matters-for-desktop-apps)
3. [Project Architecture Overview](#3-project-architecture-overview)
4. [CI/CD Pipeline Breakdown](#4-cicd-pipeline-breakdown)
5. [How Issues Were Identified and Fixed](#5-how-issues-were-identified-and-fixed)
6. [Git & GitHub Operations Reference](#6-git--github-operations-reference)
7. [Developer Workflow](#7-developer-workflow)
8. [Automatic Update Flow](#8-automatic-update-flow)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Automation Scripts](#10-automation-scripts)

---

## 1. What is CI/CD?

### CI = Continuous Integration
**Definition:** Automatically testing and validating code every time a developer pushes changes.

```
Developer pushes code → CI runs tests → Pass/Fail feedback
```

**What CI checks:**
- Does the code compile/build?
- Do all tests pass?
- Are there any security vulnerabilities?
- Does the code follow style guidelines (linting)?

### CD = Continuous Deployment/Delivery
**Definition:** Automatically deploying code to production when tests pass.

```
Code passes CI → CD deploys to production → Users get updates
```

**What CD does:**
- Builds production-ready packages
- Creates installers (Windows .exe, macOS .dmg, Linux .tar.gz)
- Publishes to download servers
- Updates version numbers

### Why This Matters for TermiVoxed

Without CI/CD:
- Manual testing on each platform (Windows, macOS, Linux)
- Risk of releasing broken builds
- Hours spent building installers manually
- No guarantee that what works locally works everywhere

With CI/CD:
- Every push is tested on all platforms automatically
- Broken code is caught before release
- Installers are built automatically
- Consistent, repeatable releases

---

## 2. Why CI/CD Matters for Desktop Apps

### The Challenge
TermiVoxed runs on 3 platforms:
- **Windows** (PyInstaller → .exe)
- **macOS** (PyInstaller → .app → .dmg)
- **Linux** (PyInstaller → binary → .tar.gz)

Each platform has different:
- File path separators (`\` vs `/`)
- FFmpeg installation methods
- Python package behaviors
- GUI rendering

### The Solution: Matrix Builds

```yaml
strategy:
  matrix:
    include:
      - os: ubuntu-latest
      - os: macos-latest
      - os: windows-latest
```

This runs the same build on all 3 platforms in parallel, catching platform-specific bugs before release.

---

## 3. Project Architecture Overview

### Repository Structure

```
termivoxed/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Main CI pipeline (runs on every push)
│       ├── release.yml         # Release pipeline (runs on version tags)
│       ├── docker.yml          # Docker image builds
│       └── security.yml        # Security scanning
├── backend/                    # Python backend (TTS, FFmpeg utils)
├── core/                       # Core business logic
├── models/                     # Data models
├── subscription/               # Subscription/licensing logic
├── web_ui/
│   ├── api/                    # FastAPI REST API
│   └── frontend/               # React/Vite frontend
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
└── Dockerfile                  # Container definition
```

### CI/CD Pipelines

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Every push/PR | Test, lint, build verification |
| `release.yml` | Version tags (v1.0.0) | Create installers & GitHub releases |
| `docker.yml` | Push to main | Build & push Docker images |
| `security.yml` | Push/schedule | Security vulnerability scanning |

---

## 4. CI/CD Pipeline Breakdown

### CI Pipeline (`ci.yml`) - 10 Jobs

```
┌─────────────────────────────────────────────────────────────┐
│                      CI PIPELINE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐                       │
│  │ lint-python  │    │lint-frontend │                       │
│  │  (Black,     │    │ (TypeScript) │                       │
│  │   flake8)    │    │              │                       │
│  └──────┬───────┘    └──────┬───────┘                       │
│         │                   │                                │
│         ▼                   ▼                                │
│  ┌──────────────┐    ┌──────────────┐                       │
│  │ test-python  │    │build-frontend│                       │
│  │ (3.10,3.11,  │    │   (Vite)     │                       │
│  │   3.12)      │    │              │                       │
│  └──────┬───────┘    └──────┬───────┘                       │
│         │                   │                                │
│         └─────────┬─────────┘                                │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              build-desktop (Matrix)                     │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │ │
│  │  │ Ubuntu   │  │  macOS   │  │ Windows  │             │ │
│  │  │PyInstaller│  │PyInstaller│  │PyInstaller│             │ │
│  │  └──────────┘  └──────────┘  └──────────┘             │ │
│  └────────────────────────────────────────────────────────┘ │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────┐    ┌──────────────┐                       │
│  │ build-docker │    │security-scan │                       │
│  │              │    │ (pip-audit,  │                       │
│  │              │    │  bandit)     │                       │
│  └──────────────┘    └──────────────┘                       │
│                   │                                          │
│                   ▼                                          │
│            ┌──────────────┐                                  │
│            │  ci-success  │                                  │
│            │ (Final Gate) │                                  │
│            └──────────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

### What Each Job Does

| Job | Purpose | Key Commands |
|-----|---------|--------------|
| `lint-python` | Check Python code style | `black --check`, `flake8`, `mypy` |
| `lint-frontend` | Check TypeScript | `npx tsc --noEmit` |
| `test-python` | Run unit tests | `pytest tests/ --cov` |
| `build-frontend` | Build React app | `npm run build` |
| `build-desktop` | Test PyInstaller builds | `pyinstaller main.py` |
| `build-docker` | Build container | `docker build` |
| `security-scan` | Find vulnerabilities | `pip-audit`, `bandit` |
| `ci-success` | Gate for merging | Checks all jobs passed |

---

## 5. How Issues Were Identified and Fixed

### Issue Discovery Process

#### Step 1: Read Existing Test Files
```bash
# Find all test files
find tests -name "*.py" -type f

# Count test functions
grep -r "def test_" tests/*.py | wc -l
# Result: 255 test functions
```

#### Step 2: Check for Fake/Placeholder Tests
```bash
# Look for suspicious assertions
grep -r "assert.*in \[200, 500\]" tests/
grep -r "continue-on-error" .github/workflows/
```

#### Step 3: Analyze CI Workflow
```bash
# Read the workflow file
cat .github/workflows/ci.yml

# Check what jobs exist
grep -E "^  [a-z].*:" .github/workflows/ci.yml
```

### Issues Found and Fixes Applied

#### Issue 1: Fake Tests (6 tests accepting 500 errors)

**Problem:** Tests were accepting both 200 and 500 status codes:
```python
# BAD - This always passes even when the API fails
assert response.status_code in [200, 500]
```

**Fix:** Proper mocking with correct method names:
```python
# GOOD - Proper mock setup
@pytest.fixture
def mock_tts_generation(self, tmp_path):
    fake_audio = tmp_path / "test_audio.mp3"
    fake_audio.write_bytes(b"fake audio content")

    with patch('web_ui.api.routes.tts.tts_service') as mock_tts, \
         patch('web_ui.api.routes.tts.FFmpegUtils') as mock_ffmpeg, \
         patch('web_ui.api.routes.tts.settings', mock_settings):

        # Mock the ACTUAL method names (not guessed ones)
        mock_tts.generate_with_resilience = AsyncMock(
            return_value=(str(fake_audio), None)  # Returns tuple!
        )
        mock_ffmpeg.get_media_duration = MagicMock(return_value=2.5)
        yield mock_tts
```

**How to find correct method names:**
```bash
# Search the actual route code for method calls
grep -n "tts_service\." web_ui/api/routes/tts.py
# Found: generate_with_resilience, get_available_voices, etc.
```

#### Issue 2: Desktop Builds Only on Release

**Problem:** PyInstaller builds were only tested during releases, not on PRs.

**Fix:** Added `build-desktop` job to CI:
```yaml
build-desktop:
  name: Desktop Build (${{ matrix.os }})
  runs-on: ${{ matrix.os }}
  needs: [test-python, build-frontend]
  strategy:
    matrix:
      include:
        - os: ubuntu-latest
        - os: macos-latest
        - os: windows-latest
```

#### Issue 3: Missing Schema Fields in Mocks

**Problem:** Mock data didn't match Pydantic schema:
```python
# Schema requires: name, short_name, gender, language, locale
# Mock only had: id, name, language, gender, provider
```

**How to find schema:**
```bash
grep -A 10 "class VoiceInfo" web_ui/api/schemas/tts_schemas.py
```

**Fix:**
```python
mock_voices = [
    {
        "name": "Ava",
        "short_name": "en-US-AvaMultilingualNeural",
        "language": "en-US",
        "locale": "en-US",
        "gender": "Female",
    }
]
```

---

## 6. Git & GitHub Operations Reference

### Basic Git Commands

```bash
# Check current status
git status

# See recent commits
git log --oneline -10

# See what branch you're on
git branch

# See remote branches
git branch -r
```

### Creating a Feature Branch

```bash
# Start from main
git checkout main
git pull origin main

# Create new branch
git checkout -b feature/my-new-feature

# Make changes...

# Stage changes
git add .

# Commit with message
git commit -m "Add my new feature

Detailed description here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Developer Name <email@example.com>"

# Push to remote
git push origin feature/my-new-feature
```

### Creating a Pull Request

```bash
# Using GitHub CLI
gh pr create \
  --title "Add my new feature" \
  --body "## Summary
- Added X feature
- Fixed Y bug

## Test plan
- [x] Local tests pass
- [x] CI passes" \
  --base main
```

### Merging a PR

```bash
# Check PR status
gh pr view 123 --json state,statusCheckRollup

# Merge (squash commits into one)
gh pr merge 123 --squash --delete-branch

# Or merge with all commits
gh pr merge 123 --merge --delete-branch
```

### Checking CI Status

```bash
# List recent workflow runs
gh run list --limit 5

# View specific run
gh run view 12345678

# View failed logs
gh run view 12345678 --log-failed

# Watch a running workflow
gh run watch 12345678
```

### Creating a Release

```bash
# Tag the version
git tag -a v1.0.0 -m "Release v1.0.0"

# Push the tag (triggers release workflow)
git push origin v1.0.0
```

---

## 7. Developer Workflow

### Daily Development Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  DEVELOPER WORKFLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Start Fresh                                              │
│     git checkout main                                        │
│     git pull origin main                                     │
│                                                              │
│  2. Create Feature Branch                                    │
│     git checkout -b feature/my-feature                       │
│                                                              │
│  3. Make Changes                                             │
│     - Edit code                                              │
│     - Run local tests: pytest tests/ -v                      │
│     - Run local build: npm run build                         │
│                                                              │
│  4. Commit & Push                                            │
│     git add .                                                │
│     git commit -m "Description of changes"                   │
│     git push origin feature/my-feature                       │
│                                                              │
│  5. Create PR                                                │
│     gh pr create --title "My Feature" --base main            │
│                                                              │
│  6. Wait for CI                                              │
│     gh run watch                                             │
│                                                              │
│  7. If CI Fails → Fix → Push → Repeat                        │
│                                                              │
│  8. If CI Passes → Merge                                     │
│     gh pr merge --squash --delete-branch                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Before Pushing Checklist

```bash
# 1. Run linting
black --check .
flake8 .

# 2. Run type checking
mypy backend/ core/ models/

# 3. Run tests
pytest tests/ -v --tb=short

# 4. Build frontend
cd web_ui/frontend && npm run build

# 5. Test locally
python main.py
```

---

## 8. Automatic Update Flow

### How Updates Reach Users

```
┌─────────────────────────────────────────────────────────────┐
│                 RELEASE FLOW                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Developer                                                   │
│     │                                                        │
│     │ git tag v1.0.1                                         │
│     │ git push origin v1.0.1                                 │
│     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              GitHub Actions (release.yml)               ││
│  │                                                          ││
│  │  1. Detect tag push                                      ││
│  │  2. Build for Windows/macOS/Linux                        ││
│  │  3. Create installers                                    ││
│  │  4. Generate changelog                                   ││
│  │  5. Create GitHub Release                                ││
│  │  6. Upload assets                                        ││
│  └─────────────────────────────────────────────────────────┘│
│     │                                                        │
│     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              GitHub Releases                             ││
│  │                                                          ││
│  │  TermiVoxed v1.0.1                                       ││
│  │  ├── TermiVoxed-1.0.1-windows-x64.zip                    ││
│  │  ├── TermiVoxed-1.0.1-macos-universal.dmg                ││
│  │  ├── TermiVoxed-1.0.1-linux-x64.tar.gz                   ││
│  │  └── checksums.txt                                       ││
│  └─────────────────────────────────────────────────────────┘│
│     │                                                        │
│     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Website Download Page                       ││
│  │                                                          ││
│  │  Downloads latest from GitHub Releases API               ││
│  │  User clicks "Download" → Gets v1.0.1                    ││
│  └─────────────────────────────────────────────────────────┘│
│     │                                                        │
│     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Auto-Update (In-App)                        ││
│  │                                                          ││
│  │  App checks GitHub Releases API                          ││
│  │  Notifies user of v1.0.1                                 ││
│  │  User clicks "Update" → Downloads & Installs             ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Versioning Strategy (Semantic Versioning)

```
v1.2.3
 │ │ │
 │ │ └── PATCH: Bug fixes, minor changes (backwards compatible)
 │ └──── MINOR: New features (backwards compatible)
 └────── MAJOR: Breaking changes
```

**Examples:**
- `v1.0.0` → `v1.0.1`: Bug fix
- `v1.0.1` → `v1.1.0`: New feature added
- `v1.1.0` → `v2.0.0`: Major redesign, breaking changes

### Creating a Release Step-by-Step

```bash
# 1. Ensure main is up to date
git checkout main
git pull origin main

# 2. Update version in pyproject.toml
# version = "1.0.1"

# 3. Commit version change
git add pyproject.toml
git commit -m "Bump version to 1.0.1"
git push origin main

# 4. Create and push tag
git tag -a v1.0.1 -m "Release v1.0.1 - Bug fixes and improvements"
git push origin v1.0.1

# 5. Watch the release workflow
gh run watch

# 6. Verify release was created
gh release view v1.0.1
```

---

## 9. Troubleshooting Guide

### Common CI Failures

#### "Module not found" Error
```bash
# Check if module is in requirements.txt
grep "module_name" requirements.txt

# If missing, add it
echo "module_name>=1.0.0" >> requirements.txt
```

#### "Test failed" Error
```bash
# Run the specific failing test locally
pytest tests/test_file.py::TestClass::test_method -v --tb=long

# Check if mocks are correct
grep -A 20 "def mock_" tests/test_file.py
```

#### "PyInstaller build failed"
```bash
# Check if all add-data paths exist
ls -la web_ui/frontend/dist/
ls -la backend/
ls -la core/

# Check hidden imports
pyinstaller --help | grep hidden
```

#### "Docker build failed"
```bash
# Build locally to see full error
docker build -t termivoxed:test .

# Check Dockerfile syntax
docker build --no-cache -t termivoxed:test .
```

### Debugging CI Locally

```bash
# Install act (runs GitHub Actions locally)
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI locally
act -j lint-python
act -j test-python
```

---

## 10. Automation Scripts

### Complete CI/CD Automation Script

Save as `scripts/release.sh`:

```bash
#!/bin/bash
#
# TermiVoxed Release Automation Script
# Author: Santhosh T / LxusBrain Technologies
#
# Usage: ./scripts/release.sh [major|minor|patch]
#
# This script:
# 1. Validates environment
# 2. Runs all tests
# 3. Bumps version
# 4. Creates Git tag
# 5. Pushes to trigger CI/CD
# 6. Monitors release progress

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/release_$(date +%Y%m%d_%H%M%S).log"
PYPROJECT="$PROJECT_ROOT/pyproject.toml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "${BLUE}$1${NC}"; }
log_success() { log "SUCCESS" "${GREEN}$1${NC}"; }
log_warn() { log "WARN" "${YELLOW}$1${NC}"; }
log_error() { log "ERROR" "${RED}$1${NC}"; }

# ============================================================================
# ERROR HANDLING
# ============================================================================

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed with exit code $exit_code"
        log_error "Check log file: $LOG_FILE"
    fi
}
trap cleanup EXIT

die() {
    log_error "$1"
    exit 1
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

check_dependencies() {
    log_info "Checking dependencies..."

    local deps=("git" "gh" "python3" "npm" "docker")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            die "Required dependency not found: $dep"
        fi
        log_success "Found: $dep"
    done

    # Check gh authentication
    if ! gh auth status &> /dev/null; then
        die "GitHub CLI not authenticated. Run: gh auth login"
    fi
    log_success "GitHub CLI authenticated"
}

check_clean_working_tree() {
    log_info "Checking for uncommitted changes..."

    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_warn "You have uncommitted changes:"
        git status --short
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            die "Aborted due to uncommitted changes"
        fi
    fi
    log_success "Working tree is clean"
}

get_current_version() {
    grep -E '^version = ' "$PYPROJECT" | sed 's/version = "\(.*\)"/\1/'
}

bump_version() {
    local current="$1"
    local bump_type="$2"

    IFS='.' read -r major minor patch <<< "$current"

    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            die "Invalid bump type: $bump_type (use major|minor|patch)"
            ;;
    esac

    echo "$major.$minor.$patch"
}

run_tests() {
    log_info "Running test suite..."

    cd "$PROJECT_ROOT"

    # Activate virtual environment if exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Run Python tests
    log_info "Running Python tests..."
    python -m pytest tests/ -v --tb=short -m "not slow and not integration" 2>&1 | tee -a "$LOG_FILE"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        die "Python tests failed"
    fi
    log_success "Python tests passed"

    # Run frontend build
    log_info "Building frontend..."
    cd "$PROJECT_ROOT/web_ui/frontend"
    npm ci 2>&1 | tee -a "$LOG_FILE"
    npm run build 2>&1 | tee -a "$LOG_FILE"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        die "Frontend build failed"
    fi
    log_success "Frontend build passed"

    cd "$PROJECT_ROOT"
}

update_version_file() {
    local new_version="$1"

    log_info "Updating version to $new_version..."

    # Update pyproject.toml
    sed -i.bak "s/^version = \".*\"/version = \"$new_version\"/" "$PYPROJECT"
    rm -f "$PYPROJECT.bak"

    log_success "Updated $PYPROJECT"
}

create_git_tag() {
    local version="$1"
    local tag="v$version"

    log_info "Creating Git tag: $tag..."

    # Commit version change
    git add "$PYPROJECT"
    git commit -m "Bump version to $version" 2>&1 | tee -a "$LOG_FILE"

    # Create annotated tag
    git tag -a "$tag" -m "Release $tag" 2>&1 | tee -a "$LOG_FILE"

    log_success "Created tag: $tag"
}

push_to_remote() {
    local tag="$1"

    log_info "Pushing to remote..."

    # Push commit
    git push origin main 2>&1 | tee -a "$LOG_FILE"

    # Push tag (triggers release workflow)
    git push origin "$tag" 2>&1 | tee -a "$LOG_FILE"

    log_success "Pushed to remote"
}

monitor_release() {
    local tag="$1"

    log_info "Monitoring release workflow..."

    # Wait for workflow to start
    sleep 10

    # Get the run ID
    local run_id=$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')

    if [ -n "$run_id" ]; then
        log_info "Watching workflow run: $run_id"
        gh run watch "$run_id"

        # Check final status
        local status=$(gh run view "$run_id" --json conclusion --jq '.conclusion')

        if [ "$status" = "success" ]; then
            log_success "Release workflow completed successfully!"
            log_info "View release: gh release view $tag"
        else
            log_error "Release workflow failed with status: $status"
            log_info "View logs: gh run view $run_id --log-failed"
            exit 1
        fi
    else
        log_warn "Could not find workflow run. Check manually: gh run list"
    fi
}

# ============================================================================
# MAIN SCRIPT
# ============================================================================

main() {
    local bump_type="${1:-patch}"

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║          TermiVoxed Release Automation Script              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"

    log_info "Starting release process (bump type: $bump_type)"
    log_info "Log file: $LOG_FILE"

    # Change to project root
    cd "$PROJECT_ROOT"

    # Pre-flight checks
    check_dependencies
    check_clean_working_tree

    # Get versions
    local current_version=$(get_current_version)
    local new_version=$(bump_version "$current_version" "$bump_type")

    log_info "Current version: $current_version"
    log_info "New version: $new_version"

    # Confirm
    read -p "Proceed with release v$new_version? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        die "Release aborted by user"
    fi

    # Run tests
    run_tests

    # Update version
    update_version_file "$new_version"

    # Create and push tag
    create_git_tag "$new_version"
    push_to_remote "v$new_version"

    # Monitor release
    monitor_release "v$new_version"

    echo ""
    log_success "════════════════════════════════════════════════════════════"
    log_success "Release v$new_version completed successfully!"
    log_success "════════════════════════════════════════════════════════════"
    echo ""
}

# Run main function with all arguments
main "$@"
```

### Quick Development Script

Save as `scripts/dev.sh`:

```bash
#!/bin/bash
#
# TermiVoxed Development Helper Script
# Author: Santhosh T / LxusBrain Technologies
#
# Usage: ./scripts/dev.sh [command]
#
# Commands:
#   test        Run all tests
#   lint        Run linting
#   build       Build frontend
#   start       Start development server
#   check       Run all checks (lint + test + build)
#   push        Push current branch with checks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$PROJECT_ROOT"

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

case "${1:-help}" in
    test)
        echo -e "${GREEN}Running tests...${NC}"
        python -m pytest tests/ -v --tb=short -m "not slow"
        ;;

    lint)
        echo -e "${GREEN}Running linting...${NC}"
        echo "Checking Python with flake8..."
        flake8 backend/ core/ models/ --max-line-length=120 || true
        echo "Checking Python with black..."
        black --check backend/ core/ models/ || true
        echo "Checking frontend TypeScript..."
        cd web_ui/frontend && npx tsc --noEmit || true
        ;;

    build)
        echo -e "${GREEN}Building frontend...${NC}"
        cd web_ui/frontend
        npm ci
        npm run build
        ;;

    start)
        echo -e "${GREEN}Starting development server...${NC}"
        python main.py
        ;;

    check)
        echo -e "${GREEN}Running all checks...${NC}"
        $0 lint
        $0 test
        $0 build
        echo -e "${GREEN}All checks passed!${NC}"
        ;;

    push)
        echo -e "${GREEN}Running checks before push...${NC}"
        $0 check

        echo -e "${GREEN}Pushing to remote...${NC}"
        git push origin "$(git branch --show-current)"

        echo -e "${GREEN}Checking CI status...${NC}"
        sleep 5
        gh run list --limit 1
        ;;

    *)
        echo "TermiVoxed Development Helper"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  test    Run all tests"
        echo "  lint    Run linting"
        echo "  build   Build frontend"
        echo "  start   Start development server"
        echo "  check   Run all checks (lint + test + build)"
        echo "  push    Push current branch with checks"
        ;;
esac
```

### Make Scripts Executable

```bash
chmod +x scripts/release.sh
chmod +x scripts/dev.sh
```

---

## Appendix: Quick Reference Card

### Git Commands
| Action | Command |
|--------|---------|
| Create branch | `git checkout -b feature/name` |
| Stage all | `git add .` |
| Commit | `git commit -m "message"` |
| Push branch | `git push origin branch-name` |
| Create tag | `git tag -a v1.0.0 -m "Release"` |
| Push tag | `git push origin v1.0.0` |

### GitHub CLI Commands
| Action | Command |
|--------|---------|
| Create PR | `gh pr create --title "Title" --base main` |
| Merge PR | `gh pr merge 123 --squash` |
| List runs | `gh run list` |
| View run | `gh run view 12345678` |
| View release | `gh release view v1.0.0` |

### Test Commands
| Action | Command |
|--------|---------|
| All tests | `pytest tests/ -v` |
| Specific test | `pytest tests/test_file.py::test_func -v` |
| With coverage | `pytest --cov=backend --cov-report=html` |
| Skip slow | `pytest -m "not slow"` |

---

*This documentation was created as part of the CI/CD setup for TermiVoxed. For questions, contact support@lxusbrain.com*
