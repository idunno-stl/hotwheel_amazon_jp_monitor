import requests
import json
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

def get_now():
    # Returns formatted timestamp for Japan Time (JST is UTC+9)
    return datetime.now().strftime("%H:%M:%S")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def main():
    timestamp = get_now()
    if IS_MANUAL:
        send_telegram(f"🛰️ <b>[{timestamp}] Manual Scan Started...</b>")

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump([], f)
    with open(DATA_FILE, "r") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.co.jp/"
    }

    try:
        # STEALTH: Wait a few seconds so we don't look like a 20-min robot
        time.sleep(5) 
        response = requests.get(AMAZON_URL, headers=headers, timeout=30)
        
        if response.status_code != 200:
            send_telegram(f"⚠️ <b>[{timestamp}] BLOCK ALERT:</b> Status {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        current_top_5 = []
        new_items_found = False

        results = soup.select("div[data-component-type='s-search-result']")
        
        for div in results:
            div_text = div.get_text().lower()
            if any(p in div_text for p in ["sponsored", "スポンサー", "featured", "ad", "広告"]):
                continue

            asin = div.get("data-asin")
            if not asin or len(asin) != 10: continue
            
            title_node = div.select_one("h2 a span") or div.select_one("h2")
            title = title_node.get_text(strip=True) if title_node else "Hot Wheels"
            link = f"https://www.amazon.co.jp/dp/{asin}"

            if len(current_top_5) < 5:
                current_top_5.append({"asin": asin, "title": title})

            if asin not in memory_asins:
                send_telegram(f"🚨 <b>NEW @ {get_now()}</b>\n{title}\n🔗 <a href='{link}'>Link</a>")
                new_items_found = True
                time.sleep(2)

        if not new_items_found and IS_MANUAL:
            send_telegram(f"💤 <b>[{get_now()}] Scan Complete.</b> No new items found.")

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_top_5, f, ensure_ascii=False, indent=2)

    except Exception as e:
        send_telegram(f"❌ <b>[{timestamp}] Error:</b> {str(e)}")

if __name__ == "__main__":
    main()
