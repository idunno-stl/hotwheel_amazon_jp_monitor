import requests
import json
import os
import time
import random
from bs4 import BeautifulSoup

# ================= CONFIG =================
# Strictly sorting by date-descending
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram failed: {e}")

def main():
    if IS_MANUAL:
        send_telegram("🚀 <b>Monitor Started</b>\nFiltering for the top 5 newest items (No Ads)...")

    # Load History
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old_asins = {item["asin"] for item in json.load(f)}
    except:
        old_asins = set()

    # Stealth Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.com/"
    }

    time.sleep(random.uniform(3, 7))

    try:
        r = requests.get(AMAZON_URL, headers=headers, timeout=30)
        if r.status_code == 503:
            if IS_MANUAL: send_telegram("⚠️ Amazon Blocked (503). Retrying later.")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        
        # Look specifically for search result containers
        search_results = soup.select("div[data-component-type='s-search-result']")

        for div in search_results:
            # 1. SKIP SPONSORED/ADS
            # Checks for the 'Sponsored' label in Japanese or English
            is_sponsored = div.select_one(".s-sponsored-label-info-desktop") or \
                           "スポンサー" in div.get_text() or \
                           "Sponsored" in div.get_text()
            
            if is_sponsored:
                continue

            asin = div.get("data-asin")
            title_elem = div.select_one("h2 a span")
            
            if asin and title_elem:
                title = title_elem.get_text(strip=True)
                current_items.append({
                    "asin": asin,
                    "title": title,
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                })
            
            # 2. STRICTLY TOP 5
            if len(current_items) >= 5:
                break

        # 3. COMPARE AND SEND
        new_count = 0
        for item in current_items:
            if item["asin"] not in old_asins:
                msg = f"🚨 <b>NEW ARRIVAL</b>\n\n{item['title']}\n\n🔗 <a href='{item['link']}'>Buy on Amazon</a>"
                send_telegram(msg)
                new_count += 1
                time.sleep(1)

        if IS_MANUAL and new_count == 0:
            send_telegram("✅ No new items in the top 5.")

        # 4. SAVE (Only top 5)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
