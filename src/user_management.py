import os
import logging
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

from src.prompts_summarize import TRANSLATIONS

def get_tashkent_time():
    tashkent_tz = timezone(timedelta(hours=5))
    return datetime.now(tashkent_tz).isoformat()

def get_translation(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"][key])

async def get_user_language(user_id: int) -> str:
    try:
        response = supabase.table('simplelearn_users').select('language').eq('user_id', str(user_id)).execute()
        if response.data and len(response.data) > 0 and 'language' in response.data[0]:
            return response.data[0]['language']
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
    return "en"

async def update_user_language(user_id: int, language: str) -> None:
    try:
        current_time = get_tashkent_time()
        response = supabase.table('simplelearn_users').select('user_id').eq('user_id', str(user_id)).execute()
        
        if response.data and len(response.data) > 0:
            supabase.table('simplelearn_users').update({
                'language': language,
                'last_interaction': current_time
            }).eq('user_id', str(user_id)).execute()
        else:
            supabase.table('simplelearn_users').insert({
                'user_id': str(user_id),
                'language': language,
                'created_at': current_time,
                'last_interaction': current_time,
                'is_premium': False
            }).execute()
            
        logger.info(f"Updated language to {language} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user language: {e}")

async def update_user_activity(user) -> None:
    try:
        current_time = get_tashkent_time()
        user_data = {
            'user_id': str(user.id),
            'first_name': user.first_name,
            'last_name': user.last_name if hasattr(user, 'last_name') else None,
            'username': user.username if hasattr(user, 'username') else None,
            'last_interaction': current_time
        }
        
        # Update user data in simplelearn_users table
        supabase.table('simplelearn_users').upsert(user_data, on_conflict='user_id').execute()
        
        logger.info(f"Updated user activity for user {user.id}")
    except Exception as e:
        logger.error(f"Error updating user activity: {e}")

async def get_total_users() -> int:
    try:
        response = supabase.table('simplelearn_users').select('user_id', count='exact').execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting total users: {e}")
        return 0

async def update_user_premium_status(user_id: int, is_premium: bool) -> None:
    try:
        current_time = get_tashkent_time()
        user_data = {
            'is_premium': is_premium,
            'last_interaction': current_time
        }
        
        # Update both tables
        supabase.table('simplelearn_users').update(user_data).eq('user_id', str(user_id)).execute()
        supabase.table('simplequizzer_users').update(user_data).eq('user_id', str(user_id)).execute()
        
        logger.info(f"Updated premium status to {is_premium} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user premium status: {e}")

async def get_user_premium_status(user_id: int) -> bool:
    try:
        response = supabase.table('simplelearn_users').select('is_premium').eq('user_id', str(user_id)).execute()
        if response.data and len(response.data) > 0 and 'is_premium' in response.data[0]:
            return response.data[0]['is_premium']
    except Exception as e:
        logger.error(f"Error getting user premium status: {e}")
    return False

async def get_total_premium_users() -> int:
    try:
        response = supabase.table('simplelearn_users').select('user_id', count='exact').eq('is_premium', True).execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting total premium users: {e}")
        return 0

async def get_user_summary_style(user_id: int) -> str:
    try:
        response = supabase.table('simplelearn_users').select('summary_style').eq('user_id', str(user_id)).execute()
        if response.data and len(response.data) > 0 and 'summary_style' in response.data[0]:
            return response.data[0]['summary_style']
    except Exception as e:
        logger.error(f"Error getting user summary style: {e}")
    return "medium"  # Default to medium

async def update_user_summary_style(user_id: int, style: str) -> None:
    try:
        if style not in ['short', 'medium', 'long']:
            logger.error(f"Invalid summary style: {style}")
            return
            
        current_time = get_tashkent_time()
        user_data = {
            'user_id': str(user_id),
            'summary_style': style,
            'last_interaction': current_time
        }
        
        logger.info(f"Attempting to update summary style for user {user_id} with data: {user_data}")
        
        # First check if user exists
        response = supabase.table('simplelearn_users').select('user_id').eq('user_id', str(user_id)).execute()
        logger.info(f"User exists check response: {response.data}")
        
        if response.data and len(response.data) > 0:
            # User exists, update the style
            update_response = supabase.table('simplelearn_users').update({
                'summary_style': style,
                'last_interaction': current_time
            }).eq('user_id', str(user_id)).execute()
            logger.info(f"Update response: {update_response.data}")
        else:
            # User doesn't exist, insert new record
            insert_response = supabase.table('simplelearn_users').insert(user_data).execute()
            logger.info(f"Insert response: {insert_response.data}")
        
        # Also update simplequizzer_users table
        quizzer_response = supabase.table('simplequizzer_users').select('user_id').eq('user_id', str(user_id)).execute()
        logger.info(f"Quizzer user exists check response: {quizzer_response.data}")
        
        if quizzer_response.data and len(quizzer_response.data) > 0:
            quizzer_update = supabase.table('simplequizzer_users').update({
                'summary_style': style,
                'last_interaction': current_time
            }).eq('user_id', str(user_id)).execute()
            logger.info(f"Quizzer update response: {quizzer_update.data}")
        else:
            quizzer_insert = supabase.table('simplequizzer_users').insert(user_data).execute()
            logger.info(f"Quizzer insert response: {quizzer_insert.data}")
        
        logger.info(f"Successfully updated summary style to {style} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user summary style: {e}")
        raise  # Re-raise the exception to handle it in the calling function 

# SQL for creating the processed_files_simplelearn table
"""
CREATE TABLE IF NOT EXISTS processed_files_simplelearn (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    processing_time INTEGER NOT NULL,  -- in seconds
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT NOT NULL,  -- 'success' or 'error'
    error_message TEXT,    -- NULL if successful
    FOREIGN KEY (user_id) REFERENCES simplelearn_users(user_id)
);

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_processed_files_user_id ON processed_files_simplelearn(user_id);
CREATE INDEX IF NOT EXISTS idx_processed_files_created_at ON processed_files_simplelearn(created_at);
"""

async def track_processed_file(
    user_id: int,
    file_type: str,
    file_size: int,
    processing_time: int,
    status: str = 'success',
    error_message: Optional[str] = None
) -> None:
    """
    Track a processed file in the database.
    
    Args:
        user_id: The user's ID
        file_type: Type of file (video, audio, document, text, url)
        file_size: Size of the file in bytes
        processing_time: Time taken to process in seconds
        status: 'success' or 'error'
        error_message: Error message if status is 'error'
    """
    try:
        current_time = get_tashkent_time()
        
        # Convert file size from bytes to KB (integer)
        file_size_kb = int(file_size / 1024)  # Convert bytes to KB
        
        # Ensure processing time is in seconds
        if processing_time < 1:
            processing_time = 1  # Minimum 1 second
            
        data = {
            'user_id': str(user_id),
            'file_type': file_type,
            'file_size': file_size_kb,  # Store size in KB
            'processing_time': processing_time,
            'created_at': current_time,
            'status': status,
            'error_message': error_message
        }
        
        response = supabase.table('processed_files_simplelearn').insert(data).execute()
        logger.info(f"Tracked processed file for user {user_id}: {response.data}")
    except Exception as e:
        logger.error(f"Error tracking processed file: {e}")

async def get_user_processed_files_count(user_id: int) -> int:
    """Get the total number of files processed by a user"""
    try:
        response = supabase.table('processed_files_simplelearn').select('id', count='exact').eq('user_id', str(user_id)).execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting processed files count: {e}")
        return 0

async def get_user_processed_files_stats(user_id: int) -> dict:
    """Get statistics about user's processed files"""
    try:
        # Get total count
        total_response = supabase.table('processed_files_simplelearn').select('id', count='exact').eq('user_id', str(user_id)).execute()
        total_count = total_response.count if total_response.count is not None else 0
        
        # Get success count
        success_response = supabase.table('processed_files_simplelearn').select('id', count='exact').eq('user_id', str(user_id)).eq('status', 'success').execute()
        success_count = success_response.count if success_response.count is not None else 0
        
        # Get file type distribution
        type_response = supabase.table('processed_files_simplelearn').select('file_type', count='exact').eq('user_id', str(user_id)).group_by('file_type').execute()
        type_distribution = {item['file_type']: item['count'] for item in type_response.data} if type_response.data else {}
        
        # Get average processing time
        time_response = supabase.table('processed_files_simplelearn').select('processing_time').eq('user_id', str(user_id)).eq('status', 'success').execute()
        processing_times = [item['processing_time'] for item in time_response.data] if time_response.data else []
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            'total_files': total_count,
            'successful_files': success_count,
            'failed_files': total_count - success_count,
            'file_type_distribution': type_distribution,
            'average_processing_time': avg_processing_time
        }
    except Exception as e:
        logger.error(f"Error getting processed files stats: {e}")
        return {
            'total_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'file_type_distribution': {},
            'average_processing_time': 0
        } 

