import re
import html as html_lib
import base64
import codecs
import time
import uuid
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

API_ID = 25492855
API_HASH = "61876db014de51a4ace6b169608be4f1"
BOT_TOKEN = "8455076923:AAGR7WcmzrylOx3AXSNDDDys7Iok8RNFxtE"

BASE_DOMAIN = "https://4khdhub.one"

# आइसोलेटेड सेशन स्टोरेज (Unique ID based)
SEARCH_SESSIONS = {}

app = Client("fourk_hdhub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FAST TOKEN BYPASSER ---
RE_TOKEN = re.compile(rb"s\(\s*['\"]o['\"]\s*,\s*['\"]([^'\"]+)['\"]")
RE_TARGET = re.compile(rb'"o"\s*:\s*"([^"]+)"')

class FastBypasser:
    def __init__(self):
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
            with self.session.get(url, stream=True, timeout=3.5) as r:
                chunk = b""
                for block in r.iter_content(chunk_size=4096):
                    chunk += block
                    match = RE_TOKEN.search(chunk)
                    if match:
                        r.close()
                        return self.decode_fast(match.group(1))
        except Exception:
            pass
        return url

bypasser = FastBypasser()

# --- OPTIMIZED FAST HTTP CLIENT ---
http_client = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=15)
http_client.mount("https://", adapter)
http_client.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_DOMAIN}/"
})

def clean_expired_sessions():
    """1 घंटे से पुराने सेशन्स को मेमोरी से हटाना"""
    now = time.time()
    expired = [sid for sid, data in SEARCH_SESSIONS.items() if now - data.get("timestamp", now) > 3600]
    for sid in expired:
        SEARCH_SESSIONS.pop(sid, None)

# --- 1. FAST SEARCH SCRAPER ---
def fetch_search_results(query):
    search_url = f"{BASE_DOMAIN}/"
    params = {"s": query}
    try:
        res = http_client.get(search_url, params=params, timeout=5)
        if res.status_code != 200:
            return []
        
        soup = BeautifulSoup(res.text, "html.parser")
        cards = soup.select(".card-grid .movie-card, .movie-card")
        
        results = []
        for card in cards:
            title_tag = card.select_one(".movie-card-title")
            meta_tag = card.select_one(".movie-card-meta")
            link = card.get("href", "")

            if not title_tag or not link:
                continue

            title = title_tag.get_text(strip=True)
            meta = meta_tag.get_text(strip=True) if meta_tag else "Movie"

            badge_tag = card.select_one(".quality-badge")
            badge = badge_tag.get_text(strip=True) if badge_tag else ""

            full_url = f"{BASE_DOMAIN}{link}" if link.startswith("/") else link

            results.append({
                "title": title,
                "meta": meta,
                "badge": badge,
                "url": full_url
            })
        return results
    except Exception as e:
        print(f"Fast Search Error: {e}")
        return []

