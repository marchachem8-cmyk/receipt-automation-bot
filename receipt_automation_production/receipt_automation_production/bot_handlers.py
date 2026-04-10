"""
Telegram Bot Handlers
Handles all Telegram events: /start, /help, photo uploads, confirmations, and edits.
"""

import os
import logging
import json
import tempfile
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from ocr_engine import extract_receipt_data
from sheets_handler import add_receipt_to_sheet

logger = logging.getLogger(__name__)

# States
WAITING_FOR_PHOTO = 1
WAITING_FOR_CONFIRMATION = 2
WAITING_FOR_EDIT = 3

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    welcome_message = f"""
👋 Welcome to Receipt Automation Bot, {user.first_name}!

I can help you automatically extract receipt data and store it in Google Sheets.

Here's how to use me:
1️⃣ Send me a receipt photo
2️⃣ I'll extract the data (date, store, amount, etc.)
3️⃣ Confirm or edit the extracted data
4️⃣ Data is automatically saved to your Google Sheet

Commands:
/start - Show this message
/help - Get help
/cancel - Cancel current operation

Let's get started! 📸 Send me a receipt photo.
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_message = """
📖 Help Guide

**How to use the bot:**
1. Send a clear photo of a receipt
2. I'll extract: Date, Store, Amount, Currency, Category
3. Review the extracted data
4. Confirm (✅), Edit (✏️), or Reject (❌)

**Supported receipt types:**
- Store receipts
- Restaurant bills
- Gas station receipts
- Online order confirmations
- Any receipt with clear text

**Tips for best results:**
- Take photos in good lighting
- Make sure the receipt text is readable
- Avoid shadows and glare
- Take a straight-on photo (not at an angle)

**Commands:**
/start - Start the bot
/help - Show this help message
/cancel - Cancel current operation

**Troubleshooting:**
- If OCR fails: Try a clearer photo
- If data is wrong: Use the edit option to correct it
- If the bot doesn't respond: Check your internet connection

Need more help? Contact the administrator.
    """
    await update.message.reply_text(help_message)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads."""
    user = update.effective_user
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text("🔄 Processing receipt... Please wait.")
        
        # Download the photo
        photo_file = await update.message.photo[-1].get_file()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            await photo_file.download_to_memory()
            photo_bytes = await photo_file.download_as_bytearray()
            tmp_file.write(photo_bytes)
            tmp_path = tmp_file.name
        
        # Extract receipt data
        logger.info(f"Extracting data from receipt for user {user.id}")
        receipt_data = await extract_receipt_data(tmp_path)
        
        # Clean up temp file
        os.remove(tmp_path)
        
        if not receipt_data:
            await processing_msg.edit_text(
                "❌ Could not extract data from the receipt. Please try:\n"
                "- A clearer photo\n"
                "- Better lighting\n"
                "- A different angle\n\n"
                "Send another receipt photo or /cancel to quit."
            )
            return WAITING_FOR_PHOTO
        
        # Store extracted data in context for later use
        context.user_data['receipt_data'] = receipt_data
        context.user_data['user_id'] = user.id
        context.user_data['username'] = user.username or user.first_name
        
        # Format the extracted data for display
        formatted_data = format_receipt_data(receipt_data)
        
        # Ask for confirmation
        confirmation_message = f"""
✅ **Extracted Receipt Data:**

{formatted_data}

Does this look correct?

Options:
✅ Approve - Save to sheet
✏️ Edit - Modify any field
❌ Reject - Try another receipt
        """
        
        await processing_msg.edit_text(
            confirmation_message,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(
                [['✅ Approve', '✏️ Edit'], ['❌ Reject']],
                one_time_keyboard=True
            )
        )
        
        return WAITING_FOR_CONFIRMATION
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text(
            f"❌ Error processing receipt: {str(e)}\n\n"
            "Please try again with a different photo or /cancel to quit."
        )
        return WAITING_FOR_PHOTO

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user confirmation of extracted data."""
    user_response = update.message.text.strip()
    receipt_data = context.user_data.get('receipt_data', {})
    
    if '✅' in user_response or 'approve' in user_response.lower():
        # Save to Google Sheets
        try:
            await update.message.reply_text(
                "💾 Saving to Google Sheet...",
                reply_markup=ReplyKeyboardRemove()
            )
            
            user_id = context.user_data.get('user_id')
            username = context.user_data.get('username', 'Unknown')
            
            success = await add_receipt_to_sheet(receipt_data, username, user_id)
            
            if success:
                await update.message.reply_text(
                    "✅ Receipt saved successfully!\n\n"
                    "📊 Data added to Google Sheet.\n\n"
                    "Send another receipt or /help for more options."
                )
                return WAITING_FOR_PHOTO
            else:
                await update.message.reply_text(
                    "❌ Error saving to Google Sheet. Please try again."
                )
                return WAITING_FOR_CONFIRMATION
                
        except Exception as e:
            logger.error(f"Error saving to sheet: {e}")
            await update.message.reply_text(
                f"❌ Error saving data: {str(e)}\n\n"
                "Please try again or contact the administrator."
            )
            return WAITING_FOR_CONFIRMATION
    
    elif '✏️' in user_response or 'edit' in user_response.lower():
        # Ask which field to edit
        edit_message = """
