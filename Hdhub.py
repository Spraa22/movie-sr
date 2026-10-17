import re
import html as html_lib
import base64
import codecs
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

API_ID = 25492855
API_HASH = "61876db014de51a4ace6b169608be4f1"
BOT_TOKEN = "8455076923:AAGR7WcmzrylOx3AXSNDDDys7Iok8RNFxtE"

BASE_DOMAIN = "https://new8.hdhub4u.cl"
SEARCH_API = "https://search.pingora.fyi/collections/post/documents/search"

USER_SEARCHES = {}

app = Client("hdhub_search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FAST TOKEN BYPASSER ---
RE_TOKEN = re.compile(rb"s\(\s*['\"]o['\"]\s*,\s*['\"]([^'\"]+)['\"]")
RE_TARGET = re.compile(rb'"o"\s*:\s*"([^"]+)"')

class FastBypasser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate"
        })

    def decode_fast(self, raw_token_b64: bytes) -> str:
        s1 = base64.b64decode(raw_token_b64)
        s2 = base64.b64decode(s1).decode("ascii")
        s3 = codecs.decode(s2, "rot_13").encode("ascii")
        s4 = base64.b64decode(s3)
        match = RE_TARGET.search(s4)
        if match:
            return base64.b64decode(match.group(1)).decode("utf-8")
        raise ValueError("Field 'o' not found")

    def get_final_url(self, url: str) -> str:
        if "greenmotors" not in url:
            return url
        try:
            with self.session.get(url, stream=True, timeout=5) as r:
                chunk = b""
                for block in r.iter_content(chunk_size=4096):
                    chunk += block
                    match = RE_TOKEN.search(chunk)
                    if match:
                        r.close()
                        return self.decode_fast(match.group(1))
        except Exception as e:
            print(f"Bypass Error: {e}")
        return url

bypasser = FastBypasser()

# --- 1. सर्च API ---
def fetch_search_results(query, page=1):
    params = {
        "q": query,
        "query_by": "post_title,category,stars,director,imdb_id",
        "query_by_weights": "4,2,2,2,4",
        "sort_by": "sort_by_date:desc",
        "limit": 8,
        "page": page
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE_DOMAIN}/"
    }
    try:
        res = requests.get(SEARCH_API, params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Search API Error: {e}")
    return None

# --- 2. केवल मुख्य डाउनलोड लिंक्स पार्सर ---
def extract_main_links(post_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
        "Referer": f"{BASE_DOMAIN}/"
    }
    try:
        res = requests.get(post_url, headers=headers, timeout=12)
        if res.status_code != 200:
            return []
        page_html = res.text
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []

    # सिर्फ मुख्य DOWNLOAD LINKS ब्लॉक को उठाएं (Single Episode से पहले)
    sec_match = re.search(
        r':\s*DOWNLOAD\s*LINKS\s*:.*?(?=:\s*Single\s*Episode|\bSingle\s*Episode|<div class="responsive-embed-container"|Index of|<h2|class="wpra-reactions|$)',
        page_html, re.I | re.S
    )
    block = sec_match.group(0) if sec_match else page_html

    links = []
    link_regex = re.compile(r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)

    for m in link_regex.finditer(block):
        raw_url = m.group(1).strip()
        txt = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        txt = re.sub(r'\s+', ' ', txt)

        if not txt or raw_url.startswith('#') or 'javascript:' in raw_url or 'catimages' in raw_url:
            continue

        final_url = bypasser.get_final_url(raw_url)
        links.append({"text": txt, "url": final_url})

    return links

# --- 3. ओरिजिनल सर्च लिस्ट UI (जैसा पहले था) ---
def build_search_view(user_id, query, page=1):
    data = fetch_search_results(query, page)
    if not data or not data.get("hits"):
        return "⚠️ <b>कोई परिणाम नहीं मिला!</b>\nकृपया सही स्पेलिंग लिखकर सर्च करें।", None

    total_hits = data.get("found", 0)
    hits = data.get("hits", [])

    USER_SEARCHES[user_id] = {
        "query": query,
        "page": page,
        "items": hits
    }

    # ओरिजिनल क्लासिक सर्च हेडर
    text = (
        f"╭─────────────────────╮\n"
        f"  🎬 <b>HDHub4u Search Engine</b>\n"
        f"╰─────────────────────╯\n"
        f"🔍 <b>Query:</b> <code>{html_lib.escape(query)}</code>\n"
        f"📊 <b>Total Found:</b> <code>{total_hits}</code> | <b>Page:</b> <code>{page}</code>\n\n"
    )

    num_buttons = []
    for idx, hit in enumerate(hits, 1):
        doc = hit.get("document", {})
        title = doc.get("post_title", "Untitled")
        category = doc.get("category", "General")

        safe_title = html_lib.escape(title)
        safe_cat = html_lib.escape(str(category))

        text += f"<b>[{idx}]</b> {safe_title}\n"
        text += f"      🏷️ <code>{safe_cat}</code>\n\n"

        num_buttons.append(InlineKeyboardButton(f"[{idx}]", callback_data=f"item_{idx}"))

    keyboard = [num_buttons[i:i + 4] for i in range(0, len(num_buttons), 4)]

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"• {page} •", callback_data="noop"))
    if (page * 8) < total_hits:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))

    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_menu")])

    return text, InlineKeyboardMarkup(keyboard)