# --- 2. POST CONTENT PARSER ---
def parse_post_content(post_url):
    try:
        res = http_client.get(post_url, timeout=7)
        if res.status_code != 200:
            return None
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        seasons_label = soup.find(lambda tag: tag.name in ["span", "div"] and "Seasons:" in tag.text)
        is_series = bool(seasons_label or soup.select(".series-tabs, #complete-pack"))

        def find_size(elem):
            if not elem:
                return ""
            for badge in elem.select(".badge"):
                b_txt = badge.get_text(strip=True)
                if re.search(r'\d+(\.\d+)?\s*(GB|MB)', b_txt, re.I):
                    return b_txt
            m = re.search(r'(\d+(\.\d+)?\s*(GB|MB))', elem.get_text(), re.I)
            return m.group(1) if m else ""

        # A. सीरीज़
        if is_series:
            download_items = soup.select("#complete-pack .download-item, .download-item")
            series_data = {}
            all_raw_links = []

            for item in download_items:
                ep_elem = item.select_one(".episode-number")
                season_name = ep_elem.get_text(strip=True).upper() if ep_elem else "PACKS"
                
                title_elem = item.select_one(".file-title")
                hdr_elem = item.select_one(".download-header")
                
                f_title = title_elem.get_text(strip=True) if title_elem else (hdr_elem.get_text(" ", strip=True) if hdr_elem else "Season Pack")
                f_size = find_size(item)

                btn_links = item.select("a.btn")
                chosen_url = None
                chosen_type = "HubCloud"

                for b in btn_links:
                    b_txt = b.get_text(strip=True).lower()
                    href = b.get("href", "").strip()
                    if not href or href.startswith("#"):
                        continue
                    if "hubcloud" in b_txt or "cloud" in href.lower():
                        chosen_url = href
                        chosen_type = "HubCloud"
                        break
                    elif not chosen_url:
                        chosen_url = href
                        chosen_type = "HubDrive"

                if chosen_url:
                    if season_name not in series_data:
                        series_data[season_name] = []
                    
                    series_data[season_name].append({
                        "title": f_title,
                        "size": f_size,
                        "btn_name": chosen_type,
                        "raw_url": chosen_url,
                        "final_url": chosen_url
                    })
                    all_raw_links.append(chosen_url)

            unique_urls = list(set(all_raw_links))
            with ThreadPoolExecutor(max_workers=10) as executor:
                resolved_urls = dict(executor.map(lambda u: (u, bypasser.get_final_url(u)), unique_urls))

            for s_name in series_data:
                for f in series_data[s_name]:
                    f["final_url"] = resolved_urls.get(f["raw_url"], f["raw_url"])

            return {"type": "series", "data": series_data}

        # B. मूवी
        else:
            file_containers = soup.select('div[id^="content-file"]')
            movie_files = []
            all_raw_links = []

            if file_containers:
                for container in file_containers:
                    title_tag = container.select_one(".file-title")
                    file_title = title_tag.get_text(strip=True) if title_tag else "Movie File"
                    
                    parent_block = container.find_parent("div", class_="download-item") or container
                    file_size = find_size(parent_block)

                    btn_links = container.select("a.btn")
                    chosen_url = None
                    chosen_type = "HubCloud"

                    for b in btn_links:
                        b_txt = b.get_text(strip=True).lower()
                        href = b.get("href", "").strip()
                        if not href or href.startswith("#"):
                            continue
                        if "hubcloud" in b_txt or "cloud" in href.lower():
                            chosen_url = href
                            chosen_type = "HubCloud"
                            break
                        elif not chosen_url:
                            chosen_url = href
                            chosen_type = "HubDrive"

                    if chosen_url:
                        movie_files.append({
                            "title": file_title,
                            "size": file_size,
                            "btn_name": chosen_type,
                            "raw_url": chosen_url,
                            "final_url": chosen_url
                        })
                        all_raw_links.append(chosen_url)

            unique_urls = list(set(all_raw_links))
            with ThreadPoolExecutor(max_workers=10) as executor:
                resolved_urls = dict(executor.map(lambda u: (u, bypasser.get_final_url(u)), unique_urls))

            for mf in movie_files:
                mf["final_url"] = resolved_urls.get(mf["raw_url"], mf["raw_url"])

            return {"type": "movie", "data": movie_files}

    except Exception as e:
        print(f"Parser Error: {e}")
        return None

# --- 3. UI व्यू बिल्डर (Session ID के साथ) ---
def build_search_view(sid, page=1):
    session = SEARCH_SESSIONS.get(sid)
    if not session:
        return "⚠️ <b>सेशन समाप्त हो गया!</b>\nकृपया पुनः /search करें।", None

    items = session["items"]
    query = session["query"]
    total_hits = len(items)
    
    PER_PAGE = 8
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    current_page_items = items[start_idx:end_idx]

    session["page"] = page

    text = (
        f"╭─────────────────────╮\n"
        f"  🎬 <b>4KHDHub Search Engine</b>\n"
        f"╰─────────────────────╯\n"
        f"🔍 <b>Query:</b> <code>{html_lib.escape(query)}</code>\n"
        f"📊 <b>Total Found:</b> <code>{total_hits}</code> | <b>Page:</b> <code>{page}</code>\n\n"
    )

    num_buttons = []
    for idx, itm in enumerate(current_page_items, 1):
        actual_idx = start_idx + idx
        safe_title = html_lib.escape(itm["title"])
        badge_str = f" [{itm['badge']}]" if itm["badge"] else ""
        meta_str = f" ({itm['meta']})" if itm["meta"] else ""

        text += f"<b>[{idx}]</b> {safe_title}{badge_str}\n"
        text += f"      🏷️ <code>{meta_str.strip()}</code>\n\n"

        num_buttons.append(InlineKeyboardButton(f"[{idx}]", callback_data=f"it_{sid}_{actual_idx}"))

    keyboard = [num_buttons[i:i + 4] for i in range(0, len(num_buttons), 4)]

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sp_{sid}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"• {page} •", callback_data="noop"))
    if end_idx < total_hits:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"sp_{sid}_{page+1}"))

    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data=f"cl_{sid}")])

    return text, InlineKeyboardMarkup(keyboard)

