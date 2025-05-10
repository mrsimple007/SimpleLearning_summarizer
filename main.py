import os
import logging
from datetime import datetime
import asyncio
import re
import tempfile
import psutil
from typing import Set, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut, NetworkError

from src.prompts_summarize import LANGUAGES, TRANSLATIONS
from src.llm_service import generate_summary
from src.audio_processing import extract_text_from_audio, save_transcription_to_temp_file
from src.document_processing import *
from src.web_processing import *
from src.user_management import *
from src.text_processing import *
from src import ELEVENLABS_API_KEY
from payment_integration import setup_payment_handlers, upgrade_command

# Resource management
BASE_FILE_SIZE = {
    'video': 20 * 1024 * 1024,  # 20MB base
    'audio': 10 * 1024 * 1024,  # 10MB base
    'document': 15 * 1024 * 1024  # 15MB base
}

PREMIUM_MULTIPLIER = 2  # Premium users get 2x the base limit

MAX_MEMORY_PER_FILE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_MEMORY = 200 * 1024 * 1024  # 200MB

# Track resources
active_tasks: Set[asyncio.Task] = set()
temp_files: Set[str] = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

logger.info(f"ELEVENLABS_API_KEY present: {bool(ELEVENLABS_API_KEY)}")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_SIMPLELEARNING", "")

LANGUAGE, CONTENT, PROCESSING, STYLE = range(4)

