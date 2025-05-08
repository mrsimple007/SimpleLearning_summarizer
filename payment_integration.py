import os
import logging
from datetime import datetime, timedelta, timezone
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut, NetworkError
from src.user_management import update_user_premium_status, get_user_premium_status
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_SIMPLELEARNING")

# PROVIDER TOKEN CONFIGURATION
PROVIDER_TOKEN = "1650291590:TEST:1746464438703_duV9PQLd38pFQi7E"

# File size limits
BASE_FILE_SIZE = {
    'video': 20 * 1024 * 1024,  # 20MB base
    'audio': 10 * 1024 * 1024,  # 10MB base
    'document': 15 * 1024 * 1024  # 15MB base
}

PREMIUM_MULTIPLIER = 2

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

async def get_subscription_status(user_id: int) -> tuple[bool, datetime, datetime]:
    """Get user's subscription status and dates from database."""
    try:
        # Get user's premium status and subscription dates from database
        response = supabase.table('simplelearn_users').select('is_premium, subscription_start, subscription_end').eq('user_id', str(user_id)).execute()
        
        if not response.data or len(response.data) == 0:
            return False, None, None
            
        user_data = response.data[0]
        is_premium = user_data.get('is_premium', False)
        
        if not is_premium:
            return False, None, None
            
        start_date = datetime.fromisoformat(user_data.get('subscription_start')) if user_data.get('subscription_start') else None
        end_date = datetime.fromisoformat(user_data.get('subscription_end')) if user_data.get('subscription_end') else None
        
        return True, start_date, end_date
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return False, None, None

async def update_subscription_dates(user_id: int, start_date: datetime, end_date: datetime) -> None:
    """Update subscription dates in database."""
    try:
        supabase.table('simplelearn_users').update({
            'subscription_start': start_date.isoformat(),
            'subscription_end': end_date.isoformat()
        }).eq('user_id', str(user_id)).execute()
    except Exception as e:
        logger.error(f"Error updating subscription dates: {e}")

async def upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /upgrade command to show premium upgrade options."""
    user_id = update.effective_user.id
    
    # Check if user already has an active subscription
    is_premium, start_date, end_date = await get_subscription_status(user_id)
    
    if is_premium and end_date:
        # Ensure all datetime objects are timezone-aware
        now = datetime.now(timezone.utc)
        if not end_date.tzinfo:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if not start_date.tzinfo:
            start_date = start_date.replace(tzinfo=timezone.utc)
            
        # Calculate remaining time
        remaining_days = (end_date - now).days
        remaining_hours = (end_date - now).seconds // 3600
        
        subscription_info = (
            "✨ *Active Premium Subscription* ✨\n\n"
            f"📅 *Subscription Period:*\n"
            f"• Start: {start_date.strftime('%Y-%m-%d')}\n"
            f"• End: {end_date.strftime('%Y-%m-%d')}\n\n"
            f"⏳ *Time Remaining:*\n"
            f"• {remaining_days} days and {remaining_hours} hours\n\n"
            f"🌟 *Your Premium Features:*\n"
            f"• 📹 Video files up to {format_file_size(BASE_FILE_SIZE['video'] * PREMIUM_MULTIPLIER)}\n"
            f"• 🎵 Audio files up to {format_file_size(BASE_FILE_SIZE['audio'] * PREMIUM_MULTIPLIER)}\n"
            f"• 📄 Documents up to {format_file_size(BASE_FILE_SIZE['document'] * PREMIUM_MULTIPLIER)}\n"
            f"• 🎨 Customizable summary styles\n"
            f"• ⚡ Priority processing\n"
            f"• 📊 Advanced formatting options\n\n"
            f"💫 *Premium Benefits:*\n"
            f"• 🚀 Faster processing times\n"
            f"• 🎯 More detailed summaries\n"
            f"• 📱 Better mobile formatting\n"
            f"• 🔄 Unlimited processing\n\n"
            f"💡 *Tip:* Use /settings to customize your summary style"
        )
        
        await update.message.reply_text(
            subscription_info,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # If not premium, show upgrade options
    keyboard = [[InlineKeyboardButton("💎 Upgrade to Premium", callback_data="upgrade_premium")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    upgrade_info = (
        "🌟 *Premium Features*\n\n"
        "✨ *Enhanced Capabilities:*\n"
        f"• 📹 Video files up to {format_file_size(BASE_FILE_SIZE['video'] * PREMIUM_MULTIPLIER)} (from {format_file_size(BASE_FILE_SIZE['video'])})\n"
        f"• 🎵 Audio files up to {format_file_size(BASE_FILE_SIZE['audio'] * PREMIUM_MULTIPLIER)} (from {format_file_size(BASE_FILE_SIZE['audio'])})\n"
        f"• 📄 Documents up to {format_file_size(BASE_FILE_SIZE['document'] * PREMIUM_MULTIPLIER)} (from {format_file_size(BASE_FILE_SIZE['document'])})\n"
        f"• 🎨 Customizable summary styles\n"
        f"• ⚡ Priority processing\n"
        f"• 📊 Advanced formatting options\n\n"
        "💫 *Premium Benefits:*\n"
        "• 🚀 Faster processing times\n"
        "• 🎯 More detailed summaries\n"
        "• 📱 Better mobile formatting\n"
        "• 🔄 Unlimited processing\n\n"
        "💎 *Subscription Details:*\n"
        "• Monthly subscription\n"
        "• Automatic renewal\n"
        "• Cancel anytime\n\n"
        "Click the button below to upgrade:"
    )
    
    await update.message.reply_text(
        upgrade_info,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def upgrade_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the upgrade button click."""
    query = update.callback_query
    await query.answer()
    
    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="Premium Upgrade",
            description=(
                "✨ *Premium Subscription*\n\n"
                "Upgrade to Premium for enhanced features:\n"
                "• 📈 2x larger file size limits\n"
                "• 🎨 Customizable summary styles\n"
                "• ⚡ Priority processing\n"
                "• 📊 Advanced formatting options\n\n"
                "💫 *Premium Benefits:*\n"
                "• 🚀 Faster processing times\n"
                "• 🎯 More detailed summaries\n"
                "• 📱 Better mobile formatting\n"
                "• 🔄 Unlimited processing\n\n"
                "💎 *Subscription Details:*\n"
                "• Monthly subscription\n"
                "• Automatic renewal\n"
                "• Cancel anytime"
            ),
            payload="premium-upgrade-payload",
            provider_token=PROVIDER_TOKEN,
            currency="UZS",
            prices=[LabeledPrice("Premium Upgrade", 3000000)],
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
    except (TimedOut, NetworkError) as e:
        logger.error(f"Network error during payment: {str(e)}")
        await query.message.reply_text(
            "❌ Connection error. Please try again in a few moments."
        )
    except BadRequest as e:
        error_message = str(e)
        logger.error(f"Error sending invoice: {error_message}")
        if "Payment_provider_invalid" in error_message:
            await query.message.reply_text(
                "❌ Payment provider error! Please try again later."
            )
        else:
            await query.message.reply_text(
                "❌ Error creating payment. Please try again later."
            )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await query.message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )

