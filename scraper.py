"""
Pocket Option Signal Scraper

Scrapes real-time trading signals from Pocket Option's Signals tab.

STRATEGY (in order of preference):
1. Load saved cookies from ~/.po_cookies.json (fast, no login needed)
2. Login with PO_EMAIL / PO_PASSWORD env vars (uses undetected-chromedriver)
3. Fall back to demo mode (no signals, only basic trading view)

If credential login fails due to reCAPTCHA, you can:
  python -c "from scraper import inject_cookies; inject_cookies('path/to/cookies.json')"
After manually logging into https://pocketoption.com in your own browser
and exporting cookies as JSON (use EditThisCookie extension or similar).

Usage:
    from scraper import get_po_signal
    result = get_po_signal("EUR/USD")
    print(result["signal"])  # "STRONG_BUY", "BUY", etc.

Requires: undetected-chromedriver, selenium
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import undetected_chromedriver as uc

logger = logging.getLogger(__name__)

PO_BASE = "https://pocketoption.com"
SIGNAL_MAP = {
    "Active uptrend": "STRONG_BUY",
    "Uptrend": "BUY",
    "Active downtrend": "STRONG_SELL",
    "Downtrend": "SELL",
    "No prediction": "NEUTRAL",
}

_driver: Optional[uc.Chrome] = None
COOKIES_PATH = Path.home() / ".po_cookies.json"


def _make_opts(headless: bool = True) -> uc.ChromeOptions:
    """Build Chrome options for undetected-chromedriver."""
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    return opts


def _copy_chromedriver() -> str:
    """Copy system chromedriver to writable location for undetected to patch."""
    import shutil
    local_driver = str(Path.home() / ".local/share/uc_chromedriver_scraper")
    target = Path(local_driver)
    if not target.exists():
        shutil.copy2("/usr/bin/chromedriver", local_driver)
        target.chmod(0o755)
    return local_driver


def _get_driver(headless: bool = True) -> uc.Chrome:
    global _driver
    if _driver is None:
        _driver = uc.Chrome(
            options=_make_opts(headless=headless),
            use_subprocess=True,
            driver_executable_path=_copy_chromedriver(),
        )
    return _driver


def close_driver():
    global _driver
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
    # Also clean up driver binary
    local = Path.home() / ".local/share/uc_chromedriver_scraper"
    if local.exists():
        local.unlink()


# ---- Cookie persistence ----

def _save_cookies(driver: uc.Chrome):
    """Save browser cookies to disk for reuse."""
    try:
        cookies = driver.get_cookies()
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
        logger.info("Saved %d cookies to %s", len(cookies), COOKIES_PATH)
    except Exception as e:
        logger.warning("Failed to save cookies: %s", e)


def _load_cookies(driver: uc.Chrome) -> bool:
    """Load saved cookies into the browser. Returns True if any were loaded."""
    if not COOKIES_PATH.exists():
        return False
    try:
        # Must be on the domain first
        driver.get(PO_BASE)
        time.sleep(3)
    except Exception:
        # Timeout is OK, we just need to be on the domain for add_cookie
        pass
    try:
        cookies = json.loads(COOKIES_PATH.read_text())
        added = 0
        for c in cookies:
            try:
                driver.add_cookie(c)
                added += 1
            except Exception:
                pass
        time.sleep(2)
        logger.info("Loaded %d/%d cookies", added, len(cookies))
        return added > 0
    except Exception as e:
        logger.warning("Failed to load cookies: %s", e)
        return False


def _is_logged_in(driver: uc.Chrome) -> bool:
    """Check if we're on an authenticated page."""
    try:
        driver.get(f"{PO_BASE}/en/cabinet/")
        time.sleep(4)
        url = driver.current_url
        return any(kw in url for kw in ["cabinet", "demo-high-low"])
    except Exception:
        return False


# ---- Login strategies ----

def _login_with_creds(driver: uc.Chrome, email: str, password: str) -> bool:
    """Log into an existing account via the login form."""
    driver.set_page_load_timeout(30)
    try:
        driver.get(f"{PO_BASE}/en/login/")
        time.sleep(4)
    except Exception:
        pass

    try:
        # Check if login page loaded
        page_text = driver.find_element("tag name", "body").text[:200]
        if "login" not in page_text.lower() and "sign in" not in page_text.lower():
            logger.warning("Login page didn't load properly: %s", page_text[:80])
            return False

        # Fill form
        driver.find_element("name", "email").send_keys(email)
        driver.find_element("name", "password").send_keys(password)
        time.sleep(2)

        # Submit
        driver.find_element("xpath", "//button[@type='submit']").click()
        time.sleep(10)

        logged_in = any(kw in driver.current_url for kw in ["cabinet", "demo-high-low"])
        if logged_in:
            _save_cookies(driver)
        return logged_in
    except Exception as e:
        logger.warning("Credential login failed: %s", e)
        return False


