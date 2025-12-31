import requests
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MAX_PRICE = 1000 
MIN_PRICE = 100 # Safety floor to ignore "5pt" or "10pt" glitches
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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.co.jp/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

def main():
    timestamp = get_now()
    
    # 1. LOAD MEMORY
    memory_asins = set()
    run_count = 0
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    memory_asins = {item["asin"] for item in data.get("asins", [])}
                    run_count = data.get("run_count", 0)
        except: pass

    # 2. HEARTBEAT
    run_count += 1
    if IS_MANUAL:
        send_telegram(f"🛰️ <b>[{timestamp}] Manual Scan Started...</b>")
    elif run_count >= 9:
        send_telegram(f"🛡️ <b>6-Hour Heartbeat:</b> Hunter is online.")
        run_count = 0

    # 3. FETCH
    try:
        time.sleep(random.randint(5, 12))
        response = requests.get(AMAZON_URL, headers=get_stealth_headers(), timeout=30)
    except Exception as e:
        send_telegram(f"❌ <b>Fetch Error:</b> {str(e)}")
        return

    if response.status_code != 200:
        send_telegram(f"⚠️ <b>BLOCK ALERT:</b> Status {response.status_code}")
        return

    # 4. PARSE & DEEP SCAN
    soup = BeautifulSoup(response.text, "html.parser")
    valid_retail_items = []
    results = soup.find_all("div", {"data-component-type": "s-search-result"})
    
    for div in results:
        # A. Ad Filter (Japanese/English labels)
        if div.get("data-ad-details") or div.select_one(".puis-sponsored-label-text"):
            continue
        ad_text = div.find_all(string=re.compile(r'スポンサー|広告|Sponsored'))
        if ad_text: continue
        
        # B. Keyword Filter
        title_node = div.select_one("h2 a span")
        title = title_node.get_text(strip=True) if title_node else ""
        if not any(k in title.lower() for k in ["hot wheels", "ホットウィール", "hotwheels"]):
            continue

        # C. Point-Proof Price Extraction
        price_val = 99999
        # Check offscreen price first (usually most accurate) then visual whole price
        price_node = div.select_one(".a-price-whole") or div.select_one(".a-offscreen")
        
        if price_node:
            raw_p = price_node.get_text(strip=True).replace(",", "").replace("￥", "").replace("¥", "")
            try:
                price_val = int(re.sub(r'\D', '', raw_p))
            except: pass

        # D. The Price Gate (Only 100 to 1000 Yen)
        if not (MIN_PRICE <= price_val <= MAX_PRICE):
            continue

        asin = div.get("data-asin")
        if not asin: continue
        
        valid_retail_items.append({
            "asin": asin, 
            "title": title, 
            "price": f"¥{price_val}", 
            "link": f"https://www.amazon.co.jp/dp/{asin}"
        })

    # 5. NOTIFY
    new_found = False
    for item in valid_retail_items:
        if item["asin"] not in memory_asins:
            send_telegram(f"🚨 <b>RETAIL FIND @ {get_now()}</b>\n{item['title']}\n💰 <b>Price: {item['price']}</b>\n🔗 <a href='{item['link']}'>Link</a>")
            new_found = True
            memory_asins.add(item["asin"])
            time.sleep(2)

    if not new_found and IS_MANUAL:
        send_telegram(f"💤 <b>[{get_now()}] No new retail items found.</b>")

    # 6. SAVE (Memory Cycling)
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            # We save the top 10 most recent to be safe against restock buried under junk
            json.dump({"asins": valid_retail_items[:10], "run_count": run_count}, f, ensure_ascii=False, indent=2)
    except: pass

if __name__ == "__main__":
    main()
