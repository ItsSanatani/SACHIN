from pyrogram import Client, filters
from pyrogram.types import ChatReportReason
import asyncio
import config

# Telegram Supported Reasons Map
REASONS = {
    "1": ChatReportReason.SPAM,
    "2": ChatReportReason.FAKE,
    "3": ChatReportReason.VIOLENCE,
    "4": ChatReportReason.PORNOGRAPHY,
    "5": ChatReportReason.CHILD_ABUSE,
    "6": ChatReportReason.COPYRIGHT,
    "7": ChatReportReason.OTHER,
    "8": ChatReportReason.PERSONAL_DETAILS
}

# Initialize Bot Clients for each session string
clients = [
    Client(
        name=f"client_{i}",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=session_string
    )
    for i, session_string in enumerate(config.SESSION_STRINGS)
]

# Initialize Control Bot
control_bot = Client("control_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token="7656369802:AAGdlo88cewouuiviq-eHoRHdxj_Ktji3To")

# Start Command
@control_bot.on_message(filters.command("start"))
async def start(bot, message):
    await message.reply("Hello! I'm Mass Report Bot. Use /report to start reporting.")

# Report Command
@control_bot.on_message(filters.command("report"))
async def report(bot, message):
    chat_id = message.chat.id

    # Ask for Group/Channel Link
    await bot.send_message(chat_id, "Please send the Group/Channel Username or Invite Link:")
    group_link = (await bot.listen(chat_id)).text

    # Ask for Report Type
    await bot.send_message(chat_id, "What do you want to report?\n1. Group/Channel\n2. Specific Message\nEnter 1 or 2:")
    target_type = (await bot.listen(chat_id)).text

    # If Specific Message, ask for Message Link
    if target_type == "2":
        await bot.send_message(chat_id, "Please send the Message Link (https://t.me/xxxx/12345):")
        message_link = (await bot.listen(chat_id)).text

    # Ask for Report Reason
    reason_menu = "\nSelect Report Reason:\n"
    for key, value in REASONS.items():
        reason_menu += f"{key}. {value}\n"
    await bot.send_message(chat_id, reason_menu)
    choice = (await bot.listen(chat_id)).text
    reason = REASONS.get(choice, ChatReportReason.SPAM)

    # Ask for Number of Reports
    await bot.send_message(chat_id, "How many reports do you want to send?")
    report_count = int((await bot.listen(chat_id)).text)

    # Confirm Details
    confirm_msg = f"Please confirm the details:\n\nGroup/Channel: {group_link}\n"
    if target_type == "2":
        confirm_msg += f"Message: {message_link}\n"
    confirm_msg += f"Reason: {reason}\nNumber of Reports: {report_count}\n\nType 'yes' to confirm or 'no' to cancel."
    await bot.send_message(chat_id, confirm_msg)
    confirmation = (await bot.listen(chat_id)).text.lower()

    if confirmation != "yes":
        await bot.send_message(chat_id, "Operation cancelled.")
        return

    # Reporting Function
    async def report_action(client):
        try:
            async with client:
                chat = await client.get_chat(group_link)
                
                for i in range(report_count):
                    if target_type == "1":
                        # Report full group/channel
                        await client.report_chat(
                            chat_id=chat.id,
                            reason=reason,
                            text="Mass Report Bot"
                        )
                    else:
                        # Report specific message
                        msg_id = int(message_link.split("/")[-1])
                        await client.report_chat_message(
                            chat_id=chat.id,
                            message_ids=[msg_id],
                            reason=reason,
                            text="Mass Report Bot"
                        )
                    
                    await bot.send_message(chat_id, f"Report successfully sent {i + 1} 📤")
                    await asyncio.sleep(1)  # थोड़ा विराम ताकि rate limit से बचा जा सके
                    
        except Exception as e:
            await bot.send_message(chat_id, f"Error: {e}")

    # Start Reporting
    tasks = [report_action(client) for client in clients]
    await asyncio.gather(*tasks)
    await bot.send_message(chat_id, "Reporting completed.")

# Run Control Bot
control_bot.run()
