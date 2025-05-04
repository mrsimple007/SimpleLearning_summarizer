import os
import logging
import uuid
import asyncio
import tempfile
import subprocess
import shutil
from typing import Tuple, Optional, Dict, Any
from src.audio_processing import extract_text_from_audio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.DEBUG,  # Change from INFO to DEBUG
    handlers=[
        logging.StreamHandler()  # Explicitly add a stream handler
    ]
)
logger = logging.getLogger(__name__)

print("Script started - checking if logging works")
logger.debug("Debug logging test")
logger.info("Info logging test")
logger.warning("Warning logging test")
logger.error("Error logging test")

# Define FFmpeg paths for different operating systems
FFMPEG_PATHS = {
    'win32': [
        r"C:\Program Files (x86)\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe"
    ],
    'linux': ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg'],
    'darwin': ['/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']
}

def check_ffmpeg_installed() -> bool:
    """Check if FFmpeg is installed and accessible."""
    # First try the system PATH
    if shutil.which('ffmpeg'):
        return True
        
    # If not in PATH, try specific paths for the current OS
    system = os.name
    if system == 'nt':  # Windows
        paths = FFMPEG_PATHS['win32']
    elif system == 'posix':  # Linux or macOS
        if os.uname().sysname == 'Darwin':  # macOS
            paths = FFMPEG_PATHS['darwin']
        else:  # Linux
            paths = FFMPEG_PATHS['linux']
    else:
        paths = []
        
    # Check each possible path
    for path in paths:
        if os.path.exists(path):
            # Add the directory to PATH temporarily
            os.environ['PATH'] = os.path.dirname(path) + os.pathsep + os.environ['PATH']
            return True
            
    return False

async def process_video_file(video_bytes: bytes, api_key: str, output_format: str = "mp3") -> Tuple[bool, str, Optional[str]]:
    """Process video file and extract text using audio transcription."""
    if not api_key:
        return False, "ElevenLabs API key is required", None
    
    # Check if FFmpeg is installed
    if not check_ffmpeg_installed():
        return False, "FFmpeg not found. Please install FFmpeg to process video files.\n\nInstallation instructions:\n\n" + \
               "Windows:\n" + \
               "1. Download FFmpeg from https://ffmpeg.org/download.html\n" + \
               "2. Extract the downloaded file\n" + \
               "3. Add the bin folder to your system PATH\n\n" + \
               "Linux:\n" + \
               "sudo apt-get update\n" + \
               "sudo apt-get install ffmpeg\n\n" + \
               "macOS:\n" + \
               "brew install ffmpeg", None
    
    try:
        # Save video bytes to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_video.write(video_bytes)
            video_path = temp_video.name
        
        # Create temporary audio file path
        audio_path = tempfile.mktemp(suffix=f'.{output_format}')
        
        try:
            # Extract audio using ffmpeg
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # No video
                "-acodec", "libmp3lame" if output_format == "mp3" else output_format,
                "-ar", "44100",  # Audio rate
                "-ac", "2",      # Audio channels
                "-b:a", "192k",  # Bitrate
                "-y",           # Overwrite output file
                audio_path
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"FFmpeg error: {error_msg}")
                return False, f"Error extracting audio: {error_msg}", None
            
            # Read the extracted audio
            with open(audio_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            
            # Transcribe the audio
            success, message, transcript = await extract_text_from_audio(audio_bytes, api_key)
            
            return success, message, transcript
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(video_path)
            except:
                pass
            try:
                os.unlink(audio_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return False, f"Error processing video: {str(e)}", None