async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the pre-checkout query."""
    query = update.pre_checkout_query
    try:
        await query.answer(ok=True)
        logger.info(f"Pre-checkout query approved for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in pre-checkout: {str(e)}")
        await query.answer(ok=False, error_message="Payment verification failed")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle successful payment and upgrade user to premium."""
    try:
        successful_payment = update.message.successful_payment
        user_id = update.effective_user.id
        
        # Calculate subscription period
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)  # 30-day subscription
        
        logger.info(f"Payment successful for user {user_id}: {successful_payment}")
        
        # Update premium status and subscription dates
        await update_user_premium_status(user_id, True)
        await update_subscription_dates(user_id, start_date, end_date)
        
        await update.message.reply_text(
            f"✨ *Premium Upgrade Successful!* ✨\n\n"
            f"💫 *Payment Details:*\n"
            f"• Amount: {successful_payment.total_amount / 100} UZS\n"
            f"• Currency: {successful_payment.currency}\n\n"
            f"📅 *Subscription Period:*\n"
            f"• Start: {start_date.strftime('%Y-%m-%d')}\n"
            f"• End: {end_date.strftime('%Y-%m-%d')}\n\n"
            f"🌟 *Premium Features Activated:*\n"
            f"• 📹 Video files up to {format_file_size(BASE_FILE_SIZE['video'] * PREMIUM_MULTIPLIER)}\n"
            f"• 🎵 Audio files up to {format_file_size(BASE_FILE_SIZE['audio'] * PREMIUM_MULTIPLIER)}\n"
            f"• 📄 Documents up to {format_file_size(BASE_FILE_SIZE['document'] * PREMIUM_MULTIPLIER)}\n"
            f"• 🎨 Customizable summary styles\n"
            f"• ⚡ Priority processing\n"
            f"• 📊 Advanced formatting options\n\n"
            f"💫 *Premium Benefits:*\n"
            f"• 🚀 Faster processing times\n"
            f"• 🎯 More detailed summaries\n"
            f"• 📱 Better mobile formatting\n"
            f"• 🔄 Unlimited processing\n\n"
            f"🎉 *Enjoy your premium experience!* 🎉\n\n"
            f"💡 *Tip:* Use /settings to customize your summary style",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error processing successful payment: {str(e)}")
        await update.message.reply_text(
            "❌ Error processing payment confirmation. Please contact support."
        )

def setup_payment_handlers(application: Application) -> None:
    """Set up payment-related handlers."""
    application.add_handler(CommandHandler("upgrade", upgrade_command))
    application.add_handler(CallbackQueryHandler(upgrade_button, pattern="^upgrade_premium$"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)) 