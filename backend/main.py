import subprocess
import re
import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "Video to Reel API is running"}

def get_video_info(url: str):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # Don't specify format here, we just want metadata
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print(f"Analyzing URL: {url}")
            info = ydl.extract_info(url, download=False)
            
            # Duration can sometimes be None for live streams or certain formats
            duration = info.get('duration') or 0
            
            return {
                "title": info.get('title', 'Unknown Title'),
                "duration": float(duration),
                "thumbnail": info.get('thumbnail'),
                "url": url
            }
        except Exception as e:
            print(f"yt-dlp error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/analyze")
async def analyze(url: str):
    info = get_video_info(url)
    return JSONResponse(content=info)

@app.get("/stream")
async def stream_video(url: str, start: float = 0, duration: float = None, mode: str = "video"):
    """
    Streams video/audio using ffmpeg pipeline.
    """
    # Use a broad format selection that is more likely to return a direct URL
    format_selector = 'best[ext=mp4]/best' if mode == "video" else 'bestaudio/best'
    
    ydl_opts = {
        'quiet': True,
        'format': format_selector,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url')
            
            if not stream_url:
                # Try getting the first format's URL if top-level url is missing
                formats = info.get('formats', [])
                if formats:
                    stream_url = formats[0].get('url')
            
            if not stream_url:
                raise HTTPException(status_code=400, detail="Could not extract stream URL from video")
                
        ffmpeg_cmd = [
            'ffmpeg',
            '-ss', str(start),
            '-i', stream_url,
        ]
        
        if duration:
            ffmpeg_cmd.extend(['-t', str(duration)])
            
        if mode == "audio":
            ffmpeg_cmd.extend(['-f', 'mp3', '-'])
            media_type = "audio/mpeg"
        else:
            ffmpeg_cmd.extend([
                '-f', 'mp4',
                '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                '-vcodec', 'libx264',
                '-acodec', 'aac',
                '-pix_fmt', 'yuv420p',
                '-preset', 'veryfast',
                '-crf', '28',
                '-'
            ])
            media_type = "video/mp4"

        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def iterfile():
            try:
                while True:
                    chunk = process.stdout.read(4096 * 32)
                    if not chunk:
                        break
                    yield chunk
            finally:
                process.stdout.close()
                process.terminate()

        return StreamingResponse(iterfile(), media_type=media_type)
    except Exception as e:
        print(f"Streaming error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_analyze")
async def upload_analyze(file: UploadFile = File(...)):
    # Save temporarily to get duration
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Get duration using ffprobe
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-show_entries', 'format=duration', 
        '-of', 'default=noprint_wrappers=1:nokey=1', 
        temp_path
    ]
    duration = subprocess.check_output(cmd).decode().strip()
    
    # We'll need to keep the file for a bit if we want to stream it
    # For a real implementation, we might want a session-based cleanup
    return JSONResponse(content={
        "title": file.filename,
        "duration": float(duration),
        "temp_path": temp_path
    })

@app.get("/stream_local")
async def stream_local(path: str, start: float = 0, duration: float = None, mode: str = "video"):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    ffmpeg_cmd = [
        'ffmpeg',
        '-ss', str(start),
        '-i', path,
    ]
    
    if duration:
        ffmpeg_cmd.extend(['-t', str(duration)])
        
    if mode == "audio":
        ffmpeg_cmd.extend(['-f', 'mp3', '-'])
        media_type = "audio/mpeg"
    else:
        ffmpeg_cmd.extend([
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-vcodec', 'libx264',
            '-acodec', 'aac',
            '-pix_fmt', 'yuv420p',
            '-preset', 'veryfast',
            '-'
        ])
        media_type = "video/mp4"

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def iterfile():
        while True:
            chunk = process.stdout.read(4096 * 32)
            if not chunk:
                break
            yield chunk
        process.stdout.close()
        process.wait()

    return StreamingResponse(iterfile(), media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
