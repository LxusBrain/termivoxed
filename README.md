# TermiVoxed

<p align="center">
  <img src="assets/logo.svg" alt="TermiVoxed Logo" width="120">
</p>

<p align="center">
  <strong>AI Voice-Over Dubbing Studio</strong><br>
  Create professional voice-overs for your videos without recording your own voice
</p>

<p align="center">
  <a href="https://github.com/lxusbrain/termivoxed/releases/latest">
    <img src="https://img.shields.io/github/v/release/lxusbrain/termivoxed?style=flat-square&color=00CED1" alt="Latest Release">
  </a>
  <a href="https://github.com/lxusbrain/termivoxed/releases">
    <img src="https://img.shields.io/github/downloads/lxusbrain/termivoxed/total?style=flat-square&color=00CED1" alt="Downloads">
  </a>
  <a href="https://lxusbrain.com/termivoxed">
    <img src="https://img.shields.io/badge/website-lxusbrain.com-00CED1?style=flat-square" alt="Website">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-Proprietary-red?style=flat-square" alt="License">
  </a>
</p>

---

## Overview

TermiVoxed is a desktop application that transforms your video content with AI-powered voice-overs. Generate professional narration scripts using local AI (Ollama) or cloud providers, then synthesize natural-sounding speech in 320+ voices across 75+ languages.

### Key Features

- **AI Script Generation** - Generate narration scripts using local Ollama models or cloud AI (OpenAI, Claude, Gemini)
- **320+ AI Voices** - Natural text-to-speech in 75+ languages via Edge TTS and Coqui TTS
- **Voice Cloning** - Clone any voice from a short audio sample (local processing only)
- **1000+ Subtitle Fonts** - Style your subtitles with professional typography
- **Multi-Video Projects** - Work with multiple videos in a single project
- **100% Local Processing** - Your data never leaves your machine when using Ollama + Coqui TTS
- **Offline Mode** - Works without internet when using local AI models

---

## Download

### Latest Release

| Platform | Download | Requirements |
|----------|----------|--------------|
| **Windows** | [TermiVoxed-Setup.exe](https://github.com/lxusbrain/termivoxed/releases/latest) | Windows 10/11 (64-bit) |
| **macOS** | [TermiVoxed.dmg](https://github.com/lxusbrain/termivoxed/releases/latest) | macOS 11+ (Intel & Apple Silicon) |
| **Linux** | [TermiVoxed.tar.gz](https://github.com/lxusbrain/termivoxed/releases/latest) | Ubuntu 20.04+, Debian 11+, Fedora 35+ |

> **Note:** This is currently in **Beta**. Please report any issues via the [issue tracker](https://github.com/lxusbrain/termivoxed/issues).

### Verifying Downloads

All releases include SHA256 checksums in `checksums.txt`. Verify your download:

```bash
# Linux/macOS
sha256sum -c checksums.txt

# Windows (PowerShell)
Get-FileHash TermiVoxed-*-Setup.exe -Algorithm SHA256
```

---

## Installation

### Windows

1. Download `TermiVoxed-X.X.X-Setup.exe`
2. Run the installer (you may see a SmartScreen warning - click "More info" → "Run anyway")
3. Follow the installation wizard
4. Launch TermiVoxed from the Start Menu

### macOS

1. Download `TermiVoxed-X.X.X-macos.dmg`
2. Open the DMG file
3. Drag TermiVoxed to your Applications folder
4. On first launch, right-click and select "Open" (required for unsigned apps)
5. Grant necessary permissions when prompted

### Linux

1. Download `TermiVoxed-X.X.X-linux-x64.tar.gz`
2. Extract: `tar -xzf TermiVoxed-*.tar.gz`
3. Run: `./TermiVoxed/TermiVoxed`

**Dependencies (auto-installed with the app):**
- FFmpeg (bundled)
- Python 3.11 runtime (bundled)

---

## Getting Started

### 1. Create an Account

TermiVoxed requires a free account to sync your subscription across devices:
- Visit [lxusbrain.com/termivoxed](https://lxusbrain.com/termivoxed) to create an account
- Sign in with Google or Microsoft

### 2. Set Up Local AI (Recommended)

For 100% private, offline AI processing:

1. Install [Ollama](https://ollama.com/download) on your system
2. Launch TermiVoxed - the setup wizard will guide you through model installation
3. Recommended models:
   - `llama3.2:3b` - Fast script generation (2GB)
   - `llama3.1:8b` - Better quality (4.7GB)
   - `llava:7b` - Video analysis (4.5GB)

### 3. Start Creating

1. Click "New Project"
2. Import your video file
3. Add segments and generate AI scripts
4. Preview and generate voice-overs
5. Export your final video

---

## System Requirements

### Minimum
- **OS:** Windows 10, macOS 11, Ubuntu 20.04
- **CPU:** 4 cores, 2.5 GHz
- **RAM:** 8 GB
- **Storage:** 2 GB (+ space for AI models)
- **GPU:** Not required (CPU inference)

### Recommended (for Local AI)
- **CPU:** 8+ cores, 3.0 GHz
- **RAM:** 16 GB
- **Storage:** 20 GB SSD
- **GPU:** 8 GB VRAM (NVIDIA with CUDA, or Apple Silicon)

---

## Privacy & Security

TermiVoxed is designed with privacy as a core principle:

### Data Processing

| Feature | Local | Cloud | Notes |
|---------|-------|-------|-------|
| AI Script Generation | Ollama | OpenAI, Claude, Gemini | You choose the provider |
| Text-to-Speech | Coqui TTS | Edge TTS | Local option available |
| Voice Cloning | Coqui TTS | - | Always local |
| Video Processing | Always | - | FFmpeg runs locally |

### What We Collect

- **Account Info:** Email (for authentication)
- **Usage Metrics:** Feature usage counts (subscription limits)
- **No Content:** We never access your videos, scripts, or audio

See our full [Privacy Policy](https://lxusbrain.com/legal/privacy) for details.

---

## Support

- **Documentation:** [docs.lxusbrain.com](https://lxusbrain.com/termivoxed)
- **Issues:** [GitHub Issues](https://github.com/lxusbrain/termivoxed/issues)
- **Email:** support@lxusbrain.com
- **Enterprise:** enterprise@lxusbrain.com

---

## License

TermiVoxed is proprietary software. See [LICENSE](LICENSE) for terms.

**Powered by Open Source:**
- [FFmpeg](https://ffmpeg.org/) - Video processing (LGPL)
- [Ollama](https://ollama.com/) - Local AI models (MIT)
- [Coqui TTS](https://github.com/coqui-ai/TTS) - Text-to-speech (MPL-2.0)
- [Edge TTS](https://github.com/rany2/edge-tts) - Microsoft TTS (GPL-3.0)
- [LangChain](https://langchain.com/) - AI framework (MIT)

---

<p align="center">
  Made with care by <a href="https://lxusbrain.com">LxusBrain</a>
</p>