def _demo_login(driver: uc.Chrome) -> bool:
    """Navigate to try-demo which auto-creates a demo account."""
    driver.set_page_load_timeout(30)
    try:
        driver.get(f"{PO_BASE}/en/cabinet/try-demo/")
        time.sleep(8)
    except Exception:
        pass
    url = driver.current_url
    return any(kw in url for kw in ["try-demo", "demo-high-low", "cabinet"])


# ---- UI helpers ----

def _dismiss_overlays(driver: uc.Chrome):
    """Dismiss tutorial / expiry overlays."""
    for text in ["Continue demo trading", "Start", "Skip", "Close", "X"]:
        try:
            for el in driver.find_elements("xpath", f"//*[contains(text(), '{text}')]"):
                if el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.5)
        except Exception:
            pass


def _click_sidebar_tab(driver: uc.Chrome, label: str) -> bool:
    """Click a sidebar tab like 'Signals', 'Trades', etc."""
    for xpath in [
        f"//*[text()='{label}']",
        f"//*[contains(text(), '{label}')]",
    ]:
        for el in driver.find_elements("xpath", xpath):
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(3)
                return True
            except Exception:
                continue
    return False


def _get_current_asset(driver: uc.Chrome) -> str:
    """Extract the currently displayed asset symbol."""
    try:
        el = driver.find_element(
            "xpath",
            "//*[contains(@class, 'current-symbol') or "
            "contains(@class, 'instrument')]",
        )
        return el.text.strip()
    except Exception:
        pass
    # Fallback: scan body text for symbol patterns
    body = driver.find_element("tag name", "body").text
    for line in body.split("\n"):
        line = line.strip()
        if "/" in line and len(line) < 20:
            return line
    return "unknown"


def _switch_asset(driver: uc.Chrome, pair: str) -> bool:
    """Try to switch the displayed asset to the requested pair."""
    try:
        sel = driver.find_element(
            "xpath",
            "//*[contains(@class, 'current-symbol') or "
            "contains(@class, 'instrument')]",
        )
        sel.click()
        time.sleep(1)
        inp = driver.find_element(
            "xpath",
            "//input[@type='text' or contains(@class, 'search')]",
        )
        inp.clear()
        inp.send_keys(pair)
        time.sleep(1.5)
        item = driver.find_element("xpath", f"//*[contains(text(), '{pair}')]")
        item.click()
        time.sleep(2)
        return True
    except Exception:
        return False


def _parse_signal(driver: uc.Chrome) -> dict:
    """Parse signal data from the DOM.

    Returns dict with keys: signal, raw_text, locked.
    """
    result = {
        "signal": "UNKNOWN",
        "raw_text": "",
        "locked": False,
    }

    time.sleep(2)
    body_text = driver.find_element("tag name", "body").text

    # Check for "registered users only" message
    if "registered users only" in body_text.lower() or "complete account registration" in body_text.lower():
        result["locked"] = True
        result["raw_text"] = (
            "⚠️ سیگنال‌های PO فقط برای حساب‌های واقعی در دسترسه.\n"
            "Pocket Option از reCAPTCHA استفاده می‌کنه "
            "که لاگین خودکار رو مسدود می‌کنه.\n"
            "راهکار: از مرورگر خودت وارد حساب PO بشو، "
            "کوکی‌ها رو Export کن، و فایل رو به bot بده."
        )
        return result

    # Parse the right-side panel text (after 'Signals' label)
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    in_signals = False
    signal_lines = []
    for line in lines:
        if line == "Signals":
            in_signals = True
            continue
        if in_signals:
            if line in ("Social Trading", "Express Trades", "Pending Trades", "Hotkeys", "Full screen"):
                break
            signal_lines.append(line)

    result["raw_text"] = "\n".join(signal_lines)

    # Match signal keywords
    for line in signal_lines:
        for keyword, signal_type in SIGNAL_MAP.items():
            if keyword in line:
                result["signal"] = signal_type
                return result

    # Fallback: check full body
    for line in lines:
        for keyword, signal_type in SIGNAL_MAP.items():
            if keyword in line:
                result["signal"] = signal_type
                if not result["raw_text"]:
                    result["raw_text"] = line
                return result

    return result


