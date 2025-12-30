import requests
import json
import os
import time
import random
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": msg, 
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram failed: {e}")

def main():
    # 1. Verification message for manual runs
    if IS_MANUAL:
        send_telegram("🚀 <b>Hot Wheels Monitor: Online</b>\nChecking Amazon for new pre-orders...")

    # 2. Database Safety Check (Prevents Exit Code 2)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            old_asins = {item["asin"] for item in old_data}
    except Exception:
        old_asins = set()

    # 3. Stealth Headers to avoid 503 Errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1"
    }

    # Random sleep to mimic a real person browsing
    time.sleep(random.uniform(3, 8))

    try:
        response = requests.get(AMAZON_URL, headers=headers, timeout=30)
        
        # Handle Amazon Blocks
        if response.status_code == 503:
            if IS_MANUAL:
                send_telegram("⚠️ <b>Amazon Blocked the Request (503).</b>\nThey detected the bot. I will try again automatically in 15 minutes.")
            return

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        current_items = []
        # Amazon search results usually live in these divs
        for div in soup.select("div[data-asin]"):
            asin = div.get("data-asin")
            if not asin or len(asin) < 5:
                continue

            # Find the title (supports multiple Amazon layout versions)
            title_elem = div.select_one("h2 a span")
            if not title_elem:
                title_elem = div.select_one(".a-size-base-plus.a-color-base.a-text-normal")
            
            if asin and title_elem:
                title = title_elem.get_text(strip=True)
                current_items.append({
                    "asin": asin,
                    "title": title,
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                })
            
            if len(current_items) >= 15: # Only track top 15 for speed
                break

        # 4. Detect New Arrivals
        new_count = 0
        for item in current_items:
            if item["asin"] not in old_asins:
                msg = (
                    f"🚨 <b>NEW HOT WHEELS PRE-ORDER</b>\n\n"
                    f"{item['title']}\n\n"
                    f"🔗 <a href='{item['link']}'>Open on Amazon.co.jp</a>"
                )
                send_telegram(msg)
                new_count += 1
                time.sleep(1) # Brief pause between messages

        if IS_MANUAL and new_count == 0:
            send_telegram("✅ Check complete. No <i>new</i> items found since last time.")

        # 5. Save State for Next Run
        if current_items:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"❌ <b>Monitor Error:</b>\n<code>{str(e)}</code>"
        print(error_msg)
        if IS_MANUAL:
            send_telegram(error_msg)

if __name__ == "__main__":
    main()
