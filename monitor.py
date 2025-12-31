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
        if res.status_code != 200: 
            print(f"Failed to load page: {res.status_code}")
            return items
            
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Look for the main result containers (Handles both Grid and List views)
        results = soup.select("div[data-component-type='s-search-result']")
        
        for div in results:
            # --- 1. THE NO PROMO SHIELD ---
            # We look for the 'Sponsored' text specifically
            is_ad = div.find(string=re.compile(r'スポンサー|広告|Sponsored'))
            if is_ad: continue

            asin = div.get("data-asin")
            if not asin: continue
            
            # --- 2. THE TITLE (The 'Key' to saving) ---
            t_node = div.select_one("h2")
            title = t_node.get_text(strip=True) if t_node else ""
            
            # Check if it's actually a car (Very relaxed check)
            if not any(k in title.lower() for k in ["hot", "wheel", "ホット", "ウィール", "車"]):
                continue

            # --- 3. THE PRICE ---
            price_val = 99999
            # Amazon often hides the price in 'a-offscreen' for bots
            p_node = div.select_one(".a-offscreen") or div.select_one(".a-price-whole")
            if p_node:
                digits = re.sub(r'\D', '', p_node.get_text())
                if digits: price_val = int(digits)
            
            items[asin] = {
                "title": title[:70], 
                "price": price_val, 
                "link": f"https://www.amazon.co.jp/dp/{asin}"
            }
    except Exception as e:
        print(f"Scrape Error: {e}")
    return items

def main():
    # 1. LOAD DB
    db = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except: db = {}

    # 2. RUN SCAN
    scanned_items = {}
    if IS_MANUAL and (not db or len(db) < 5):
        send_telegram("🛰️ <b>Building Database...</b> Scanning Page 1 & 2.")
        scanned_items.update(scrape_page(BASE_URL + "&page=1"))
        time.sleep(5)
        scanned_items.update(scrape_page(BASE_URL + "&page=2"))
        
        if not scanned_items:
            send_telegram("⚠️ <b>Debug:</b> No items found. Is Amazon showing a Captcha?")
        else:
            send_telegram(f"✅ Cached {len(scanned_items)} items to database.")
    else:
        # Automated run: Scan page 1 only
        scanned_items = scrape_page(BASE_URL + "&page=1")

    # 3. COMPARE & NOTIFY
    for asin, info in scanned_items.items():
        new_p = info["price"]
        # If ASIN exists in DB, get its old price. If not, default to 99999
        old_p = db.get(asin, {}).get("price", 99999)
        
        is_new = asin not in db
        is_drop = (old_p > MAX_PRICE and new_p <= MAX_PRICE)
        
        if (is_new or is_drop) and (new_p <= MAX_PRICE):
            label = "🚨 <b>NEW</b>" if is_new else "📉 <b>RETAIL DROP</b>"
            send_telegram(f"{label}\n{info['title']}\n💰 <b>Price: ¥{new_p}</b>\n🔗 <a href='{info['link']}'>Link</a>")

    # 4. SYNC
    db.update(scanned_items)
    
    # Keep the most recent 200 items so the file doesn't grow forever
    if len(db) > 200:
        db = dict(list(db.items())[-200:])
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
