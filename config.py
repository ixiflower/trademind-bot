"""
Configuration for Trading Signal Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Binance (optional - public API works without keys)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

# Trading pairs available for signals
AVAILABLE_PAIRS = {
    # ============ Crypto ============
    "BTC/USD": {"type": "crypto", "binance_symbol": "BTCUSDT", "decimal_places": 2},
    "ETH/USD": {"type": "crypto", "binance_symbol": "ETHUSDT", "decimal_places": 2},
    "SOL/USD": {"type": "crypto", "binance_symbol": "SOLUSDT", "decimal_places": 3},
    "BNB/USD": {"type": "crypto", "binance_symbol": "BNBUSDT", "decimal_places": 2},
    "XRP/USD": {"type": "crypto", "binance_symbol": "XRPUSDT", "decimal_places": 4},
    "DOGE/USD": {"type": "crypto", "binance_symbol": "DOGEUSDT", "decimal_places": 5},
    "ADA/USD": {"type": "crypto", "binance_symbol": "ADAUSDT", "decimal_places": 4},
    "DOT/USD": {"type": "crypto", "binance_symbol": "DOTUSDT", "decimal_places": 3},
    "LINK/USD": {"type": "crypto", "binance_symbol": "LINKUSDT", "decimal_places": 3},
    "AVAX/USD": {"type": "crypto", "binance_symbol": "AVAXUSDT", "decimal_places": 3},
    "MATIC/USD": {"type": "crypto", "binance_symbol": "MATICUSDT", "decimal_places": 4},
    "ATOM/USD": {"type": "crypto", "binance_symbol": "ATOMUSDT", "decimal_places": 3},
    "LTC/USD": {"type": "crypto", "binance_symbol": "LTCUSDT", "decimal_places": 2},
    "BCH/USD": {"type": "crypto", "binance_symbol": "BCHUSDT", "decimal_places": 2},
    "TRX/USD": {"type": "crypto", "binance_symbol": "TRXUSDT", "decimal_places": 5},
    "XLM/USD": {"type": "crypto", "binance_symbol": "XLMUSDT", "decimal_places": 5},
    "FIL/USD": {"type": "crypto", "binance_symbol": "FILUSDT", "decimal_places": 3},
    "APT/USD": {"type": "crypto", "binance_symbol": "APTUSDT", "decimal_places": 3},
    "SUI/USD": {"type": "crypto", "binance_symbol": "SUIUSDT", "decimal_places": 3},
    "ARB/USD": {"type": "crypto", "binance_symbol": "ARBUSDT", "decimal_places": 4},
    "NEAR/USD": {"type": "crypto", "binance_symbol": "NEARUSDT", "decimal_places": 3},
    "OP/USD": {"type": "crypto", "binance_symbol": "OPUSDT", "decimal_places": 3},
    "INJ/USD": {"type": "crypto", "binance_symbol": "INJUSDT", "decimal_places": 3},
    "PEPE/USD": {"type": "crypto", "binance_symbol": "PEPEUSDT", "decimal_places": 6},
    "SHIB/USD": {"type": "crypto", "binance_symbol": "SHIBUSDT", "decimal_places": 7},

    # Missing crypto from Pocket Option
    "TON/USD": {"type": "crypto", "binance_symbol": "TONUSDT", "decimal_places": 3},
    "DASH/USD": {"type": "crypto", "binance_symbol": "DASHUSDT", "decimal_places": 2},

    # ============ Indices (from Pocket Option) ============
    "AUS200": {"type": "indices", "otc": True, "yfinance_symbol": "^AXJO", "decimal_places": 2},
    "UK100": {"type": "indices", "otc": True, "yfinance_symbol": "^FTSE", "decimal_places": 2},
    "DE30": {"type": "indices", "otc": True, "yfinance_symbol": "^GDAXI", "decimal_places": 2},
    "DJI30": {"type": "indices", "otc": True, "yfinance_symbol": "^DJI", "decimal_places": 2},
    "EU35": {"type": "indices", "otc": True, "yfinance_symbol": "^STOXX50E", "decimal_places": 2},
    "EU50": {"type": "indices", "otc": True, "yfinance_symbol": "^STOXX", "decimal_places": 2},
    "F40": {"type": "indices", "otc": True, "yfinance_symbol": "^FCHI", "decimal_places": 2},
    "JP225": {"type": "indices", "otc": True, "yfinance_symbol": "^N225", "decimal_places": 2},
    "US100": {"type": "indices", "otc": True, "yfinance_symbol": "^NDX", "decimal_places": 2},
    "SP500": {"type": "indices", "otc": True, "yfinance_symbol": "^GSPC", "decimal_places": 2},

    # ============ Forex (via Yahoo Finance) ============
    # Standard pairs (non-OTC) — with yfinance support
    "AUD/CAD": {"type": "forex", "yfinance_symbol": "AUDCAD=X", "decimal_places": 5},
    "AUD/CHF": {"type": "forex", "yfinance_symbol": "AUDCHF=X", "decimal_places": 5},
    "AUD/JPY": {"type": "forex", "yfinance_symbol": "AUDJPY=X", "decimal_places": 3},
    "AUD/USD": {"type": "forex", "yfinance_symbol": "AUDUSD=X", "decimal_places": 5},
    "CAD/CHF": {"type": "forex", "yfinance_symbol": "CADCHF=X", "decimal_places": 5},
    "CAD/JPY": {"type": "forex", "yfinance_symbol": "CADJPY=X", "decimal_places": 3},
    "CHF/JPY": {"type": "forex", "yfinance_symbol": "CHFJPY=X", "decimal_places": 3},
    "EUR/AUD": {"type": "forex", "yfinance_symbol": "EURAUD=X", "decimal_places": 5},
    "EUR/CAD": {"type": "forex", "yfinance_symbol": "EURCAD=X", "decimal_places": 5},
    "EUR/CHF": {"type": "forex", "yfinance_symbol": "EURCHF=X", "decimal_places": 5},
    "EUR/GBP": {"type": "forex", "yfinance_symbol": "EURGBP=X", "decimal_places": 5},
    "EUR/JPY": {"type": "forex", "yfinance_symbol": "EURJPY=X", "decimal_places": 3},
    "EUR/USD": {"type": "forex", "yfinance_symbol": "EURUSD=X", "decimal_places": 5},
    "GBP/AUD": {"type": "forex", "yfinance_symbol": "GBPAUD=X", "decimal_places": 5},
    "GBP/CAD": {"type": "forex", "yfinance_symbol": "GBPCAD=X", "decimal_places": 5},
    "GBP/CHF": {"type": "forex", "yfinance_symbol": "GBPCHF=X", "decimal_places": 5},
    "GBP/JPY": {"type": "forex", "yfinance_symbol": "GBPJPY=X", "decimal_places": 3},
    "GBP/USD": {"type": "forex", "yfinance_symbol": "GBPUSD=X", "decimal_places": 5},
    "USD/CAD": {"type": "forex", "yfinance_symbol": "USDCAD=X", "decimal_places": 5},
    "USD/CHF": {"type": "forex", "yfinance_symbol": "USDCHF=X", "decimal_places": 5},
    "USD/JPY": {"type": "forex", "yfinance_symbol": "USDJPY=X", "decimal_places": 3},
    # OTC / Exotic pairs
    "AED/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "AUD/CAD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "AUD/CHF OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "AUD/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "AUD/NZD OTC": {"type": "forex", "yfinance_symbol": "AUDNZD=X", "decimal_places": 5},
    "AUD/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "BHD/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "CAD/CHF OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "CAD/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "CHF/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "CHF/NOK OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "EUR/CHF OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "EUR/GBP OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "EUR/HUF OTC": {"type": "forex", "yfinance_symbol": "EURHUF=X", "decimal_places": 4},
    "EUR/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "EUR/NZD OTC": {"type": "forex", "yfinance_symbol": "EURNZD=X", "decimal_places": 5},
    "EUR/RUB OTC": {"type": "forex", "yfinance_symbol": "EURRUB=X", "decimal_places": 4},
    "EUR/TRY OTC": {"type": "forex", "yfinance_symbol": "EURTRY=X", "decimal_places": 4},
    "EUR/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "GBP/AUD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "GBP/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "GBP/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "JOD/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "KES/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "LBP/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "MAD/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "NGN/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "NZD/JPY OTC": {"type": "forex", "yfinance_symbol": "NZDJPY=X", "decimal_places": 3},
    "NZD/USD OTC": {"type": "forex", "yfinance_symbol": "NZDUSD=X", "decimal_places": 5},
    "OMR/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "QAR/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "SAR/CNY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "TND/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "UAH/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/ARS OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/BDT OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/BRL OTC": {"type": "forex", "yfinance_symbol": "USDBRL=X", "decimal_places": 4},
    "USD/CAD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "USD/CHF OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 5},
    "USD/CLP OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/CNH OTC": {"type": "forex", "yfinance_symbol": "USDCNH=X", "decimal_places": 5},
    "USD/COP OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/DZD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/EGP OTC": {"type": "forex", "yfinance_symbol": "USDEGP=X", "decimal_places": 4},
    "USD/IDR OTC": {"type": "forex", "yfinance_symbol": "USDIDR=X", "decimal_places": 4},
    "USD/INR OTC": {"type": "forex", "yfinance_symbol": "USDINR=X", "decimal_places": 4},
    "USD/JPY OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 3},
    "USD/MXN OTC": {"type": "forex", "yfinance_symbol": "USDMXN=X", "decimal_places": 4},
    "USD/MYR OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/PHP OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/PKR OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/RUB OTC": {"type": "forex", "yfinance_symbol": "USDRUB=X", "decimal_places": 4},
    "USD/SGD OTC": {"type": "forex", "yfinance_symbol": "USDSGD=X", "decimal_places": 5},
    "USD/THB OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "USD/VND OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "YER/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},
    "ZAR/USD OTC": {"type": "forex", "yfinance_symbol": "", "decimal_places": 4},

    # ============ Stocks / OTC ============
    "AAPL": {"type": "stock", "otc": True, "yfinance_symbol": "AAPL", "decimal_places": 2},
    "TSLA": {"type": "stock", "otc": True, "yfinance_symbol": "TSLA", "decimal_places": 2},
    "GOOGL": {"type": "stock", "otc": True, "yfinance_symbol": "GOOGL", "decimal_places": 2},
    "AMZN": {"type": "stock", "otc": True, "yfinance_symbol": "AMZN", "decimal_places": 2},
    "NVDA": {"type": "stock", "otc": True, "yfinance_symbol": "NVDA", "decimal_places": 2},
    "META": {"type": "stock", "otc": True, "yfinance_symbol": "META", "decimal_places": 2},
    "MSFT": {"type": "stock", "otc": True, "yfinance_symbol": "MSFT", "decimal_places": 2},
    "TSM": {"type": "stock", "otc": True, "yfinance_symbol": "TSM", "decimal_places": 2},
    "AMD": {"type": "stock", "otc": True, "yfinance_symbol": "AMD", "decimal_places": 2},
    "NFLX": {"type": "stock", "otc": True, "yfinance_symbol": "NFLX", "decimal_places": 2},
    "AMC": {"type": "stock", "otc": True, "yfinance_symbol": "AMC", "decimal_places": 2},
    "GME": {"type": "stock", "otc": True, "yfinance_symbol": "GME", "decimal_places": 2},
    "DIS": {"type": "stock", "otc": True, "yfinance_symbol": "DIS", "decimal_places": 2},
    "BA": {"type": "stock", "otc": True, "yfinance_symbol": "BA", "decimal_places": 2},
    "JPM": {"type": "stock", "otc": True, "yfinance_symbol": "JPM", "decimal_places": 2},
    "V": {"type": "stock", "otc": True, "yfinance_symbol": "V", "decimal_places": 2},
    "JNJ": {"type": "stock", "otc": True, "yfinance_symbol": "JNJ", "decimal_places": 2},
    "WMT": {"type": "stock", "otc": True, "yfinance_symbol": "WMT", "decimal_places": 2},
    "KO": {"type": "stock", "otc": True, "yfinance_symbol": "KO", "decimal_places": 2},
    "MCD": {"type": "stock", "otc": True, "yfinance_symbol": "MCD", "decimal_places": 2},
    "NKE": {"type": "stock", "otc": True, "yfinance_symbol": "NKE", "decimal_places": 2},
    "SBUX": {"type": "stock", "otc": True, "yfinance_symbol": "SBUX", "decimal_places": 2},
    "PLTR": {"type": "stock", "otc": True, "yfinance_symbol": "PLTR", "decimal_places": 2},
    "UBER": {"type": "stock", "otc": True, "yfinance_symbol": "UBER", "decimal_places": 2},
    "RIVN": {"type": "stock", "otc": True, "yfinance_symbol": "RIVN", "decimal_places": 2},
    "COIN": {"type": "stock", "otc": True, "yfinance_symbol": "COIN", "decimal_places": 2},
    "SNAP": {"type": "stock", "otc": True, "yfinance_symbol": "SNAP", "decimal_places": 2},
    "PYPL": {"type": "stock", "otc": True, "yfinance_symbol": "PYPL", "decimal_places": 2},
    "SQ": {"type": "stock", "otc": True, "yfinance_symbol": "SQ", "decimal_places": 2},
    "MRNA": {"type": "stock", "otc": True, "yfinance_symbol": "MRNA", "decimal_places": 2},
    "PFE": {"type": "stock", "otc": True, "yfinance_symbol": "PFE", "decimal_places": 2},

    # ============ Commodities ============
    "XAU/USD": {"type": "commodity", "otc": True, "yfinance_symbol": "GC=F", "decimal_places": 2},
    "XAG/USD": {"type": "commodity", "otc": True, "yfinance_symbol": "SI=F", "decimal_places": 3},
    "USOIL": {"type": "commodity", "otc": True, "yfinance_symbol": "CL=F", "decimal_places": 2},
    "UKOIL": {"type": "commodity", "otc": True, "yfinance_symbol": "BZ=F", "decimal_places": 2},
    "NATGAS": {"type": "commodity", "otc": True, "yfinance_symbol": "NG=F", "decimal_places": 3},
    "COPPER": {"type": "commodity", "otc": True, "yfinance_symbol": "HG=F", "decimal_places": 4},
    "PLATINUM": {"type": "commodity", "otc": True, "yfinance_symbol": "PL=F", "decimal_places": 2},
    "PALLADIUM": {"type": "commodity", "otc": True, "yfinance_symbol": "PA=F", "decimal_places": 2},
    "ALUMINUM": {"type": "commodity", "otc": True, "yfinance_symbol": "ALI=F", "decimal_places": 2},
    "WHEAT": {"type": "commodity", "otc": True, "yfinance_symbol": "ZW=F", "decimal_places": 2},
    "CORN": {"type": "commodity", "otc": True, "yfinance_symbol": "ZC=F", "decimal_places": 2},
    "SOYBEAN": {"type": "commodity", "otc": True, "yfinance_symbol": "ZS=F", "decimal_places": 2},
    "COFFEE": {"type": "commodity", "otc": True, "yfinance_symbol": "KC=F", "decimal_places": 2},
    "SUGAR": {"type": "commodity", "otc": True, "yfinance_symbol": "SB=F", "decimal_places": 3},
    "COTTON": {"type": "commodity", "otc": True, "yfinance_symbol": "CT=F", "decimal_places": 2},
    "COCOA": {"type": "commodity", "otc": True, "yfinance_symbol": "CC=F", "decimal_places": 1},
    "OATS": {"type": "commodity", "otc": True, "yfinance_symbol": "ZO=F", "decimal_places": 2},
    "RICE": {"type": "commodity", "otc": True, "yfinance_symbol": "ZR=F", "decimal_places": 2},
    "LUMBER": {"type": "commodity", "otc": True, "yfinance_symbol": "LBS=F", "decimal_places": 2},
}

# Timeframes available for analysis
TIMEFRAMES = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "30m": "30 minutes",
    "1h": "1 hour",
    "4h": "4 hours",
}

# Default expiry times for binary options (in minutes)
BINARY_EXPIRY_OPTIONS = [1, 5, 15, 30, 60]

# Signal confidence thresholds
HIGH_CONFIDENCE = 75  # >= 75%
MEDIUM_CONFIDENCE = 55  # >= 55%
LOW_CONFIDENCE = 0  # < 55%

# Bot messages
WELCOME_MESSAGE = """🤖 **TradeMind Signal Bot** 🚀

