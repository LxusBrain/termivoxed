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
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/release_$(date +%Y%m%d_%H%M%S).log"
PYPROJECT="$PROJECT_ROOT/pyproject.toml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

ensure_log_dir() {
    mkdir -p "$LOG_DIR"
}

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_line="[$timestamp] [$level] $message"

    # Write to log file (without colors)
    echo "$log_line" >> "$LOG_FILE"

    # Print to console (with colors)
    case "$level" in
        INFO)    echo -e "${BLUE}$log_line${NC}" ;;
        SUCCESS) echo -e "${GREEN}$log_line${NC}" ;;
        WARN)    echo -e "${YELLOW}$log_line${NC}" ;;
        ERROR)   echo -e "${RED}$log_line${NC}" ;;
        *)       echo "$log_line" ;;
    esac
}

log_info() { log "INFO" "$1"; }
log_success() { log "SUCCESS" "$1"; }
log_warn() { log "WARN" "$1"; }
log_error() { log "ERROR" "$1"; }

log_step() {
    local step="$1"
    local message="$2"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Step $step: $message${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    log "STEP" "Step $step: $message"
}

# ============================================================================
# ERROR HANDLING
# ============================================================================

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        log_error "════════════════════════════════════════════════════════════"
        log_error "Script failed with exit code $exit_code"
        log_error "Check log file: $LOG_FILE"
        log_error "════════════════════════════════════════════════════════════"
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
    log_info "Checking required dependencies..."

    local deps=("git" "gh" "python3" "npm")
    local missing=()

    for dep in "${deps[@]}"; do
        if command -v "$dep" &> /dev/null; then
            log_success "  ✓ Found: $dep ($(command -v "$dep"))"
        else
            log_error "  ✗ Missing: $dep"
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        die "Missing required dependencies: ${missing[*]}"
    fi

    # Check gh authentication
    log_info "Checking GitHub CLI authentication..."
    if gh auth status &> /dev/null; then
        local gh_user=$(gh api user --jq '.login' 2>/dev/null || echo "unknown")
        log_success "  ✓ Authenticated as: $gh_user"
    else
        die "GitHub CLI not authenticated. Run: gh auth login"
    fi
}

check_git_status() {
    log_info "Checking Git status..."

    # Check if we're in a git repo
    if ! git rev-parse --git-dir &> /dev/null; then
        die "Not in a Git repository"
    fi

    # Check current branch
    local branch=$(git branch --show-current)
    log_info "  Current branch: $branch"

    if [ "$branch" != "main" ] && [ "$branch" != "master" ]; then
        log_warn "  You are not on main/master branch"
        read -p "  Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            die "Aborted: Please switch to main branch"
        fi
    fi

    # Check for uncommitted changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_warn "  You have uncommitted changes:"
        git status --short | head -10
        read -p "  Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            die "Aborted: Please commit or stash changes"
        fi
    else
        log_success "  ✓ Working tree is clean"
    fi

    # Check if up to date with remote
    log_info "  Fetching latest from remote..."
    git fetch origin &> /dev/null || log_warn "  Could not fetch from remote"

    local local_hash=$(git rev-parse HEAD)
    local remote_hash=$(git rev-parse origin/main 2>/dev/null || echo "unknown")

    if [ "$local_hash" != "$remote_hash" ] && [ "$remote_hash" != "unknown" ]; then
        log_warn "  Local branch differs from remote"
        log_info "  Local:  $local_hash"
        log_info "  Remote: $remote_hash"
    else
        log_success "  ✓ Up to date with remote"
    fi
}

get_current_version() {
    if [ ! -f "$PYPROJECT" ]; then
        die "pyproject.toml not found at $PYPROJECT"
    fi
    grep -E '^version = ' "$PYPROJECT" | sed 's/version = "\(.*\)"/\1/'
}

