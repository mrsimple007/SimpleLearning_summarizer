import os
import logging
from io import BytesIO
import docx2txt
import PyPDF2
import re

logger = logging.getLogger(__name__)

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()

def is_valid_file_type(filename: str, supported_types: list) -> bool:
    return get_file_extension(filename) in supported_types

def get_file_type_category(filename: str) -> str:
    ext = get_file_extension(filename)
    if ext in [".pdf", ".docx", ".txt"]:
        return "document"
    elif ext in [".mp3", ".wav", ".ogg", ".m4a"]:
        return "audio"
    elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
        return "video"
    return None

def format_file_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

async def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with BytesIO(file_bytes) as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    page_text = re.sub(r'/\d+"\'.*?\w+\s*[<>].*?[\(\),\.\-]', ' ', page_text)
                    page_text = re.sub(r'KELISHILDI:.*?:', '', page_text)
                    text += page_text + "\n\n"
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
    return text

async def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        with BytesIO(file_bytes) as file:
            text = docx2txt.process(file)
            return text
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""

async def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8")
        return text
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("cp1251")
            return text
        except Exception as e:
            logger.error(f"Error decoding TXT file: {e}")
            return ""
    except Exception as e:
        logger.error(f"Error extracting text from TXT: {e}")
        return ""