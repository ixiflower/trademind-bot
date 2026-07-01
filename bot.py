"""
TradeMind Signal Bot - Telegram Bot
AI-powered trading signals for binary options
Persian UI + chat cleanup + back navigation everywhere
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
    InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultsButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler
)
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN, AVAILABLE_PAIRS, PAIRS_LIST_HEADER,
    WELCOME_MESSAGE, HELP_MESSAGE, ERROR_MESSAGE,
    PAIR_NOT_FOUND, BINARY_EXPIRY_OPTIONS, CATEGORY_ORDER,
    CATEGORY_DISPLAY, PAIRS_PER_ROW, get_pair_display,
    get_pairs_by_category,
)
from signal_engine import generate_signal, generate_full_analysis

# ---- Optional Pocket Option scraper (slow, runs in thread) ----
try:
    import scraper as _po_scraper
    _PO_AVAILABLE = True
except ImportError:
    _PO_AVAILABLE = False

# ---- Setup ----

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TradeMindBot")

SESSION_PATH = Path(__file__).parent / "trademind_bot.session"
DATA_DIR = Path(__file__).parent / "data"
STATIC_DIR = Path(__file__).parent / "static"

def _photo(caption: str, reply_markup: InlineKeyboardMarkup | None = None):
    """Helper: create InputMediaPhoto with a caption for editing."""
    return InputMediaPhoto(
        media=open(STATIC_DIR / "welcome.jpg", "rb"),
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
    )
DATA_DIR.mkdir(exist_ok=True)
SUBSCRIPTIONS_FILE = DATA_DIR / "subscriptions.json"

# Pairs per page for inline keyboard
PAIRS_PER_PAGE = 12


# ---- Data Persistence ----

def load_subscriptions() -> dict:
    if SUBSCRIPTIONS_FILE.exists():
        try:
            return json.loads(SUBSCRIPTIONS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}, "chats": {}}

def save_subscriptions(data: dict):
    SUBSCRIPTIONS_FILE.write_text(json.dumps(data, indent=2))


# ========================================================
# CHAT CLEANUP
# ========================================================

async def _clean_prev_msg(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Delete previous bot message to keep chat clean."""
    last_msg_id = context.user_data.get("last_bot_msg_id")
    last_chat_id = context.user_data.get("last_bot_chat_id")
    if last_msg_id and last_chat_id and last_chat_id == chat_id:
        try:
            await context.bot.delete_message(chat_id=last_chat_id, message_id=last_msg_id)
        except Exception:
            pass


