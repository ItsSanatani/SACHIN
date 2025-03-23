import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7656369802:AAGdlo88cewouuiviq-eHoRHdxj_Ktji3To"
API_ID = 28795512
API_HASH = "c17e4eb6d994c9892b8a8b6bfea4042a"

SESSION_STRINGS = [
    "BQFgymkAIm-auno6Zrvp6Dya59D5eV2-1FvVtBsB-55TJd2Hy9gSOSO2-So6xVPztmCljtfJuI4lagV-5Di4rzKblAKsrzA7hPVZpjZzOAW4NKNZE8qSFhZ4rOEqryK2JXFIxNINvfifnSqWw08tf5W2Nytm30361EvjS7DWeaSfAwaHxK6SGpwx4FRpwub2f0_NgpJFE8Wx7BQxNLSjEzCfSfHq2IRYXFNgyG9IBfze__uL-6QogfGHeUeXmCqY37w2ldNYHonpdmjUsxtNLd_YaocP0BJ3Z-FIShe4viahSANMWgsVlkljV1mHdPypkD_GsVicOvudFKiJGEFFCRlnxmhTVQAAAAGvVNXGAA",
    "BQFgymkAVTMxSUj6LsU_3n5Drp2A6Qxrf_1CdOpNK2SqvQHYFehSmu1rzZr6ZeWZVffbquBPV-orsQKh01ydXX4yNfPybJP8b1PVZnNf8NEOb-vxw0ATay79muzQCUH_EZj8m0LTakEfphuq7nXK2cU6ravdGwDTqQtcez8Pqnz0II8W8PRlZwkUHzXe2VFKuLC3gLamhRyV6AT6sPANyU9Pb2mx9VC_s0RiPpbFQy_1KNmqgHWt5ZNxK267LcreOVTmF6lW1K9iSZfPE78YFIR9scwq01Pf9Cv8Ali8fi5TVj8ago2M0m9WjibLCZls15uYmYR5YTNZoM1aZQrWfTzuRfa_7AAAAAG3U1eFAA",
    "BQFgymkAezjS5jiJSx-AZ07UHv-1BVM9I3Y3d45o3RVg2-4jICfCZfGcvI-81BmxryzDhrb936ytuX0VElw3OdHbuNE0hIHkUHuIFjIF-8Gscilk1whOjz7d28rkS-2Hg-Hrd6GS__HKfwHVrey8JVpC4iKEtU1iXMxfmBnlVtqqVZvpPL9NNX9hLOhUtdOiC9bzZ3qv8mlzP7SMZ3UjJuPz1MATHgUuyKv4QzCplmPgWpFGlfFUwnkPsKffeu2S7MaDhteRopEB1eQtEahHb_hPLw97vm0_GR02zLHGZdkeXKtltIE7J7q5h2NpLyT7OBO94DFuHq3KgrA6oLM540q22vxYDQAAAAGuvoCcAA"
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

# Function to start user clients only if they are not already connected
async def start_user_clients():
    for user_client in user_clients:
        if not await user_client.is_connected():
            await user_client.start()

# Dictionary to store user data
user_data = {}

# Start command handler
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply(
        "Hello! I'm the Mass Report Bot. Please send the link of the group or channel you want to report.",
        reply_markup=ForceReply(selective=True)
    )
    user_data[message.chat.id] = {"state": "awaiting_link"}

# Message handler
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_message(client, message):
    chat_id = message.chat.id
    text = message.text.strip()
    user_info = user_data.get(chat_id, {})

    if not user_info:
        await message.reply("Please start the process by sending /start.")
        return

    state = user_info.get("state")

    if state == "awaiting_link":
        user_info["link"] = text
        user_info["state"] = "awaiting_reason"
        buttons = [
            [InlineKeyboardButton(reason[0], callback_data=f"reason_{reason[1]}")] for reason in REPORT_REASONS
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("Please select the reason for the report:", reply_markup=reply_markup)

    elif state == "awaiting_count":
        if text.isdigit() and int(text) > 0:
            user_info["count"] = int(text)
            user_info["state"] = "ready_to_report"
            await message.reply(f"Starting to send {user_info['count']} reports for the link: {user_info['link']} with reason: {user_info['reason']}")
            await send_reports(client, message, user_info)
        else:
            await message.reply("Please enter a valid number of reports.", reply_markup=ForceReply(selective=True))

# Callback query handler for report reason
@bot.on_callback_query(filters.regex(r"^reason_"))
async def handle_reason(client, callback_query):
    chat_id = callback_query.message.chat.id
    user_info = user_data.get(chat_id, {})

    if not user_info or user_info.get("state") != "awaiting_reason":
        await callback_query.message.reply("Something went wrong. Please start over with /start.")
        return

    reason_code = callback_query.data.split("_")[1]
    user_info["reason"] = reason_code
    user_info["state"] = "awaiting_count"
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
    user_info["state"] = "completed"

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