# --- 4. सीरीज़ सीज़न लिंक्स व्यू ---
def build_season_links_view(sid, season_name, page=1):
    session = SEARCH_SESSIONS.get(sid)
    if not session or "series_data" not in session:
        return None, None

    title = session["selected_title"]
    files = session["series_data"].get(season_name, [])

    if not files:
        return "❌ <i>इस सीज़न के लिए कोई पैक लिंक उपलब्ध नहीं है।</i>", None

    PER_PAGE = 4
    total_files = len(files)
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    page_files = files[start_idx:end_idx]

    safe_title = html_lib.escape(title)
    
    text = (
        f"📺 <b>{safe_title}</b>\n"
        f"📁 <b>Season:</b> <code>{season_name}</code> (Zip / Packs)\n"
        f"────────────────────────\n"
        f"📥 <b>DOWNLOAD LINKS:</b>\n\n"
    )

    for f in page_files:
        f_name = html_lib.escape(f["title"])
        f_url = html_lib.escape(f["final_url"])
        size_str = f" 💾 <code>{f['size']}</code>" if f['size'] else ""
        
        text += f"⚡ <b>{f_name}</b>{size_str}\n"
        text += f"   └ <b>{f['btn_name']}:</b> <code>{f_url}</code>\n\n"

    text += "────────────────────────\n💡 <i>लिंक पर टैप करके कॉपी या ओपन करें।</i>"

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"snp_{sid}_{season_name}_{page-1}"))
    if end_idx < total_files:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"snp_{sid}_{season_name}_{page+1}"))

    keyboard = []
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("« Back to Seasons", callback_data=f"bks_{sid}")])
    keyboard.append([InlineKeyboardButton("« Back to Search Results", callback_data=f"bkl_{sid}")])

    return text, InlineKeyboardMarkup(keyboard)

# --- 5. बॉट कमांड्स & कॉलबैक हैंडलर ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text(
        "👋 <b>नमस्ते!</b>\n4KHDHub से 4K/FHD मूवीज & सीरीज खोजने के लिए लिखें:\n<code>/search movie_or_series</code>",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("search"))