# Resource management functions
def check_memory_usage() -> float:
    """Check current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # Memory usage in MB


async def cleanup_resources() -> None:
    """Clean up all temporary resources"""
    # Clean up temporary files
    for temp_file in temp_files.copy():
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            temp_files.remove(temp_file)
        except Exception as e:
            logger.error(f"Error removing temp file {temp_file}: {e}")
    
    # Cancel and clean up background tasks
    for task in active_tasks.copy():
        try:
            task.cancel()
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
        finally:
            active_tasks.remove(task)

def create_temp_file(suffix: str = None) -> str:
    """Create a temporary file and track it"""
    temp_path = tempfile.mktemp(suffix=suffix)
    temp_files.add(temp_path)
    return temp_path

def get_file_size_limit(file_type: str, is_premium: bool) -> int:
    base_limit = BASE_FILE_SIZE.get(file_type, 0)
    if is_premium:
        return base_limit * PREMIUM_MULTIPLIER
    return base_limit



async def check_user_exists(user_id: int) -> bool:
    try:
        response = supabase.table('simplelearn_users') \
            .select('user_id') \
            .eq('user_id', str(user_id)) \
            .execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error checking simplelearn user existence: {e}")
        return False

async def create_new_user (
    user_id: int, 
    username: str = None, 
    first_name: str = None, 
    last_name: str = None, 
    language: str = "en"
) -> bool:
    try:
        current_time = get_tashkent_time()
        response = supabase.table('simplelearn_users').insert({
            'user_id': str(user_id),
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'language': language,
            'created_at': current_time,
            'last_interaction': current_time,
            'is_premium': False
        }).execute()
        logger.info(f"Created new simplelearn user with ID {user_id}")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error creating new simplelearn user: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_chat_action("typing")

    # Check if user exists in simplelearn_users, create if not
    user_exists = await check_user_exists(user.id)
    if not user_exists:
        await create_new_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language="en"
        )

    await update_user_activity(user)

    # Admin dashboard
    if str(user.id) == "999932510":
        total_users = await get_total_users()
        total_processed_files = await get_total_processed_files()
        total_processed_files += 20  # Add the initial count
        todays_active_users = await get_todays_active_users()

        admin_message = (
            "👑 *Admin Dashboard*\n\n"
            f"📊 Total Users: {total_users}\n"
            f"👥 Active Users Today: {todays_active_users}\n"
            f"📝 Total Processed Files: {total_processed_files}\n\n"
            "📈 *Statistics:*\n"
            f"• Average files per user: {total_processed_files/total_users:.1f}\n"
            f"• Success rate: {await get_success_rate():.1f}%"
        )
        await update.message.reply_text(
            text=admin_message,
            parse_mode=ParseMode.MARKDOWN
        )

    # Get user language
    language = await get_user_language(user.id)

    # If language is not set, show language selection
    if not language:
        keyboard = [
            [InlineKeyboardButton(text, callback_data=f"lang_{code}")]
            for code, text in LANGUAGES.items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            get_translation("en", "choose_language"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return LANGUAGE

    # If user exists and has a language set, show welcome message
    await update.message.reply_text(
        text=get_translation(language, "welcome"),
        parse_mode=ParseMode.MARKDOWN
    )
    return CONTENT

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language_code = query.data.split('_')[1]
    
    logger.info(f"User {user.id} selected language: {language_code}")
    
    await update_user_language(user.id, language_code)
    
    await query.edit_message_text(
        text=get_translation(language_code, "language_selected"),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send welcome message and prompt for content
    await query.message.reply_text(
        text=get_translation(language_code, "welcome"),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send document prompt
    await query.message.reply_text(
        text=get_translation(language_code, "send_document"),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONTENT

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_chat_action("typing")
    
    language = await get_user_language(user.id)
    is_premium = await get_user_premium_status(user.id)
    is_admin = str(user.id) == "999932510"
    
    keyboard = [
        [InlineKeyboardButton(get_translation(language, "language"), callback_data="settings_lang")]
    ]
    
    # Only show summary style option for premium users and admin
    if is_premium or is_admin:
        keyboard.append([InlineKeyboardButton(get_translation(language, "summary_style"), callback_data="settings_style")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_style = await get_user_summary_style(user.id)
    style_translations = {
        "short": get_translation(language, "style_short"),
        "medium": get_translation(language, "style_medium"),
        "long": get_translation(language, "style_long")
    }
    
    settings_text = f"{get_translation(language, 'settings')}:\n\n"
    settings_text += f"{get_translation(language, 'current_language')} {LANGUAGES[language]}\n"
    
    if is_premium or is_admin:
        settings_text += f"{get_translation(language, 'current_style')} {style_translations[current_style]}\n"
    
    await update.message.reply_text(
        settings_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    is_premium = await get_user_premium_status(user.id)
    is_admin = str(user.id) == "999932510"
    
    if query.data == "settings_lang":
        keyboard = [
            [InlineKeyboardButton(text, callback_data=f"lang_{code}")]
            for code, text in LANGUAGES.items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_translation(language, "choose_language"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return LANGUAGE
    
    elif query.data == "settings_style":
        if not (is_premium or is_admin):
            await query.edit_message_text(
                get_translation(language, "premium_required"),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
            
        keyboard = [
            [InlineKeyboardButton(get_translation(language, "style_short"), callback_data="style_short")],
            [InlineKeyboardButton(get_translation(language, "style_medium"), callback_data="style_medium")],
            [InlineKeyboardButton(get_translation(language, "style_long"), callback_data="style_long")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_translation(language, "choose_style"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return STYLE
    
    elif query.data.startswith("lang_"):
        language_code = query.data.split('_')[1]
        await update_user_language(user.id, language_code)
        
        await query.edit_message_text(
            text=get_translation(language_code, "language_selected"),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send welcome message and prompt for content
        await query.message.reply_text(
            text=get_translation(language_code, "welcome"),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send document prompt
        await query.message.reply_text(
            text=get_translation(language_code, "send_document"),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return CONTENT
    
    elif query.data.startswith("style_"):
        if not (is_premium or is_admin):
            await query.edit_message_text(
                get_translation(language, "premium_required"),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
            
        style = query.data.split('_')[1]
        
        try:
            await update_user_summary_style(user.id, style)
            
            style_translations = {
                "short": get_translation(language, "style_short"),
                "medium": get_translation(language, "style_medium"),
                "long": get_translation(language, "style_long")
            }
            
            await query.edit_message_text(
                text=get_translation(language, "style_selected").format(style=style_translations[style]),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error updating summary style: {e}")
            await query.edit_message_text(
                text=get_translation(language, "error"),
                parse_mode=ParseMode.MARKDOWN
            )
        
        return CONTENT
    
    return None

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_chat_action("typing")
    
    language = await get_user_language(user.id)
    
    await update.message.reply_text(
        get_translation(language, "help"),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print(f"Handling content type: {update.message}")

    user = update.effective_user
    language = await get_user_language(user.id)
    is_premium = await get_user_premium_status(user.id)
    
    await update_user_activity(user)
    await update.message.reply_chat_action("typing")
    
    if update.message.text and update.message.text.startswith('/'):
        return CONTENT
    
    if 'extracted_text' in context.user_data:
        del context.user_data['extracted_text']
    
    if 'processing_state' in context.user_data:
        del context.user_data['processing_state']
    
    extracted_text = ""
    status_message = None
    typing_task = None
    start_time = datetime.now()
    
    try:
        # Check memory usage before processing
        current_memory = check_memory_usage()
        if current_memory > MAX_TOTAL_MEMORY:
            await update.message.reply_text(
                f"⚠️ *System Memory Limit Exceeded*\n\n"
                f"Current memory usage: {current_memory:.1f}MB\n"
                f"Maximum allowed: {MAX_TOTAL_MEMORY/1024/1024:.1f}MB\n\n"
                "Please try again later or with a smaller file.",
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
        
        # Handle video files
        if update.message.video:
            print("Handling video message")
            logger.info("Video message detected")
            
            video_size = update.message.video.file_size
            max_video_size = get_file_size_limit('video', is_premium)
            
            if video_size > max_video_size:
                await update.message.reply_text(
                    f"⚠️ *Video Too Large*\n\nThe video file is {video_size / 1024 / 1024:.2f} MB, which exceeds the maximum allowed size of {max_video_size / 1024 / 1024:.0f} MB. Please upload a smaller video.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            if not ELEVENLABS_API_KEY:
                await update.message.reply_text(
                    "⚠️ API Key Missing\nAudio/video transcription is not available. Please contact the bot administrator.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
                
            status_message = await update.message.reply_text(
                get_translation(language, "processing_video"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            try:
                video = update.message.video
                file = await context.bot.get_file(video.file_id)
                
                # Create temporary file for video
                video_path = create_temp_file(suffix='.mp4')
                await file.download_to_drive(video_path)
                
                from src.video_processing import process_video_file
                
                # Start typing indicator task
                async def keep_typing():
                    while True:
                        await update.message.reply_chat_action("typing")
                        await asyncio.sleep(4)
                
                typing_task = asyncio.create_task(keep_typing())
                active_tasks.add(typing_task)
                
                # Read video file in chunks
                with open(video_path, 'rb') as f:
                    video_bytes = f.read()
                
                success, message, transcript_text = await process_video_file(
                    video_bytes, 
                    ELEVENLABS_API_KEY,
                    output_format="mp3"
                )
                
                if not success:
                    await update.message.reply_text(
                        f"❌ *Video Processing Error*\n\n{message}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
                
                if not transcript_text:
                    await update.message.reply_text(
                        "❌ *No Text Extracted*\n\nCould not extract any text from the video. Please try a different video.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
                    
                extracted_text = transcript_text
                
                # Track the processed file
                processing_time = int((datetime.now() - start_time).total_seconds())
                await track_processed_file(
                    user_id=user.id,
                    file_type='video',
                    file_size=video_size,
                    processing_time=processing_time,
                    status='success'
                )
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                await update.message.reply_text(
                    f"❌ *Error Processing Video*\n\nAn error occurred: {str(e)}",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
        
        # Handle audio files or voice messages
        elif update.message.voice or update.message.audio:
            print("Handling audio message")
            logger.info("Audio message detected")
            
            audio_obj = update.message.voice or update.message.audio
            audio_size = audio_obj.file_size
            max_audio_size = get_file_size_limit('audio', is_premium)
            
            if audio_size > max_audio_size:
                await update.message.reply_text(
                    f"⚠️ *Audio Too Large*\n\nThe audio file is {audio_size / 1024 / 1024:.2f} MB, which exceeds the maximum allowed size of {max_audio_size / 1024 / 1024:.0f} MB. Please upload a smaller audio file.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            if not ELEVENLABS_API_KEY:
                await update.message.reply_text(
                    "⚠️ API Key Missing\nAudio/video transcription is not available. Please contact the bot administrator.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
                    
            status_message = await update.message.reply_text(
                get_translation(language, "transcribing"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            try:
                file_obj = update.message.voice or update.message.audio
                file = await context.bot.get_file(file_obj.file_id)
                
                # Create temporary file for audio
                audio_path = create_temp_file(suffix='.mp3')
                await file.download_to_drive(audio_path)
                
                # Start typing indicator task
                async def keep_typing():
                    while True:
                        await update.message.reply_chat_action("typing")
                        await asyncio.sleep(4)
                
                typing_task = asyncio.create_task(keep_typing())
                active_tasks.add(typing_task)
                
                # Read audio file in chunks
                with open(audio_path, 'rb') as f:
                    audio_bytes = f.read()
                
                success, message, transcript_text = await extract_text_from_audio(
                    audio_bytes, 
                    ELEVENLABS_API_KEY
                )
                
                if not success:
                    await update.message.reply_text(
                        f"❌ *Transcription Error*\n\n{message}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
                
                if not transcript_text:
                    await update.message.reply_text(
                        "❌ *No Text Extracted*\n\nCould not extract any text from the audio. Please try a different audio file.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
                    
                extracted_text = transcript_text
                
                # Track the processed file
                processing_time = int((datetime.now() - start_time).total_seconds())
                await track_processed_file(
                    user_id=user.id,
                    file_type='audio',
                    file_size=audio_size,
                    processing_time=processing_time,
                    status='success'
                )
                
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                await update.message.reply_text(
                    f"❌ *Error Processing Audio*\n\nAn error occurred: {str(e)}",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
        
        # Handle document files
        elif update.message.document:
            document = update.message.document
            max_doc_size = get_file_size_limit('document', is_premium)
            file_name = document.file_name if document.file_name else "unnamed"
            file_ext = os.path.splitext(file_name)[1].lower() if file_name else ""
            
            # Log document details for debugging
            logger.info(f"Processing document: {file_name} ({file_ext}) - Size: {document.file_size} bytes")
            
            if document.file_size > max_doc_size:
                size_mb = document.file_size / 1024 / 1024
                max_size_mb = max_doc_size / 1024 / 1024
                await update.message.reply_text(
                    f"❌ *File Size Limit Exceeded*\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"📊 Size: {size_mb:.1f}MB\n"
                    f"⚖️ Max allowed: {max_size_mb:.1f}MB\n\n"
                    "💡 *Please try:*\n"
                    "• Compressing the file\n"
                    "• Splitting it into smaller parts\n"
                    "• Using a smaller document\n\n"
                    f"💎 *Premium users get {PREMIUM_MULTIPLIER}x larger file limits!*",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
                await update.message.reply_text(
                    f"❌ *Unsupported File Format*\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"📎 Format: `{file_ext}`\n\n"
                    "✅ *Supported formats:*\n"
                    "• PDF (`.pdf`)\n"
                    "• Word (`.docx`, `.doc`)\n"
                    "• Text (`.txt`)\n\n"
                    "Please convert your file to one of these formats and try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            status_message = await update.message.reply_text(
                f"🔄 *Processing Document*\n\n"
                f"📄 File: `{file_name}`\n"
                "Please wait...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            try:
                file = await context.bot.get_file(document.file_id)
                doc_path = create_temp_file(suffix=file_ext)
                await file.download_to_drive(doc_path)
                
                # Start typing indicator
                async def keep_typing():
                    while True:
                        await update.message.reply_chat_action("typing")
                        await asyncio.sleep(4)
                
                typing_task = asyncio.create_task(keep_typing())
                active_tasks.add(typing_task)
                
                with open(doc_path, 'rb') as f:
                    file_bytes = f.read()
                
                if file_ext == '.pdf':
                    extracted_text = await extract_text_from_pdf(file_bytes)
                elif file_ext in ['.docx', '.doc']:
                    extracted_text = await extract_text_from_docx(file_bytes)
                elif file_ext == '.txt':
                    extracted_text = await extract_text_from_txt(file_bytes)
                
                if not extracted_text or len(extracted_text.strip()) == 0:
                    await update.message.reply_text(
                        f"❌ *No Text Found*\n\n"
                        f"📄 File: `{file_name}`\n\n"
                        "The document appears to be empty or contains no extractable text.\n\n"
                        "💡 *Please check:*\n"
                        "• The file is not password protected\n"
                        "• The file contains actual text (not just images)\n"
                        "• The file is not corrupted",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
                
                # Track successful processing
                processing_time = int((datetime.now() - start_time).total_seconds())
                await track_processed_file(
                    user_id=user.id,
                    file_type='document',
                    file_size=document.file_size,
                    processing_time=processing_time,
                    status='success'
                )
                
            except Exception as e:
                logger.error(f"Error processing document {file_name}: {str(e)}")
                error_message = str(e)
                
                # Track failed processing
                processing_time = int((datetime.now() - start_time).total_seconds())
                await track_processed_file(
                    user_id=user.id,
                    file_type='document',
                    file_size=document.file_size,
                    processing_time=processing_time,
                    status='error',
                    error_message=error_message
                )
                
                await update.message.reply_text(
                    f"❌ *Error Processing Document*\n\n"
                    f"📄 File: `{file_name}`\n"
                    f"❗ Error: {error_message}\n\n"
                    "💡 *Please try:*\n"
                    "• Using a different document\n"
                    "• Checking if the file is corrupted\n"
                    "• Converting to a different format\n"
                    "• Making sure the file isn't password protected",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
        
        # Handle text messages
        elif update.message.text:
            text = update.message.text.strip()
            if len(text) < 50:
                await update.message.reply_text(
                    get_translation(language, "text_too_short"),
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            # Track the text processing
            processing_time = int((datetime.now() - start_time).total_seconds())
            await track_processed_file(
                user_id=user.id,
                file_type='text',
                file_size=len(text.encode('utf-8')),  
                processing_time=processing_time,
                status='success'
            )
            
            extracted_text = text
            context.user_data['extracted_text'] = extracted_text
            
            keyboard = [
                [InlineKeyboardButton("✅ Summarize", callback_data="process_summarize")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
            
            await update.message.reply_text(
                f"✅ *{get_translation(language, 'text_successfully_processed')}*\n\n"
                f"*Preview:*\n```\n{preview}\n```\n\n"
                f"{get_translation(language, 'would_you_like_summary')}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            return PROCESSING
        
        # Process the extracted text
        if extracted_text:
            extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()
            
            if len(extracted_text) < 50:
                await update.message.reply_text(
                    "⚠️ *Content too short*\n\nThe extracted content is too short to create a meaningful summary. Please provide more content.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
                
            context.user_data['extracted_text'] = await truncate_text(extracted_text)
            
            keyboard = [
                [InlineKeyboardButton("✅ Summarize", callback_data="process_summarize")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
            
            await update.message.reply_text(
                f"✅ *Content Successfully Extracted*\n\n"
                f"*Preview:*\n```\n{preview}\n```\n\n"
                "Would you like me to create a summary of this content?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            return PROCESSING
        
        await update.message.reply_text(
            get_translation(language, "error"),
            parse_mode=ParseMode.MARKDOWN
        )
        return CONTENT
        
    except Exception as e:
        logger.error(f"Error processing content: {e}")
        # Track the failed file processing
        processing_time = int((datetime.now() - start_time).total_seconds())
        await track_processed_file(
            user_id=user.id,
            file_type='unknown',
            file_size=0,
            processing_time=processing_time,
            status='error',
            error_message=str(e)
        )
        raise
        
    finally:
        # Clean up resources
        if status_message:
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
        
        if typing_task:
            try:
                typing_task.cancel()
                await typing_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling typing task: {e}")
            finally:
                active_tasks.discard(typing_task)
        
        await cleanup_resources()

async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    status_message = None
    typing_task = None
    
    try:
        if query.data == "process_summarize":
            # Check memory usage before processing
            if check_memory_usage() > MAX_TOTAL_MEMORY:
                await query.message.reply_text(
                    "⚠️ *Memory Limit Exceeded*\n\nPlease try again later or with a smaller file.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            
            status_message = await query.message.reply_text(
                get_translation(language, "summarizing"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            extracted_text = context.user_data.get('extracted_text', '')
            
            if extracted_text:
                try:
                    # Start typing indicator task
                    async def keep_typing():
                        while True:
                            await query.message.reply_chat_action("typing")
                            await asyncio.sleep(4)
                    
                    typing_task = asyncio.create_task(keep_typing())
                    active_tasks.add(typing_task)
                    
                    summary = await generate_summary(extracted_text, language)
                    
                    # Send the formatted summary
                    await query.message.reply_text(
                        summary,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Send a simple message indicating the summary is ready
                    await query.message.reply_text(
                        get_translation(language, "summary_ready"),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    if 'extracted_text' in context.user_data:
                        del context.user_data['extracted_text']
                    if 'processing_state' in context.user_data:
                        del context.user_data['processing_state']
                    
                except Exception as e:
                    logger.error(f"Error generating summary: {e}")
                    await query.message.reply_text(
                        get_translation(language, "error"),
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await query.message.reply_text(
                    get_translation(language, "error"), 
                    parse_mode=ParseMode.MARKDOWN
                )
        return CONTENT
        
    finally:
        # Clean up resources
        if status_message:
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
        
        if typing_task:
            try:
                typing_task.cancel()
                await typing_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling typing task: {e}")
            finally:
                active_tasks.discard(typing_task)
        
        await cleanup_resources()

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    logger.debug("Setting up handlers")
    application.add_handler(CallbackQueryHandler(language_selection, pattern=r"^lang_"))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"^settings_"))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"^style_"))
    
    # Set up payment handlers
    setup_payment_handlers(application)
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CommandHandler("upgrade", upgrade_command),
                CallbackQueryHandler(language_selection, pattern=r"^lang_"),
                MessageHandler(filters.Document.ALL | filters.TEXT | filters.VIDEO | filters.AUDIO | filters.VOICE & ~filters.COMMAND, handle_content),
            ],
            CONTENT: [
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CommandHandler("upgrade", upgrade_command),
                MessageHandler(filters.Document.ALL | filters.TEXT | filters.VIDEO | filters.AUDIO | filters.VOICE & ~filters.COMMAND, handle_content),
            ],
            PROCESSING: [
                CallbackQueryHandler(process_content, pattern=r"^process_"),
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CommandHandler("upgrade", upgrade_command),
            ],
            STYLE: [
                CallbackQueryHandler(settings_button, pattern=r"^style_"),
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CommandHandler("upgrade", upgrade_command),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        name="main_conversation",
        persistent=False,
    )
    
    application.add_handler(conv_handler)
    logger.debug("Conversation handler added")
    
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("help", help_command))
    logger.debug("Additional handlers added")
    
    logger.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()