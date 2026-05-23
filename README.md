<div align="center">
  <h1>ReelForge 🔥</h1>
  <p><strong>Agentic Instagram Automation Tool</strong></p>
  <p>Upload videos → AI splits into 30s Reels → Generates captions → Schedules & posts automatically</p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
    <img src="https://img.shields.io/badge/status-production--ready-brightgreen" alt="Production Ready">
  </p>
</div>

---

## 🚀 What is ReelForge?

**ReelForge** is a production-grade, open-source Instagram automation tool built with a **multi-agent AI framework** (CrewAI). It lets you:

1. **Connect** your Instagram Business/Creator account via OAuth
2. **Upload** full-length videos (any length — 1 min, 10 min, 1 hour)
3. **Automatically split** them into 30-second Reel segments (using FFmpeg)
4. **Generate AI captions** for each segment (OpenAI, Anthropic, or local Ollama)
5. **Schedule posts** at specific times — **survives server restarts** (APScheduler + SQLite)
6. **Edit, delete, reschedule** any segment or post

All powered by a **CrewAI agentic framework** with specialized agents:
- 🎬 **VideoProcessorAgent** — Splits videos
- ✍️ **CaptionAgent** — Writes scroll-stopping captions
- 📅 **SchedulerAgent** — Manages persistent scheduling
- 📤 **InstagramPublisherAgent** — Publishes via Instagram Graph API

---

## ✨ Features

| Feature | Status |
|---------|--------|
| Instagram OAuth (Business/Creator accounts) | ✅ |
| Video upload (MP4, MOV, AVI, MKV, WebM) | ✅ |
| Auto-split into 30s Reel segments | ✅ |
| AI caption generation (OpenAI / Anthropic / Ollama) | ✅ |
| Multiple caption styles (engaging, professional, humorous, etc.) | ✅ |
| Persistent scheduling (survives server restarts) | ✅ |
| Edit captions & hashtags | ✅ |
| Delete segments & posts | ✅ |
| Reschedule posts | ✅ |
| Dashboard UI | ✅ |
| REST API | ✅ |
| No Docker required | ✅ |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS)                   │
│                    Dashboard UI                         │
└────────────────────────┬───────────────────────────────┘
                         │ REST API
┌────────────────────────▼───────────────────────────────┐
│                    FastAPI Backend                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Auth Routes  │  │  Post Routes │  │  Media Serve │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│  ┌──────▼─────────────────▼─────────────────▼───────┐  │
│  │              Agent Orchestrator (CrewAI)          │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │  │
│  │  │  Video   │ │ Caption  │ │Scheduler │ │ Insta │ │  │
│  │  │Processor │ │  Agent   │ │  Agent   │ │Publisher│ │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘ │  │
│  └───────┼────────────┼────────────┼───────────┼──────┘  │
│          │            │            │           │          │
│  ┌───────▼────────────▼────────────▼───────────▼──────┐  │
│  │                  Services Layer                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │  │
│  │  │  FFmpeg  │ │  Caption │ │ Instagram│ │APSchd. │ │  │
│  │  │ Service  │ │ Service  │ │  Client  │ │Service │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │           Database (SQLite + APScheduler)           │   │
│  │  Accounts │ Uploads │ Segments │ Scheduled Posts    │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

- **Python 3.10+**
- **FFmpeg** (for video splitting)
  ```bash
  # Linux
  sudo apt install ffmpeg

  # macOS
  brew install ffmpeg

  # Windows
  choco install ffmpeg
  ```
- **Instagram Business/Creator Account** (linked to a Facebook Page)
- **Facebook Developer Account** (for API credentials)

---

## 🔧 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/punithkrishnakeepudi/video-to-reels.git
cd reelforge

pip install -r backend/requirements.txt
```

### 2. Set Up Instagram API (Get API Keys)

You need a Facebook App with Instagram Graph API enabled:

1. Go to [Facebook Developers](https://developers.facebook.com/apps/)
2. Create a new **Business** app
3. Add **Instagram Graph API** product
4. Go to **Settings > Basic** to get your **App ID** and **App Secret**
5. Add `http://localhost:8000/api/auth/instagram/callback` as an OAuth redirect URI
6. (Optional for testing) Add your Instagram account as a **Test User**

### 3. Configure Environment

```bash
cp backend/.env.example backend/.env
# Edit .env with your credentials
```

Minimum required in `.env`:
```env
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret

# Pick one caption provider:
CAPTION_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
# OR
# CAPTION_PROVIDER=ollama
# OLLAMA_MODEL=llama3
```

### 4. Run

```bash
cd backend
python main.py
```

Open **http://localhost:8000** for the dashboard.

---

## 📖 Usage Guide

### Connecting Instagram

1. Click **"+ Connect Instagram"** in the top nav
2. A Facebook Login popup appears
3. Authorize the app with your Instagram Business/Creator account
4. Close the popup and refresh the page

### Uploading & Processing

1. Select your Instagram account from the Upload tab
2. Drag & drop a video or click to browse
3. Wait for upload to complete
4. Click **"Split into Reels"**
5. The video is split into 30-second segments with AI-generated captions

### Editing Segments

- ✏️ **Edit** — Change caption and hashtags
- 🔄 **Caption** — Regenerate caption with AI
- 📅 **Schedule** — Set a posting time
- 🗑️ **Delete** — Remove segment

### Scheduling Posts

1. Click **"Schedule"** on any segment
2. Pick a date and time (UTC)
3. The post is saved to persistent storage
4. **Even if the server restarts**, the post will be published at the scheduled time

### Managing Schedules

