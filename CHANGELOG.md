# Changelog

All notable changes to TermiVoxed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.0.5] - 2025-01-03

### Fixed
- **CRITICAL: Desktop app server startup failure** - App would open browser but show blank page
  - Fixed missing FastAPI/Starlette hidden imports for PyInstaller
  - Added comprehensive module imports: fastapi.middleware.cors, starlette.middleware.*, uvicorn submodules
  - Updated both macOS and Linux build configurations in release workflow
  - Updated Windows spec file with complete hidden imports list

---

## [1.0.4] - 2025-01-03

### Fixed
- **CRITICAL: Desktop app launch failure** - App was failing to start on Windows/macOS
  - Fixed entry point: Now uses desktop launcher instead of console CLI
  - Fixed console window: GUI mode enabled (no terminal window)
  - Fixed icon path: Installer and app now show TermiVoxed logo
  - Fixed frontend serving: React UI now properly served at root

### Added
- Frontend serving from FastAPI for bundled desktop app
- Error logging to `startup_error.log` for debugging launch issues
- Windows error dialog on startup failure for better user experience
- Additional uvicorn/fastapi hidden imports for PyInstaller compatibility

### Changed
- Improved PyInstaller spec file with correct data files and hidden imports
- Enhanced launcher with comprehensive error handling

---

## [1.0.3] - 2025-01-03

### Added
- **Ollama Setup Wizard**: New first-run setup experience for local AI
  - Automatic detection of Ollama installation
  - Platform-specific installation instructions (Windows, macOS, Linux)
  - One-click model downloads with progress tracking
  - Recommended models: llama3.2:3b, llama3.1:8b, llava:7b
- **User Consent Flow**: Privacy consent for local AI processing
- **Improved Model Management**: Download and manage Ollama models from Settings

### Changed
- Enhanced first-run experience for new users
- Improved AI provider status indicators in the header
- Better error messages for AI connectivity issues

### Fixed
- Fixed TypeScript type annotations in frontend components
- Fixed fetch headers type error in Ollama store
- Resolved AsyncIterator import error in backend

---

## [1.0.2] - 2025-01-01

### Added
- **Supply Chain Security**: Checksums for all release artifacts
- **FFmpeg Bundling**: FFmpeg now included in installers (no separate download needed)
- **Multi-platform Installers**: Windows (NSIS), macOS (DMG), Linux (tar.gz)

### Changed
- Improved installer size optimization
- Enhanced security headers in API responses
- Updated CORS configuration for better security

### Fixed
- Fixed Docker build configuration
- Resolved setup.bat issues on Windows
- Fixed path handling for bundled binaries

---

## [1.0.1] - 2024-12-28

### Added
- Rate limiting middleware for API protection
- Security headers middleware (X-Frame-Options, CSP, HSTS)
- Improved error handling across the application

### Changed
- Enhanced subscription tier enforcement
- Better voice selector component with favorites
- Improved timeline segment editing

### Fixed
- Fixed authentication token refresh flow
- Resolved video player sync issues
- Fixed segment timing calculations

---

## [1.0.0] - 2024-12-20

### Added
- **Initial Release**
- Multi-video project support
- AI script generation with Ollama, OpenAI, Claude, Gemini
- Text-to-speech with Edge TTS and Coqui TTS
- Voice cloning support (Coqui TTS)
- 320+ AI voices in 75+ languages
- 1000+ subtitle fonts
- Real-time timeline editing
- Video export with subtitles and voice-overs
- Subscription-based feature tiers (Free, Pro, Team, Enterprise)
- OAuth authentication (Google, Microsoft)

---

## Version History

| Version | Date | Type |
|---------|------|------|
| 1.0.5 | 2025-01-03 | Critical Fix |
| 1.0.4 | 2025-01-03 | Critical Fix |
| 1.0.3 | 2025-01-03 | Feature |
| 1.0.2 | 2025-01-01 | Security |
| 1.0.1 | 2024-12-28 | Patch |
| 1.0.0 | 2024-12-20 | Initial Release |

---

## Upgrade Notes

### Upgrading to 1.0.3
- New Ollama setup wizard will appear on first launch if Ollama is not installed
- Existing Ollama installations are automatically detected
- No data migration required

### Upgrading from 1.0.x to 1.0.2+
- FFmpeg is now bundled; you can remove any manually installed FFmpeg if desired
- Existing projects are fully compatible

---

## Release Verification

All releases include SHA256 checksums in `checksums.txt`. Verify your download:

```bash
# Linux/macOS
sha256sum -c checksums.txt

# Windows (PowerShell)
Get-FileHash TermiVoxed-*-Setup.exe -Algorithm SHA256
```

---

[Unreleased]: https://github.com/lxusbrain/termivoxed/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/lxusbrain/termivoxed/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/lxusbrain/termivoxed/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/lxusbrain/termivoxed/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/lxusbrain/termivoxed/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/lxusbrain/termivoxed/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/lxusbrain/termivoxed/releases/tag/v1.0.0
