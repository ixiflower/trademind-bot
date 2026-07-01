"""
TradeMind Signal Bot - Telegram Bot
AI-powered trading signals for Pocket Option and binary options
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InlineQueryResultArticle,
    InputTextMessageContent, InlineQueryResultsButton,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler,
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

# ---- Setup ----

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TradeMindBot")

SESSION_PATH = Path(__file__).parent / "trademind_bot.session"
DATA_DIR = Path(__file__).parent / "data"
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


# =======================================================
# INLINE KEYBOARD BUILDERS
# =======================================================

def category_keyboard() -> InlineKeyboardMarkup:
    """Main category selection keyboard (2 rows of 2)."""
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
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pg_{category}_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pg_{category}_{page+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="back_cat")])
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
        InlineKeyboardButton("🔙 Back to Pairs", callback_data=f"back_pairs_{pair}"),
    ])
    return InlineKeyboardMarkup(rows)


def signal_timeframe_keyboard(pair: str, active_tf: str) -> InlineKeyboardMarkup:
    """Compact timeframe switcher shown below the signal."""
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
    return InlineKeyboardMarkup(rows)


# =======================================================
# SIGNAL FORMATTING (NEW STRUCTURED FORMAT)
# =======================================================

def format_signal(signal: dict) -> str:
    """
    Structured signal format matching user's requested layout:
      - Signal Info
      - Market Setting (with Risk bar)
      - Technical Overview
      - Probabilities (single bar + Bot favors)
      - Bot Signal
    """
    direction = signal["direction"]
    confidence = signal["confidence"]
    pair = signal["pair"]
    price = signal["current_price"]
    tf = signal["timeframe"]
    dec = signal.get("decimal_places", 5)

    # Display name with (OTC) if applicable
    display_pair = get_pair_display(pair)

    # Direction
    if direction == "CALL":
        dir_emoji = "🟢"
        dir_text = "BUY (CALL) 📗"
        signal_text = "BUY (CALL) 📗"
    elif direction == "PUT":
        dir_emoji = "🔴"
        dir_text = "SELL (PUT) 📕"
        signal_text = "SELL (PUT) 📕"
    else:
        dir_emoji = "⚪"
        dir_text = "NEUTRAL ⚖️"
        signal_text = direction

    # Price change
    change = signal.get("price_change_pct", 0)
    change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"

    # Trend
    trend = signal.get("trend", "neutral")

    # Volatility
    vol = signal.get("volatility", "medium").upper()
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

    tech_overview = "\n".join(tech_lines) if tech_lines else "  No data"

    # Probabilities section
    if direction == "CALL":
        prob_value = confidence
        prob_label = "CALL (BUY)"
        prob_emoji = "🟢"
    elif direction == "PUT":
        prob_value = confidence
        prob_label = "PUT (SELL)"
        prob_emoji = "🔴"
    else:
        prob_value = confidence
        prob_label = "NEUTRAL"
        prob_emoji = "⚪"

    bar_count = max(1, min(10, prob_value // 10))
    bar_fill = "━" * bar_count
    bar_empty = "─" * (10 - bar_count)

    # Expiry based on specific timeframe
    expiry_map = {
        "1m": ["1min", "5min"],
        "5m": ["5min", "15min"],
        "15m": ["15min", "30min"],
        "30m": ["30min", "1h"],
        "1h": ["1h"],
    }
    expiry_list = expiry_map.get(tf, ["Auto"])
    expiry_str = ", ".join(expiry_list[:2])

    # Timestamp
    ts = signal.get("timestamp", datetime.now(timezone.utc))
    if isinstance(ts, datetime):
        time_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    else:
        time_str = str(ts)

    msg = (
        f"╔═══ ⚡️ **SIGNAL** ⚡️ ═══╗\n\n"
        f"**{display_pair}** | `{tf}`\n\n"
        f"📋 **Signal Info:**\n"
        f"💵 **Price:** `{price:.{dec}f}`\n"
        f"🔄 **Change:** `{change_emoji} {change:+.2f}%`\n"
        f"⏰ **Updated:** `{time_str}`\n\n"
        f"📌 **Market Setting:**\n"
        f"📉 **Trend:** `{trend}`\n"
        f"{vol_emoji} **Volatility:** `{vol}`\n"
    )

    if candle_str:
        msg += f"🕯 **Pattern:** {candle_str}\n"

    msg += (
        f"⚖️ **Risk:** `{risk_str}`\n"
        f"📐 **Support:** `{support:.{dec}f}`\n"
        f"📐 **Resistance:** `{resistance:.{dec}f}`\n\n"
        f"🔬 **Technical Overview:**\n"
        f"{tech_overview}\n\n"
        f"🎯 **Probabilities:**\n"
        f"`┃{bar_fill}{bar_empty}┃ {confidence}%`\n"
        f"▸ **Bot favors:** `{signal_text}`\n\n"
        f"🤖 **Bot Signal:** `{signal_text}`\n"
        f"⏱️ **Expiry:** `{expiry_str}`\n\n"
        f"╚═══ ⚠️ *DYOR* ═══╝"
    )

    return msg


def format_analysis(pair_name: str, analysis: dict) -> str:
    """Format full multi-timeframe analysis."""
    if not analysis or not analysis.get("signals"):
        return f"❌ Could not analyze **{pair_name}**. Data unavailable."

    display_pair = get_pair_display(pair_name)
    pair_type = analysis.get("type", "unknown").upper()
    price = analysis.get("current_price")
    pair_info = AVAILABLE_PAIRS.get(pair_name, {})
    dec = pair_info.get("decimal_places", 5)

    now = datetime.now(timezone.utc)
    msg = (
        f"╔═══ 📊 **MARKET ANALYSIS** ═══╗\n\n"
        f"**{display_pair}** | `{pair_type}`\n"
    )
    if price:
        msg += f"💵 Price: `{price:.{dec}f}`\n"
    msg += f"⏰ `{now.strftime('%Y-%m-%d %H:%M UTC')}`\n\n"

    msg += "**📈 Multi-Timeframe Overview:**\n"
    msg += "```\n"
    msg += f"{'TF':<6} {'Signal':<8} {'Conf':<6} {'Trend':<12}\n"
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

    msg += "\n\n⚠️ *Educational purposes only. DYOR!*"
    return msg


def format_pairs_list() -> str:
    """Format available trading pairs grouped by category."""
    msg = PAIRS_LIST_HEADER + "\n"

    for cat in CATEGORY_ORDER:
        cd = CATEGORY_DISPLAY[cat]
        pairs = get_pairs_by_category(cat)
        if pairs:
            display_names = [get_pair_display(p) for p in pairs]
            msg += f"\n{cd['emoji']} **{cd['label']}**\n"
            msg += "`" + ", ".join(display_names) + "`\n"

    msg += "\n🔹 `/signal BTC/USD` or just type the pair!"
    return msg


# =======================================================
# HANDLERS
# =======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _clean_prev_msg(context, chat_id)
    await _del_user_msg(update)
    with open(STATIC_DIR / "welcome.jpg", "rb") as f:
        sent = await update.message.reply_photo(
            photo=f,
            caption="🤖 **به TradeMind Signal Bot خوش آمدی!** 🚀\n\nاز منوی زیر انتخاب کن:",
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
            photo=f, caption=HELP_MESSAGE,
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
            photo=f, caption=format_pairs_list(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
    await _track_msg(context, sent)


# ---- Signal Command ----

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        # No pair specified → show category selection
        await update.message.reply_text(
            "📊 **یک دسته بازار را انتخاب کنید:**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        return

    pair = " ".join(context.args).strip().upper()
    pair = normalize_pair(pair)

    if pair not in AVAILABLE_PAIRS:
        await update.message.reply_text(
            f"❌ جفت‌ارز `{pair}` پیدا نشد!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        return

    # Pair specified → show timeframe selection
    context.user_data["signal_pair"] = pair
    display = get_pair_display(pair)
    await update.message.reply_text(
        f"**{display}** ⏱️ Choose timeframe:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=timeframe_keyboard(pair),
    )


# ---- Category Callback ----

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat = query.data.replace("cat_", "")
    cd = CATEGORY_DISPLAY.get(cat, {})
    label = cd.get("label", cat)
    emoji = cd.get("emoji", "📊")

    await query.edit_message_text(
        f"{emoji} **{label}** — Select a pair:",
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

    await query.edit_message_text(
        f"**{display}** ⏱️ Choose timeframe:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=timeframe_keyboard(pair),
    )


# ---- Back Navigation ----

async def back_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to category selection."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 **یک دسته بازار را انتخاب کنید:**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=category_keyboard(),
    )


async def back_pairs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to pair selection for the current category (page 0)."""
    query = update.callback_query
    await query.answer()

    pair = query.data.replace("back_pairs_", "")
    info = AVAILABLE_PAIRS.get(pair, {})
    cat = info.get("type", "crypto")
    cd = CATEGORY_DISPLAY.get(cat, {})

    await query.edit_message_text(
        f"{cd.get('emoji', '📊')} **{cd['label']}** — Select a pair:",
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

    await query.edit_message_text(
        f"{cd.get('emoji', '📊')} **{label}** — Select a pair: (Page {page+1})",
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
        await query.edit_message_text("❌ Cancelled.", parse_mode=ParseMode.MARKDOWN)
        return

    pair = context.user_data.get("signal_pair", "")
    if not pair or pair not in AVAILABLE_PAIRS:
        await query.edit_message_text(
            "❌ Session expired! Try /signal again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )
        return

    display = get_pair_display(pair)

    # Show loading
    await query.edit_message_text(
        f"🔍 Analyzing **{display}** on **{tf}**... ⏳",
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
            await query.edit_message_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=signal_timeframe_keyboard(pair, tf),
            )
        else:
            await query.edit_message_text(
                f"❌ Insufficient data for `{pair}` on `{tf}`.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=category_keyboard(),
            )
    except Exception as e:
        logger.error(f"Error generating signal for {pair} on {tf}: {e}")
        await query.edit_message_text(
            f"❌ Error: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=category_keyboard(),
        )


# ---- Analysis Command ----

async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Specify a pair!\nExample: `/analysis BTC/USD`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    pair = " ".join(context.args).strip().upper()
    pair = normalize_pair(pair)

    if pair not in AVAILABLE_PAIRS:
        await update.message.reply_text(
            f"❌ Pair `{pair}` not found!", parse_mode=ParseMode.MARKDOWN
        )
        return

    sent = await update.message.reply_text(f"🔍 Running full analysis on **{pair}**... ⏳", parse_mode=ParseMode.MARKDOWN)

    try:
        analysis = generate_full_analysis(pair)
        if analysis:
            msg = format_analysis(pair, analysis)
            await sent.edit_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await sent.edit_text(f"❌ Insufficient data for `{pair}`.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in full analysis for {pair}: {e}")
        await sent.edit_text(f"❌ Error: {str(e)[:100]}", parse_mode=ParseMode.MARKDOWN)


# ---- Subscribe / Unsubscribe ----

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    interval = 5
    if context.args:
        try:
            interval = max(1, min(60, int(context.args[0].rstrip("m"))))
        except ValueError:
            pass

    chat_id = str(update.effective_chat.id)
    subscriptions = load_subscriptions()
    subscriptions.setdefault("chats", {})[chat_id] = {
        "interval_minutes": interval,
        "user_id": update.effective_user.id,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_subscriptions(subscriptions)
    await update.message.reply_text(
        f"✅ **Subscribed!** 🎯\n\n📨 Signals every **{interval} minute(s)**.\nUse `/unsubscribe` to stop.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    subscriptions = load_subscriptions()
    if str(chat_id) in subscriptions.get("chats", {}):
        del subscriptions["chats"][chat_id]
        save_subscriptions(subscriptions)
        await update.message.reply_text("✅ **Unsubscribed.**", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Not subscribed.", parse_mode=ParseMode.MARKDOWN)


# ---- Direct Pair Input ----

async def handle_pair_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages that look like trading pairs."""
    text = update.message.text.strip().upper()
    if text in AVAILABLE_PAIRS:
        context.user_data["signal_pair"] = text
        display = get_pair_display(text)
        await update.message.reply_text(
            f"**{display}** ⏱️ Choose timeframe:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=timeframe_keyboard(text),
        )


# ---- Unknown Commands ----

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.startswith("/"):
        await update.message.reply_text(
            f"❌ Unknown command `{text.split()[0]}`.\nUse /help to see available commands.",
            parse_mode=ParseMode.MARKDOWN,
        )


# =======================================================
# PAIR NORMALIZER
# =======================================================

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


# =======================================================
# MAIN
# =======================================================

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set!")
        return

    print("""
    ╔══════════════════════════════════╗
    ║     🤖 TradeMind Signal Bot     ║
    ║  AI-Powered Trading Signals      ║
    ║  for Pocket Option & Binary Ops  ║
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

    # Callbacks
    app.add_handler(CallbackQueryHandler(category_callback, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(pair_select_callback, pattern=r"^pair_"))
    app.add_handler(CallbackQueryHandler(page_callback, pattern=r"^pg_"))
    app.add_handler(CallbackQueryHandler(signal_timeframe_callback, pattern=r"^tf_"))
    app.add_handler(CallbackQueryHandler(back_cat_callback, pattern=r"^back_cat$"))
    app.add_handler(CallbackQueryHandler(back_pairs_callback, pattern=r"^back_pairs_"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

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