- View all posts in the **Schedule** tab
- **Reschedule** — Change the posting time
- **Cancel** — Remove a scheduled post
- **Retry** — Re-attempt failed posts

---

## 🧠 Agentic Framework

ReelForge uses **CrewAI** to orchestrate specialized AI agents:

### Agents

| Agent | Role | Tools |
|-------|------|-------|
| 🎬 **VideoProcessorAgent** | Video editor | FFmpeg splitting, metadata analysis |
| ✍️ **CaptionAgent** | Social media copywriter | AI caption generation (3 providers) |
| 📅 **SchedulerAgent** | Content scheduling coordinator | APScheduler, persistent job management |
| 📤 **InstagramPublisherAgent** | IG publishing specialist | Graph API container creation & publishing |

### Workflow (end-to-end)

```
User Uploads Video
       │
       ▼
[VideoProcessorAgent] — Splits into 30s segments via FFmpeg
       │
       ▼
[CaptionAgent] — Generates AI captions + hashtags
       │
       ▼
[User Edits] — Reviews and refines captions
       │
       ▼
[SchedulerAgent] — Schedules at user-defined time
       │
       ▼
[APScheduler] — Persistent job store (survives restarts)
       │
       ▼
[InstagramPublisherAgent] — Publishes at scheduled time
```

---

## 🌐 API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/instagram/login` | GET | Get Instagram OAuth URL |
| `/api/auth/instagram/callback` | GET | Handle OAuth callback |
| `/api/auth/instagram/accounts` | GET | List connected accounts |
| `/api/auth/instagram/accounts/{id}` | DELETE | Disconnect account |

### Video Posts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/posts/upload` | POST | Upload video |
| `/api/posts/{id}/process` | POST | Split into segments + captions |
| `/api/posts/uploads` | GET | List uploads |
| `/api/posts/uploads/{id}` | DELETE | Delete upload |

### Segments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/posts/segments` | GET | List segments |
| `/api/posts/segments/{id}` | PATCH | Edit segment (caption, hashtags) |
| `/api/posts/segments/{id}` | DELETE | Delete segment |
| `/api/posts/segments/{id}/regenerate-caption` | POST | Regenerate caption |

### Scheduling

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/posts/schedule` | POST | Schedule a post |
| `/api/posts/schedule` | GET | List scheduled posts |
| `/api/posts/schedule/{id}` | PATCH | Update scheduled post |
| `/api/posts/schedule/{id}` | DELETE | Cancel scheduled post |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Health check + config status |
| `/api/scheduler/status` | GET | Scheduler info |

---

## 🛠️ Development

### Project Structure

```
video-to-reel/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Environment config
│   ├── database.py          # SQLAlchemy models
│   ├── models.py            # Pydantic schemas
│   ├── api/
│   │   ├── routes.py        # Main API router
│   │   ├── auth_routes.py   # Instagram OAuth
│   │   └── post_routes.py   # Post management
│   ├── agents/
│   │   ├── orchestrator.py  # CrewAI orchestration
│   │   ├── video_processor.py
│   │   ├── caption_agent.py
│   │   ├── instagram_publisher.py
│   │   └── scheduler_agent.py
│   ├── services/
│   │   ├── video_service.py
│   │   ├── caption_service.py
│   │   ├── instagram_client.py
│   │   └── scheduler_service.py
│   ├── utils/
│   │   └── helpers.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html           # Dashboard UI
├── uploads/                 # Uploaded videos & segments
├── reelforge.db             # SQLite database
└── scheduler_jobs.db        # APScheduler job store
```

---

## ⚙️ Configuration

All configuration is via environment variables (`.env` file).

| Variable | Default | Description |
|----------|---------|-------------|
| `FACEBOOK_APP_ID` | — | Facebook App ID (required) |
| `FACEBOOK_APP_SECRET` | — | Facebook App Secret (required) |
| `CAPTION_PROVIDER` | `openai` | `openai`, `anthropic`, `ollama`, or `none` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `REEL_DURATION_SECONDS` | `30` | Length of each segment |
| `MAX_UPLOAD_SIZE_MB` | `500` | Max upload size |
| `DATABASE_URL` | `sqlite:///./reelforge.db` | Database URL |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Public server URL |

---

## 🔒 Important Notes

### Instagram API Requirements

- Your Instagram account **must be a Business or Creator account** linked to a Facebook Page
- The Facebook App needs **Instagram Graph API** enabled
- For production use, your app needs **Facebook App Review** (takes a few days)
- For local testing, use **Test Users** in your Facebook App dashboard

### Posting Limits

- Instagram API allows **100 posts per 24-hour rolling window** per account
- Videos must be **3 seconds to 60 minutes** long
- Caption limit: **2,200 characters**
- Supported formats: MP4 (recommended), MOV, AVI, MKV, WebM

### Scheduling Persistence

The scheduler uses **APScheduler with SQLite storage**:
- Jobs are stored in `scheduler_jobs.db`
- **Survives server restarts** — jobs are reloaded on boot
- **Misfire grace time**: 1 hour (jobs run if server was down ≤1 hour)
- **Coalescing**: Duplicate missed runs are combined into one

---

## 📄 License

MIT License — free for personal and commercial use.

---

## 🙏 Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewai) — Multi-agent orchestration framework
- [FastAPI](https://fastapi.tiangolo.com/) — Python web framework
- [APScheduler](https://apscheduler.readthedocs.io/) — Persistent task scheduling
- [FFmpeg](https://ffmpeg.org/) — Video processing
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-platform/) — Content publishing

---

<div align="center">
  <p>Built with ❤️ for content creators</p>
</div>