async def get_total_processed_files() -> int:
    """Get the total number of processed files"""
    try:
        response = supabase.table('processed_files_simplelearn').select('id', count='exact').execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting total processed files: {e}")
        return 0

async def get_success_rate() -> float:
    """Calculate the success rate of file processing"""
    try:
        # Get total count
        total_response = supabase.table('processed_files_simplelearn').select('id', count='exact').execute()
        total_count = total_response.count if total_response.count is not None else 0
        
        if total_count == 0:
            return 100.0  # If no files processed yet, return 100%
            
        # Get success count
        success_response = supabase.table('processed_files_simplelearn').select('id', count='exact').eq('status', 'success').execute()
        success_count = success_response.count if success_response.count is not None else 0
        
        return (success_count / total_count) * 100
    except Exception as e:
        logger.error(f"Error calculating success rate: {e}")
        return 0.0 

async def get_todays_active_users() -> int:
    """Get the number of users who interacted with the bot today"""
    try:
        # Get today's date in Tashkent timezone
        tashkent_tz = timezone(timedelta(hours=5))
        today = datetime.now(tashkent_tz).date()
        today_start = datetime.combine(today, datetime.min.time(), tzinfo=tashkent_tz)
        today_end = datetime.combine(today, datetime.max.time(), tzinfo=tashkent_tz)
        
        # Query users who interacted today
        response = supabase.table('simplelearn_users') \
            .select('user_id', count='exact') \
            .gte('last_interaction', today_start.isoformat()) \
            .lte('last_interaction', today_end.isoformat()) \
            .execute()
            
        return response.count if response.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting today's active users: {e}")
        return 0 