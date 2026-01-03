# Security Policy

## Supported Versions

We actively support and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

We recommend always using the latest version to ensure you have the most recent security patches and features.

## Reporting a Vulnerability

We take the security of TermiVoxed seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to:

**security@lxusbrain.com**

### What to Include

Please include the following information in your report:

- **Description**: A clear description of the vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Impact**: The potential impact of the vulnerability
- **Affected Version(s)**: Which version(s) are affected
- **Proof of Concept**: If possible, include a minimal proof of concept
- **Suggested Fix**: If you have suggestions for how to fix the issue

### What to Expect

1. **Acknowledgment**: We will acknowledge receipt of your report within 48 hours
2. **Assessment**: Our security team will assess the vulnerability and determine its severity
3. **Updates**: We will keep you informed about our progress
4. **Resolution**: We aim to resolve critical vulnerabilities within 7 days
5. **Credit**: With your permission, we will credit you in our release notes

### Response Timeline

| Severity | Initial Response | Target Resolution |
| -------- | --------------- | ----------------- |
| Critical | 24 hours        | 7 days            |
| High     | 48 hours        | 14 days           |
| Medium   | 72 hours        | 30 days           |
| Low      | 1 week          | 60 days           |

## Security Measures

### Application Security

TermiVoxed implements the following security measures:

- **Local Processing**: Video, audio, and AI processing happens entirely on your machine
- **No Content Upload**: Your videos and audio files are never uploaded to our servers
- **Encrypted Authentication**: We use industry-standard OAuth 2.0 for authentication
- **Secure Storage**: Sensitive data is encrypted at rest
- **Minimal Data Collection**: We only collect what's necessary for the service

### Data Handling

| Data Type | Storage Location | Purpose |
| --------- | ---------------- | ------- |
| Videos/Audio | Local only | Never leaves your machine |
| AI Scripts | Local only | Generated and stored locally |
| Account Email | LxusBrain servers | Authentication only |
| Usage Metrics | LxusBrain servers | Subscription management |

### Third-Party Services

TermiVoxed integrates with third-party services. Here's how we handle them:

| Service | Purpose | Data Shared |
| ------- | ------- | ----------- |
| Firebase Auth | Authentication | Email, OAuth tokens |
| Edge TTS | Cloud text-to-speech | Text content (if selected) |
| OpenAI/Claude/Gemini | Cloud AI (optional) | Prompts (if selected) |
| Ollama | Local AI | None (runs locally) |
| Coqui TTS | Local TTS | None (runs locally) |

### Recommendations

For maximum privacy:

1. Use **Ollama** for AI script generation (100% local)
2. Use **Coqui TTS** for voice synthesis (100% local)
3. Enable offline mode when not syncing subscription

## Safe Harbor

We support safe harbor for security researchers who:

- Make a good faith effort to avoid privacy violations, data destruction, and service disruption
- Only interact with accounts you own or with explicit permission
- Do not exploit vulnerabilities beyond what is necessary to demonstrate them
- Report vulnerabilities promptly and do not disclose them publicly until resolved

We will not pursue legal action against researchers who follow these guidelines.

## Contact

- **Security Issues**: security@lxusbrain.com
- **General Support**: support@lxusbrain.com
- **Enterprise Inquiries**: enterprise@lxusbrain.com

---

Thank you for helping keep TermiVoxed and our users safe!
