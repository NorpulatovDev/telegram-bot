import logging
import re
import gspread
import os
import json
from datetime import datetime
from collections import defaultdict
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(level=logging.INFO)

# Load brands from file
with open("brands.txt", "r", encoding="utf-8") as f:
    BRANDS = [line.strip() for line in f if line.strip()]

# Per-user brand history (in-memory)
user_history = defaultdict(set)

# Setup Google Sheets
google_creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Turnover").sheet1

# Conversation states
DATE, COMPANY, CHECKS, TOTAL = range(4)

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    today = datetime.now().strftime("%Y/%m/%d")
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(today)]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📅 Enter the date (or press 'Today'):", reply_markup=reply_markup)
    return DATE

# Handle date input
async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date = update.message.text.strip()
    if not re.match(r'^\d{4}/\d{2}/\d{2}$', date):
        await update.message.reply_text("❌ Invalid format. Use YYYY/MM/DD:")
        return DATE
    context.user_data['date'] = date

    cancel_markup = ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🏢 Enter Company Name (partial name is OK):", reply_markup=cancel_markup)
    return COMPANY

# Handle company input with suggestions
async def get_company(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == "cancel":
        return await cancel(update, context)

    user_id = update.effective_user.id
    suggestions = []

    # History-based suggestions
    history_matches = [b for b in user_history[user_id] if b.lower().startswith(text.lower())]
    if history_matches:
        suggestions.extend(history_matches)

    # File-based suggestions
    file_matches = [b for b in BRANDS if b.lower().startswith(text.lower()) and b not in suggestions]
    suggestions.extend(file_matches)

    # If user selected a suggestion exactly
    if any(text.lower() == s.lower() for s in suggestions):
        context.user_data['company'] = text
        user_history[user_id].add(text)
        await update.message.reply_text("📦 Enter the number of Sold Checks:", reply_markup=ReplyKeyboardRemove())
        return CHECKS

    if not suggestions:
        await update.message.reply_text("❌ No brand found. Try again or type 'Cancel'.")
        return COMPANY

    # Suggest options
    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton(b)] for b in suggestions[:10]] + [["Cancel"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text("🤔 Choose from the suggestions or type more:", reply_markup=reply_markup)
    return COMPANY

# Handle sold checks
async def get_checks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == "cancel":
        return await cancel(update, context)
    if not text.isdigit():
        await update.message.reply_text("❌ Must be a number:")
        return CHECKS
    context.user_data['checks'] = text
    await update.message.reply_text("💰 Enter the Total price:")
    return TOTAL

# Handle total price and save
async def get_total(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == "cancel":
        return await cancel(update, context)
    if not text.isdigit():
        await update.message.reply_text("❌ Must be a number:")
        return TOTAL
    context.user_data['total'] = text

    # Save to Google Sheets
    sheet.append_row([
        context.user_data['date'],
        context.user_data['company'],
        context.user_data['checks'],
        context.user_data['total'],
    ])

    markup = ReplyKeyboardMarkup([["/start"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("✅ Data saved! Press /start to enter another.", reply_markup=markup)
    return ConversationHandler.END

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = ReplyKeyboardMarkup([["/start"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("❌ Cancelled. Press /start to begin again.", reply_markup=markup)
    return ConversationHandler.END

# Main
def main():
    app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company)],
            CHECKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_checks)],
            TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_total)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
