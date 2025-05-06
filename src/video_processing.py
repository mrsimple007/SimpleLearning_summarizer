import os
import logging
import uuid
import asyncio
import tempfile
from typing import Tuple, Optional, Dict, Any
from moviepy import VideoFileClip
from src.audio_processing import extract_text_from_audio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.DEBUG,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("Script started - checking if logging works")
logger.debug("Debug logging test")
logger.info("Info logging test")
logger.warning("Warning logging test")
logger.error("Error logging test")

async def process_video_file(video_bytes: bytes, api_key: str, output_format: str = "mp3") -> Tuple[bool, str, Optional[str]]:
    """Process video file and extract text using audio transcription."""
    if not api_key:
        return False, "ElevenLabs API key is required", None
    
    try:
        # Save video bytes to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_video.write(video_bytes)
            video_path = temp_video.name
        
        # Create temporary audio file path
        audio_path = tempfile.mktemp(suffix=f'.{output_format}')
        
        try:
            # Extract audio using MoviePy
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(
                audio_path,
                fps=44100,
                nbytes=2,
                codec='libmp3lame' if output_format == "mp3" else output_format,
                bitrate='192k'
            )
            video.close()
            
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