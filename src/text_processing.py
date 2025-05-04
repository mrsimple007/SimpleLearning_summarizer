import logging
from datetime import datetime
import re
from typing import Optional

logger = logging.getLogger(__name__)

MAX_TOKEN_LIMIT = 30000

def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def truncate_text(text: str, max_length: int = 3000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

async def truncate_text(text: str, max_length: int = 16000) -> str:
    """Truncate text to max_length while preserving word boundaries."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0]

def clean_text(text: str) -> str:
    """Clean text from garbage characters and normalize spacing."""
    text = re.sub(r'[^\w\s\.,!?;:\'\"()\[\]{}\-–—/]', ' ', text)
    
    text = re.sub(r'\s+', ' ', text)
    
    text = re.sub(r'\s[_\-–—/]\s', ' ', text)
    
    patterns = [
        r'/\d+["\']',  
        r'_[a-zA-Z]+<', 
        r'>[a-zA-Z]+\s',  # Matches patterns like >l
        r'\s[a-zA-Z]\s',  # Single letters
        r'[<>]',  # Remove < and >
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, ' ', text)
    
    # Clean up the result
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text

def detect_language(text: str) -> str:
    cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    uzbek = len(re.findall(r'[ўқғҳ]', text))
    
    if uzbek > 0 or ('oʻzbek' in text.lower()):
        return 'uz'
    elif cyrillic > latin:
        return 'ru'
    else:
        return 'en' 