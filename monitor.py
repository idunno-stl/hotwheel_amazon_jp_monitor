import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import time  # Added for a small delay between messages

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"
PROXY_URL = os.getenv("GOOGLE_PROXY_URL")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # disable_web_page_preview is set to False (default) so images show up
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload, timeout=15)

def main():
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
        
        if "AMZ_BLOCK" in r.text or "not a robot" in r.text:
            if IS_MANUAL: send_telegram("❌ <b>Blocked by Amazon.</b> Try a new Deployment URL.")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        seen_this_scan = set() # <--- DUPLICATE PROTECTOR

        # Find all potential product blocks
        items = soup.find_all("div", {"data-asin": True})

        for item in items:
            asin = item.get("data-asin")
            
            # Validation: Must be 10 chars, not sponsored, and NOT already seen in this scan
            if not asin or len(asin) != 10 or asin in seen_this_scan:
                continue
            
            if any(x in item.get_text().lower() for x in ["sponsored", "スポンサー"]):
                continue

            title_node = item.select_one("h2 a span") or item.select_one("h2") or item.select_one(".a-size-base-plus")
            title = title_node.get_text(strip=True) if title_node else f"Product {asin}"

            current_items.append({
                "asin": asin,
                "title": title,
                "link": f"https://www.amazon.co.jp/dp/{asin}"
            })
            seen_this_scan.add(asin) # Mark as seen
            
            if len(current_items) >= 5: break

        # 3. Logic & Reporting
        if not current_items:
            if IS_MANUAL: send_telegram("❌ No items found. Check the proxy URL.")
            return

        if IS_MANUAL:
            send_telegram(f"📋 <b>Found {len(current_items)} Unique Items:</b>")
            for item in current_items:
                # Send one by one so images load
                send_telegram(f"📦 <a href='{item['link']}'>{item['title']}</a>")
                time.sleep(1) # Tiny pause to avoid Telegram flood limits
        else:
            # Automatic mode: only notify on NEW items
            for item in current_items:
                if item["asin"] not in memory_asins:
                    send_telegram(f"🚨 <b>NEW PRE-ORDER!</b>\n\n{item['title']}\n\n🔗 <a href='{item['link']}'>View on Amazon</a>")
                    time.sleep(1)

        # Update memory
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ <b>Error:</b> {str(e)}")

    if IS_MANUAL:
        send_telegram("💤 <b>Scan Complete.</b>")

if __name__ == "__main__":
    main()
