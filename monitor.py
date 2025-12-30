import requests
import json
import os
import time
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PROXY_URL = os.getenv("GOOGLE_PROXY_URL")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload, timeout=15)

def main():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump([], f)
    with open(DATA_FILE, "r") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    try:
        r = requests.get(PROXY_URL, params={'url': AMAZON_URL}, timeout=60)
        
        if "STEALTH_FAIL" in r.text:
            if IS_MANUAL: send_telegram("⚠️ Amazon blocked the proxy. Retrying in 15m.")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        seen_this_scan = set()

        # Find items
        results = soup.select("div[data-component-type='s-search-result']")
        for div in results:
            asin = div.get("data-asin")
            if not asin or asin in seen_this_scan or len(asin) != 10: continue
            
            # Filter Sponsored
            if "sponsored" in div.get_text().lower() or "スポンサー" in div.get_text().lower():
                continue

            title_node = div.select_one("h2 a span") or div.select_one("h2")
            title = title_node.get_text(strip=True) if title_node else "Hot Wheels Product"

            current_items.append({"asin": asin, "title": title, "link": f"https://www.amazon.co.jp/dp/{asin}"})
            seen_this_scan.add(asin)
            if len(current_items) >= 5: break

        # Send Notifications
        for item in current_items:
            if item["asin"] not in memory_asins:
                send_telegram(f"🚨 <b>NEW PRE-ORDER!</b>\n\n{item['title']}\n\n🔗 <a href='{item['link']}'>Open in Amazon</a>")
                time.sleep(2) # Delay for images to load

        # Save Memory
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
