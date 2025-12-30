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
#   status      Check CI status
#   setup       Setup development environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

activate_venv() {
    if [ -d "$PROJECT_ROOT/venv" ]; then
        source "$PROJECT_ROOT/venv/bin/activate"
        print_info "Activated virtual environment"
    else
        print_warn "No virtual environment found at $PROJECT_ROOT/venv"
    fi
}

# ============================================================================
# COMMANDS
# ============================================================================

cmd_test() {
    print_header "Running Tests"
    cd "$PROJECT_ROOT"
    activate_venv

    local test_args="${1:-}"

    if [ -n "$test_args" ]; then
        print_info "Running specific test: $test_args"
        python -m pytest "$test_args" -v --tb=short
    else
        print_info "Running all tests (excluding slow/integration)..."
        python -m pytest tests/ -v --tb=short -m "not slow and not integration"
    fi

    print_success "Tests completed"
}

cmd_lint() {
    print_header "Running Linting"
    cd "$PROJECT_ROOT"
    activate_venv

    local has_errors=0

    # Python - flake8
    print_info "Checking Python with flake8..."
    if flake8 backend/ core/ models/ subscription/ \
        --max-line-length=120 \
        --exclude=__pycache__,venv,.git \
        --count --statistics; then
        print_success "flake8: No issues"
    else
        print_warn "flake8: Issues found (see above)"
        has_errors=1
    fi

    # Python - black (check only)
    echo ""
    print_info "Checking Python formatting with black..."
    if black --check --diff backend/ core/ models/ subscription/ 2>/dev/null; then
        print_success "black: Code is formatted correctly"
    else
        print_warn "black: Formatting issues found"
        print_info "Run 'black backend/ core/ models/ subscription/' to fix"
        has_errors=1
    fi

    # Frontend - TypeScript
    echo ""
    print_info "Checking frontend TypeScript..."
    cd "$PROJECT_ROOT/web_ui/frontend"
    if npx tsc --noEmit 2>/dev/null; then
        print_success "TypeScript: No type errors"
    else
        print_warn "TypeScript: Type errors found"
        has_errors=1
    fi

    # Frontend - ESLint
    echo ""
    print_info "Checking frontend with ESLint..."
    if npm run lint 2>/dev/null; then
        print_success "ESLint: No issues"
    else
        print_warn "ESLint: Issues found"
        has_errors=1
    fi

    cd "$PROJECT_ROOT"

    if [ $has_errors -eq 0 ]; then
        echo ""
        print_success "All lint checks passed!"
    else
        echo ""
        print_warn "Some lint checks had issues (see above)"
    fi

    return $has_errors
}

cmd_build() {
    print_header "Building Frontend"
    cd "$PROJECT_ROOT/web_ui/frontend"

    print_info "Installing dependencies..."
    npm ci

    print_info "Building production bundle..."
    npm run build

    print_success "Frontend build completed"
    print_info "Output: $PROJECT_ROOT/web_ui/frontend/dist/"

    cd "$PROJECT_ROOT"
}

cmd_start() {
    print_header "Starting Development Server"
    cd "$PROJECT_ROOT"
    activate_venv

    print_info "Starting TermiVoxed..."
    print_info "Press Ctrl+C to stop"
    echo ""

    python main.py
}

cmd_check() {
    print_header "Running All Checks"

    local has_errors=0

    # Lint
    if ! cmd_lint; then
        has_errors=1
    fi

    # Test
    echo ""
    if ! cmd_test; then
        has_errors=1
    fi

    # Build
    echo ""
    if ! cmd_build; then
        has_errors=1
    fi

    echo ""
    if [ $has_errors -eq 0 ]; then
        print_success "════════════════════════════════════════════════════════════"
        print_success "All checks passed! Ready to push."
        print_success "════════════════════════════════════════════════════════════"
    else
        print_error "════════════════════════════════════════════════════════════"
        print_error "Some checks failed. Please fix before pushing."
        print_error "════════════════════════════════════════════════════════════"
        exit 1
    fi
}

cmd_push() {
    print_header "Push with Checks"
    cd "$PROJECT_ROOT"

    local branch=$(git branch --show-current)
    print_info "Current branch: $branch"

    # Run checks first
    print_info "Running pre-push checks..."
    if ! cmd_check; then
        print_error "Pre-push checks failed. Aborting push."
        exit 1
    fi

    # Push
    echo ""
    print_info "Pushing to origin/$branch..."
    git push origin "$branch"

    # Wait and show CI status
    echo ""
    print_info "Waiting for CI to start..."
    sleep 5

    cmd_status
}

cmd_status() {
    print_header "CI/CD Status"
    cd "$PROJECT_ROOT"

    print_info "Recent workflow runs:"
    echo ""
    gh run list --limit 5

    echo ""
    print_info "To watch a specific run: gh run watch <run-id>"
    print_info "To view failed logs: gh run view <run-id> --log-failed"
}

cmd_setup() {
    print_header "Setting Up Development Environment"
    cd "$PROJECT_ROOT"

    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating Python virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi

    # Activate and install dependencies
    source venv/bin/activate

    print_info "Upgrading pip..."
    pip install --upgrade pip

    print_info "Installing Python dependencies..."
    pip install -r requirements.txt

    print_info "Installing development tools..."
    pip install pytest pytest-asyncio pytest-cov pytest-mock httpx black flake8 mypy

    # Frontend dependencies
    print_info "Installing frontend dependencies..."
    cd "$PROJECT_ROOT/web_ui/frontend"
    npm ci

    cd "$PROJECT_ROOT"

    echo ""
    print_success "════════════════════════════════════════════════════════════"
    print_success "Development environment setup complete!"
    print_success "════════════════════════════════════════════════════════════"
    echo ""
    print_info "To activate the environment: source venv/bin/activate"
    print_info "To start developing: ./scripts/dev.sh start"
}

cmd_help() {
    echo ""
    echo -e "${CYAN}TermiVoxed Development Helper${NC}"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  test [path]   Run tests (optionally specify test path)"
    echo "  lint          Run all linting checks"
    echo "  build         Build frontend for production"
    echo "  start         Start development server"
    echo "  check         Run all checks (lint + test + build)"
    echo "  push          Run checks and push current branch"
    echo "  status        Show CI/CD status"
    echo "  setup         Setup development environment"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 test                     # Run all tests"
    echo "  $0 test tests/test_tts.py   # Run specific test file"
    echo "  $0 lint                     # Check code style"
    echo "  $0 check                    # Full pre-push check"
    echo "  $0 push                     # Check and push"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        test)    cmd_test "$@" ;;
        lint)    cmd_lint ;;
        build)   cmd_build ;;
        start)   cmd_start ;;
        check)   cmd_check ;;
        push)    cmd_push ;;
        status)  cmd_status ;;
        setup)   cmd_setup ;;
        help|--help|-h) cmd_help ;;
        *)
            print_error "Unknown command: $command"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
