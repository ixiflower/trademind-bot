"""
Pocket Option Signal Scraper

Scrapes real-time trading signals from Pocket Option's demo trading page.

Uses Selenium (headless Chrome) to:
1. Start a PO demo session (one-click or email/password)
2. Navigate to the Signals tab
3. Extract signal recommendation for the current asset

If the demo one-click account can't access signals (locked for unregistered users),
try credentials from PO_EMAIL / PO_PASSWORD environment variables.

Usage:
    from scraper import get_po_signal
    result = get_po_signal()
    print(result["signal"])  # "BUY", "SELL", "NEUTRAL", or "UNKNOWN"
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

PO_BASE = "https://pocketoption.com"
# Known English → enum mapping for PO signals
SIGNAL_MAP = {
    "Active uptrend": "STRONG_BUY",
    "Uptrend": "BUY",
    "Active downtrend": "STRONG_SELL",
    "Downtrend": "SELL",
    "No prediction": "NEUTRAL",
}

_driver: Optional[webdriver.Chrome] = None


def _make_opts() -> Options:
    opts = Options()
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
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    return opts


def _get_driver() -> webdriver.Chrome:
    global _driver
    if _driver is None:
        _driver = webdriver.Chrome(options=_make_opts())
    return _driver


def close_driver():
    global _driver
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


def _demo_login(driver: webdriver.Chrome) -> bool:
    """Navigate to try-demo which auto-creates a demo account."""
    driver.set_page_load_timeout(25)
    try:
        driver.get(f"{PO_BASE}/en/cabinet/try-demo/")
    except Exception:
        pass
    time.sleep(5)
    return "try-demo" in driver.current_url


def _cred_login(driver: webdriver.Chrome, email: str, password: str) -> bool:
    """Log into an existing account via the login page."""
    driver.set_page_load_timeout(20)
    try:
        driver.get(f"{PO_BASE}/en/login/")
    except Exception:
        pass
    time.sleep(3)

    try:
        e_input = driver.find_element(By.NAME, "email")
        p_input = driver.find_element(By.NAME, "password")
        e_input.clear()
        e_input.send_keys(email)
        p_input.clear()
        p_input.send_keys(password)
        btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        btn.click()
        time.sleep(5)
        return "cabinet" in driver.current_url or "demo-high-low" in driver.current_url
    except Exception:
        return False


def _dismiss_overlays(driver: webdriver.Chrome):
    """Dismiss tutorial / expiry overlays."""
    for text in ["Continue demo trading", "Start", "Skip", "Close"]:
        try:
            el = driver.find_element(By.XPATH, f"//*[contains(text(), '{text}')]")
            if el.is_displayed():
                driver.execute_script("arguments[0].click();", el)
                time.sleep(0.5)
        except Exception:
            pass


def _click_sidebar_tab(driver: webdriver.Chrome, label: str) -> bool:
    """Click a sidebar tab like 'Signals', 'Trades', etc."""
    for xpath in [
        f"//*[text()='{label}']",
        f"//*[contains(text(), '{label}')]",
    ]:
        els = driver.find_elements(By.XPATH, xpath)
        for el in els:
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(1.5)
                return True
            except Exception:
                continue
    return False


def _get_current_asset(driver: webdriver.Chrome) -> str:
    """Extract the currently displayed asset."""
    try:
        el = driver.find_element(
            By.XPATH,
            "//*[contains(@class, 'current-symbol') or "
            "contains(@class, 'instrument')]",
        )
        return el.text.strip()
    except Exception:
        pass
    body = driver.find_element(By.TAG_NAME, "body").text
    for line in body.split("\n"):
        if "/" in line and len(line.strip()) < 20:
            return line.strip()
    return "unknown"


def _parse_signal(driver: webdriver.Chrome) -> dict:
    """Parse signal data from the DOM.

    Returns dict with keys: signal (BUY/SELL/etc), raw_text, locked.
    """
    result = {
        "signal": "UNKNOWN",
        "raw_text": "",
        "locked": False,
    }

    body_text = driver.find_element(By.TAG_NAME, "body").text

    # Check for "registered users only" message
    if "registered users only" in body_text.lower() or "complete account registration" in body_text.lower():
        result["locked"] = True
        result["raw_text"] = (
            "⚠️ PO signals require a real account login.\n"
            "Pocket Option uses reCAPTCHA which blocks automated logins.\n"
            "Please log into your PO account manually via a real browser "
            "and check the Signals tab."
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


def get_po_signal(pair: str = None, force_new: bool = False) -> dict:
    """Scrape the current PO signal for the selected asset.

    Args:
        pair: Asset pair (e.g. "EUR/USD") — used for display only.
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
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        driver = _get_driver()

        # Prefer real account credentials if available
        email = os.environ.get("PO_EMAIL")
        password = os.environ.get("PO_PASSWORD")
        logged_in = False
        if email and password:
            logged_in = _cred_login(driver, email, password)
            if not logged_in:
                result["error"] = "Failed to log in with credentials"
                return result
        else:
            # Fall back to demo one-click
            logged_in = _demo_login(driver)

        if not logged_in:
            result["error"] = "Failed to create session"
            return result

        _dismiss_overlays(driver)

        asset = _get_current_asset(driver)
        result["symbol"] = asset

        # Open Signals tab
        if not _click_sidebar_tab(driver, "Signals"):
            result["error"] = "Could not find Signals tab"
            return result

        _dismiss_overlays(driver)

        # Parse signal data
        sig = _parse_signal(driver)
        result.update(sig)

    except Exception as e:
        logger.exception("Signal scrape failed")
        result["error"] = str(e)

    return result


# ---- Signal cache for quick display (avoids Selenium each time) ----
_last_signal_cache: dict = {}


def get_cached_po_signal(pair: str = None, max_age_seconds: int = 300) -> dict:
    """Get PO signal, using a 5-min cache."""
    cache_key = pair or "current"
    cached = _last_signal_cache.get(cache_key)
    if cached:
        age = (datetime.utcnow() - datetime.fromisoformat(cached["timestamp"])).total_seconds()
        if age < max_age_seconds:
            return cached

    fresh = get_po_signal(pair, force_new=False)
    _last_signal_cache[cache_key] = fresh
    return fresh


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    pair = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(get_po_signal(pair, force_new=True), indent=2))
    close_driver()
