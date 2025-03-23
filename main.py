import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from motor.motor_asyncio import AsyncIOMotorClient
from config import BOT_TOKEN, API_ID, API_HASH, SESSION_STRINGS, MONGO_DB_URI  # Importing from config.py

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB client setup
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client['mass_report_bot']
users_collection = db['users']

# Bot client
bot = Client("mass_report_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Userbot clients
user_clients = []
for i, string in enumerate(SESSION_STRINGS):
    user_client = Client(f"session_{i}", api_id=API_ID, api_hash=API_HASH, session_string=string)
    user_clients.append(user_client)

# Function to start user clients only if they are not already connected
async def start_user_clients():
    for i, user_client in enumerate(user_clients):
        session_string = SESSION_STRINGS[i] if i < len(SESSION_STRINGS) else None
        
        if session_string is None:
            logger.error(f"Session string at index {i} is None. Skipping client.")
            continue
        
        try:
            if not await user_client.is_connected():
                await user_client.start()
            else:
                logger.info(f"User client {user_client} is already connected.")
        except Exception as e:
            logger.error(f"Failed to start client {user_client}: {e}")

# Start command handler
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply(
        "Hello! I'm the Mass Report Bot. Please send the link of the group or channel you want to report.",
        reply_markup=ForceReply(selective=True)
    )
    # Add user data to MongoDB if not already present
    user_data = await users_collection.find_one({"chat_id": message.chat.id})
    if not user_data:
        await users_collection.insert_one({"chat_id": message.chat.id, "state": "awaiting_link"})

# Message handler
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_message(client, message):
    chat_id = message.chat.id
    text = message.text.strip()
    user_info = await users_collection.find_one({"chat_id": chat_id})

    if not user_info:
        await message.reply("Please start the process by sending /start.")
        return

    state = user_info.get("state")

    if state == "awaiting_link":
        await users_collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"link": text, "state": "awaiting_reason"}}
        )
        buttons = [
            [InlineKeyboardButton(reason[0], callback_data=f"reason_{reason[1]}")] for reason in REPORT_REASONS
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("Please select the reason for the report:", reply_markup=reply_markup)

    elif state == "awaiting_count":
        if text.isdigit() and int(text) > 0:
            await users_collection.update_one(
                {"chat_id": chat_id},
                {"$set": {"count": int(text), "state": "ready_to_report"}}
            )
            await message.reply(f"Starting to send {text} reports for the link: {user_info['link']} with reason: {user_info['reason']}")
            await send_reports(client, message, user_info)
        else:
            await message.reply("Please enter a valid number of reports.", reply_markup=ForceReply(selective=True))

# Callback query handler for report reason
@bot.on_callback_query(filters.regex(r"^reason_"))
async def handle_reason(client, callback_query):
    chat_id = callback_query.message.chat.id
    user_info = await users_collection.find_one({"chat_id": chat_id})

    if not user_info or user_info.get("state") != "awaiting_reason":
        await callback_query.message.reply("Something went wrong. Please start over with /start.")
        return

    reason_code = callback_query.data.split("_")[1]
    await users_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"reason": reason_code, "state": "awaiting_count"}}
    )
    await callback_query.message.reply("Please enter the number of reports to send:", reply_markup=ForceReply(selective=True))

# Function to send reports
async def send_reports(client, message, user_info):
    link = user_info["link"]
    reason = user_info["reason"]
    count = user_info["count"]

    success_count = 0
    failure_count = 0

    for i in range(count):
        for user_client in user_clients:
            try:
                async with user_client:
                    await user_client.report(link, reason)  # Corrected line
                    success_count += 1
                    await message.reply(f"Report sent: {success_count}")
            except FloodWait as e:
                logger.warning(f"Flood wait: {e.x} seconds")
                await asyncio.sleep(e.x)
            except Exception as e:
                logger.error(f"Failed to send report: {e}")
                failure_count += 1

    await message.reply(f"Reporting completed.\nTotal successful reports: {success_count}\nTotal failed reports: {failure_count}")
    await users_collection.update_one(
        {"chat_id": message.chat.id},
        {"$set": {"state": "completed"}}
    )

# Running the bot and user clients
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Start user clients only if not already running
    loop.run_until_complete(start_user_clients())

    bot.run()

    # Stop user clients after bot stops
    for user_client in user_clients:
        if user_client.is_connected():
            user_client.stop()
