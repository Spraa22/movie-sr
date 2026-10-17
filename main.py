import html as html_lib
import uuid
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# 1. Dono files ko directly import karein
import Hdhub
import importlib

# Python mein file name number se start ho toh importlib use hota hai
fourk = importlib.import_module("4khdub")

API_ID = 25492855
API_HASH = "61876db014de51a4ace6b169608be4f1"
BOT_TOKEN = "8455076923:AAGR7WcmzrylOx3AXSNDDDys7Iok8RNFxtE"

# Master Bot Client
app = Client("master_router_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Active Search Sessions
PENDING_ROUTER = {}

@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "👋 <b>Namaste!</b>\n\nMovie ya Series search karne ke liye command dein:\n<code>/search movie_name</code>",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("search"))
async def search_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ <b>Kripya movie ka naam likhein!</b>\nUdaharan: <code>/search avengers</code>",
            parse_mode=enums.ParseMode.HTML
        )

    query = message.text.split(maxsplit=1)[1].strip()
    qid = uuid.uuid4().hex[:8]

    PENDING_ROUTER[qid] = {
        "user_id": message.from_user.id,
        "query": query,
        "chat_id": message.chat.id,
        "msg_id": message.id
    }

    # Dono servers ke buttons
    text = (
        f"╭─────────────────────╮\n"
        f"  🌐 <b>SELECT SEARCH SERVER</b>\n"
        f"╰─────────────────────╯\n"
        f"🔍 <b>Query:</b> <code>{html_lib.escape(query)}</code>\n\n"
        f"Kahan search karna chahte hain? Server select karein:"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ HDHub4u Server", callback_data=f"rt_{qid}_hdhub")],
        [InlineKeyboardButton("💎 4KHDHub Server", callback_data=f"rt_{qid}_4khd")],
        [InlineKeyboardButton("❌ Close", callback_data=f"rt_{qid}_close")]
    ])

    await message.reply_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)

# Server Selector Callback Handler
@app.on_callback_query(filters.regex(r"^rt_"))
async def server_route_callback(client: Client, callback: CallbackQuery):
    _, qid, choice = callback.data.split("_")

    if choice == "close":
        PENDING_ROUTER.pop(qid, None)
        return await callback.message.delete()

    session = PENDING_ROUTER.get(qid)
    if not session:
        return await callback.answer("⚠️ Session expire ho chuka hai. Naya /search karein.", show_alert=True)

    query = session["query"]
    user_id = session["user_id"]
    chat_id = session["chat_id"]
    orig_msg_id = session["msg_id"]

    await callback.message.delete()

    # --- Choice A: HDHub4u ---
    if choice == "hdhub":
        await callback.answer("HDHub4u se fetch ho raha hai...")
        text, markup = Hdhub.build_search_view(user_id, query, page=1)
        if markup:
            await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_to_message_id=orig_msg_id
            )
        else:
            await client.send_message(chat_id=chat_id, text=text, parse_mode=enums.ParseMode.HTML, reply_to_message_id=orig_msg_id)

    # --- Choice B: 4KHDHub ---
    elif choice == "4khd":
        await callback.answer("4KHDHub se fetch ho raha hai...")
        items = fourk.fetch_search_results(query)
        if not items:
            return await client.send_message(
                chat_id=chat_id,
                text="⚠️ <b>4KHDHub: Koi result nahi mila!</b>",
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=orig_msg_id
            )

        sid = uuid.uuid4().hex[:8]
        fourk.SEARCH_SESSIONS[sid] = {
            "user_id": user_id,
            "query": query,
            "page": 1,
            "items": items,
            "timestamp": 0
        }

        text, markup = fourk.build_search_view(sid, page=1)
        if markup:
            await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_to_message_id=orig_msg_id
            )

    PENDING_ROUTER.pop(qid, None)

# --- Sub-file Callbacks Ko Pass Karna ---
# 1. Hdhub.py ke callbacks: [item_, page_, back_to_list, close_menu]
@app.on_callback_query(filters.regex(r"^(item_|page_|back_to_list|close_menu)"))
async def hdhub_delegate(client: Client, callback: CallbackQuery):
    await Hdhub.callback_handler(client, callback)

# 2. 4khdub.py ke callbacks: [it_, sp_, sn_, snp_, bks_, bkl_, cl_]
@app.on_callback_query(filters.regex(r"^(it_|sp_|sn_|snp_|bks_|bkl_|cl_)"))
async def fourk_delegate(client: Client, callback: CallbackQuery):
    await fourk.callback_handler(client, callback)


if __name__ == "__main__":
    print("Master Router Bot is running perfectly...")
    app.run()
