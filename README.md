# TermiVoxed

<div align="center">

<img src="./assets/SVG/Horizontal_Logo.svg" alt="TermiVoxed Logo" width="600">

**AI-Powered Video Voice-Over & Dubbing Platform**

Transform your videos with professional AI voice-overs and styled subtitles

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![FFmpeg Required](https://img.shields.io/badge/FFmpeg-Required-orange.svg)](https://ffmpeg.org/)

[Get Started](#getting-started) | [Features](#features) | [Pricing](#pricing) | [Documentation](#documentation)

</div>

---

## Overview

TermiVoxed is a professional video dubbing and voice-over platform that combines AI-powered text-to-speech with advanced subtitle styling. Whether you're a content creator, educator, or business professional, TermiVoxed helps you create multilingual video content effortlessly.

---

## Features

### Voice Generation

- **200+ AI Voices** - Natural-sounding voices in 80+ languages
- **Voice Cloning** - Clone voices with just 6 seconds of audio (Pro+)
- **Multiple TTS Engines** - Edge-TTS (cloud) + Coqui (local fallback)
- **Voice Preview** - Listen before you commit

### Subtitle Styling

- **Google Fonts Integration** - 1000+ fonts auto-installed
- **Full Customization** - Colors, borders, shadows, positioning
- **Multi-language Support** - Language-specific font recommendations
- **ASS Format** - Professional subtitle rendering

### Video Processing

- **Multi-Video Projects** - Work with multiple videos seamlessly
- **Smart Audio Mixing** - Balanced voice-over and background audio
- **Background Music** - Add BGM with auto-loop and fade
- **Video Combination** - Merge edited videos into one output
- **Quality Presets** - Lossless, High, Balanced export options

### Platform

- **Web Interface** - Modern React-based UI
- **Desktop Apps** - Windows (.exe) and macOS (.dmg)
- **Cross-Platform** - Works on Windows, macOS, and Linux
- **Offline Mode** - 72-hour grace period for offline work
- **Auto-Updates** - Secure Ed25519-signed updates

---

## Getting Started

### Web Application

Visit [termivoxed.luxusbrain.com](https://termivoxed.luxusbrain.com) to get started with the web interface.

### Desktop Application

Download the latest version for your platform:

- **Windows**: [Download .exe installer](https://termivoxed.luxusbrain.com/download/windows)
- **macOS**: [Download .dmg](https://termivoxed.luxusbrain.com/download/macos)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/san-gitlogin/termivoxed.git
cd termivoxed

# Run setup script
./setup.sh        # macOS/Linux
setup.bat         # Windows CMD
.\setup.ps1       # Windows PowerShell

# Start the application
./run.sh          # macOS/Linux
run.bat           # Windows CMD
```

### Docker

```bash
docker-compose up -d
```

---

## Pricing

| Plan           | Exports/Month  | Price (INR) | Price (USD) |
| -------------- | -------------- | ----------- | ----------- |
| **Free Trial** | 5 exports      | Free        | Free        |
| **Individual** | 200 exports    | ₹499/mo     | $6.99/mo    |
| **Pro**        | 500 exports    | ₹999/mo     | $12.99/mo   |
| **Enterprise** | 2000 exports   | Custom      | Custom      |
| **Lifetime**   | 500/mo forever | ₹4,999      | $59.99      |

All paid plans include:

- Watermark-free exports
- Priority TTS processing
- Voice cloning (Pro+)
- Email support

---

## Documentation

| Document                        | Description                       |
| ------------------------------- | --------------------------------- |
| [Proxy Setup](PROXY_SETUP.md)   | Configure corporate proxy for TTS |
| [Contributing](CONTRIBUTING.md) | Contribution guidelines           |
| [Changelog](CHANGELOG.md)       | Version history                   |

---

## System Requirements

### Minimum

- **OS**: Windows 10, macOS 10.14, Ubuntu 20.04
- **RAM**: 4 GB
- **Storage**: 2 GB free space
- **FFmpeg**: Required for video processing

### Recommended

- **RAM**: 8 GB+
- **Storage**: 10 GB+ (for voice models)
- **GPU**: CUDA-compatible (for local TTS)

---

## Tech Stack

| Component | Technology                                 |
| --------- | ------------------------------------------ |
| Frontend  | React 18, TypeScript, TailwindCSS, Zustand |
| Backend   | FastAPI, Python 3.8+                       |
| Database  | Firebase Firestore                         |
| Auth      | Firebase Authentication                    |
| Payments  | Razorpay (India), Stripe (International)   |
| TTS       | Edge-TTS, Coqui TTS                        |
| Video     | FFmpeg                                     |

---

## Security

- AES-256 encryption for sensitive data
- Firebase Authentication with JWT tokens
- OWASP-compliant PBKDF2 key derivation
- Ed25519 signed application updates
- GDPR & India DPDP Act compliant

---

## Support

- **Email**: support@luxusbrain.com
- **Documentation**: [docs.termivoxed.com](https://docs.termivoxed.com)
- **Issues**: [GitHub Issues](https://github.com/san-gitlogin/termivoxed/issues)

---

## Legal

- [Terms of Service](https://termivoxed.luxusbrain.com/legal/terms)
- [Privacy Policy](https://termivoxed.luxusbrain.com/legal/privacy)
- [Refund Policy](https://termivoxed.luxusbrain.com/legal/refund)
- [EULA](https://termivoxed.luxusbrain.com/legal/eula)

---

## License

Copyright 2024-2025 LxusBrain. All rights reserved.

This software is proprietary. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built by [LXUSBrain](https://luxusbrain.com)**

</div>
