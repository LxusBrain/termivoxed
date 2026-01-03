# Privacy & Data Handling

This document explains how TermiVoxed handles your data. For the complete privacy policy, visit [lxusbrain.com/legal/privacy](https://lxusbrain.com/legal/privacy).

## Our Privacy Principles

1. **Local First**: Your content stays on your machine
2. **Minimal Collection**: We only collect what's necessary
3. **Transparency**: You know exactly what data goes where
4. **User Control**: You choose cloud vs. local processing

---

## Data Categories

### Content You Create (Always Local)

| Data | Storage | Uploaded? |
|------|---------|-----------|
| Video files | Your computer | Never |
| Audio/voice-overs | Your computer | Never |
| Project files | Your computer | Never |
| Generated scripts | Your computer | Never |
| Subtitles | Your computer | Never |

**Your creative content never leaves your machine.** All video processing, audio generation, and file exports happen locally using FFmpeg.

### Account Information

| Data | Purpose | Storage |
|------|---------|---------|
| Email address | Account identification | Firebase (Google Cloud) |
| Display name | Personalization | Firebase |
| OAuth tokens | Authentication | Encrypted, local + Firebase |
| Subscription tier | Feature access | Firebase |

### Usage Metrics

We track usage counts (not content) for subscription limits:

| Metric | Purpose | What's Tracked |
|--------|---------|----------------|
| TTS generations | Subscription limit | Count only, not text |
| AI script generations | Subscription limit | Count only, not content |
| Video exports | Subscription limit | Count only |
| Projects created | Subscription limit | Count only |

---

## AI & Cloud Services

### Local AI (Recommended for Privacy)

When using local AI providers, your data never leaves your machine:

| Service | Data Sent | Privacy Level |
|---------|-----------|---------------|
| **Ollama** (Local LLM) | None | Maximum |
| **Coqui TTS** (Local voices) | None | Maximum |
| **Piper TTS** (Local voices) | None | Maximum |

### Cloud AI (Optional)

If you choose to use cloud AI services:

| Service | Data Sent | Privacy Policy |
|---------|-----------|----------------|
| Edge TTS (Microsoft) | Text for speech | [Microsoft Privacy](https://privacy.microsoft.com/) |
| OpenAI | Prompts/text | [OpenAI Privacy](https://openai.com/privacy/) |
| Claude (Anthropic) | Prompts/text | [Anthropic Privacy](https://www.anthropic.com/privacy) |
| Google Gemini | Prompts/text | [Google Privacy](https://policies.google.com/privacy) |

**Note**: When using cloud AI, your prompts and text content are sent to those services. We recommend using local AI (Ollama) for sensitive content.

---

## Authentication

We use industry-standard OAuth 2.0 for secure authentication:

| Provider | Data Accessed | Purpose |
|----------|--------------|---------|
| Google Sign-In | Email, name, profile photo | Account creation |
| Microsoft Sign-In | Email, name | Account creation |

We only request the minimum permissions needed. We do not access your contacts, files, or other Google/Microsoft data.

---

## Payment Processing

Payment processing is handled by third-party providers:

| Region | Provider | Data Handled |
|--------|----------|--------------|
| India | Razorpay | Payment info, billing address |
| International | Stripe | Payment info, billing address |

We never store your complete payment card details. Only transaction references are stored for subscription management.

---

## Data Storage Locations

| Data Type | Location | Provider |
|-----------|----------|----------|
| Authentication | United States | Firebase (Google Cloud) |
| Subscription data | United States | Firebase (Google Cloud) |
| Payment records | Provider's region | Stripe/Razorpay |
| Your content | Your computer | You control this |

---

## Your Rights

You have the right to:

- **Access**: Request a copy of your data
- **Delete**: Request deletion of your account and data
- **Export**: Export your projects (always available locally)
- **Opt-out**: Use local-only mode without cloud features

### Data Deletion

To delete your account and associated data:

1. Contact us at privacy@lxusbrain.com
2. We will delete your data within 30 days
3. Local files on your computer are your responsibility

---

## Offline Mode

TermiVoxed can run in offline mode with reduced functionality:

| Feature | Offline Availability |
|---------|---------------------|
| Video editing | Full |
| Local TTS (Coqui/Piper) | Full |
| Local AI (Ollama) | Full |
| Edge TTS | Requires internet |
| Cloud AI | Requires internet |
| Subscription sync | Requires internet |

---

## Children's Privacy

TermiVoxed is not intended for children under 13. We do not knowingly collect data from children.

---

## Updates to This Document

We may update this document as our practices evolve. Significant changes will be communicated through the application or our website.

Last updated: January 2025

---

## Contact

- **Privacy Questions**: privacy@lxusbrain.com
- **Data Requests**: privacy@lxusbrain.com
- **General Support**: support@lxusbrain.com

---

*For the complete legal privacy policy, visit [lxusbrain.com/legal/privacy](https://lxusbrain.com/legal/privacy)*
