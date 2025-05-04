import os
import asyncio
import logging
import re
import json
from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from src.text_processing import clean_text, detect_language
from src import GOOGLE_API_KEY  # Import from src package

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.7

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=DEFAULT_TEMPERATURE,
    max_retries=3
)

def format_summary(summary_data: Dict[str, Any]) -> str:
    """Format the summary with explicit markdown for Telegram compatibility."""
    try:
        # Start with the title
        formatted_text = f"*{summary_data['title']}*\n\n"
        
        for point in summary_data['points']:
            formatted_text += f"*{point['title']}*\n"
            
            key_points_text = ", ".join([f"*{key_point}*" for key_point in point['key_points']])
            formatted_text += f"{key_points_text}\n"
            
            # Summary (italic)
            summary_text = point['summary'].replace('*', '').replace('_', '')
            formatted_text += f"_{summary_text}_\n\n"
        
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        formatted_text = re.sub(r'(\w)\*(\w)', r'\1 *\2', formatted_text)
        formatted_text = re.sub(r'(\w)\*(\s)', r'\1* \2', formatted_text)
        
        formatted_text = re.sub(r'(\w)_(\w)', r'\1 _\2', formatted_text)
        formatted_text = re.sub(r'(\w)_(\s)', r'\1_ \2', formatted_text)
        
        return formatted_text.strip()
    except Exception as e:
        logger.error(f"Error in formatting summary: {e}")
        return str(summary_data)

async def generate_summary(text: str, user_language: str = None, style: str = "medium") -> str:
    try:
        cleaned_text = clean_text(text)
        
        style_instructions = {
            "short": "Create a very concise summary with 2-3 main points. Each point should have a bold title, key points in bold, and a brief italic summary.",
            "medium": "Create a balanced summary with 4-6 main points. Each point should have a bold title, key points in bold, and a detailed italic summary.",
            "long": "Create a comprehensive summary with 7-10 main points. Each point should have a bold title, key points in bold, and a thorough italic summary."
        }
        
        system_prompt = f"""You are an expert document summarizer that creates well-structured summaries.

IMPORTANT: Your summary MUST follow these requirements:
- Return the summary in JSON format with this structure:
{{
    "title": "Main Title",
    "points": [
        {{
            "title": "Point 1 Title",
            "key_points": ["Key Point 1", "Key Point 2"],
            "summary": "Summary of point 1"
        }},
        {{
            "title": "Point 2 Title",
            "key_points": ["Key Point 1", "Key Point 2"],
            "summary": "Summary of point 2"
        }}
    ]
}}
- Maintain the original language of the text
- Write in clear, natural language

Style requirements:
{style_instructions[style]}"""
        
        user_prompt = f"""Please create a well-structured summary of this text following the specified style:

{cleaned_text}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await asyncio.to_thread(
            lambda: llm.invoke(messages).content
        )
        
        try:
            # Extract JSON from response if needed (sometimes models wrap JSON in text)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|(\{[\s\S]*\})', response)
            if json_match:
                json_str = json_match.group(1) or json_match.group(2)
            else:
                json_str = response
                
            # Parse the JSON response
            summary_data = json.loads(json_str)
            
            # Format the summary with proper markdown
            return format_summary(summary_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            cleaned_response = re.sub(r'```json|```', '', response).strip()
            return cleaned_response
        
    except Exception as e:
        logger.error(f"Error in LLM summarization: {e}")
        raise