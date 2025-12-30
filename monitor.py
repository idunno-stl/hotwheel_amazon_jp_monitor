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
    return datetime.now().strftime("%H:%M:%S")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def main():
    timestamp = get_now()
    
    # Load Memory
    if not os.path.exists(DATA_FILE):
        # Added 'run_count' to track the 6-hour heartbeat
        with open(DATA_FILE, "w") as f: json.dump({"asins": [], "run_count": 0}, f)
    
    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
            memory_asins = {item["asin"] for item in data.get("asins", [])}
            run_count = data.get("run_count", 0)
        except:
            memory_asins = set()
            run_count = 0

    # Requirement: Heartbeat Logic (Once every 9 runs = 6 hours at 40-min intervals)
    run_count += 1
    if IS_MANUAL:
        send_telegram(f"🛰️ <b>[{timestamp}] Manual Scan Started...</b>")
    elif run_count >= 9:
        send_telegram(f"🛡️ <b>6-Hour Heartbeat:</b> Bot is online. No blocks detected.")
        run_count = 0 # Reset counter

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9"
    }

    try:
        response = requests.get(AMAZON_URL, headers=headers, timeout=30)
        
        # Requirement 4: Alert if blocked (This ALWAYS pings you)
        if response.status_code != 200:
            send_telegram(f"⚠️ <b>[{timestamp}] BLOCK ALERT:</b> Status {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        valid_real_items = []

        # 1. Filter Promo Shit
        results = soup.select("div[data-component-type='s-search-result']")
        for div in results:
            if div.get("data-ad-details") or div.get("data-ad-type") or div.select_one(".puis-sponsored-label-text"):
                continue
            div_text = div.get_text().lower()
            if any(p in div_text for p in ["sponsored", "スポンサー", "featured", "ad", "広告"]):
                continue

            asin = div.get("data-asin")
            if not asin or len(asin) != 10: continue
            
            title_node = div.select_one("h2 a span") or div.select_one("h2")
            title = title_node.get_text(strip=True) if title_node else "Hot Wheels"
            link = f"https://www.amazon.co.jp/dp/{asin}"
            valid_real_items.append({"asin": asin, "title": title, "link": link})

        # 2. Slice Top 5 & Check for New Items
        top_5_real = valid_real_items[:5]
        new_items_found = False

        for item in top_5_real:
            if item["asin"] not in memory_asins:
                send_telegram(f"🚨 <b>NEW @ {get_now()}</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")
                new_items_found = True
                time.sleep(2)

        if not new_items_found and IS_MANUAL:
            send_telegram(f"💤 <b>[{get_now()}] No new items.</b> Entering sleep mode.")

        # 3. Save Data (Including the run_count)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"asins": top_5_real, "run_count": run_count}, f, ensure_ascii=False, indent=2)

    except Exception as e:
        send_telegram(f"❌ <b>[{timestamp}] Error:</b> {str(e)}")

if __name__ == "__main__":
    main()
