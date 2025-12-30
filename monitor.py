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

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    # 1. Start Notification
    send_telegram("🛰️ <b>Scan Started...</b>")

    # 2. Load Memory
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump([], f)
    with open(DATA_FILE, "r") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    # 3. Fetch Data
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.co.jp/"
    }

    try:
        response = requests.get(AMAZON_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        current_items = []
        new_found = False

        results = soup.select("div[data-component-type='s-search-result']")
        for div in results:
            asin = div.get("data-asin")
            if not asin or len(asin) != 10: continue
            
            if "sponsored" in div.get_text().lower() or "スポンサー" in div.get_text().lower():
                continue

            title_node = div.select_one("h2 a span") or div.select_one("h2")
            title = title_node.get_text(strip=True) if title_node else "Hot Wheels Product"
            link = f"https://www.amazon.co.jp/dp/{asin}"

            current_items.append({"asin": asin, "title": title, "link": link})
            
            # 4. Alert if New
            if asin not in memory_asins:
                send_telegram(f"🚨 <b>NEW PRE-ORDER!</b>\n\n{title}\n\n🔗 <a href='{link}'>View on Amazon</a>")
                new_found = True
                time.sleep(2) # Delay for image preview

        # 5. Save Progress
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        send_telegram(f"❌ <b>Error:</b> {str(e)}")

    # 6. End Notification
    if not new_found:
        send_telegram("💤 <b>Scan Complete. No new items.</b>")

if __name__ == "__main__":
    main()