# --- 4. बॉट इवेंट्स ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text(
        "👋 <b>नमस्ते!</b>\nमूवी या सीरीज सर्च करने के लिए लिखें:\n<code>/search movie_name</code>",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("search"))
async def search_handler(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ <b>कृपया मूवी का नाम लिखें!</b>\nउदाहरण: <code>/search animal</code>",
            parse_mode=enums.ParseMode.HTML
        )

    query = message.text.split(maxsplit=1)[1].strip()
    status_msg = await message.reply_text("⚡ <i>सर्च किया जा रहा है...</i>", parse_mode=enums.ParseMode.HTML)

    text, reply_markup = build_search_view(message.from_user.id, query, page=1)
    if reply_markup:
        await status_msg.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    else:
        await status_msg.edit_text(text, parse_mode=enums.ParseMode.HTML)

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    cb_data = callback.data

    if cb_data == "close_menu":
        USER_SEARCHES.pop(user_id, None)
        return await callback.message.delete()

    if cb_data == "noop":
        return await callback.answer()

    user_session = USER_SEARCHES.get(user_id)

    # पेजिंग
    if cb_data.startswith("page_"):
        if not user_session:
            return await callback.answer("⚠️ सेशन समाप्त हो गया, पुनः /search करें।", show_alert=True)

        target_page = int(cb_data.split("_")[1])
        await callback.answer(f"पेज {target_page}...")
        text, reply_markup = build_search_view(user_id, user_session["query"], target_page)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # डाउनलोड लिंक्स पेज (MESSAGE_TOO_LONG सेफ + नो हाइपरलिंक)
    elif cb_data.startswith("item_"):
        if not user_session:
            return await callback.answer("⚠️ सेशन समाप्त हो गया, पुनः /search करें।", show_alert=True)

        idx = int(cb_data.split("_")[1]) - 1
        items = user_session.get("items", [])
        if idx >= len(items):
            return await callback.answer("अमान्य चयन!", show_alert=True)

        doc = items[idx].get("document", {})
        title = doc.get("post_title", "Media Details")
        category = doc.get("category", "General")
        permalink = doc.get("permalink", "")

        if permalink.startswith("http"):
            post_url = f"{BASE_DOMAIN}/" + "/".join(permalink.split("/")[3:])
        elif permalink.startswith("/"):
            post_url = f"{BASE_DOMAIN}{permalink}"
        else:
            post_url = f"{BASE_DOMAIN}/{permalink}"

        await callback.answer("डिकोडिंग लिंक्स...")
        await callback.message.edit_text(
            f"⚡ <b>'{html_lib.escape(title)}' के लिंक्स लोड हो रहे हैं...</b>",
            parse_mode=enums.ParseMode.HTML
        )

        links = extract_main_links(post_url)
        back_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back to Results", callback_data="back_to_list")],
            [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ])

        safe_title = html_lib.escape(title)
        safe_cat = html_lib.escape(str(category))

        if not links:
            return await callback.message.edit_text(
                f"🎬 <b>{safe_title}</b>\n\n❌ <i>कोई मुख्य डाउनलोड लिंक नहीं मिला।</i>",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        # नया साफ-सुथरा UI (बिना एक्स्ट्रा गैप और बिना हाइपरलिंक)
        header_text = (
            f"🎬 <b>{safe_title}</b>\n"
            f"🏷️ <code>{safe_cat}</code>\n"
            f"────────────────────────\n"
            f"📥 <b>DOWNLOAD LINKS:</b>\n"
        )

        res_text = header_text
        footer_note = "\n────────────────────────\n💡 <i>लिंक पर टैप करके कॉपी या ओपन करें।</i>"

        for lk in links:
            t_clean = html_lib.escape(lk["text"])
            u_clean = html_lib.escape(lk["url"])
            
            # डायरेक्ट URL (बिना हाइपरलिंक के - सादा और कॉपी करने में आसान)
            line = f"⚡ <b>{t_clean}</b>\n🔗 <code>{u_clean}</code>\n\n"

            # 4000 कैरेक्टर सीमा की सख्त जांच (MESSAGE_TOO_LONG रोकने के लिए)
            if len(res_text) + len(line) + len(footer_note) > 4000:
                res_text += "⚠️ <i>[बाकी लिंक्स बहुत लंबे होने के कारण ट्रिम किए गए]</i>\n"
                break

            res_text += line

        res_text = res_text.rstrip() + footer_note

        try:
            await callback.message.edit_text(
                res_text,
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            # अगर फिर भी कोई साइज दिक्कत आए तो इमरजेंसी फॉलबैक
            print(f"Edit Message Error: {e}")
            safe_fallback = header_text + "\n".join([f"• <b>{html_lib.escape(l['text'])}:</b> {html_lib.escape(l['url'])}" for l in links[:5]])
            await callback.message.edit_text(
                safe_fallback[:3900],
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

    # बैक टू सर्च लिस्ट
    elif cb_data == "back_to_list":
        if not user_session:
            return await callback.answer("⚠️ सेशन समाप्त हो गया, पुनः /search करें।", show_alert=True)

        await callback.answer()
        text, reply_markup = build_search_view(user_id, user_session["query"], user_session.get("page", 1))
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

if __name__ == "__main__":
    print("Bot is running with Safe Character Limits & Direct URLs...")
    app.run()
