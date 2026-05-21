# Video to Reel - Deployment Guide

This project consists of a FastAPI backend and a static HTML frontend.

## Prerequisites

- **Python 3.10+**
- **FFmpeg & FFprobe**: Required for video processing and metadata extraction.
- **Node.js**: Required by `yt-dlp` as a JavaScript runtime for YouTube signature extraction. Install via `sudo apt install nodejs`.

## 1. Backend Deployment (Render / Vercel)

### Option A: Render (Recommended for Python)
1. Create a new "Web Service" on [Render](https://render.com/).
2. Connect your GitHub repository.
3. Use the following settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   - Ensure `ffmpeg` and `ffprobe` are available. Render's default Python environment usually includes them, or you can add a `render.yaml` with `plan: free` and specify `ffmpeg` in the build steps if needed. Most often, they are pre-installed.
5. Copy your Render service URL (e.g., `https://video-to-reel-api.onrender.com`).

### Option B: Vercel (Requires Serverless Functions)
Vercel is trickier for long-running streaming and `ffmpeg`. Render is highly recommended for this specific project.

---

## 2. Frontend Deployment (GitHub Pages)

1. Open `frontend/index.html`.
2. Locate the `API_BASE` constant in the `<script>` tag:
   ```javascript
   const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'YOUR_RENDER_URL_HERE';
   ```
3. Replace `'YOUR_RENDER_URL_HERE'` with your actual backend URL from Render.
4. Push your code to GitHub.
5. Go to your Repo **Settings > Pages**.
6. Select the `main` branch and the `/frontend` folder (or just push the `index.html` to the root).
7. Your site will be live at `https://your-username.github.io/video-to-reel`.

---

## 3. Local Development

1. **Start Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```
2. **Open Frontend**:
   Simply open `frontend/index.html` in your browser.

## Technical Notes
- **Streaming**: The app uses `ffmpeg` pipeline streaming. It does not save the full video to the server disk (except for temporary metadata extraction on uploads).
- **CORS**: The backend is configured to allow all origins, enabling the GitHub Pages frontend to communicate with the Render backend.
- **Formats**: YouTube links are resolved to the best MP4 quality available.
