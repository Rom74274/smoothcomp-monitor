import json
import logging
import os
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = "https://smoothcomp.com/en/event/31206/register/1513381/entries"
STATE_FILE = Path("state.json")

CALLMEBOT_PHONE = os.environ["CALLMEBOT_PHONE"]
CALLMEBOT_APIKEY = os.environ["CALLMEBOT_APIKEY"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def fetch_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=60000)
        # Attendre que le contenu réel soit chargé
        try:
            page.wait_for_selector('script#data[type="application/json"]', timeout=15000)
        except Exception:
            pass  # On continue, check_availability gèrera l'absence
        html = page.content()
        browser.close()
    return html


def check_availability(html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # La vraie page Smoothcomp fait 20k+ chars et contient le script JSON.
    # Si la page est trop petite ou sans script JSON, c'est une page bloquée/challenge.
    data_script = soup.find("script", id="data", attrs={"type": "application/json"})
    if len(html) < 10000 or not data_script:
        logging.warning(
            "Page incomplète ou bloquée (%d chars, data_script=%s). Ignoré.",
            len(html), bool(data_script),
        )
        return None, {"error": "page_incomplete"}

    unavailable_labels = soup.find_all("span", class_="label label-warning")
    has_unavailable_label = any(
        "Item not available" in label.get_text() for label in unavailable_labels
    )

    has_available_true = False
    if data_script.string:
        try:
            data = json.loads(data_script.string)
            has_available_true = _find_available_true(data)
        except json.JSONDecodeError as exc:
            logging.warning("JSON invalide: %s", exc)

    available = (not has_unavailable_label) or has_available_true
    return available, {
        "has_unavailable_label": has_unavailable_label,
        "has_available_true": has_available_true,
    }


def _find_available_true(obj):
    if isinstance(obj, dict):
        if obj.get("available") is True:
            return True
        return any(_find_available_true(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_find_available_true(v) for v in obj)
    return False


def send_whatsapp(text):
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={CALLMEBOT_PHONE}"
        f"&apikey={CALLMEBOT_APIKEY}"
        f"&text={requests.utils.quote(text)}"
    )
    resp = requests.get(url, timeout=15)
    if resp.ok:
        logging.info("WhatsApp envoyé.")
    else:
        logging.error("CallMeBot failed: %s %s", resp.status_code, resp.text[:200])


def load_state():
    if not STATE_FILE.exists():
        return "unknown"
    try:
        return json.loads(STATE_FILE.read_text()).get("last", "unknown")
    except json.JSONDecodeError:
        return "unknown"


def save_state(value):
    STATE_FILE.write_text(json.dumps({"last": value}))


def main():
    try:
        html = fetch_page()
    except Exception as exc:
        logging.error("Playwright fetch error: %s", exc)
        sys.exit(0)

    logging.info("Page récupérée (%d chars)", len(html))
    available, details = check_availability(html)

    if available is None:
        logging.warning("Check ignoré (page incomplète).")
        return

    last = load_state()
    current = "available" if available else "unavailable"

    logging.info("current=%s last=%s | %s", current, last, details)

    if current == "available" and last != "available":
        send_whatsapp(
            f"🎉 *Smoothcomp : place dispo !*\n\n"
            f"Ouvre la page d'inscription :\n{URL}"
        )

    if current != last:
        save_state(current)


if __name__ == "__main__":
    main()