سلام! به ربات سیگنال‌دهنده هوشمند خوش اومدی!

من با استفاده از **تحلیل تکنیکال پیشرفته** و **هوش مصنوعی** سیگنال‌های معاملاتی برای بازارهای مختلف ارائه میدم.

📋 **دستورات:**
/signal <pair> - دریافت سیگنال برای یک جفت‌ارز
/analysis <pair> - تحلیل کامل بازار
/pairs - لیست جفت‌ارزهای قابل معامله
/help - راهنما

🔹 **مثال:** /signal BTC/USD
🔹 **مثال:** /analysis EUR/USD

قدرت هوش مصنوعی در خدمت معاملات تو! 🎯"""

HELP_MESSAGE = """📖 **راهنمای ربات TradeMind Signal Bot**

**🔍 دستورات اصلی:**

▪️ `/signal BTC/USD` — دریافت سیگنال خرید/فروش
▪️ `/analysis EUR/USD` — تحلیل کامل تکنیکال
▪️ `/pairs` — نمایش همه جفت‌ارزهای قابل معامله
▪️ `/subscribe 5m` — دریافت خودکار سیگنال هر ۵ دقیقه
▪️ `/unsubscribe` — لغو دریافت خودکار سیگنال
▪️ `/help` — نمایش این راهنما

