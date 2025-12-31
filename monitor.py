import requests
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
BASE_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MAX_PRICE = 1000 
IS_MANUAL = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def scrape_page(url):
    items = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9"
    }
    try:
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200: return items
        soup = BeautifulSoup(res.text, "html.parser")
        results = soup.find_all("div", {"data-component-type": "s-search-result"})
        
        for div in results:
            # --- 1. THE "NO PROMO" SHIELD ---
            # Checks for data attributes, CSS classes, and hidden text labels
            is_ad = div.get("data-ad-details") or \
                    div.select_one(".puis-sponsored-label-text") or \
                    div.find(string=re.compile(r'スポンサー|広告|Sponsored'))
            if is_ad: continue

            asin = div.get("data-asin")
            if not asin: continue
            
            # --- 2. THE PRICE CAPTURE ---
            price_val = 99999
            # Priority 1: Clean offscreen text, Priority 2: Visual whole price
            p_node = div.select_one(".a-offscreen") or div.select_one(".a-price-whole")
            if p_node:
                try: 
                    digits = re.sub(r'\D', '', p_node.get_text())
                    price_val = int(digits) if digits else 99999
                except: pass
            
            # --- 3. KEYWORD FILTER ---
            t_node = div.select_one("h2")
            title = t_node.get_text(strip=True) if t_node else ""
            if any(k in title.lower() for k in ["hot", "wheels", "ホットウィール"]):
                items[asin] = {
                    "title": title[:70], 
                    "price": price_val, 
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                }
    except: pass
    return items

def main():
    # 1. LOAD MASTER DATABASE
    db = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except: pass

    # 2. SCAN STRATEGY
    scanned_items = {}
    if IS_MANUAL and len(db) < 5:
        send_telegram("🛰️ <b>Building Master Database (Pages 1-2)...</b>")
        scanned_items.update(scrape_page(BASE_URL + "&page=1"))
        time.sleep(random.randint(4, 7)) 
        scanned_items.update(scrape_page(BASE_URL + "&page=2"))
        send_telegram(f"✅ Database cached {len(scanned_items)} items. Now monitoring for drops.")
    else:
        # Standard automated run
        scanned_items = scrape_page(BASE_URL + "&page=1")

    # 3. COMPARE LOGIC
    for asin, info in scanned_items.items():
        new_p = info["price"]
        # If item is new to DB, old_p defaults to a high number to trigger if it's retail
        old_p = db.get(asin, {}).get("price", 99999)
        
        # Trigger if:
        # A) It's an ASIN we've never seen before AND it's retail
        # B) It's an ASIN we knew was expensive, but now it's retail (Drop/Restock)
        is_new = asin not in db
        is_drop = (old_p > MAX_PRICE and new_p <= MAX_PRICE)
        
        if (is_new or is_drop) and (new_p <= MAX_PRICE):
            alert_type = "🚨 <b>NEW RETAIL ITEM</b>" if is_new else "📉 <b>PRICE DROP / RESTOCK</b>"
            send_telegram(f"{alert_type}\n{info['title']}\n💰 <b>Price: ¥{new_p}</b>\n🔗 <a href='{info['link']}'>Link</a>")

    # 4. SYNC & CLEANUP
    db.update(scanned_items)
    # Maintain a lean DB of the most recent 150 items
    if len(db) > 150:
        db = dict(list(db.items())[-150:])
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
