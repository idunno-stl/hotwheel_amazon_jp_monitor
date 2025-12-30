import requests
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"
PROXY_URL = os.getenv("GOOGLE_PROXY_URL")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, data=payload, timeout=15)

def main():
    now = datetime.now().strftime("%H:%M")
    
    if IS_MANUAL:
        send_telegram("🚀 <b>Deep Scan Started...</b>")

    # 1. Load Memory
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    # 2. Fetch via Google Proxy
    try:
        r = requests.get(PROXY_URL, params={'url': AMAZON_URL}, timeout=60)
        
        # Check if we got a "Security" page
        if "api-services-support@amazon.com" in r.text or "not a robot" in r.text:
            if IS_MANUAL: send_telegram("❌ <b>Blocked:</b> Amazon detected the Google Proxy as a bot. Retrying in 15 mins...")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []

        # Find ALL divs that might be products
        items = soup.find_all("div", {"data-asin": True})

        for item in items:
            asin = item.get("data-asin")
            if not asin or len(asin) != 10: continue
            
            # Skip Sponsored
            if any(x in item.get_text().lower() for x in ["sponsored", "スポンサー"]):
                continue

            # Try to get title from the best available source in the div
            title_node = item.select_one("h2 a span") or item.select_one("h2") or item.select_one(".a-size-base-plus")
            title = title_node.get_text(strip=True) if title_node else f"Product {asin}"

            current_items.append({
                "asin": asin,
                "title": title,
                "link": f"https://www.amazon.co.jp/dp/{asin}"
            })
            
            if len(current_items) >= 5: break

        # 3. Logic & Reporting
        if not current_items:
            if IS_MANUAL:
                # Send a bit more of the HTML so I can see what's wrong
                debug_txt = r.text[:400].replace("<", "&lt;")
                send_telegram(f"❌ <b>Still no items.</b>\nDebug: <code>{debug_txt}</code>")
            return

        if IS_MANUAL:
            report = f"📋 <b>Latest Items Found:</b>\n\n"
            for i, item in enumerate(current_items, 1):
                report += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n\n"
            send_telegram(report)
        else:
            # Automatic mode: only notify on NEW items
            for item in current_items:
                if item["asin"] not in memory_asins:
                    send_telegram(f"🚨 <b>NEW!</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")

        # Save to memory
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ <b>System Error:</b> {str(e)}")

    if IS_MANUAL:
        send_telegram("💤 <b>Scan Complete.</b> Resuming 15-min checks.")

if __name__ == "__main__":
    main()
