import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
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
