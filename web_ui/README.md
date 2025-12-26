# TermiVoxed Web UI

A modern, sleek web interface for TermiVoxed - the AI Voice-Over Dubbing Tool.

## Features

### Core Functionality (Preserved from Console Version)
- **Multi-video project support** - Handle multiple videos in a single project
- **Timeline-based segment editing** - Visual segment management
- **200+ AI voices** - Microsoft Edge TTS integration
- **Styled subtitles** - Language-specific fonts and styling
- **Smart caching** - MD5-based TTS caching for faster re-exports
- **Background music mixing** - With TTS boost and BGM reduction
- **Quality presets** - Lossless, High, Balanced export options

### New AI-Powered Features
- **AI Script Generation** - Generate narration scripts using:
  - **Ollama** (Local, free) - llama3.2, mistral, codellama, etc.
  - **OpenAI** - GPT-4, GPT-3.5 Turbo
  - **Anthropic** - Claude 3 Opus, Sonnet, Haiku
  - **Custom Endpoints** - Any OpenAI-compatible API

- **Smart Duration Fitting** - AI-generated scripts automatically fit segment duration
- **Script Refinement** - Shorten, lengthen, or rephrase scripts
- **Segment Description to Script** - Describe what happens, AI writes the narration

## Tech Stack

### Backend
- **FastAPI** - Modern async Python API framework
- **WebSockets** - Real-time export progress
- **Existing Services** - Reuses TTSService, FFmpegUtils, ExportPipeline

### Frontend
- **React 18** + TypeScript
- **Vite** - Fast development and building
- **TailwindCSS** - Dark console theme (black/red/white)
- **Framer Motion** - Smooth animations
- **Zustand** - Lightweight state management
- **React Query** - Server state management

## Getting Started

### Prerequisites

1. **Python 3.8+** with pip
2. **Node.js 18+** with npm
3. **FFmpeg 6+** for video processing
4. **Ollama** (optional) for local AI

### Installation

```bash
# From the console_video_editor directory
cd web_ui

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running the Application

```bash
# Easy way - use the startup script
./start.sh

# Or manually start both servers:

# Terminal 1 - Backend API
cd /path/to/console_video_editor
python -m uvicorn web_ui.api.main:app --reload --port 8000

# Terminal 2 - Frontend
cd /path/to/console_video_editor/web_ui/frontend
npm run dev
```

### Access Points
- **Web UI**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
web_ui/
├── api/                    # FastAPI Backend
│   ├── main.py            # App entry point
│   ├── routes/            # API endpoints
│   │   ├── projects.py    # Project CRUD
│   │   ├── videos.py      # Video management
│   │   ├── segments.py    # Segment operations
│   │   ├── tts.py         # TTS operations
│   │   ├── export.py      # Export with progress
│   │   ├── llm.py         # AI script generation
│   │   └── settings.py    # App settings
│   ├── services/          # Business logic
│   │   ├── llm_service.py # Multi-provider LLM
│   │   └── script_fitter.py # Duration fitting
│   └── schemas/           # Pydantic models
│
├── frontend/              # React Frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   │   ├── VideoPlayer.tsx
│   │   │   ├── Timeline.tsx
│   │   │   ├── SegmentEditor.tsx
│   │   │   └── AIScriptGenerator.tsx
│   │   ├── pages/         # Route pages
│   │   ├── stores/        # Zustand stores
│   │   ├── api/           # API client
│   │   └── types/         # TypeScript types
│   └── tailwind.config.js
│
├── requirements.txt       # Python dependencies
├── start.sh              # Startup script
└── README.md
```

## Using AI Script Generation

### With Ollama (Recommended - Free & Local)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3.2:3b`
3. Start Ollama: `ollama serve`
4. In TermiVoxed, select "Ollama" as provider

### With Cloud APIs

1. Go to Settings page
2. Enter your API key for OpenAI/Anthropic
3. Select the provider when generating scripts

### Workflow

1. **Create a project** with your video(s)
2. **Click "AI Script"** button
3. **Add segments** with start/end times
4. **Describe each segment** (what happens visually)
5. **Select style** (documentary, casual, etc.)
6. **Generate scripts** - AI writes the narration
7. **Review & apply** to timeline
8. **Export** with voice-over and subtitles

## Design Philosophy

### Dark Console Theme
- **Black** (#0a0a0a) - Primary background
- **Red** (#dc2626) - Accent color, CTAs
- **White** (#ffffff) - Primary text
- Monospace fonts for data/code
- Subtle glow effects on interactive elements

### UX Principles
- Real-time feedback for all operations
- Clear loading/processing states
- Non-blocking operations where possible
- Keyboard shortcuts for power users
- Mobile-responsive design

## API Reference

See full API documentation at http://localhost:8000/docs when running.

### Key Endpoints

```
POST /api/v1/projects              # Create project
GET  /api/v1/projects              # List projects
GET  /api/v1/projects/{name}       # Get project

POST /api/v1/segments/{project}    # Create segment
PUT  /api/v1/segments/{project}/{id} # Update segment

GET  /api/v1/tts/voices            # List voices
POST /api/v1/tts/preview           # Preview voice

POST /api/v1/llm/generate-script   # AI script generation
POST /api/v1/llm/refine-script     # Refine script

POST /api/v1/export/start          # Start export
WS   /api/v1/export/progress/{id}  # Export progress
```

## Contributing

1. The console version (`main.py`) remains the primary CLI interface
2. Web UI is an additional interface, not a replacement
3. All backend logic should be reusable by both interfaces
4. Keep the same project file format for interoperability
