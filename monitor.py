import requests
import json
import os
import time
from bs4 import BeautifulSoup

# CONFIG
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true" # New check

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram failed: {e}")

def main():
    # 1. Startup Notification (Only if you click 'Run Workflow' manually)
    if IS_MANUAL:
        send_telegram("🚀 <b>Monitor Started!</b>\nConnection successful. Checking Amazon now...")

    # 2. Load History
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump([], f)
    
    try:
        with open(DATA_FILE, "r") as f:
            old_asins = {i["asin"] for i in json.load(f)}
    except:
        old_asins = set()

    # 3. Fetch Data
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja-JP"
    }
    
    try:
        r = requests.get(AMAZON_URL, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        current_items = []
        for div in soup.select("div[data-asin]")[:15]:
            asin = div.get("data-asin")
            title_elem = div.select_one("h2 a span")
            if asin and title_elem:
                current_items.append({
                    "asin": asin, 
                    "title": title_elem.get_text(strip=True), 
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                })

        # 4. Compare & Notify
        new_found = 0
        for item in current_items:
            if item["asin"] not in old_asins:
                send_telegram(f"🚨 <b>NEW HOT WHEELS</b>\n\n{item['title']}\n\n🔗 <a href='{item['link']}'>View on Amazon</a>")
                new_found += 1

        if IS_MANUAL and new_found == 0:
            send_telegram("No new items found right now, but I'm watching! 👀")

        # 5. Save State
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ <b>Error:</b> {str(e)}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
