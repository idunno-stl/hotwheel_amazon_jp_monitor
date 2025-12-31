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
IS_MANUAL = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

def get_now():
    return datetime.now().strftime("%H:%M:%S")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def get_stealth_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.co.jp/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Cookie": f"session-id={random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}"
    }

def main():
    timestamp = get_now()
    
    # 1. LOAD MEMORY
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump({"asins": [], "run_count": 0}, f)
    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
            # Handle legacy list format or new dict format
            if isinstance(data, list):
                memory_asins = {item["asin"] for item in data}
                run_count = 0
            else:
                memory_asins = {item["asin"] for item in data.get("asins", [])}
                run_count = data.get("run_count", 0)
        except:
            memory_asins, run_count = set(), 0

    # 2. HEARTBEAT & MANUAL STATUS
    run_count += 1
    if IS_MANUAL:
        send_telegram(f"🛰️ <b>[{timestamp}] Manual Scan Started...</b>")
    elif run_count >= 9: # 9 runs * 40 mins = 6 hours
        send_telegram(f"🛡️ <b>6-Hour Heartbeat:</b> Bot is online.")
        run_count = 0

    # 3. STEALTH FETCH WITH RETRY
    response = None
    for attempt in range(2):
        try:
            time.sleep(random.randint(5, 15)) # Anti-detection jitter
            response = requests.get(AMAZON_URL, headers=get_stealth_headers(), timeout=30)
            if response.status_code == 200: break
            time.sleep(20) # Cool down before retry
        except: continue

    if not response or response.status_code != 200:
        status = response.status_code if response else "Timeout"
        send_telegram(f"⚠️ <b>[{timestamp}] BLOCK ALERT:</b> Status {status}")
        return

    # 4. PARSE & AGGRESSIVE FILTERING
    soup = BeautifulSoup(response.text, "html.parser")
    valid_real_items = []
    results = soup.select("div[data-component-type='s-search-result']")
    
    for div in results:
        # A. Filter "Promo Shit" (Ads/Sponsored)
        if div.get("data-ad-details") or div.get("data-ad-type") or div.select_one(".puis-sponsored-label-text"):
            continue
        
        # B. Filter Unrelated Items (Must be Hot Wheels)
        title_node = div.select_one("h2 a span") or div.select_one("h2")
        title = title_node.get_text(strip=True) if title_node else ""
        if not any(k in title.lower() for k in ["hot wheels", "ホットウィール", "hotwheels"]):
            continue

        asin = div.get("data-asin")
        if not asin or len(asin) != 10: continue
        
        link = f"https://www.amazon.co.jp/dp/{asin}"
        valid_real_items.append({"asin": asin, "title": title, "link": link})

    # 5. TOP 5 LOGIC & NOTIFICATION
    top_5_real = valid_real_items[:5]
    new_found = False
    
    for item in top_5_real:
        if item["asin"] not in memory_asins:
            send_telegram(f"🚨 <b>NEW @ {get_now()}</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")
            new_found = True
            memory_asins.add(item["asin"]) # Prevent repeats in same run
            time.sleep(2)

    if not new_found and IS_MANUAL:
        send_telegram(f"💤 <b>[{get_now()}] No new items.</b>")

    # 6. SAVE MEMORY (Ensures top 5 are saved even if not new)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"asins": top_5_real, "run_count": run_count}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