Which field would you like to edit?

Reply with the field name and new value:
- date: YYYY-MM-DD
- store: Store name
- amount: 123.45
- currency: USD
- category: Groceries
- remarks: Any notes
- cancellation: yes/no

Example: "store: New Store Name"
        """
        await update.message.reply_text(
            edit_message,
            reply_markup=ReplyKeyboardRemove()
        )
        return WAITING_FOR_EDIT
    
    elif '❌' in user_response or 'reject' in user_response.lower():
        # Reject and ask for new photo
        await update.message.reply_text(
            "❌ Receipt rejected.\n\n"
            "Please send another receipt photo or /cancel to quit.",
            reply_markup=ReplyKeyboardRemove()
        )
        return WAITING_FOR_PHOTO
    
    else:
        await update.message.reply_text(
            "Please choose one of the options: ✅ Approve, ✏️ Edit, or ❌ Reject"
        )
        return WAITING_FOR_CONFIRMATION

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle field edits."""
    user_input = update.message.text.strip()
    receipt_data = context.user_data.get('receipt_data', {})
    
    try:
        # Parse the edit input (format: "field: value")
        if ':' not in user_input:
            await update.message.reply_text(
                "Invalid format. Please use: field: value\n"
                "Example: store: New Store Name"
            )
            return WAITING_FOR_EDIT
        
        field, value = user_input.split(':', 1)
        field = field.strip().lower()
        value = value.strip()
        
        # Update the receipt data
        if field in receipt_data:
            receipt_data[field] = value
            context.user_data['receipt_data'] = receipt_data
            
            # Show updated data
            formatted_data = format_receipt_data(receipt_data)
            
            confirmation_message = f"""
✅ **Updated Receipt Data:**

{formatted_data}

Does this look correct now?

Options:
✅ Approve - Save to sheet
✏️ Edit - Modify another field
❌ Reject - Try another receipt
            """
            
            await update.message.reply_text(
                confirmation_message,
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup(
                    [['✅ Approve', '✏️ Edit'], ['❌ Reject']],
                    one_time_keyboard=True
                )
            )
            
            return WAITING_FOR_CONFIRMATION
        else:
            await update.message.reply_text(
                f"Field '{field}' not found. Available fields:\n"
                "- date\n"
                "- store\n"
                "- amount\n"
                "- currency\n"
                "- category\n"
                "- remarks\n"
                "- cancellation"
            )
            return WAITING_FOR_EDIT
            
    except Exception as e:
        logger.error(f"Error editing field: {e}")
        await update.message.reply_text(
            f"Error updating field: {str(e)}\n"
            "Please try again."
        )
        return WAITING_FOR_EDIT

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "Send /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return -1  # End conversation

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again or contact the administrator."
        )

def format_receipt_data(data: dict) -> str:
    """Format receipt data for display."""
    formatted = ""
    fields = {
        'date': '📅 Date',
        'store': '🏪 Store',
        'amount': '💰 Amount',
        'currency': '💵 Currency',
        'category': '📂 Category',
        'remarks': '📝 Remarks',
        'cancellation': '❌ Cancellation'
    }
    
    for key, label in fields.items():
        value = data.get(key, 'N/A')
        formatted += f"{label}: `{value}`\n"
    
    return formatted
