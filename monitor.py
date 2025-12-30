import requests
import json
import os
import time
from bs4 import BeautifulSoup

# ================= CONFIG =================
# We use a search URL that mimics a real user's browser search
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload, timeout=15)

def main():
    # 1. Load History
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump([], f)
    with open(DATA_FILE, "r") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    # 2. Setup "Human-Like" Headers
    # This is the most important part to avoid the "Block"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.co.jp/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # Requesting directly from GitHub's server
        response = requests.get(AMAZON_URL, headers=headers, timeout=30)
        
        if response.status_code != 200:
            if IS_MANUAL: send_telegram(f"⚠️ Error {response.status_code}: Amazon is being tough.")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        current_items = []
        seen_in_this_run = set()

        # Find products
        results = soup.select("div[data-component-type='s-search-result']")
        
        for div in results:
            asin = div.get("data-asin")
            if not asin or asin in seen_in_this_run: continue
            
            # Filter out sponsored
            if "sponsored" in div.get_text().lower() or "スポンサー" in div.get_text().lower():
                continue

            title_node = div.select_one("h2 a span") or div.select_one("h2")
            title = title_node.get_text(strip=True) if title_node else "Hot Wheels"

            current_items.append({"asin": asin, "title": title, "link": f"https://www.amazon.co.jp/dp/{asin}"})
            seen_in_this_run.add(asin)
            if len(current_items) >= 5: break

        # 3. Notification Logic
        for item in current_items:
            if item["asin"] not in memory_asins:
                # Individual message for the image preview
                send_telegram(f"🚨 <b>NEW HOT WHEELS!</b>\n\n{item['title']}\n\n🔗 <a href='{item['link']}'>Buy on Amazon</a>")
                time.sleep(2) 

        # Save new state
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ System Error: {str(e)}")

if __name__ == "__main__":
    main()
