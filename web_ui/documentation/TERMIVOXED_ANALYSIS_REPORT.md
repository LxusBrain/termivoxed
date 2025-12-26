# Termivoxed Comprehensive Analysis Report

**Date:** December 14, 2025
**Analyst:** Claude Code
**Scope:** Complete codebase analysis, FFmpeg capabilities, timeline scenarios, and subscription model design

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [FFmpeg Capabilities Analysis](#3-ffmpeg-capabilities-analysis)
4. [Timeline Combination Scenarios](#4-timeline-combination-scenarios)
5. [Current Issues & Bugs](#5-current-issues--bugs)
6. [Subscription Model Architecture](#6-subscription-model-architecture)
7. [Implementation Plan](#7-implementation-plan)

---

## 1. Executive Summary

Termivoxed is a powerful video editor with AI voice-over capabilities built on FFmpeg. The application consists of:
- **Backend**: Python/FastAPI with core FFmpeg processing
- **Frontend**: React/TypeScript with Zustand state management
- **Core**: Export pipeline, video combining, subtitle burning

### Key Findings:
1. **FFmpeg capabilities are underutilized** - Only ~5% of FFmpeg's features are leveraged
2. **Timeline logic has edge cases** - Multiple video/segment combinations not fully handled
3. **Subscription model** - Feasible to implement with local-first, cloud-verified approach
4. **Critical bugs identified** - Segment positioning, audio sync, multi-video export

---

## 2. Architecture Overview

### 2.1 Directory Structure
```
console_video_editor/
├── backend/
│   ├── ffmpeg_utils.py      # FFmpeg command generation (CRITICAL)
│   ├── subtitle_utils.py    # Subtitle/ASS file handling
│   └── tts_service.py       # Edge-TTS integration
├── core/
│   ├── export_pipeline.py   # Export orchestration
│   └── video_combiner.py    # Multi-video handling
├── models/
│   ├── project.py           # Project data model
│   ├── video.py             # Video model with timeline
│   ├── segment.py           # Segment (voiceover) model
│   ├── timeline.py          # Timeline management
│   └── bgm_track.py         # Background music model
├── web_ui/
│   ├── api/                 # FastAPI routes
│   └── frontend/            # React application
└── config.py                # Settings
```

### 2.2 Data Flow
```
User Action → React Component → API Route → Model → FFmpeg → Output
     ↓              ↓              ↓          ↓         ↓
   appStore     client.ts      routes/    Project   ffmpeg_utils.py
```

### 2.3 Key Components

**Project Model (`models/project.py`):**
- Manages multiple videos
- Handles BGM tracks (multiple)
- Stores settings (quality, subtitle preferences)
- Serializes to JSON for persistence

**Video Model (`models/video.py`):**
- Contains timeline with segments
- Stores video metadata (width, height, fps, codec)
- Has `timeline_start` and `timeline_end` for positioning
- Orientation detection (horizontal/vertical)

**Segment Model (`models/segment.py`):**
- Represents a voiceover section
- Has start_time, end_time, text, voice settings
- References audio_path and subtitle_path
- Linked to video_id

**Timeline Model (`models/timeline.py`):**
- Manages segments for a single video
- Validates segment overlaps
- Tracks video duration

---

## 3. FFmpeg Capabilities Analysis

### 3.1 Currently Used Features (~5%)
Based on `ffmpeg_utils.py`:
- Basic video info extraction (ffprobe)
- Subtitle burning (ass filter)
- Audio mixing (amix, adelay)
- Video concatenation (concat filter)
- Volume control (volume filter)
- Fade in/out for audio (afade)
- Scaling (scale filter)
- Pixel format conversion

### 3.2 Missing Professional Features

**Video Manipulation:**
- [ ] Crop/trim with frame accuracy
- [ ] Multiple video tracks/layers
- [ ] Picture-in-picture (overlay)
- [ ] Transitions (xfade with 40+ types)
- [ ] Speed control (setpts, atempo)
- [ ] Color correction (eq, curves, colorbalance)
- [ ] Green screen (chromakey)
- [ ] Video stabilization (vidstab)
- [ ] Denoising (hqdn3d, nlmeans)
- [ ] Sharpening (unsharp)

**Audio Manipulation:**
- [ ] Audio ducking (sidechaincompress)
- [ ] EQ (equalizer, bass, treble)
- [ ] Noise reduction (afftdn, arnndn)
- [ ] Compression (acompressor, alimiter)
- [ ] Reverb/effects (aecho, chorus)
- [ ] Loudness normalization (loudnorm)
- [ ] Multi-track mixing beyond 2 inputs

**Timeline Features:**
- [ ] Keyframe animation
- [ ] Time remapping
- [ ] Freeze frame
- [ ] Reverse playback
- [ ] Loop sections
- [ ] Split/join clips

### 3.3 FFmpeg Filter Syntax for Complex Operations

**Multi-video with segments at different positions:**
```bash
ffmpeg -i video1.mp4 -i video2.mp4 -i segment1_audio.mp3 -i bgm.mp3 \
-filter_complex "
  [0:v]trim=0:10,setpts=PTS-STARTPTS[v0];
  [1:v]trim=5:20,setpts=PTS-STARTPTS[v1];
  [v0][v1]concat=n=2:v=1:a=0[video];
  [0:a]atrim=0:10,asetpts=PTS-STARTPTS[a0];
  [1:a]atrim=5:20,asetpts=PTS-STARTPTS[a1];
  [a0][a1]concat=n=2:v=0:a=1[orig_audio];
  [2:a]adelay=5000|5000[seg_audio];
  [3:a]volume=0.3[bgm];
  [orig_audio][seg_audio][bgm]amix=inputs=3:duration=longest[audio]
" -map "[video]" -map "[audio]" output.mp4
```

---

## 4. Timeline Combination Scenarios

### 4.1 All Possible Combinations Matrix

| Videos | Segments | BGM Tracks | Scenario Complexity |
|--------|----------|------------|---------------------|
| 1      | 0        | 0          | Simple passthrough |
| 1      | 0        | 1          | BGM only |
| 1      | 0        | N          | Multiple BGM layers |
| 1      | 1        | 0          | Single segment |
| 1      | 1        | 1          | Standard case |
| 1      | 1        | N          | Segment + multi BGM |
| 1      | N        | 0          | Multiple segments |
| 1      | N        | 1          | Multiple segments + BGM |
| 1      | N        | N          | Complex single video |
| N      | 0        | 0          | Multi-video concat |
| N      | 0        | 1          | Multi-video + BGM |
| N      | 0        | N          | Multi-video + multi BGM |
| N      | 1        | 0          | Segment spans videos |
| N      | 1        | 1          | Segment spans + BGM |
| N      | N        | 0          | Segments in each video |
| N      | N        | 1          | Full complexity base |
| N      | N        | N          | **MAXIMUM COMPLEXITY** |

### 4.2 Critical Scenarios Requiring Special Handling

**Scenario 1: Segment Spanning Multiple Videos**
- Segment starts at 8s, ends at 15s
- Video 1 is 10s, Video 2 starts at 10s
- Segment audio must overlay both videos
- Subtitle must appear across both

**Scenario 2: Overlapping Segments**
- Segment A: 5s-10s
- Segment B: 8s-12s
- Currently blocked but user may want it for effects

**Scenario 3: Video with Different Resolutions**
- Video 1: 1920x1080
- Video 2: 1280x720
- Must scale to common resolution before concat

**Scenario 4: Video with Different Frame Rates**
- Video 1: 30fps
- Video 2: 60fps
- Must normalize to prevent sync issues

**Scenario 5: BGM Duration Mismatch**
- BGM: 3 minutes
- Video: 10 minutes
- Must handle looping or silence

**Scenario 6: Trimmed Videos**
- Video 1 trimmed: 5s-15s (10s duration)
- Video 2 trimmed: 0s-10s (10s duration)
- Segments must reference absolute vs relative time

**Scenario 7: Videos with Gaps**
- Video 1 ends at 10s
- Video 2 starts at 15s (5s gap)
- Need black/silence or user-specified fill

### 4.3 Timestamp Calculations

**Current Issue:** `timeline_start` and `timeline_end` in Video model are not consistently used.

**Required Formula:**
```python
# For segment absolute position in final timeline:
absolute_start = video.timeline_start + segment.start_time
absolute_end = video.timeline_start + segment.end_time

# For multi-video export, cumulative offset:
for video in videos:
    video.timeline_offset = cumulative_duration
    cumulative_duration += video.get_trimmed_duration()
```

---

## 5. Current Issues & Bugs

### 5.1 Critical Bugs

**Bug #1: Multi-video segment timing**
- Location: `core/export_pipeline.py:200-250`
- Issue: Segments use video-relative time, not timeline-absolute
- Impact: Audio plays at wrong time in multi-video export

**Bug #2: BGM track positioning**
- Location: `backend/ffmpeg_utils.py:350-400`
- Issue: BGM start_time not used in filter_complex
- Impact: BGM always starts at 0, ignoring track.start_time

**Bug #3: Resolution mismatch in concat**
- Location: `core/video_combiner.py`
- Issue: No scaling before concatenation
- Impact: FFmpeg error or stretched video

**Bug #4: Audio stream assumptions**
- Location: `backend/ffmpeg_utils.py`
- Issue: Assumes all videos have audio stream
- Impact: Fails on videos without audio

**Bug #5: Segment overlap validation**
- Location: `models/timeline.py:143-153`
- Issue: Validation only per-video, not across timeline
- Impact: Overlapping segments across videos not detected

### 5.2 Edge Cases Not Handled

1. **Empty segment text** - TTS fails silently
2. **Missing font file** - Subtitle burning fails
3. **Video codec incompatibility** - Concat fails
4. **Network interruption** - Edge-TTS partial download
5. **Disk full during export** - No graceful handling
6. **Invalid timeline positions** - No bounds checking

### 5.3 Performance Issues

1. **Full re-render on any change** - No caching
2. **Synchronous FFmpeg calls** - Blocks event loop
3. **No progress reporting for long operations**
4. **Memory usage with large videos** - No streaming

---

## 6. Subscription Model Architecture

### 6.1 Design Principles

1. **Local-first**: All processing happens locally
2. **Privacy-preserving**: Only subscription status verified online
3. **Offline grace period**: Works offline for 7 days
4. **Device binding**: Single device active at a time
5. **Fair pricing**: Tiered based on features

### 6.2 Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL APPLICATION                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Auth UI    │  │   License    │  │   Feature Gate   │   │
│  │   Screens    │  │   Manager    │  │   Controller     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│          │                │                   │              │
│          └────────────────┼───────────────────┘              │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │   Local DB   │                          │
│                    │  (encrypted) │                          │
│                    └──────────────┘                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (verification only)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CLOUD SERVICE                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Auth API   │  │  License DB  │  │   Device Mgmt    │   │
│  │   (JWT)      │  │              │  │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Subscription Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Free Trial** | $0 | 7 days, watermark, 720p max |
| **Basic** | $9.99/mo | No watermark, 1080p, 5 projects |
| **Pro** | $19.99/mo | 4K, unlimited projects, priority TTS |
| **Lifetime** | $199 | All Pro features forever |

### 6.4 Device Management

```python
# Unique device fingerprint (privacy-preserving)
device_id = hash(
    machine_id +
    os_version +
    installed_timestamp
)

# On login:
1. Check existing active devices for user
2. If device_id matches existing → allow
3. If no matching device and count < limit → register new
4. If count >= limit → prompt to logout other device
```

### 6.5 API Endpoints Needed

```
POST /api/auth/register     - Create account
POST /api/auth/login        - Login, get JWT + license
POST /api/auth/logout       - Invalidate session
POST /api/auth/refresh      - Refresh JWT token
GET  /api/license/verify    - Verify subscription status
POST /api/device/register   - Register device
POST /api/device/deactivate - Logout from device
GET  /api/device/list       - List active devices
POST /api/subscription/create - Start subscription
POST /api/subscription/cancel - Cancel subscription
```

### 6.6 Local License Storage

```python
@dataclass
class LocalLicense:
    user_id: str
    email: str
    tier: str  # 'trial', 'basic', 'pro', 'lifetime'
    device_id: str
    expires_at: datetime
    last_verified: datetime
    offline_days_remaining: int  # Grace period
    signature: str  # HMAC to prevent tampering
```

### 6.7 Security Measures

1. **License signed with server secret** - Can't be forged
2. **Device binding** - Can't share license
3. **Periodic verification** - Every 24h when online
4. **Offline grace** - 7 days before lockout
5. **Feature gating in code** - Not just UI hiding

---

## 7. Implementation Plan

### Phase 1: Subscription Model (Priority 1)

#### Step 1.1: Backend Cloud Service
- Set up FastAPI cloud service (Vercel/Railway/Heroku)
- Database: PostgreSQL for users, subscriptions, devices
- Authentication: JWT with refresh tokens
- Stripe integration for payments

#### Step 1.2: Local License Manager
- Create `license/` directory in web_ui
- Implement LicenseManager class
- Encrypt local storage with machine-specific key
- Handle offline verification

#### Step 1.3: UI Screens
- Login/Register modal
- Subscription selection page
- Account settings page
- Device management page
- Trial banner component

#### Step 1.4: Feature Gating
- Decorator for gated API endpoints
- Frontend hooks for feature availability
- Graceful degradation for expired licenses

### Phase 2: Timeline Bug Fixes (Priority 2)

#### Step 2.1: Timeline Position System
- Implement absolute timeline coordinates
- Update segment timing calculations
- Add validation for cross-video segments

#### Step 2.2: Multi-video Export Fix
- Proper cumulative offset calculation
- Handle resolution/fps normalization
- Test all combination scenarios

#### Step 2.3: BGM Track Positioning
- Implement start_time in filter_complex
- Handle multiple overlapping BGM tracks
- Add fade in/out at boundaries

### Phase 3: Professional Features (Priority 3)

#### Step 3.1: Video Manipulation
- Crop/trim UI and backend
- Transitions between clips
- Speed control

#### Step 3.2: Audio Enhancement
- Audio ducking (BGM quieter during speech)
- Basic EQ presets
- Noise reduction option

#### Step 3.3: Color Correction
- Basic brightness/contrast/saturation
- Preset filters (vintage, B&W, etc.)

---

## Appendix A: FFmpeg Command Patterns

### A.1 Multi-video with Segments and BGM
```bash
ffmpeg \
  -i video1.mp4 \
  -i video2.mp4 \
  -i segment1.mp3 \
  -i segment2.mp3 \
  -i bgm.mp3 \
  -filter_complex "
    # Normalize video resolution
    [0:v]scale=1920:1080:force_original_aspect_ratio=decrease,
         pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];
    [1:v]scale=1920:1080:force_original_aspect_ratio=decrease,
         pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];

    # Concatenate videos
    [v0][v1]concat=n=2:v=1:a=0[video];

    # Handle original audio
    [0:a]asetpts=PTS-STARTPTS[a0];
    [1:a]asetpts=PTS-STARTPTS,adelay=10000|10000[a1];

    # Position segment audio
    [2:a]adelay=5000|5000[seg1];
    [3:a]adelay=15000|15000[seg2];

    # BGM with volume reduction
    [4:a]volume=0.3,afade=t=in:st=0:d=2,afade=t=out:st=28:d=2[bgm];

    # Mix all audio
    [a0][a1][seg1][seg2][bgm]amix=inputs=5:duration=longest[audio]
  " \
  -map "[video]" -map "[audio]" \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  output.mp4
```

### A.2 Subtitle Burning with Word-level Timing
```bash
ffmpeg -i video.mp4 \
  -vf "ass=subtitles.ass:fontsdir=/path/to/fonts" \
  -c:v libx264 -crf 23 \
  -c:a copy \
  output.mp4
```

---

## Appendix B: Database Schema for Subscription Service

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions table
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- active, cancelled, expired
    stripe_subscription_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Devices table
CREATE TABLE devices (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    device_fingerprint VARCHAR(255) NOT NULL,
    device_name VARCHAR(255),
    last_seen TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, device_fingerprint)
);

-- License verifications (for audit)
CREATE TABLE license_verifications (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    device_id UUID REFERENCES devices(id),
    verified_at TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(45),
    result VARCHAR(50)  -- success, expired, device_mismatch
);
```

---

## Appendix C: Test Scenarios Checklist

### Single Video Tests
- [ ] No segments, no BGM
- [ ] One segment, no BGM
- [ ] Multiple non-overlapping segments, no BGM
- [ ] No segments, one BGM
- [ ] One segment, one BGM
- [ ] Multiple segments, one BGM
- [ ] Multiple segments, multiple BGM tracks

### Multi-Video Tests
- [ ] Two videos, no segments, no BGM
- [ ] Two videos with same resolution
- [ ] Two videos with different resolutions
- [ ] Two videos with different frame rates
- [ ] Segment in first video only
- [ ] Segment in second video only
- [ ] Segment spanning both videos
- [ ] BGM across both videos
- [ ] Full complexity: multiple videos, segments, BGM tracks

### Edge Cases
- [ ] Very short video (< 1s)
- [ ] Very long video (> 1 hour)
- [ ] Video without audio stream
- [ ] Video with multiple audio streams
- [ ] Segment with empty text
- [ ] Segment duration longer than video
- [ ] BGM shorter than video (looping)
- [ ] BGM longer than video (truncation)
- [ ] Unicode text in segments
- [ ] Special characters in file paths

---

**END OF ANALYSIS REPORT**