**📊 نحوه تحلیل:**
- RSI (شاخص قدرت نسبی)
- MACD (میانگین متحرک همگرایی/واگرایی)
- EMA Crossover (تقاطع میانگین‌های متحرک)
- Bollinger Bands (باندهای بولینگر)
- Stochastic (استوکستیک)
- تحلیل هم‌جهت چند اندیکاتور

**💡 نکات مهم:**
⚠️ سیگنال‌ها فقط برای اهداف آموزشی و تحلیلی هستند
⚠️ هیچ تضمینی برای سودآوری وجود ندارد
⚠️ همیشه مدیریت سرمایه رو رعایت کن

**📞 پشتیبانی:**
@trademind_help
"""

PAIRS_LIST_HEADER = """📊 **لیست جفت‌ارزهای قابل معامله**

برای دریافت سیگنال از دستور زیر استفاده کن:
`/signal <نام>`"""

ERROR_MESSAGE = "❌ خطا در پردازش درخواست. لطفاً دوباره تلاش کن."
PAIR_NOT_FOUND = "❌ جفت‌ارز مورد نظر یافت نشد! از /pairs برای دیدن لیست استفاده کن."

# Category display config for inline buttons
CATEGORY_ORDER = ["forex", "other"]
CATEGORY_DISPLAY = {
    "forex": {"emoji": "💱", "label": "ارزها (Currencies)"},
    "other": {"emoji": "📊", "label": "سایر (Other)"},
}

# Max pairs per row in inline buttons
PAIRS_PER_ROW = 3


def get_pair_display(pair_name: str) -> str:
    """Get display name for a pair, e.g. 'BTC/USD', 'AAPL (OTC)'"""
    info = AVAILABLE_PAIRS.get(pair_name)
    if info and info.get("otc"):
        return f"{pair_name} (OTC)"
    return pair_name


def get_pairs_by_category(category: str) -> list:
    """Get list of pair names in a category, sorted.
    'other' is a meta-category covering crypto, stock, and commodity."""
    if category == "other":
        pairs = [p for p, info in AVAILABLE_PAIRS.items() if info.get("type") in ("crypto", "stock", "commodity", "indices")]
    else:
        pairs = [p for p, info in AVAILABLE_PAIRS.items() if info.get("type") == category]
    return sorted(pairs)

