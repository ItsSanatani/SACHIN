import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from config import BOT_TOKEN, API_ID, API_HASH, SESSION_STRINGS, MONGO_DB_URI  # Importing from config.py

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB client setup
mongo_client = MongoClient(MONGO_DB_URI)
db = mongo_client["mass_report_db"]
user_collection = db["user_data"]  # MongoDB collection for user data

# Custom MongoDB session storage class
class MongoDBStorage:
    def __init__(self, db_uri, db_name, collection_name):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
    
    async def load(self, session_name):
        session_data = self.collection.find_one({"session_name": session_name})
        if session_data:
            return session_data["session_string"]
        return None
    
    async def save(self, session_name, session_string):
        existing_session = self.collection.find_one({"session_name": session_name})
        if existing_session:
            self.collection.update_one({"session_name": session_name}, {"$set": {"session_string": session_string}})
        else:
            self.collection.insert_one({"session_name": session_name, "session_string": session_string})
    
    async def delete(self, session_name):
        self.collection.delete_one({"session_name": session_name})

# MongoDB storage object
mongo_storage = MongoDBStorage(MONGO_DB_URI, "mass_report_db", "sessions")

bot = Client("mass_report_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Check and initialize user clients
user_clients = []
for i, string in enumerate(SESSION_STRINGS):
    if string:
        user_client = Client(f"session_{i}", api_id=API_ID, api_hash=API_HASH, session_string=string)
        user_clients.append(user_client)
    else:
        logger.warning(f"Session string at index {i} is None or empty. Skipping client.")

# Function to start user clients only if they are not already connected
async def start_user_clients():
    for i, user_client in enumerate(user_clients):
        try:
            if not await user_client.is_connected():
                logger.info(f"Starting user client {i}...")
                await user_client.start()
            else:
                logger.info(f"User client {i} is already connected.")
        except Exception as e:
            logger.error(f"Failed to start client {i}: {e}")

# Start command handler
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # Save user data in MongoDB
    user_data = {
        "chat_id": message.chat.id,
        "state": "awaiting_link"
    }
    user_collection.update_one({"chat_id": message.chat.id}, {"$set": user_data}, upsert=True)

    await message.reply(
        "Hello! I'm the Mass Report Bot. Please send the link of the group or channel you want to report.",
        reply_markup=ForceReply(selective=True)
    )

# Message handler
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_message(client, message):
    chat_id = message.chat.id
    text = message.text.strip()

    user_info = user_collection.find_one({"chat_id": chat_id})

    if not user_info:
        await message.reply("Please start the process by sending /start.")
        return

    state = user_info.get("state")

    if state == "awaiting_link":
        user_collection.update_one({"chat_id": chat_id}, {"$set": {"link": text, "state": "awaiting_reason"}})

        buttons = [
            [InlineKeyboardButton(reason[0], callback_data=f"reason_{reason[1]}")] for reason in REPORT_REASONS
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("Please select the reason for the report:", reply_markup=reply_markup)

    elif state == "awaiting_count":
        if text.isdigit() and int(text) > 0:
            user_collection.update_one({"chat_id": chat_id}, {"$set": {"count": int(text), "state": "ready_to_report"}})
            await message.reply(f"Starting to send {text} reports for the link: {user_info['link']} with reason: {user_info['reason']}")
            await send_reports(client, message, user_info)
        else:
            await message.reply("Please enter a valid number of reports.", reply_markup=ForceReply(selective=True))

# Callback query handler for report reason
@bot.on_callback_query(filters.regex(r"^reason_"))
async def handle_reason(client, callback_query):
    chat_id = callback_query.message.chat.id
    user_info = user_collection.find_one({"chat_id": chat_id})

    if not user_info or user_info.get("state") != "awaiting_reason":
        await callback_query.message.reply("Something went wrong. Please start over with /start.")
        return

    reason_code = callback_query.data.split("_")[1]
    user_collection.update_one({"chat_id": chat_id}, {"$set": {"reason": reason_code, "state": "awaiting_count"}})

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
    user_collection.update_one({"chat_id": user_info["chat_id"]}, {"$set": {"state": "completed"}})

# Running the bot and user clients
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Start user clients only if not already running
    loop.run_until_complete(start_user_clients())

    bot.run()

    # Stop user clients after bot stops
    for i, user_client in enumerate(user_clients):
        if user_client.is_connected():
            user_client.stop()
