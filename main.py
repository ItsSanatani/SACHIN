import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "YOUR_BOT_TOKEN"
API_ID = YOUR_API_ID
API_HASH = "YOUR_API_HASH"

# List of session strings
SESSION_STRINGS = [
    "SESSION_STRING_1",
    "SESSION_STRING_2",
    # Add more session strings as needed
]

# List of report reasons
REPORT_REASONS = [
    ("Spam", "spam"),
    ("Fake", "fake"),
    ("Child Abuse", "child_abuse"),
    ("Violence", "violence"),
    ("Pornography", "pornography"),
    ("Copyright", "copyright"),
    ("Other", "other")
]

# Bot client
bot = Client("mass_report_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Userbot clients
user_clients = [Client(f"session_{i}", api_id=API_ID, api_hash=API_HASH, session_string=string) for i, string in enumerate(SESSION_STRINGS)]

# Dictionary to store user data
user_data = {}

# Start command handler
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply(
        "Hello! I'm the Mass Report Bot. Please send the link of the group or channel you want to report."
    )

# Link handler
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_link(client, message):
    text = message.text.strip()
    if not text:
        await message.reply("Please send a valid link.")
        return

    # Store user data
    user_data[message.chat.id] = {"link": text}

    # Ask user for report reason
    buttons = [
        [InlineKeyboardButton(reason[0], callback_data=f"reason_{reason[1]}")] for reason in REPORT_REASONS
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("Please select the reason for the report:", reply_markup=reply_markup)

# Report reason handler
@bot.on_callback_query(filters.regex(r"^reason_"))
async def handle_reason(client, callback_query):
    reason_code = callback_query.data.split("_")[1]
    user_info = user_data.get(callback_query.message.chat.id, {})
    if not user_info:
        await callback_query.message.reply("Something went wrong. Please start over with /start.")
        return

    user_info["reason"] = reason_code

    # Ask user for the number of reports
    await callback_query.message.reply("Please enter the number of reports to send:")

# Report count handler
@bot.on_message(filters.private & filters.text & filters.regex(r"^\d+$"))
async def handle_report_count(client, message):
    user_info = user_data.get(message.chat.id, {})
    if not user_info or "reason" not in user_info:
        await message.reply("Something went wrong. Please start over with /start.")
        return

    report_count = int(message.text.strip())
    if report_count <= 0:
        await message.reply("Please enter a valid number.")
        return

    user_info["count"] = report_count

    # Start sending reports
    await message.reply(f"Starting to send reports...\nLink: {user_info['link']}\nReason: {user_info['reason']}\nCount: {user_info['count']}")

    # Send reports
    await send_reports(client, message, user_info)

# Function to send reports
async def send_reports(client, message, user_info):
    link = user_info["link"]
    reason = user_info["reason"]
    count = user_info["count"]

    # Initialize success and failure counts
    success_count = 0
    failure_count = 0

    for i in range(count):
        for user_client in user_clients:
            try:
                async with user_client:
                    await user_client.report_chat(link, reason)
                    success_count += 1
                    await message.reply(f"Report sent: {success_count}")
            except FloodWait as e:
                logger.warning(f"Flood wait: {e.x} seconds")
                await asyncio.sleep(e.x)
            except Exception as e:
                logger.error(f"Failed to send report: {e}")
                failure_count += 1

    await message.reply(f"Reporting completed.\nTotal successful reports: {success_count}\nTotal failed reports: {failure_count}")

# Run the bot
if __name__ == "__main__":
    for user_client in user_clients:
        user_client.start()
    bot.run()
    for user_client in user_clients:
        user_client.stop()
