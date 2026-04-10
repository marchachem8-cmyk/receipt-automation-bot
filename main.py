#!/usr/bin/env python3
"""
Receipt Automation System - Main Bot Entry Point
Telegram bot that receives receipt photos, extracts data using OCR and AI, 
and stores the data in Google Sheets.
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bot_handlers import (
    start_command,
    help_command,
    handle_photo,
    handle_confirmation,
    handle_edit,
    cancel_command,
    error_handler
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Start the bot."""
    
    # Get credentials from environment
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    logger.info("🤖 Starting Receipt Automation Bot...")
    
    # Create the Application
    application = Application.builder().token(telegram_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot with polling
    logger.info("✅ Bot is running and listening for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