async def search_handler(client, message):
    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ <b>कृपया नाम लिखें!</b>\nउदाहरण: <code>/search reacher</code>",
            parse_mode=enums.ParseMode.HTML
        )

    query = message.text.split(maxsplit=1)[1].strip()
    clean_expired_sessions()
    
    status_msg = await message.reply_text("⚡ <i>सर्च किया जा रहा है...</i>", parse_mode=enums.ParseMode.HTML)

    # फ्रेश सर्च फेच
    items = fetch_search_results(query)
    if not items:
        return await status_msg.edit_text("⚠️ <b>कोई परिणाम नहीं मिला!</b>\nकृपया सही स्पेलिंग लिखकर सर्च करें।", parse_mode=enums.ParseMode.HTML)

    # हर सर्च को नया यूनिक सेशन ID
    sid = uuid.uuid4().hex[:8]
    SEARCH_SESSIONS[sid] = {
        "user_id": message.from_user.id,
        "query": query,
        "page": 1,
        "items": items,
        "timestamp": time.time()
    }

    text, reply_markup = build_search_view(sid, page=1)
    await status_msg.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    cb_data = callback.data

    if cb_data == "noop":
        return await callback.answer()

    parts = cb_data.split("_")
    action = parts[0]

    # क्लोज
    if action == "cl":
        sid = parts[1]
        SEARCH_SESSIONS.pop(sid, None)
        return await callback.message.delete()

    # सर्च पेजिनेशन (sp_{sid}_{page})
    if action == "sp":
        sid = parts[1]
        target_page = int(parts[2])
        if sid not in SEARCH_SESSIONS:
            return await callback.answer("⚠️ यह सर्च एक्सपायर हो चुकी है। नया /search करें।", show_alert=True)
        
        await callback.answer()
        text, reply_markup = build_search_view(sid, target_page)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # आइटम चुनना (it_{sid}_{idx})
    elif action == "it":
        sid = parts[1]
        actual_idx = int(parts[2]) - 1

        session = SEARCH_SESSIONS.get(sid)
        if not session or actual_idx >= len(session["items"]):
            return await callback.answer("⚠️ यह सर्च एक्सपायर हो चुकी है। नया /search करें।", show_alert=True)

        selected_item = session["items"][actual_idx]
        title = selected_item["title"]
        post_url = selected_item["url"]

        await callback.answer("डिकोडिंग लिंक...")
        await callback.message.edit_text(
            f"⚡ <b>'{html_lib.escape(title)}' लोड हो रहा है...</b>",
            parse_mode=enums.ParseMode.HTML
        )

        parsed = parse_post_content(post_url)

        back_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back to Results", callback_data=f"bkl_{sid}")],
            [InlineKeyboardButton("❌ Close", callback_data=f"cl_{sid}")]
        ])

        safe_title = html_lib.escape(title)

        if not parsed or not parsed["data"]:
            return await callback.message.edit_text(
                f"🎬 <b>{safe_title}</b>\n\n❌ <i>कोई मुख्य डाउनलोड लिंक उपलब्ध नहीं है।</i>",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        # सीरीज़ (सीज़न बटन्स)
        if parsed["type"] == "series":
            session["series_data"] = parsed["data"]
            session["selected_title"] = title

            seasons_available = list(parsed["data"].keys())
            s_text = (
                f"📺 <b>{safe_title}</b>\n"
                f"────────────────────────\n"
                f"📁 <b>उपलब्ध सीज़न (Seasons):</b>\n"
                f"नीचे दिए गए किसी भी सीज़न बटन पर क्लिक करें:\n"
            )

            season_btns = [InlineKeyboardButton(f"📂 {s}", callback_data=f"sn_{sid}_{s}") for s in seasons_available]
            s_keyboard = [season_btns[i:i + 3] for i in range(0, len(season_btns), 3)]
            s_keyboard.append([InlineKeyboardButton("« Back to Search Results", callback_data=f"bkl_{sid}")])
            s_keyboard.append([InlineKeyboardButton("❌ Close", callback_data=f"cl_{sid}")])

            await callback.message.edit_text(
                s_text,
                reply_markup=InlineKeyboardMarkup(s_keyboard),
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

        # मूवी (डायरेक्ट फाइल्स)
        else:
            m_text = (
                f"🎬 <b>{safe_title}</b>\n"
                f"────────────────────────\n"
                f"📥 <b>DOWNLOAD LINKS:</b>\n\n"
            )
            footer_note = "────────────────────────\n💡 <i>लिंक पर टैप करके कॉपी या ओपन करें।</i>"

            for mf in parsed["data"]:
                mf_title = html_lib.escape(mf["title"])
                mf_url = html_lib.escape(mf["final_url"])
                size_str = f" 💾 <code>{mf['size']}</code>" if mf['size'] else ""

                m_line = f"⚡ <b>{mf_title}</b>{size_str}\n"
                m_line += f"   └ <b>{mf['btn_name']}:</b> <code>{mf_url}</code>\n\n"

                if len(m_text) + len(m_line) + len(footer_note) > 4000:
                    m_text += "⚠️ <i>[बाकी लिंक्स बहुत लंबे होने के कारण ट्रिम किए गए]</i>\n\n"
                    break

                m_text += m_line

            m_text += footer_note
            await callback.message.edit_text(
                m_text,
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )

    # सीज़न चयन (sn_{sid}_{season})
    elif action == "sn":
        sid = parts[1]
        season_name = parts[2]
        await callback.answer(f"सीज़न {season_name}...")
        text, markup = build_season_links_view(sid, season_name, page=1)
        if text:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # सीज़न पेजिनेशन (snp_{sid}_{season}_{page})
    elif action == "snp":
        sid = parts[1]
        season_name = parts[2]
        target_page = int(parts[3])
        await callback.answer()
        text, markup = build_season_links_view(sid, season_name, page=target_page)
        if text:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # वापस सीज़न्स मेनू (bks_{sid})
    elif action == "bks":
        sid = parts[1]
        session = SEARCH_SESSIONS.get(sid)
        if not session or "series_data" not in session:
            return await callback.answer("⚠️ सेशन समाप्त हो गया, पुनः /search करें।", show_alert=True)

        await callback.answer()
        safe_title = html_lib.escape(session["selected_title"])
        seasons_available = list(session["series_data"].keys())

        s_text = (
            f"📺 <b>{safe_title}</b>\n"
            f"────────────────────────\n"
            f"📁 <b>उपलब्ध सीज़न (Seasons):</b>\n"
            f"नीचे दिए गए किसी भी सीज़न बटन पर क्लिक करें:\n"
        )
        season_btns = [InlineKeyboardButton(f"📂 {s}", callback_data=f"sn_{sid}_{s}") for s in seasons_available]
        s_keyboard = [season_btns[i:i + 3] for i in range(0, len(season_btns), 3)]
        s_keyboard.append([InlineKeyboardButton("« Back to Search Results", callback_data=f"bkl_{sid}")])
        s_keyboard.append([InlineKeyboardButton("❌ Close", callback_data=f"cl_{sid}")])

        await callback.message.edit_text(s_text, reply_markup=InlineKeyboardMarkup(s_keyboard), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # वापस सर्च लिस्ट (bkl_{sid})
    elif action == "bkl":
        sid = parts[1]
        if sid not in SEARCH_SESSIONS:
            return await callback.answer("⚠️ सेशन समाप्त हो गया, पुनः /search करें।", show_alert=True)

        await callback.answer()
        current_page = SEARCH_SESSIONS[sid].get("page", 1)
        text, reply_markup = build_search_view(sid, current_page)
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

if __name__ == "__main__":
    print("4KHDHub Bot running: Cache Isolation + Session IDs + High Speed...")
    app.run()
