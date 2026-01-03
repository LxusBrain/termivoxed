# TermiVoxed Developer Guide

> **A Complete Beginner's Guide to Development, Git, CI/CD, and Releases**
>
> Keep this document handy for your daily development workflow.

---

## Table of Contents

1. [Understanding the Basics](#1-understanding-the-basics)
2. [Daily Development Workflow](#2-daily-development-workflow)
3. [Git Commands Cheat Sheet](#3-git-commands-cheat-sheet)
4. [Making Changes and Committing](#4-making-changes-and-committing)
5. [Understanding CI/CD](#5-understanding-cicd)
6. [Creating Releases](#6-creating-releases)
7. [Bug Management](#7-bug-management)
8. [Troubleshooting Common Issues](#8-troubleshooting-common-issues)
9. [Quick Reference Card](#9-quick-reference-card)

---

## 1. Understanding the Basics

### What is Git?

Git is a version control system that tracks changes to your code. Think of it as a "save game" system for your code - you can save checkpoints (commits) and go back to any previous state.

**Key Concepts:**

| Term | What it means |
|------|---------------|
| **Repository (Repo)** | Your project folder tracked by Git |
| **Commit** | A saved snapshot of your code at a point in time |
| **Branch** | A separate line of development (like a parallel universe) |
| **Push** | Upload your commits to GitHub (cloud) |
| **Pull** | Download latest changes from GitHub |
| **Clone** | Download a complete copy of a repository |
| **Merge** | Combine changes from one branch into another |
| **Tag** | A label for a specific commit (used for releases) |

### What is CI/CD?

**CI (Continuous Integration):** Every time you push code, automated tests run to check if your code works.

**CD (Continuous Deployment/Delivery):** When you create a release, the system automatically builds your app for Windows, macOS, and Linux.

### Your Repository Structure

```
termivoxed/
├── backend/           # Python backend (FastAPI)
├── core/              # Core video processing logic
├── web_ui/
│   ├── frontend/      # React frontend
│   └── api/           # API routes
├── build_tools/       # Build and release scripts
├── .github/
│   └── workflows/     # CI/CD automation
├── docs/              # Documentation
└── tests/             # Test files
```

---

## 2. Daily Development Workflow

### Starting Your Day

```bash
# 1. Open terminal and go to project folder
cd /Users/santhu/Projects/termivoxed

# 2. Check if there are any updates from GitHub
git pull origin main

# 3. Check current status
git status

# 4. Start the development server
./start.sh
```

### While Developing

1. **Make your changes** in the code editor (VS Code, etc.)
2. **Test locally** - make sure the app works
3. **Save frequently** - commit small, logical changes

### Ending Your Day

```bash
# 1. Check what you changed
git status

# 2. Add your changes
git add -A

# 3. Commit with a message
git commit -m "What you did today"

# 4. Push to GitHub
git push origin main
```

---

## 3. Git Commands Cheat Sheet

### Most Common Commands (Daily Use)

```bash
# Check what's changed
git status

# See detailed changes
git diff

# Add all changes to staging
git add -A

# Add specific file
git add path/to/file.py

# Commit changes
git commit -m "Your message here"

# Push to GitHub
git push origin main

# Pull latest from GitHub
git pull origin main

# See commit history
git log --oneline -10
```

### Understanding Git Status

When you run `git status`, you'll see:

```
Changes not staged for commit:    ← Modified files (red)
  modified:   backend/app.py

Untracked files:                  ← New files (red)
  new_feature.py

Changes to be committed:          ← Staged files (green, ready to commit)
  modified:   frontend/App.tsx
```

**Color meanings:**
- 🔴 **Red** = Not staged (won't be in next commit)
- 🟢 **Green** = Staged (will be in next commit)

### Commit Message Best Practices

```bash
# Format: type: short description
git commit -m "fix: Resolve login button not working"
git commit -m "feat: Add dark mode toggle"
git commit -m "docs: Update README"
git commit -m "refactor: Clean up timeline code"
git commit -m "test: Add unit tests for export"
```

**Types:**
- `feat:` = New feature
- `fix:` = Bug fix
- `docs:` = Documentation only
- `refactor:` = Code cleanup (no new feature)
- `test:` = Adding tests
- `chore:` = Maintenance tasks

---

## 4. Making Changes and Committing

### Step-by-Step: Making a Code Change

```bash
# Step 1: Make sure you have latest code
git pull origin main

# Step 2: Make your changes in the code editor
# ... edit files ...

# Step 3: Test your changes locally
./start.sh
# Open browser, test the feature

# Step 4: Check what you changed
git status
git diff

# Step 5: Stage your changes
git add -A

# Step 6: Commit with descriptive message
git commit -m "fix: Timeline segments now visible after moving video"

# Step 7: Push to GitHub
git push origin main

# Step 8: Check CI status (wait 2-5 minutes)
gh run list --limit 3
```

### What Happens After You Push

1. **GitHub receives your code**
2. **CI workflows start automatically:**
   - Security scan
   - Code linting (style check)
   - Type checking
   - Unit tests
   - Build verification
3. **You get results in ~5 minutes**

### Checking CI Status

```bash
# Quick check
gh run list --limit 5

# Detailed view of latest run
gh run view

# Watch a run in real-time
gh run watch
```

**Status meanings:**
- ✅ `success` = All good!
- ❌ `failure` = Something broke
- 🟡 `in_progress` = Still running
- ⏳ `queued` = Waiting to start

---

## 5. Understanding CI/CD

### What Runs on Every Push

| Workflow | What it does | Time |
|----------|--------------|------|
| **CI** | Tests, linting, type checks | ~6 min |
| **Security** | Scans for vulnerabilities | ~2 min |
| **Docker Build** | Verifies Docker image builds | ~2 min |

### What Runs on Release (Tags)

| Job | What it does |
|-----|--------------|
| **Prepare** | Determines version, generates changelog |
| **Test** | Runs all tests before building |
| **Build Windows** | Creates .exe installer |
| **Build macOS** | Creates .dmg installer |
| **Build Linux** | Creates .tar.gz archive |
| **Create Release** | Publishes to GitHub Releases |

### Reading CI Logs

If a workflow fails:

```bash
# View the failed run
gh run view <run-id>

# View specific job logs
gh run view <run-id> --log-failed
```

Or go to GitHub → Actions → Click the failed run → Click the red ❌ job.

---

## 6. Creating Releases

### When to Create a Release

- ✅ New feature is complete and tested
- ✅ Bug fixes ready for users
- ✅ All CI checks pass
- ✅ You've tested locally

### Version Numbering (Semantic Versioning)

```
v1.2.3
 │ │ └── PATCH: Bug fixes (no new features)
 │ └──── MINOR: New features (backwards compatible)
 └────── MAJOR: Breaking changes
```

**Examples:**
- `v1.0.0` → First stable release
- `v1.0.1` → Bug fix
- `v1.1.0` → New feature added
- `v2.0.0` → Major redesign/breaking changes
- `v1.0.0-beta.1` → Pre-release for testing

### Step-by-Step: Creating a Release

#### Method 1: Using Git Tags (Recommended)

```bash
# Step 1: Make sure all changes are committed and pushed
git status
# Should show: "nothing to commit, working tree clean"

# Step 2: Pull latest
git pull origin main

# Step 3: Check CI is passing
gh run list --limit 3
# All should show "success"

# Step 4: Create a version tag
git tag v1.0.0

# Step 5: Push the tag
git push origin v1.0.0

# Step 6: Monitor the release workflow
gh run list --limit 5
# You'll see "Release" workflow starting

# Step 7: Wait for completion (~10-15 minutes)
gh run watch
```

#### Method 2: Using GitHub UI

1. Go to: https://github.com/san-gitlogin/lxb-termivoxed
2. Click **Actions** tab
3. Click **Release** workflow on left
4. Click **Run workflow** button
5. Enter version (e.g., `1.0.0`)
6. Check "Mark as pre-release" if testing
7. Click **Run workflow**
8. Wait for completion

### After Release is Created

1. **Check GitHub Releases:**
   ```
   https://github.com/san-gitlogin/lxb-termivoxed/releases
   ```

2. **Share with testers:**
   - Send them the release URL
   - They download the appropriate file for their OS

3. **Verify downloads work:**
   - Download the installer yourself
   - Install and test basic functionality

### Creating a Test Release (Pre-release)

For testing before official release:

```bash
# Use beta/alpha/rc suffix
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

This creates a "pre-release" that's marked as testing.

---

## 7. Bug Management

### When You Find a Bug

1. **Document it** in GitHub Issues:
   - Go to: https://github.com/san-gitlogin/lxb-termivoxed/issues
   - Click "New Issue"
   - Describe: What happened? What did you expect? Steps to reproduce?

2. **Label it:**
   - `bug` - It's broken
   - `priority: high` - Urgent fix needed
   - `priority: low` - Can wait

### Fixing a Bug

```bash
# Step 1: Pull latest code
git pull origin main

# Step 2: Find and fix the bug
# ... edit code ...

# Step 3: Test the fix locally
./start.sh

# Step 4: Commit with reference to issue
git add -A
git commit -m "fix: Resolve timeline crash when moving segments

Fixes #42"

# Step 5: Push
git push origin main
```

The `Fixes #42` syntax automatically closes issue #42 when merged.

### Hotfix for Production

If there's a critical bug in a released version:

```bash
# 1. Fix the bug and push
git add -A
git commit -m "fix: Critical security patch for auth"
git push origin main

# 2. Wait for CI to pass
gh run watch

# 3. Create a patch release
git tag v1.0.1
git push origin v1.0.1

# 4. Notify users to update
```

---

## 8. Troubleshooting Common Issues

### Problem: "Push rejected"

```bash
# Error: Updates were rejected because the remote contains work you don't have

# Solution: Pull first, then push
git pull origin main
git push origin main
```

### Problem: "Merge conflict"

```bash
# Error: Automatic merge failed; fix conflicts and commit

# Solution:
# 1. Open the conflicted file(s)
# 2. Look for these markers:
<<<<<<< HEAD
your code here
=======
their code here
>>>>>>> main

# 3. Edit to keep what you want, remove the markers
# 4. Save the file
# 5. Stage and commit
git add -A
git commit -m "fix: Resolve merge conflict"
git push origin main
```

### Problem: "CI is failing"

```bash
# Check what failed
gh run view --log-failed

# Common fixes:
# 1. TypeScript error → Fix the type error in your code
# 2. Lint error → Run: npm run lint --fix (in frontend folder)
# 3. Test failure → Fix the failing test or update it
```

### Problem: "I committed something wrong"

```bash
# Undo last commit (keeps changes)
git reset --soft HEAD~1

# Now your changes are staged but not committed
# Fix them, then commit again
git commit -m "correct message"
```

### Problem: "I want to undo my changes"

```bash
# Discard all uncommitted changes (CAREFUL - cannot undo!)
git checkout .

# Discard changes in specific file
git checkout path/to/file.py
```

### Problem: "Release workflow failed"

```bash
# 1. Check what failed
gh run view <run-id> --log-failed

# 2. Fix the issue in code
git add -A
git commit -m "fix: Resolve release build issue"
git push origin main

# 3. Delete the failed tag
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# 4. Wait for CI to pass, then re-tag
gh run watch
git tag v1.0.0
git push origin v1.0.0
```

### Problem: "I need to see old code"

```bash
# See file at specific commit
git show <commit-hash>:path/to/file.py

# Temporarily go to old commit
git checkout <commit-hash>
# To come back:
git checkout main
```

---

## 9. Quick Reference Card

### Daily Commands
```bash
git pull origin main          # Get latest
git status                    # See changes
git add -A                    # Stage all
git commit -m "message"       # Commit
git push origin main          # Upload
gh run list --limit 3         # Check CI
```

### Release Commands
```bash
git tag v1.0.0               # Create tag
git push origin v1.0.0       # Trigger release
gh run watch                 # Monitor build
```

### Emergency Commands
```bash
git reset --soft HEAD~1      # Undo last commit
git checkout .               # Discard all changes
git stash                    # Temporarily save changes
git stash pop                # Restore stashed changes
```

### Check Status
```bash
git status                   # Local changes
git log --oneline -5         # Recent commits
gh run list --limit 5        # CI status
gh release list              # All releases
```

---

## Development Environment Setup

### First-Time Setup (Already Done)

```bash
# Clone repository
git clone https://github.com/san-gitlogin/lxb-termivoxed.git
cd lxb-termivoxed

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd web_ui/frontend
npm install
cd ../..

# Start development
./start.sh
```

### Running the App Locally

```bash
# Option 1: All-in-one script
./start.sh

# Option 2: Separate terminals
# Terminal 1 - Backend:
cd /Users/santhu/Projects/termivoxed
python -m uvicorn web_ui.api.main:app --reload --port 8000

# Terminal 2 - Frontend:
cd /Users/santhu/Projects/termivoxed/web_ui/frontend
npm run dev
```

### Building Locally (Optional)

```bash
# Build frontend for production
cd web_ui/frontend
npm run build

# Build desktop app (current platform only)
python build_tools/release.py --version 1.0.0 --skip-tests
```

---

## Important URLs

| Resource | URL |
|----------|-----|
| Repository | https://github.com/san-gitlogin/lxb-termivoxed |
| Actions (CI/CD) | https://github.com/san-gitlogin/lxb-termivoxed/actions |
| Releases | https://github.com/san-gitlogin/lxb-termivoxed/releases |
| Issues | https://github.com/san-gitlogin/lxb-termivoxed/issues |

---

## 10. Release Infrastructure (Deep Dive)

### How the Build System Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    TermiVoxed Build Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. You create a tag: git tag v1.2.3                             │
│                          ↓                                        │
│  2. GitHub detects tag push                                       │
│                          ↓                                        │
│  3. .github/workflows/release.yml triggers                        │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   PREPARE JOB                               │  │
│  │  - Extract version from tag (v1.2.3 → 1.2.3)              │  │
│  │  - Detect if pre-release (alpha/beta/rc)                   │  │
│  │  - Generate changelog from commits                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    TEST JOB                                 │  │
│  │  - Install Python & Node.js                                │  │
│  │  - Run linting (flake8, eslint)                            │  │
│  │  - Run type checks (mypy, tsc)                             │  │
│  │  - Run unit tests (pytest)                                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          ↓                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   WINDOWS   │  │    MACOS    │  │    LINUX    │  (parallel)  │
│  │    BUILD    │  │    BUILD    │  │    BUILD    │              │
│  │             │  │             │  │             │              │
│  │ PyInstaller │  │ PyInstaller │  │ PyInstaller │              │
│  │      ↓      │  │      ↓      │  │      ↓      │              │
│  │ Inno Setup  │  │    DMG      │  │   tar.gz    │              │
│  │      ↓      │  │             │  │             │              │
│  │  .exe       │  │   .dmg      │  │  .tar.gz    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                          ↓                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  RELEASE JOB                                │  │
│  │  - Collect all build artifacts                             │  │
│  │  - Generate checksums (SHA256)                             │  │
│  │  - Create GitHub Release                                    │  │
│  │  - Upload all installers & archives                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files in the Build System

| File | Purpose |
|------|---------|
| `.github/workflows/release.yml` | Main release automation (800+ lines) |
| `.github/workflows/ci.yml` | Continuous integration (runs on every push) |
| `build_tools/release.py` | Local build script (for testing locally) |
| `build_tools/desktop/launcher.py` | Desktop app entry point |
| `assets/icons/icon.icns` | macOS app icon |
| `assets/icons/icon.ico` | Windows app icon |
| `assets/icons/icon.png` | Linux app icon |

### Understanding PyInstaller

PyInstaller takes your Python code and bundles it into a standalone executable.

```
Your Code (Python files)
        ↓
PyInstaller analyzes imports
        ↓
Bundles Python interpreter + your code + dependencies
        ↓
Single executable (or folder with all files)
```

**Our configuration:**
```bash
pyinstaller --name TermiVoxed \
  --onedir \                           # Create folder with files (not single exe)
  --windowed \                         # Hide console window (GUI app)
  --icon assets/icons/icon.icns \      # App icon
  --add-data "web_ui/frontend/dist:web_ui/frontend/dist" \  # Include frontend
  --add-data "backend:backend" \       # Include backend code
  --hidden-import=uvicorn.logging \    # Manually include hidden imports
  build_tools/desktop/launcher.py      # Entry point (NOT main.py!)
```

**IMPORTANT:** The entry point is `build_tools/desktop/launcher.py`, not `main.py`!
- `launcher.py` = Starts FastAPI server, opens browser (desktop app)
- `main.py` = CLI application with interactive menus (console app)

### Platform-Specific Details

#### Windows Build
1. **PyInstaller** creates `dist/windows/TermiVoxed/` folder
2. **Inno Setup** creates `.exe` installer from that folder
3. Creates Start Menu shortcuts and optional desktop icon
4. Supports silent installation: `TermiVoxed-1.0.0-Setup.exe /SILENT`

#### macOS Build
1. **PyInstaller** creates `dist/macos/TermiVoxed/` folder
2. We create a `.app` bundle structure
3. **hdiutil** creates `.dmg` installer
4. **NOTE:** App is unsigned - users must right-click → Open on first launch

#### Linux Build
1. **PyInstaller** creates `dist/linux/TermiVoxed/` folder
2. **tar** creates `.tar.gz` archive
3. Users extract and run `./TermiVoxed/TermiVoxed`

### Signing and Notarization (Future)

Currently, apps are **unsigned**, which causes security warnings:

**macOS:**
```
"TermiVoxed" cannot be opened because Apple cannot check it for malware.
```
**Solution for users:** Right-click → Open → Open

**Windows:**
```
Windows protected your PC - Microsoft Defender SmartScreen prevented...
```
**Solution for users:** Click "More info" → Run anyway

**To remove these warnings (requires paid developer accounts):**

| Platform | Requirement | Cost |
|----------|-------------|------|
| macOS | Apple Developer Program | $99/year |
| Windows | EV Code Signing Certificate | $400-500/year |

---

## 11. Making Your App Public

### Distribution Options

#### Option 1: GitHub Releases (Current - Free)

**Pros:**
- Free
- Automatic with our CI/CD
- Direct download links
- Version history
- Changelogs

**Cons:**
- Unsigned apps (security warnings)
- Manual download (no auto-update)
- Not discoverable (users need direct link)

**Current URL:** https://github.com/san-gitlogin/lxb-termivoxed/releases

#### Option 2: Your Own Website (Recommended)

1. **Create a landing page** on lxusbrain.com with:
   - Product description
   - Screenshots/demo video
   - Download buttons linking to GitHub Releases
   - FAQ and support info

2. **Download links format:**
```
https://github.com/san-gitlogin/lxb-termivoxed/releases/latest/download/TermiVoxed-1.0.2-Setup.exe
https://github.com/san-gitlogin/lxb-termivoxed/releases/latest/download/TermiVoxed-1.0.2-macos.dmg
https://github.com/san-gitlogin/lxb-termivoxed/releases/latest/download/TermiVoxed-1.0.2-linux-x64.tar.gz
```

The `/latest/download/` URL automatically points to the most recent release!

#### Option 3: App Stores (Requires Investment)

| Store | Requirements | Cost | Time |
|-------|--------------|------|------|
| **Mac App Store** | Apple Developer ($99/yr), App Review | ~$99/yr | 1-2 weeks review |
| **Microsoft Store** | Microsoft Partner Center | Free (one-time $19) | 1-3 days review |
| **Homebrew** (macOS) | Open source, formula PR | Free | Community review |
| **Winget** (Windows) | Manifest PR to Microsoft | Free | Community review |
| **Flathub** (Linux) | Flatpak packaging | Free | Community review |

#### Option 4: Private Distribution (Beta Testing)

For testing with specific users before public release:

1. **Create a pre-release:**
   ```bash
   git tag v1.0.0-beta.1
   git push origin v1.0.0-beta.1
   ```

2. **Share private link with testers:**
   - The release is marked as "Pre-release"
   - Only people with the direct link can find it
   - Collect feedback via GitHub Issues or email

### Making the Repository Public

Your repo is currently **private**. To make releases publicly accessible:

**Option A: Keep Repo Private, Make Releases Public**
- Not directly possible on GitHub
- Workaround: Host files on your own server

**Option B: Make Entire Repo Public**
```bash
# Go to GitHub → Settings → General → Danger Zone
# Click "Change visibility" → Make public
```

**Before making public, ensure:**
- [ ] No secrets/API keys in code (use environment variables)
- [ ] No hardcoded passwords
- [ ] LICENSE file exists
- [ ] README is professional
- [ ] Remove any internal/sensitive comments

**Option C: Separate Public Release Repo**
1. Create new public repo: `lxusbrain/termivoxed-releases`
2. Use GitHub Actions to copy release assets there
3. Keep source code private

### Auto-Update Feature (Future)

To add automatic updates:

1. **Check for updates on app launch:**
   ```python
   response = requests.get(
       "https://api.github.com/repos/san-gitlogin/lxb-termivoxed/releases/latest"
   )
   latest_version = response.json()["tag_name"]
   if latest_version > current_version:
       show_update_dialog()
   ```

2. **Use electron-builder or similar** for automatic download+install

---

## 12. Testing Before Release

### Pre-Release Checklist

```markdown
## Before Creating a Release

### Code Quality
- [ ] All TypeScript errors fixed: `cd web_ui/frontend && npx tsc --noEmit`
- [ ] No Python linting issues: `flake8 backend core`
- [ ] Tests pass: `pytest tests/`

### Manual Testing
- [ ] App starts without errors
- [ ] Can create a new project
- [ ] Can add videos and segments
- [ ] TTS works (requires API keys)
- [ ] Export works (requires FFmpeg)

### Build Testing
- [ ] CI passes on main branch: `gh run list --limit 1`
- [ ] No secrets in code: `git grep -i "password\|secret\|api.key"`

### Version
- [ ] Version follows semantic versioning
- [ ] CHANGELOG updated (optional)
```

### Creating Test Releases

```bash
# Create a beta release (marked as pre-release)
git tag v1.1.0-beta.1
git push origin v1.1.0-beta.1

# Users can test, give feedback
# When ready for production:
git tag v1.1.0
git push origin v1.1.0
```

---

## Getting Help

1. **Check this guide first**
2. **Search GitHub Issues** for similar problems
3. **Check CI logs** for build errors
4. **Google the error message**

---

*Last updated: January 2026*
*Keep this guide handy in your Apple Notes!*
