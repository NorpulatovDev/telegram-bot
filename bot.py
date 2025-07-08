import logging
import re
import gspread
import os, json
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load Google credentials from env
google_creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("SalesData").sheet1  # change to your sheet name if needed

# Define conversation states
COMPANY, CHECKS, TOTAL, DATE = range(4)

# Start conversation
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter the Company Number (digits only):")
    return COMPANY

async def get_company(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    company = update.message.text.strip()
    if not company.isdigit():
        await update.message.reply_text("❌ Company Number must be digits only. Try again:")
        return COMPANY
    context.user_data['company'] = company
    await update.message.reply_text("Enter the number of sold checks:")
    return CHECKS

async def get_checks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    checks = update.message.text.strip()
    if not checks.isdigit():
        await update.message.reply_text("❌ Sold Checks must be a number. Try again:")
        return CHECKS
    context.user_data['checks'] = checks
    await update.message.reply_text("Enter the Total price (numbers only, e.g., 10000):")
    return TOTAL

async def get_total(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    total = update.message.text.strip()
    if not total.isdigit():
        await update.message.reply_text("❌ Total must be a number. Try again:")
        return TOTAL
    context.user_data['total'] = total
    await update.message.reply_text("Enter the date (YYYY-MM-DD):")
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date = update.message.text.strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD:")
        return DATE
    context.user_data['date'] = date

    # Save to Google Sheet
    sheet.append_row([
        context.user_data['company'],
        context.user_data['checks'],
        context.user_data['total'],
        context.user_data['date'],
    ])
    await update.message.reply_text("✅ Data saved successfully!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token("8050316570:AAFX9b1fHDR5fwSGudOroLdaQZZkTpyrllQ").build()  # Replace with your actual bot token

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company)],
            CHECKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_checks)],
            TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_total)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
