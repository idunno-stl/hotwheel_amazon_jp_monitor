import requests
import json
import os
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"
# Replace GITHUB_REPO with your 'username/repo-name'
REPO_URL = f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/workflows/monitor.yml"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Adding a 'Check Now' button link at the bottom of every message
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🔄 Check Now (Manual)", "url": REPO_URL},
            {"text": "📂 View Memory", "url": f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/blob/main/{DATA_FILE}"}
        ]]
    }
    payload = {
        "chat_id": CHAT_ID, 
        "text": msg, 
        "parse_mode": "HTML",
        "reply_markup": json.dumps(reply_markup)
    }
    requests.post(url, data=payload, timeout=15)

def main():
    # 1. Create Timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if IS_MANUAL:
        send_telegram(f"🚀 <b>Manual Check Triggered</b>\nTime: <code>{now}</code>\nFiltering top 5...")

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old_asins = {item["asin"] for item in json.load(f)}
    except:
        old_asins = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9"
    }

    time.sleep(random.uniform(2, 5))

    try:
        r = requests.get(AMAZON_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        
        search_results = soup.select("div[data-component-type='s-search-result']")
        for div in search_results:
            if "sponsored" in div.get_text().lower() or "スポンサー" in div.get_text():
                continue

            asin = div.get("data-asin")
            title_elem = div.select_one("h2 a span")
            
            if asin and title_elem:
                current_items.append({
                    "asin": asin,
                    "title": title_elem.get_text(strip=True),
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                })
            
            if len(current_items) >= 5: break

        new_count = 0
        for item in current_items:
            if item["asin"] not in old_asins:
                msg = (
                    f"🚨 <b>NEW HOT WHEELS</b>\n\n"
                    f"{item['title']}\n\n"
                    f"🕒 Detected at: <code>{now}</code>\n"
                    f"🔗 <a href='{item['link']}'>Amazon Link</a>"
                )
                send_telegram(msg)
                new_count += 1

        if IS_MANUAL and new_count == 0:
            send_telegram(f"✅ <b>No changes.</b>\nTop 5 items match the memory.\nCheck Time: <code>{now}</code>")

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ Error at {now}: {e}")

if __name__ == "__main__":
    main()