async def _edit_or_send(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    chat_id: int, photo_path: Path, caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    """Edit the last tracked message if available, otherwise send a new photo.
    Returns the sent/edited message for tracking.
    """
    last_msg_id = context.user_data.get("last_bot_msg_id")
    last_chat_id = context.user_data.get("last_bot_chat_id")

    if last_msg_id and last_chat_id and last_chat_id == chat_id:
        # Edit existing tracked message
        media = InputMediaPhoto(
            media=open(photo_path, "rb"),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            msg = await context.bot.edit_message_media(
                chat_id=chat_id,
                message_id=last_msg_id,
                media=media,
                reply_markup=reply_markup,
            )
            return msg
        except Exception:
            pass  # fall through to send new

    # Fallback: send new photo
    with open(photo_path, "rb") as f:
        sent = await update.message.reply_photo(
            photo=f, caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
    return sent

async def _track_msg(context: ContextTypes.DEFAULT_TYPE, sent):
    """Remember sent message for future cleanup."""
    context.user_data["last_bot_msg_id"] = sent.message_id
    context.user_data["last_bot_chat_id"] = sent.chat_id

async def _del_user_msg(update: Update):
    """Delete user's command message."""
    try:
        await update.message.delete()
    except Exception:
        pass


# ========================================================
# INLINE KEYBOARD BUILDERS
# ========================================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu with algorithm and scraper."""
    rows = [
        [
            InlineKeyboardButton("🟣 الگوریتم", callback_data="main_algo"),
        ],
        [
            InlineKeyboardButton("🔵 Website Scraper", callback_data="main_scraper"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def category_keyboard() -> InlineKeyboardMarkup:
    """Category selection keyboard (2 rows of 2, plus back to main)."""
    rows = []
    cats = CATEGORY_ORDER
    for i in range(0, len(cats), 2):
        row = []
        for cat in cats[i:i+2]:
            cd = CATEGORY_DISPLAY[cat]
            row.append(InlineKeyboardButton(
                f"{cd['emoji']} {cd['label']}",
                callback_data=f"cat_{cat}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def pairs_keyboard(category: str, page: int = 0) -> InlineKeyboardMarkup:
    """Pair selection keyboard for a category (3 per row, paginated)."""
    pairs = get_pairs_by_category(category)
    total_pages = max(1, (len(pairs) + PAIRS_PER_PAGE - 1) // PAIRS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAIRS_PER_PAGE
    end = start + PAIRS_PER_PAGE
    page_pairs = pairs[start:end]

    rows = []
    # Search button at top
    rows.append([InlineKeyboardButton("🔍 جستجو / Search", switch_inline_query_current_chat="")])
    for i in range(0, len(page_pairs), PAIRS_PER_ROW):
        row = []
        for pair in page_pairs[i:i+PAIRS_PER_ROW]:
            display = get_pair_display(pair)
            row.append(InlineKeyboardButton(display, callback_data=f"pair_{pair}"))
        rows.append(row)

    # Navigation row
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"pg_{category}_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"pg_{category}_{page+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 بازگشت به دسته\u200cبندی", callback_data="back_cat")])
    return InlineKeyboardMarkup(rows)


def timeframe_keyboard(pair: str, active_tf: str = None) -> InlineKeyboardMarkup:
    """Timeframe selection keyboard with current one highlighted."""
    tf_config = [
        ("1m", "1m ⚡"),
        ("5m", "5m 🔥"),
        ("15m", "15m 📊"),
        ("30m", "30m 📈"),
        ("1h", "1h 🕐"),
    ]
    rows = [
        [
            InlineKeyboardButton(
                f"▸ {label}" if tf == active_tf else label,
                callback_data=f"tf_{tf}"
            )
            for tf, label in row
        ]
        for row in [tf_config[:3], tf_config[3:]]
    ]
    rows.append([
        InlineKeyboardButton("🔙 بازگشت به جفت‌ارزها", callback_data=f"back_pairs_{pair}"),
    ])
    return InlineKeyboardMarkup(rows)


def signal_timeframe_keyboard(pair: str, active_tf: str) -> InlineKeyboardMarkup:
    """Compact timeframe switcher shown below the signal + back button."""
    tf_config = [
        ("1m", "1m ⚡"),
        ("5m", "5m 🔥"),
        ("15m", "15m 📊"),
        ("30m", "30m 📈"),
        ("1h", "1h 🕐"),
    ]
    rows = [
        [
            InlineKeyboardButton(
                f"▸ {label}" if tf == active_tf else label,
                callback_data=f"tf_{tf}"
            )
            for tf, label in row
        ]
        for row in [tf_config[:3], tf_config[3:]]
    ]
    rows.append([
        InlineKeyboardButton("🔙 بازگشت به جفت‌ارزها", callback_data=f"back_pairs_{pair}"),
    ])
    return InlineKeyboardMarkup(rows)


# ========================================================
# SIGNAL FORMATTING (Persian)
# ========================================================

def format_signal(signal: dict) -> str:
    """
    Structured signal format in Persian.
    """
    direction = signal["direction"]
    confidence = signal["confidence"]
    pair = signal["pair"]
    price = signal["current_price"]
    tf = signal["timeframe"]
    dec = signal.get("decimal_places", 5)

    # Display name with (OTC) if applicable
    display_pair = get_pair_display(pair)

    # Direction in Persian
    if direction == "CALL":
        dir_emoji = "🟢"
        dir_text = "خرید (CALL) 📗"
        signal_text = "خرید (CALL) 📗"
    elif direction == "PUT":
        dir_emoji = "🔴"
        dir_text = "فروش (PUT) 📕"
        signal_text = "فروش (PUT) 📕"
    else:
        dir_emoji = "⚪"
        dir_text = "خنثی ⚖️"
        signal_text = direction

    # Price change
    change = signal.get("price_change_pct", 0)
    change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"

    # Trend
    trend = signal.get("trend", "neutral")

    # Volatility in Persian
    vol = signal.get("volatility", "medium").upper()
    vol_map = {"HIGH": "بالا", "MEDIUM": "متوسط", "LOW": "پایین"}
    vol_fa = vol_map.get(vol, vol)
    vol_emoji = "⚡" if vol == "HIGH" else "🌊" if vol == "MEDIUM" else "💤"

    # Candlestick pattern
    candle = signal.get("candle_pattern", "")
    candle_str = f"`{candle}`" if candle else ""

    # Risk score (1-10)
    risk_data = signal.get("risk_score", {})
    if isinstance(risk_data, dict):
        risk_score = risk_data.get("score", 5)
        risk_label = risk_data.get("label", "MEDIUM 🟡")
    else:
        risk_score = 5
        risk_label = "MEDIUM 🟡"
    # Translate risk label
    risk_label = risk_label.replace("LOW 🟢", "کم 🟢").replace("MEDIUM 🟡", "متوسط 🟡").replace("HIGH 🔴", "زیاد 🔴")
    risk_bar_fill = "━" * risk_score
    risk_bar_empty = "─" * (10 - risk_score)
    risk_str = f"┃{risk_bar_fill}{risk_bar_empty}┃ {risk_score}/10 {risk_label}"

    # Support & Resistance
    support = signal.get("support", 0)
    resistance = signal.get("resistance", 0)

    # Format indicator analysis details
    details = signal.get("details", [])
    tech_lines = []
    for d in details[:5]:
        clean = d.strip()
        tech_lines.append(f"  {clean}")

    tech_overview = "\n".join(tech_lines) if tech_lines else "  بدون داده"

    # Probabilities section
    if direction == "CALL":
        prob_value = confidence
        prob_label = "خرید (CALL)"
        prob_emoji = "🟢"
    elif direction == "PUT":
        prob_value = confidence
        prob_label = "فروش (PUT)"
        prob_emoji = "🔴"
    else:
        prob_value = confidence
        prob_label = "خنثی"
        prob_emoji = "⚪"

    bar_count = max(1, min(10, prob_value // 10))
    bar_fill = "━" * bar_count
    bar_empty = "─" * (10 - bar_count)

    # Expiry based on specific timeframe
    expiry_for_tf = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
    }
    expiry_str = expiry_for_tf.get(tf, "Auto")

    # Timestamp
    ts = signal.get("timestamp", datetime.now(timezone.utc))
    if isinstance(ts, datetime):
        time_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    else:
        time_str = str(ts)

    msg = (
        f"╔═══ ⚡️ **سیگنال** ⚡️ ═══╗\n\n"
        f"**{display_pair}** | `{tf}`\n\n"
        f"📋 **اطلاعات سیگنال:**\n"
        f"💵 **قیمت:** `{price:.{dec}f}`\n"
        f"🔄 **تغییرات:** `{change_emoji} {change:+.2f}%`\n"
        f"⏰ **به‌روزرسانی:** `{time_str}`\n\n"
        f"📌 **وضعیت بازار:**\n"
        f"📉 **روند:** `{trend}`\n"
        f"{vol_emoji} **نوسان:** `{vol_fa}`\n"
    )

    if candle_str:
        msg += f"🕯 **الگو:** {candle_str}\n"

    msg += (
        f"⚖️ **ریسک:** `{risk_str}`\n"
        f"📐 **حمایت:** `{support:.{dec}f}`\n"
        f"📐 **مقاومت:** `{resistance:.{dec}f}`\n\n"
        f"🔬 **نمای تکنیکال:**\n"
        f"{tech_overview}\n\n"
        f"🎯 **احتمال:**\n"
        f"`┃{bar_fill}{bar_empty}┃ {confidence}%`\n"
        f"▸ **ربات پیشنهاد می‌دهد:** `{signal_text}`\n\n"
        f"🤖 **سیگنال ربات:** `{signal_text}`\n"
        f"⏱️ **انقضا:** `{expiry_str}`\n\n"
        f"╚═══ ⚠️ *خودت تحقیق کن* ═══╝"
    )

    return msg


def format_analysis(pair_name: str, analysis: dict) -> str:
    """Format full multi-timeframe analysis in Persian."""
    if not analysis or not analysis.get("signals"):
        return f"❌ نمی‌توان **{pair_name}** را تحلیل کرد. داده در دسترس نیست."

    display_pair = get_pair_display(pair_name)
    pair_type = analysis.get("type", "unknown").upper()
    price = analysis.get("current_price")
    pair_info = AVAILABLE_PAIRS.get(pair_name, {})
    dec = pair_info.get("decimal_places", 5)

    now = datetime.now(timezone.utc)
    msg = (
        f"╔═══ 📊 **تحلیل بازار** ═══╗\n\n"
        f"**{display_pair}** | `{pair_type}`\n"
    )
    if price:
        msg += f"💵 قیمت: `{price:.{dec}f}`\n"
    msg += f"⏰ `{now.strftime('%Y-%m-%d %H:%M UTC')}`\n\n"

    msg += "**📈 نمای چند تایم‌فریم:**\n"
    msg += "```\n"
    msg += f"{'TF':<6} {'سیگنال':<8} {'اطمینان':<6} {'روند':<12}\n"
    msg += "-" * 35 + "\n"

    tf_signals = analysis.get("signals", {})
    for tf in ["1m", "5m", "15m", "30m", "1h"]:
        sig = tf_signals.get(tf)
        if sig:
            dir_short = sig["direction"][:4]
            conf = f"{sig['confidence']}%"
            trend_short = sig.get("trend", "-")[:10]
            msg += f"{tf:<6} {dir_short:<8} {conf:<6} {trend_short:<12}\n"
    msg += "```\n\n"

    # Detailed signal for primary timeframe
    primary = tf_signals.get("5m") or tf_signals.get("15m") or next(iter(tf_signals.values()))
    if primary:
        msg += format_signal(primary)

    msg += "\n\n⚠️ *فقط برای اهداف آموزشی. خودت تحقیق کن!*"
    return msg


def format_pairs_list() -> str:
    """Format available trading pairs grouped by category (Persian)."""
    msg = PAIRS_LIST_HEADER + "\n"

    for cat in CATEGORY_ORDER:
        cd = CATEGORY_DISPLAY[cat]
        pairs = get_pairs_by_category(cat)
        if pairs:
            msg += f"\n{cd['emoji']} **{cd['label']}**\n"

            # For 'other', show sub-categories
            if cat == "other":
                for sub_cat, sub_label in [("crypto", "ارز دیجیتال"), ("stock", "سهام (OTC)"), ("commodity", "کالا"), ("indices", "شاخص (Indices)")]:
                    sub_pairs = sorted([p for p, info in AVAILABLE_PAIRS.items() if info.get("type") == sub_cat])
                    if sub_pairs:
                        display_names = [get_pair_display(p) for p in sub_pairs]
                        msg += f"  **{sub_label}:** `{', '.join(display_names)}`\n"
            else:
                display_names = [get_pair_display(p) for p in pairs]
                msg += "`" + ", ".join(display_names) + "`\n"

    msg += "\n🔹 `/signal BTC/USD` یا اسم جفت‌ارز رو تایپ کن!"
    return msg


# ========================================================
# HANDLERS
# ========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    with open(STATIC_DIR / "welcome.jpg", "rb") as f:
        sent = await update.message.reply_photo(
            photo=f,
            caption="🤖 **به TradeMind Signal Bot خوش آمدی!** 🚀\n\n"
                    "از منوی زیر انتخاب کن:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
    await _track_msg(context, sent)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    with open(STATIC_DIR / "welcome.jpg", "rb") as f:
        sent = await update.message.reply_photo(
            photo=f,
            caption=HELP_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
    await _track_msg(context, sent)


async def pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    with open(STATIC_DIR / "category.jpg", "rb") as f:
        sent = await update.message.reply_photo(
            photo=f,
            caption=format_pairs_list(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
    await _track_msg(context, sent)


# ---- Signal Command ----

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _del_user_msg(update)

    if not context.args:
        # No pair specified → show category selection
        with open(STATIC_DIR / "category.jpg", "rb") as f:
            sent = await update.message.reply_photo(
                photo=f,
                caption="📊 **یک دسته بازار را انتخاب کنید:**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=category_keyboard(),
            )
        await _track_msg(context, sent)
        return

    pair = " ".join(context.args).strip().upper()
    pair = normalize_pair(pair)

    if pair not in AVAILABLE_PAIRS:
        sent = await _edit_or_send(
            update, context, chat_id, STATIC_DIR / "category.jpg",
            f"❌ جفت‌ارز `{pair}` پیدا نشد!\n"
            "از دکمه زیر یکی رو انتخاب کن:",
            category_keyboard(),
        )
        await _track_msg(context, sent)
        return

    # Pair specified → show timeframe selection (edits existing message)
    context.user_data["signal_pair"] = pair
    display = get_pair_display(pair)
    sent = await _edit_or_send(
        update, context, chat_id, STATIC_DIR / "category.jpg",
        f"**{display}** ⏱️ تایم‌فریم را انتخاب کنید:",
        timeframe_keyboard(pair),
    )
    await _track_msg(context, sent)


# ---- Main Menu Callbacks ----

async def main_algo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go to algorithm flow — show category selection."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=open(STATIC_DIR / "category.jpg", "rb"),
            caption="📊 **یک دسته بازار را انتخاب کنید:**",
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=category_keyboard(),
    )


async def main_scraper_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Website scraper — show status page."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=open(STATIC_DIR / "scraper.jpg", "rb"),
            caption=(
                "🌐 **Website Scraper**\n\n"
                f"**Pocket Option Signal Scraper** {'✅' if _PO_AVAILABLE else '❌'}\n\n"
                "یک اسکرپر مبتنی بر Selenium که:\n"
                "• وارد دمو Pocket Option می‌شه\n"
                "• تب سیگنال‌ها رو باز می‌کنه\n"
                "• نتیجه رو برمی‌گردونه\n\n"
                "⚠️ سیگنال‌های PO فقط برای کاربران "
                "واقعی در دسترسه (دمو قفله).\n"
                "برای تنظیم ایمیل و رمز PO:\n"
                "`PO_EMAIL` و `PO_PASSWORD`\n\n"
                "دستور: `/posignal [نماد]`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")],
        ]),
    )


# ---- Category Callback ----

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat = query.data.replace("cat_", "")
    cd = CATEGORY_DISPLAY.get(cat, {})
    label = cd.get("label", cat)
    emoji = cd.get("emoji", "📊")

    await query.edit_message_caption(
        caption=f"{emoji} **{label}** — یک جفت‌ارز انتخاب کنید:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=pairs_keyboard(cat),
    )


# ---- Pair Selection Callback ----

async def pair_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pair = query.data.replace("pair_", "")
    context.user_data["signal_pair"] = pair
    display = get_pair_display(pair)

    await query.edit_message_caption(
        caption=f"**{display}** ⏱️ تایم‌فریم را انتخاب کنید:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=timeframe_keyboard(pair),
    )


# ---- Back Navigation ----

async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to main menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_media(
        media=InputMediaPhoto(
            media=open(STATIC_DIR / "welcome.jpg", "rb"),
            caption="🤖 **به TradeMind Signal Bot خوش آمدی!** 🚀\n\n"
                    "از منوی زیر انتخاب کن:",
            parse_mode=ParseMode.MARKDOWN,
        ),
        reply_markup=main_menu_keyboard(),
    )


async def back_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to category selection."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_caption(
        caption="📊 **یک دسته بازار را انتخاب کنید:**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=category_keyboard(),
    )


async def back_pairs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to pair selection for the current category (page 0)."""
    query = update.callback_query
    await query.answer()

    pair = query.data.replace("back_pairs_", "")
    info = AVAILABLE_PAIRS.get(pair, {})
    pair_type = info.get("type", "crypto")
    # Map actual type to display category
    if pair_type in ("crypto", "stock", "commodity"):
        cat = "other"
    else:
        cat = pair_type
    cd = CATEGORY_DISPLAY.get(cat, {})

    await query.edit_message_caption(
        caption=f"{cd.get('emoji', '📊')} **{cd['label']}** — یک جفت‌ارز انتخاب کنید:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=pairs_keyboard(cat, page=0),
    )


# ---- Pagination Callback ----

async def page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pair list pagination."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_", 2)  # pg_{category}_{page}
    if len(parts) < 3:
        return
    cat = parts[1]
    page = int(parts[2])
    cd = CATEGORY_DISPLAY.get(cat, {})
    label = cd.get("label", cat)

    await query.edit_message_caption(
        caption=f"{cd.get('emoji', '📊')} **{label}** — یک جفت‌ارز انتخاب کنید: (صفحه {page+1})",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=pairs_keyboard(cat, page=page),
    )


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """No-op callback for placeholder buttons (page indicator)."""
    await update.callback_query.answer()


# ---- Timeframe Callback (Generate Signal) ----

async def signal_timeframe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tf = query.data.replace("tf_", "")

    if tf == "cancel":
        await query.edit_message_caption(
            caption="❌ لغو شد.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    pair = context.user_data.get("signal_pair", "")
    if not pair or pair not in AVAILABLE_PAIRS:
        await query.edit_message_caption(
            caption="❌ نشست منقضی شد! دوباره /signal را بزن.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        return

    display = get_pair_display(pair)

    # Show loading
    await query.edit_message_caption(
        caption=f"🔍 در حال تحلیل **{display}** روی **{tf}**... ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        signal = generate_signal(pair, tf)
        if signal is None:
            fallbacks = {"1m": "5m", "5m": "15m", "15m": "30m", "30m": "1h", "1h": "4h"}
            fallback = fallbacks.get(tf, "5m")
            signal = generate_signal(pair, fallback)

        if signal:
            pair_info = AVAILABLE_PAIRS[pair]
            signal["decimal_places"] = pair_info.get("decimal_places", 5)
            msg = format_signal(signal)
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=open(STATIC_DIR / "signal.jpg", "rb"),
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                ),
                reply_markup=signal_timeframe_keyboard(pair, tf),
            )
        else:
            await query.edit_message_caption(
                caption=f"❌ داده کافی برای `{pair}` روی `{tf}` وجود نداره.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=category_keyboard(),
            )
    except Exception as e:
        logger.error(f"Error generating signal for {pair} on {tf}: {e}")
        await query.edit_message_caption(
            caption=f"❌ خطا: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )


# ---- Analysis Command ----

async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    if not context.args:
        sent = await update.message.reply_text(
            "❌ یک جفت‌ارز مشخص کن!\nمثال: `/analysis BTC/USD`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        await _track_msg(context, sent)
        return

    pair = " ".join(context.args).strip().upper()
    pair = normalize_pair(pair)

    if pair not in AVAILABLE_PAIRS:
        sent = await update.message.reply_text(
            f"❌ جفت‌ارز `{pair}` پیدا نشد!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        await _track_msg(context, sent)
        return

    sent = await update.message.reply_text(
        f"🔍 در حال تحلیل کامل **{pair}**... ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        analysis = generate_full_analysis(pair)
        if analysis:
            msg = format_analysis(pair, analysis)
            await sent.edit_text(msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")],
                ]))
        else:
            await sent.edit_text(
                f"❌ داده کافی برای `{pair}` وجود نداره.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=category_keyboard(),
            )
    except Exception as e:
        logger.error(f"Error in full analysis for {pair}: {e}")
        await sent.edit_text(
            f"❌ خطا: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )


# ---- PO Signal Scraper Command ----

async def posignal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scrape current Pocket Option signal (slow - takes ~20s).

    Uses undetected-chromedriver to log into PO and read the Signals tab.
    Falls back gracefully when PO is blocked or signals are locked.
    """
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    if not _PO_AVAILABLE:
        sent = await update.message.reply_text(
            "❌ ماژول اسکرپر در دسترس نیست.\n"
            "فایل `scraper.py` وجود نداره یا وابستگی‌هاش نصب نشده.",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _track_msg(context, sent)
        return

    sent = await update.message.reply_text(
        "🔍 **در حال اتصال به Pocket Option...** ⏳\n"
        "حدود ۲۰ ثانیه طول می‌کشه.",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _track_msg(context, sent)

    pair = " ".join(context.args).strip().upper() if context.args else None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _po_scraper.get_po_signal, pair, False)

        if result.get("error"):
            err = result["error"]
            if "connect" in err.lower() or "proxy" in err.lower():
                msg = (
                    "🌐 **اتصال به Pocket Option ممکن نیست.**\n\n"
                    "❌ سرور PO از طریق پروکسی فعلی در دسترس نیست.\n"
                    "ممکنه IP پروکسی بلاک شده باشه.\n\n"
                    "💡 راهکار:\n"
                    "• پروکسی/VPN خودت رو عوض کن\n"
                    "• یا از طریق مرورگر خودت وارد PO بشو و کوکی رو Export کن\n"
                    "• با دستور `/pocookie` می‌تونی کوکی رو به ربات بدی"
                )
            else:
                msg = f"❌ **خطا:** {err}"
        elif result.get("locked"):
            msg = (
                "🔒 **سیگنال‌های PO قفل هستند.**\n\n"
                "دمو یک‌کلیک دسترسی به سیگنال‌ها نداره.\n"
                "برای استفاده:\n"
                "• ایمیل و رمز PO را در متغیرهای محیطی تنظیم کن،\n"
                "• یا از مرورگر خودت وارد PO بشو، کوکی رو Export کن\n"
                "  و با `/pocookie` به ربات بده."
            )
        else:
            signal = result.get("signal", "UNKNOWN")
            signal_emoji = {
                "STRONG_BUY": "🟢🟢",
                "BUY": "🟢",
                "STRONG_SELL": "🔴🔴",
                "SELL": "🔴",
                "NEUTRAL": "⚪",
            }.get(signal, "❓")
            account_type = result.get("account_type", "?")
            account_icon = "👤" if account_type == "real" else "🧪"

            msg = (
                f"🌐 **سیگنال Pocket Option** {account_icon}\n\n"
                f"**نماد:** `{result.get('symbol', '?')}`\n"
                f"**سیگنال:** {signal_emoji} `{signal}`\n"
                f"**زمان:** `{result.get('timestamp', '?')[:19]}`\n\n"
                f"📋 **جزئیات:**\n```\n{result.get('raw_text', '')[:400]}\n```"
            )

        await sent.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.exception("PO signal command failed")
        await sent.edit_text(
            f"❌ **خطا در دریافت سیگنال PO:**\n`{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        await loop.run_in_executor(None, _po_scraper.close_driver)

# ---- Subscribe / Unsubscribe ----

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    interval = 5
    if context.args:
        try:
            interval = max(1, min(60, int(context.args[0].rstrip("m"))))
        except ValueError:
            pass

    chat_id_str = str(update.effective_chat.id)
    subscriptions = load_subscriptions()
    subscriptions.setdefault("chats", {})[chat_id_str] = {
        "interval_minutes": interval,
        "user_id": update.effective_user.id,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_subscriptions(subscriptions)
    sent = await update.message.reply_text(
        f"✅ **مشترک شدی!** 🎯\n\n"
        f"📨 ارسال سیگنال هر **{interval} دقیقه**.\n"
        f"برای لغو از `/unsubscribe` استفاده کن.",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _track_msg(context, sent)


async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    chat_id_str = str(update.effective_chat.id)
    subscriptions = load_subscriptions()
    if chat_id_str in subscriptions.get("chats", {}):
        del subscriptions["chats"][chat_id_str]
        save_subscriptions(subscriptions)
        sent = await update.message.reply_text(
            "✅ **اشتراک لغو شد.**",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        sent = await update.message.reply_text(
            "❌ مشترک نیستی.",
            parse_mode=ParseMode.MARKDOWN,
        )
    await _track_msg(context, sent)


# ---- Direct Pair Input ----

async def handle_pair_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages that look like trading pairs — send to timeframe selection."""
    chat_id = update.effective_chat.id
    await _del_user_msg(update)

    text = update.message.text.strip().upper()

    if text in AVAILABLE_PAIRS:
        context.user_data["signal_pair"] = text
        display = get_pair_display(text)
        sent = await _edit_or_send(
            update, context, chat_id, STATIC_DIR / "category.jpg",
            f"**{display}** ⏱️ تایم‌فریم را انتخاب کنید:",
            timeframe_keyboard(text),
        )
        await _track_msg(context, sent)


# ---- Unknown Commands ----

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    text = (update.message.text or "").strip()
    if text.startswith("/"):
        with open(STATIC_DIR / "welcome.jpg", "rb") as f:
            sent = await update.message.reply_photo(
                photo=f,
                caption=f"❌ دستور `{text.split()[0]}` ناشناس است.\n"
                        "برای مشاهده دستورات از /help استفاده کن.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
        await _track_msg(context, sent)


# ========================================================
# PAIR NORMALIZER
# ========================================================

def normalize_pair(pair: str) -> str:
    if "/" in pair:
        return pair
    if pair.endswith("USD") and len(pair) > 5:
        return pair[:-3] + "/USD"
    if pair.endswith("USDT") and len(pair) > 6:
        return pair[:-4] + "/USD"
    if pair.endswith("JPY") and len(pair) > 5:
        return pair[:-3] + "/JPY"
    if pair.endswith("EUR") and len(pair) > 5:
        return pair[:-3] + "/EUR"
    if pair in [p for p in AVAILABLE_PAIRS if "/" not in p]:
        return pair
    for ap in AVAILABLE_PAIRS:
        if ap.replace("/", "") == pair:
            return ap
    return pair


# ---- Inline Query (Real-time Drawer Search) ----

# Emoji per pair type for inline results
TYPE_EMOJI = {
    "forex": "💱",
    "crypto": "₿",
    "stock": "📈",
    "commodity": "🛢️",
    "indices": "📊",
}


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries — real-time drawer search from the input bar.

    User types @botname EUR and sees matching pairs update as they type,
    like a search drawer sliding up from the text input.

    Using:
      - inline_query → triggers this handler
      - answerInlineQuery (update.inline_query.answer) → shows results
    """
    query = update.inline_query.query.strip().upper()
    user = update.effective_user

    if not query:
        # Empty query: show pairs from different categories
        forex = [p for p in AVAILABLE_PAIRS if AVAILABLE_PAIRS[p].get("type") == "forex"][:8]
        crypto = [p for p in AVAILABLE_PAIRS if AVAILABLE_PAIRS[p].get("type") == "crypto"][:6]
        stock = [p for p in AVAILABLE_PAIRS if AVAILABLE_PAIRS[p].get("type") == "stock"][:4]
        commodity = [p for p in AVAILABLE_PAIRS if AVAILABLE_PAIRS[p].get("type") == "commodity"][:4]
        results = forex + crypto + stock + commodity
    else:
        results = [p for p in AVAILABLE_PAIRS if query in p]
        results.sort()
        results = results[:50]  # Telegram limit

    inline_results = []
    for pair in results:
        display = get_pair_display(pair)
        info = AVAILABLE_PAIRS.get(pair, {})
        ptype = info.get("type", "")
        emoji = TYPE_EMOJI.get(ptype, "📊")
        is_otc = info.get("otc", False)

        # Build description: category + OTC tag
        type_labels = {
            "forex": "فارکس",
            "crypto": "کریپتو",
            "stock": "سهام",
            "commodity": "کالا",
        }
        label = type_labels.get(ptype) or ptype.title()
        if is_otc:
            label += " (OTC)"

        inline_results.append(
            InlineQueryResultArticle(
                id=pair,
                title=f"{emoji} {display}",
                description=f"{label} — {pair}",
                input_message_content=InputTextMessageContent(
                    f"/signal {pair}"
                ),
                url="",
            )
        )

    await update.inline_query.answer(
        inline_results,
        cache_time=2,
        is_personal=True,
        button=InlineQueryResultsButton(
            text="🔍 جستجوی جفت‌ارز در TradeMind",
            start_parameter="search",
        ),
    )


# ---- PO Cookie Injection Command ----


async def pocookie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inject PO cookies from a JSON file for authenticated scraping.

    Usage:
        /pocookie - shows instructions
        /pocookie <path> - loads cookies from the given file path

    The cookies file should be exported from your browser after
    manually logging into https://pocketoption.com.
    Use EditThisCookie extension or 'Export cookies JSON' tools.
    """
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)

    if not _PO_AVAILABLE:
        sent = await update.message.reply_text(
            "❌ ماژول اسکرپر در دسترس نیست.",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _track_msg(context, sent)
        return

    if context.args:
        cookie_path = " ".join(context.args)
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(
            None, _po_scraper.inject_cookies, cookie_path
        )
    else:
        msg = (
            "🍪 **راهنمای تنظیم کوکی Pocket Option**\n\n"
            "برای دریافت سیگنال‌های PO نیاز به کوکی مرورگر داری:\n\n"
            "1️⃣ در مرورگر خودت (Chrome/Firefox) وارد "
            "https://pocketoption.com بشو و لاگین کن\n\n"
            "2️⃣ با افزونه **EditThisCookie** یا ابزار مشابه، "
            "کوکی‌ها رو به صورت JSON Export کن\n\n"
            "3️⃣ فایل رو روی سرور ذخیره کن و دستور زیر رو بزن:\n"
            "`/pocookie /path/to/cookies.json`\n\n"
            "یا فایل رو بذار توی `~/.po_cookies.json` "
            "تا ربات خودکار بارش کنه."
        )

    sent = await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    await _track_msg(context, sent)


# ========================================================
# MAIN
# ========================================================

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN تنظیم نشده!")
        return

    print("""
    ╔══════════════════════════════════╗
    ║     🤖 TradeMind Signal Bot     ║
    ║  AI-Powered Trading Signals      ║
    ╚══════════════════════════════════╝
    """)

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("pairs", pairs))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("analysis", analysis_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    if _PO_AVAILABLE:
        app.add_handler(CommandHandler("posignal", posignal_cmd))
        app.add_handler(CommandHandler("pocookie", pocookie_cmd))

    # Callbacks — main menu
    app.add_handler(CallbackQueryHandler(main_algo_callback, pattern=r"^main_algo$"))
    app.add_handler(CallbackQueryHandler(main_scraper_callback, pattern=r"^main_scraper$"))

    # Callbacks — categories & pairs
    app.add_handler(CallbackQueryHandler(category_callback, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(pair_select_callback, pattern=r"^pair_"))
    app.add_handler(CallbackQueryHandler(page_callback, pattern=r"^pg_"))
    app.add_handler(CallbackQueryHandler(signal_timeframe_callback, pattern=r"^tf_"))

    # Callbacks — back navigation
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern=r"^back_main$"))
    app.add_handler(CallbackQueryHandler(back_cat_callback, pattern=r"^back_cat$"))
    app.add_handler(CallbackQueryHandler(back_pairs_callback, pattern=r"^back_pairs_"))

    # Callbacks — utility
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

    # Inline query — drawer search
    app.add_handler(InlineQueryHandler(inline_search))

    # Direct pair input
    app.add_handler(MessageHandler(
        filters.Regex(r"^[A-Z]{2,8}/[A-Z]{2,8}$") & ~filters.COMMAND,
        handle_pair_message
    ))

    # Unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("🤖 TradeMind Signal Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