bump_version() {
    local current="$1"
    local bump_type="$2"

    # Validate current version format
    if ! [[ "$current" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        die "Invalid version format: $current (expected X.Y.Z)"
    fi

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

    # Activate virtual environment if exists
    if [ -d "$PROJECT_ROOT/venv" ]; then
        log_info "  Activating virtual environment..."
        source "$PROJECT_ROOT/venv/bin/activate"
    fi

    # Run Python tests
    log_info "  Running Python tests..."
    if python -m pytest tests/ -v --tb=short -m "not slow and not integration" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Python tests passed"
    else
        die "Python tests failed"
    fi

    # Run frontend type check
    log_info "  Checking frontend TypeScript..."
    cd "$PROJECT_ROOT/web_ui/frontend"
    if npx tsc --noEmit 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Frontend type check passed"
    else
        log_warn "  TypeScript errors found (non-blocking)"
    fi

    # Build frontend
    log_info "  Building frontend..."
    if npm run build 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Frontend build passed"
    else
        die "Frontend build failed"
    fi

    cd "$PROJECT_ROOT"
}

update_version_file() {
    local new_version="$1"

    log_info "Updating version to $new_version in pyproject.toml..."

    # Create backup
    cp "$PYPROJECT" "$PYPROJECT.bak"

    # Update version
    if sed -i.tmp "s/^version = \".*\"/version = \"$new_version\"/" "$PYPROJECT"; then
        rm -f "$PYPROJECT.tmp"
        log_success "  ✓ Updated pyproject.toml"

        # Verify change
        local verify=$(get_current_version)
        if [ "$verify" = "$new_version" ]; then
            log_success "  ✓ Verified: version is now $verify"
            rm -f "$PYPROJECT.bak"
        else
            log_error "  Version verification failed (expected $new_version, got $verify)"
            mv "$PYPROJECT.bak" "$PYPROJECT"
            die "Version update failed"
        fi
    else
        mv "$PYPROJECT.bak" "$PYPROJECT"
        die "Failed to update version in pyproject.toml"
    fi
}

create_git_tag() {
    local version="$1"
    local tag="v$version"

    log_info "Creating Git commit and tag..."

    # Stage version file
    git add "$PYPROJECT"

    # Commit
    log_info "  Committing version bump..."
    if git commit -m "Bump version to $version

🤖 Generated with [Claude Code](https://claude.com/claude-code)" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Committed version bump"
    else
        die "Failed to commit version change"
    fi

    # Check if tag already exists
    if git rev-parse "$tag" &> /dev/null; then
        die "Tag $tag already exists. Please use a different version."
    fi

    # Create annotated tag
    log_info "  Creating tag: $tag..."
    if git tag -a "$tag" -m "Release $tag

Automated release created by release.sh" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Created tag: $tag"
    else
        die "Failed to create tag"
    fi
}

push_to_remote() {
    local tag="$1"

    log_info "Pushing to remote..."

    # Push commit
    log_info "  Pushing commit to origin/main..."
    if git push origin main 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Pushed commit"
    else
        die "Failed to push commit"
    fi

    # Push tag (this triggers the release workflow)
    log_info "  Pushing tag $tag (triggers release workflow)..."
    if git push origin "$tag" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "  ✓ Pushed tag"
    else
        die "Failed to push tag"
    fi
}

monitor_release() {
    local tag="$1"

    log_info "Monitoring release workflow..."
    log_info "  Waiting for workflow to start..."

    # Wait for workflow to appear
    sleep 10

    # Find the release workflow run
    local run_id=""
    local attempts=0
    local max_attempts=6

    while [ -z "$run_id" ] && [ $attempts -lt $max_attempts ]; do
        run_id=$(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || echo "")
        if [ -z "$run_id" ]; then
            attempts=$((attempts + 1))
            log_info "  Waiting for workflow to appear (attempt $attempts/$max_attempts)..."
            sleep 10
        fi
    done

    if [ -z "$run_id" ]; then
        log_warn "Could not find release workflow run"
        log_info "Check manually: gh run list --workflow=release.yml"
        return 0
    fi

    log_info "  Found workflow run: $run_id"
    log_info "  Watching progress (this may take several minutes)..."
    echo ""

    # Watch the workflow
    if gh run watch "$run_id" --exit-status; then
        log_success "  ✓ Release workflow completed successfully!"
    else
        local status=$(gh run view "$run_id" --json conclusion --jq '.conclusion')
        log_error "  Release workflow failed with status: $status"
        log_info "  View logs: gh run view $run_id --log-failed"
        return 1
    fi

    # Show release info
    echo ""
    log_info "Release artifacts:"
    gh release view "$tag" --json assets --jq '.assets[].name' 2>/dev/null | while read -r asset; do
        log_info "  - $asset"
    done
}

# ============================================================================
# MAIN SCRIPT
# ============================================================================

show_banner() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                            ║${NC}"
    echo -e "${CYAN}║          TermiVoxed Release Automation Script              ║${NC}"
    echo -e "${CYAN}║          Author: Santhosh T / LxusBrain Technologies       ║${NC}"
    echo -e "${CYAN}║                                                            ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_usage() {
    echo "Usage: $0 [major|minor|patch]"
    echo ""
    echo "Bump types:"
    echo "  major   - Breaking changes (1.0.0 → 2.0.0)"
    echo "  minor   - New features (1.0.0 → 1.1.0)"
    echo "  patch   - Bug fixes (1.0.0 → 1.0.1)"
    echo ""
    echo "Examples:"
    echo "  $0 patch    # 1.0.0 → 1.0.1"
    echo "  $0 minor    # 1.0.0 → 1.1.0"
    echo "  $0 major    # 1.0.0 → 2.0.0"
}

main() {
    local bump_type="${1:-}"

    show_banner

    # Validate arguments
    if [ -z "$bump_type" ]; then
        show_usage
        exit 1
    fi

    if [[ ! "$bump_type" =~ ^(major|minor|patch)$ ]]; then
        log_error "Invalid bump type: $bump_type"
        show_usage
        exit 1
    fi

    # Setup
    ensure_log_dir
    log_info "Starting release process..."
    log_info "Log file: $LOG_FILE"

    # Change to project root
    cd "$PROJECT_ROOT"

    # Step 1: Pre-flight checks
    log_step "1/7" "Pre-flight checks"
    check_dependencies
    check_git_status

    # Step 2: Get version info
    log_step "2/7" "Determining version"
    local current_version=$(get_current_version)
    local new_version=$(bump_version "$current_version" "$bump_type")

    log_info "Current version: $current_version"
    log_info "New version:     $new_version"
    log_info "Bump type:       $bump_type"

    # Confirm
    echo ""
    read -p "Proceed with release v$new_version? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        die "Release aborted by user"
    fi

    # Step 3: Run tests
    log_step "3/7" "Running tests"
    run_tests

    # Step 4: Update version
    log_step "4/7" "Updating version"
    update_version_file "$new_version"

    # Step 5: Create Git tag
    log_step "5/7" "Creating Git tag"
    create_git_tag "$new_version"

    # Step 6: Push to remote
    log_step "6/7" "Pushing to remote"
    push_to_remote "v$new_version"

    # Step 7: Monitor release
    log_step "7/7" "Monitoring release"
    monitor_release "v$new_version"

    # Done!
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}║          Release v$new_version completed successfully!          ║${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log_info "View release: gh release view v$new_version"
    log_info "Download URL: https://github.com/san-gitlogin/lxb-termivoxed/releases/tag/v$new_version"
    echo ""
}

# Run main function
main "$@"
