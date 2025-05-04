import os
import logging
from datetime import datetime
import asyncio
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from src.prompts_summarize import LANGUAGES, TRANSLATIONS
from src.llm_service import generate_summary
from src.audio_processing import extract_text_from_audio, save_transcription_to_temp_file
from src.document_processing import *
from src.web_processing import *
from src.user_management import *
from src.text_processing import *
from src import ELEVENLABS_API_KEY  

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

logger.info(f"ELEVENLABS_API_KEY present: {bool(ELEVENLABS_API_KEY)}")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

LANGUAGE, CONTENT, PROCESSING, STYLE = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_chat_action("typing")
    
    await update_user_activity(user)
    
    language = await get_user_language(user.id)
    
    # Check if user is admin
    if str(user.id) == "999932510":
        total_users = await get_total_users()
        admin_message = f"👑 *Admin Dashboard*\n\n📊 Total Users: {total_users}\n\n"
        await update.message.reply_text(
            text=admin_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    if language and language in LANGUAGES:
        await update.message.reply_text(
            text=get_translation(language, "welcome"),
            parse_mode=ParseMode.MARKDOWN
        )
        return CONTENT
    else:
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
    
    await query.message.reply_text(
        text=get_translation(language_code, "welcome"),
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
    
    await update_user_activity(user)
    await update.message.reply_chat_action("typing")
    
    if update.message.text and update.message.text.startswith('/'):
        return CONTENT
    
    if 'extracted_text' in context.user_data:
        del context.user_data['extracted_text']
    
    if 'processing_state' in context.user_data:
        del context.user_data['processing_state']
    
    extracted_text = ""
    
    # Handle video files
    if update.message.video:
        print("Handling video message")
        logger.info("Video message detected")
        
        # Get user's premium status
        is_premium = await get_user_premium_status(user.id)
        
        # Set different size limits for premium and regular users
        MAX_VIDEO_SIZE = 20 * 1024 * 4096 if is_premium else 10 * 1024 * 4096  # 80MB for premium, 40MB for regular
        video_size = update.message.video.file_size
        logger.info(f"Video size: {video_size} bytes ({video_size / 1024 / 1024:.2f} MB)")
        
        if video_size > MAX_VIDEO_SIZE:
            await update.message.reply_text(
                f"⚠️ *Video Too Large*\n\nThe video file is {video_size / 1024 / 1024:.2f} MB, which exceeds the maximum allowed size of {MAX_VIDEO_SIZE / 1024 / 1024:.0f} MB. Please upload a smaller video.",
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
            await update.message.reply_chat_action("typing")
            
            video = update.message.video
            file = await context.bot.get_file(video.file_id)
            file_bytes = await file.download_as_bytearray()
            
            from src.video_processing import process_video_file
            print("Successfully imported video_processing module")

            async def keep_typing():
                while True:
                    await update.message.reply_chat_action("typing")
                    await asyncio.sleep(4)  

            typing_task = asyncio.create_task(keep_typing())

            success, message, transcript_text = await process_video_file(
                file_bytes, 
                ELEVENLABS_API_KEY,
                output_format="mp3"
            )
            
            typing_task.cancel()
            
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
            
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
            
            # Send the extracted text as a file
            transcript_file = await save_transcription_to_temp_file(transcript_text)
            try:
                with open(transcript_file, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename="video_transcript.txt",
                        caption="📝 *Transcript of Your video* \n",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Error sending transcript file: {e}")
            finally:
                try:
                    os.remove(transcript_file)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
            await update.message.reply_text(
                f"❌ *Error Processing Video*\n\nAn error occurred: {str(e)}",
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
            
    
    # Handle audio files or voice messages
    elif update.message.voice or update.message.audio:
        print("Handling audio message")
        logger.info("Audio message detected")
        
        # Get user's premium status
        is_premium = await get_user_premium_status(user.id)
        
        # Set different size limits for premium and regular users
        MAX_AUDIO_SIZE = 10 * 1024 * 4096 if is_premium else 5 * 1024 * 4096  # 40MB for premium, 20MB for regular
        audio_obj = update.message.voice or update.message.audio
        audio_size = audio_obj.file_size
        logger.info(f"Audio size: {audio_size} bytes ({audio_size / 1024 / 1024:.2f} MB)")
        
        if audio_size > MAX_AUDIO_SIZE:
            await update.message.reply_text(
                f"⚠️ *Audio Too Large*\n\nThe audio file is {audio_size / 1024 / 1024:.2f} MB, which exceeds the maximum allowed size of {MAX_AUDIO_SIZE / 1024 / 1024:.0f} MB. Please upload a smaller audio file.",
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
        
        # Use the global variable instead of fetching it again
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
            # Keep showing typing indicator while processing
            await update.message.reply_chat_action("typing")
            
            file_obj = update.message.voice or update.message.audio
            file = await context.bot.get_file(file_obj.file_id)
            file_bytes = await file.download_as_bytearray()
            
            from src.audio_processing import extract_text_from_audio
            
            # Start a background task to keep showing typing indicator
            async def keep_typing():
                while True:
                    await update.message.reply_chat_action("typing")
                    await asyncio.sleep(4)  # Telegram typing indicator lasts for 5 seconds

            typing_task = asyncio.create_task(keep_typing())

            success, message, transcript_text = await extract_text_from_audio(
                file_bytes, 
                ELEVENLABS_API_KEY
            )
            
            # Cancel the typing task
            typing_task.cancel()
            
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
            
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
            
            # Send the extracted text as a file
            transcript_file = await save_transcription_to_temp_file(transcript_text)
            try:
                with open(transcript_file, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename="audio_transcript.txt",
                        caption="📝 *Audio Transcript* \n",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Error sending transcript file: {e}")
            finally:
                try:
                    os.remove(transcript_file)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
            await update.message.reply_text(
                f"❌ *Error Processing Audio*\n\nAn error occurred: {str(e)}",
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
    
    # Handle document files
    elif update.message.document:
        document = update.message.document
        
        # Get user's premium status
        is_premium = await get_user_premium_status(user.id)
        
        # Set different size limits for premium and regular users
        MAX_DOCUMENT_SIZE = 30 * 1024 * 1024 if is_premium else 15 * 1024 * 1024  # 30MB for premium, 15MB for regular
        
        if document.file_size > MAX_DOCUMENT_SIZE:
            await update.message.reply_text(
                f"⚠️ *File Size Limit Exceeded* ⚠️\n\n📏 *The document is larger than {MAX_DOCUMENT_SIZE / 1024 / 1024:.0f}MB*\n\n💡 *Please try:*\n• Compressing the file\n• Splitting it into smaller parts\n• Using a smaller document",
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
        
        file_name = document.file_name if document.file_name else ""
        file_ext = os.path.splitext(file_name)[1].lower() if file_name else ""
        
        if file_ext in ['.pdf', '.docx', '.doc', '.txt']:
            status_message = await update.message.reply_text(
                get_translation(language, "processing"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Keep showing typing indicator while processing
            await update.message.reply_chat_action("typing")
            
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()
            
            if file_ext == '.pdf':
                extracted_text = await extract_text_from_pdf(file_bytes)
            elif file_ext in ['.docx', '.doc']:
                extracted_text = await extract_text_from_docx(file_bytes)
            elif file_ext == '.txt':
                extracted_text = await extract_text_from_txt(file_bytes)
            
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
        else:
            await update.message.reply_text(
                get_translation(language, "unsupported"),
                parse_mode=ParseMode.MARKDOWN
            )
            return CONTENT
    
    # Handle text or URLs
    elif update.message.text:
        text = update.message.text
        
        if text.startswith(('http://', 'https://')) or any(text.startswith(prefix) for prefix in ['www.', 'youtu.be/']):
            if not text.startswith(('http://', 'https://')):
                text = 'https://' + text.replace('www.', '', 1) if text.startswith('www.') else 'https://' + text
                
            status_message = await update.message.reply_text(
                get_translation(language, "processing"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Keep showing typing indicator while processing
            await update.message.reply_chat_action("typing")
            
            try:
                extracted_text = await extract_text_from_url(text)
                if extracted_text.startswith("Error:") or "Failed to retrieve content from URL" in extracted_text:
                    try:
                        await status_message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting status message: {e}")
                    await update.message.reply_text(
                        f"⚠️ *URL Access Issue*\n\n{extracted_text}\n\nPlease check if:\n• The URL is correct\n• The website allows access\n• The site isn't behind a login",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return CONTENT
            except Exception as e:
                logger.error(f"Error processing URL: {e}")
                try:
                    await status_message.delete()
                except Exception as e:
                    logger.error(f"Error deleting status message: {e}")
                await update.message.reply_text(
                    f"❌ *Error Processing URL*\n\nI encountered an issue: `{str(e)}`\nPlease try a different URL.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT
            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")
        else:
            extracted_text = text
    
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
            f"✅ *Content Successfully Extracted*\n\n*Preview:*\n```\n{preview}\n```\n\nWould you like me to create a summary of this content?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        return PROCESSING
    
    await update.message.reply_text(
        get_translation(language, "error"),
        parse_mode=ParseMode.MARKDOWN
    )
    return CONTENT


async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    if query.data == "process_summarize":
        try:
            status_message = await query.message.reply_text(
                get_translation(language, "summarizing"),
                parse_mode=ParseMode.MARKDOWN
            )
            
            extracted_text = context.user_data.get('extracted_text', '')
            
            if extracted_text:
                try:
                    # Start a background task to keep showing typing indicator
                    async def keep_typing():
                        while True:
                            await query.message.reply_chat_action("typing")
                            await asyncio.sleep(4)  # Telegram typing indicator lasts for 5 seconds

                    typing_task = asyncio.create_task(keep_typing())
                    
                    summary = await generate_summary(extracted_text, language)
                    
                    # Cancel the typing task
                    typing_task.cancel()
                    
                    try:
                        await status_message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting status message: {e}")
                    
                    # Send the formatted summary
                    await query.message.reply_text(
                        summary,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    if 'extracted_text' in context.user_data:
                        del context.user_data['extracted_text']
                    if 'processing_state' in context.user_data:
                        del context.user_data['processing_state']
                    
                    # Ask if the user wants to summarize more content
                    await query.message.reply_text(
                        get_translation(language, "send_document"),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                except Exception as e:
                    logger.error(f"Error generating summary: {e}")
                    try:
                        await status_message.delete()
                    except Exception as e:
                        logger.error(f"Error deleting status message: {e}")
                    await query.message.reply_text(
                        get_translation(language, "error"),
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                try:
                    await status_message.delete()
                except Exception as e:
                    logger.error(f"Error deleting status message: {e}")
                await query.message.reply_text(
                    get_translation(language, "error"), 
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error in process_content: {e}")
            await query.message.reply_text(
                get_translation(language, "error"),
                parse_mode=ParseMode.MARKDOWN
            )
    
    return CONTENT

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    logger.debug("Setting up handlers")
    application.add_handler(CallbackQueryHandler(language_selection, pattern=r"^lang_"))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"^settings_"))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"^style_"))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CallbackQueryHandler(language_selection, pattern=r"^lang_"),
            ],
            CONTENT: [
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                MessageHandler(filters.Document.ALL | filters.TEXT | filters.VIDEO | filters.AUDIO | filters.VOICE & ~filters.COMMAND, handle_content),
            ],
            PROCESSING: [
                CallbackQueryHandler(process_content, pattern=r"^process_"),
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
            ],
            STYLE: [
                CallbackQueryHandler(settings_button, pattern=r"^style_"),
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
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