# ---- Public API ----

def ensure_session(max_retries: int = 2) -> tuple:
    """Try to establish a PO session. Returns (driver, is_logged_in, account_type).

    account_type is 'real', 'demo', or None.
    This can be called separately to pre-warm the session before scraping signals.
    """
    driver = _get_driver()
    logged_in = False
    account_type = None

    for attempt in range(max_retries + 1):
        # Try saved cookies first
        if attempt == 0 and COOKIES_PATH.exists():
            if _load_cookies(driver) and _is_logged_in(driver):
                logged_in = True
                account_type = "real"
                break

        # Try credential login
        email = os.environ.get("PO_EMAIL")
        password = os.environ.get("PO_PASSWORD")
        if email and password and _login_with_creds(driver, email, password):
            logged_in = True
            account_type = "real"
            break

        # Fall back to demo
        if _demo_login(driver):
            logged_in = True
            account_type = "demo"
            break

        time.sleep(2)

    return driver, logged_in, account_type


def get_po_signal(pair: str = None, force_new: bool = False) -> dict:
    """Scrape the current PO signal for the selected asset.

    Args:
        pair: Asset pair (e.g. "EUR/USD") — switches to that asset if given.
        force_new: Restart browser session.

    Returns:
        dict with keys: symbol, signal, raw_text, locked, error, timestamp.
    """
    if force_new:
        close_driver()

    result = {
        "symbol": pair or "current",
        "signal": "UNKNOWN",
        "raw_text": "",
        "locked": False,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        driver, logged_in, account_type = ensure_session()
        if not logged_in:
            result["error"] = "Could not connect to Pocket Option. Check your proxy/VPN."
            return result

        result["account_type"] = account_type

        # Try navigating to cabinet (real account) or stay on demo
        if account_type == "real":
            try:
                driver.get(f"{PO_BASE}/en/cabinet/")
                time.sleep(4)
            except Exception:
                pass
        elif account_type == "demo":
            try:
                driver.get(f"{PO_BASE}/en/cabinet/try-demo/")
                time.sleep(4)
            except Exception:
                pass

        _dismiss_overlays(driver)

        # Switch asset if requested
        if pair:
            result["symbol"] = pair
            _switch_asset(driver, pair)

        # Get current asset display name
        asset = _get_current_asset(driver)
        if asset and asset != "unknown":
            result["symbol"] = asset

        _dismiss_overlays(driver)

        # Open Signals tab
        if not _click_sidebar_tab(driver, "Signals"):
            result["error"] = "Could not find Signals tab on the page"
            return result

        _dismiss_overlays(driver)

        # Parse signal data
        sig = _parse_signal(driver)
        result.update(sig)

    except Exception as e:
        logger.exception("Signal scrape failed")
        result["error"] = str(e)

    return result


# ---- Cookie helper for user ----

def inject_cookies(cookies_path: str = None) -> str:
    """Inject cookies from a JSON file exported from the user's own browser.

    Args:
        cookies_path: Path to cookies JSON file. If None, prompts user.

    The cookies file should be an array of cookie objects with:
        name, value, domain, path, httpOnly, secure, sameSite, expirationDate

    Export from Chrome using EditThisCookie or similar extension.
    """
    if cookies_path:
        src = Path(cookies_path)
    else:
        src = COOKIES_PATH

    if not src.exists():
        return f"❌ File not found: {src}"

    try:
        cookies = json.loads(src.read_text())
        # Validate structure
        if not isinstance(cookies, list):
            return "❌ Invalid cookie format: expected array of cookie objects"

        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
        return f"✅ Loaded {len(cookies)} cookies from {src}\nNow run the bot and it will use these cookies."

    except Exception as e:
        return f"❌ Failed to load cookies: {e}"


# ---- Cache ----

_last_signal_cache: dict = {}


def get_cached_po_signal(pair: str = None, max_age_seconds: int = 300) -> dict:
    """Get PO signal, using a 5-min cache."""
    cache_key = pair or "current"
    cached = _last_signal_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["timestamp"])).total_seconds()
        if age < max_age_seconds:
            return cached

    fresh = get_po_signal(pair, force_new=False)
    _last_signal_cache[cache_key] = fresh
    return fresh


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    pair = sys.argv[1] if len(sys.argv) > 1 else None
    res = get_po_signal(pair, force_new=True)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    close_driver()
