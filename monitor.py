import requests
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
# Updated to your specific Car Culture search (Newest Arrivals)
BASE_URL = "https://www.amazon.co.jp/-/en/s?k=%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+car+culture&i=toys&s=date-desc-rank"
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
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8"
    }
    try:
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200: return items
        
        soup = BeautifulSoup(res.text, "html.parser")
        results = soup.select("div[data-component-type='s-search-result']")
        
        for div in results:
            # 1. NO PROMO SHIELD (English & Japanese)
            is_ad = div.find(string=re.compile(r'スポンサー|広告|Sponsored|AD', re.I))
            if is_ad: continue

            asin = div.get("data-asin")
            if not asin: continue
            
            # 2. TITLE & KEYWORD CHECK
            t_node = div.select_one("h2")
            title = t_node.get_text(strip=True) if t_node else ""
            # Car Culture check included
            if not any(k in title.lower() for k in ["hot", "wheel", "ホット", "ウィール", "culture"]):
                continue

            # 3. PRICE CAPTURE
            price_val = 99999
            p_node = div.select_one(".a-offscreen") or div.select_one(".a-price-whole")
            if p_node:
                digits = re.sub(r'\D', '', p_node.get_text())
                if digits: price_val = int(digits)
            
            items[asin] = {
                "title": title[:75], 
                "price": price_val, 
                "link": f"https://www.amazon.co.jp/dp/{asin}"
            }
    except Exception: pass
    return items

def main():
    db = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except: db = {}

    scanned_items = {}
    # Build database on manual run if empty
    if IS_MANUAL and (not db or len(db) < 5):
        send_telegram("🏎️ <b>Building Car Culture Database...</b> (Pages 1-2)")
        scanned_items.update(scrape_page(BASE_URL + "&page=1"))
        time.sleep(5)
        scanned_items.update(scrape_page(BASE_URL + "&page=2"))
        send_telegram(f"✅ Cached {len(scanned_items)} items. Watching for retail prices!")
    else:
        scanned_items = scrape_page(BASE_URL + "&page=1")

    for asin, info in scanned_items.items():
        new_p = info["price"]
        old_p = db.get(asin, {}).get("price", 99999)
        
        is_new = asin not in db
        is_drop = (old_p > MAX_PRICE and new_p <= MAX_PRICE)
        
        if (is_new or is_drop) and (new_p <= MAX_PRICE):
            tag = "🚨 <b>NEW CAR CULTURE</b>" if is_new else "📉 <b>RETAIL DROP</b>"
            send_telegram(f"{tag}\n{info['title']}\n💰 <b>Price: ¥{new_p}</b>\n🔗 <a href='{info['link']}'>Link</a>")

    db.update(scanned_items)
    if len(db) > 200:
        db = dict(list(db.items())[-200:])
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
