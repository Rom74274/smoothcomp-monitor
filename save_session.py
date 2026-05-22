"""
Lance un navigateur. Connecte-toi à Smoothcomp manuellement.
Le script attend que tu appuies sur Entrée dans le terminal,
puis sauvegarde les cookies.
"""
from playwright.sync_api import sync_playwright
import json

LOGIN = "https://smoothcomp.com/en/auth/login"
TARGET = "https://smoothcomp.com/en/event/31206/register/1513381/entries"
OUTPUT = "session_state.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="chrome")
    context = browser.new_context()
    page = context.new_page()
    page.goto(LOGIN)

    input("\n>>> Connecte-toi dans le navigateur, puis appuie sur ENTRÉE ici...\n")

    # Navigate to target to verify
    page.goto(TARGET, wait_until="networkidle", timeout=60000)
    html = page.content()
    print(f"Page: {len(html)} chars | Title: {page.title()}")

    if len(html) > 10000:
        state = context.storage_state()
        with open(OUTPUT, "w") as f:
            json.dump(state, f)
        print(f"✅ Session sauvegardée dans {OUTPUT}")
    else:
        print("❌ Page toujours bloquée. Vérifie que tu es bien connecté.")

    browser.close()
