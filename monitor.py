import requests
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
# Simplified clean URL to reduce bot detection
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

def get_human_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

def scrape_page(url):
    items = {}
    try:
        # Using a session to handle cookies like a real browser
        session = requests.Session()
        res = session.get(url, headers=get_human_headers(), timeout=30)
        
        if res.status_code != 200:
            print(f"Status Error: {res.status_code}")
            return items
        
        soup = BeautifulSoup(res.text, "html.parser")
        # Broaden search to find all result cards
        results = soup.select(".s-result-item[data-asin]")
        
        for div in results:
            asin = div.get("data-asin")
            if not asin or len(asin) < 5: continue
            
            # 1. THE NO PROMO SHIELD
            if div.select_one(".puis-sponsored-label-text") or "Sponsored" in div.text:
                continue

            # 2. TITLE
            title = ""
            t_node = div.select_one("h2 a span") or div.select_one("h2")
            if t_node:
                title = t_node.get_text(strip=True)

            # 3. PRICE (Looking deeper into multiple spans)
            price_val = 99999
            # Amazon Japan price logic
            price_span = div.select_one(".a-price-whole")
            if price_span:
                price_text = price_span.get_text(strip=True).replace(",", "").replace("￥", "").replace("¥", "")
                digits = re.sub(r'\D', '', price_text)
                if digits: price_val = int(digits)
            elif div.select_one(".a-offscreen"):
                price_text = div.select_one(".a-offscreen").get_text(strip=True).replace(",", "").replace("￥", "").replace("¥", "")
                digits = re.sub(r'\D', '', price_text)
                if digits: price_val = int(digits)

            # 4. FILTER (Save if it has a title)
            if title:
                items[asin] = {
                    "title": title[:100], 
                    "price": price_val, 
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                }
    except Exception as e:
        print(f"Scrape error: {e}")
    return items

def main():
    db = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except: db = {}

    scanned_items = {}
    # Build database
    if IS_MANUAL and (not db or len(db) < 5):
        send_telegram("🛰️ <b>Deep Scan Started...</b>")
        scanned_items.update(scrape_page(BASE_URL + "&page=1"))
        time.sleep(random.randint(5, 10)) # Human-like pause
        scanned_items.update(scrape_page(BASE_URL + "&page=2"))
        
        if len(scanned_items) < 5:
            send_telegram(f"⚠️ <b>Alert:</b> Only found {len(scanned_items)} items. Amazon is likely throttling.")
        else:
            send_telegram(f"✅ Cached {len(scanned_items)} items.")
    else:
        scanned_items = scrape_page(BASE_URL + "&page=1")

    # ALERTS
    for asin, info in scanned_items.items():
        new_p = info["price"]
        old_p = db.get(asin, {}).get("price", 99999)
        
        # We notify if: 
        # - It's a new ASIN under retail price
        # - It's an old ASIN that just dropped from high/unknown price to retail
        if new_p <= MAX_PRICE:
            if asin not in db or old_p > MAX_PRICE:
                send_telegram(f"🚨 <b>RETAIL FIND</b>\n{info['title']}\n💰 <b>Price: ¥{new_p}</b>\n🔗 <a href='{info['link']}'>Link</a>")

    db.update(scanned_items)
    if len(db) > 300:
        db = dict(list(db.items())[-300:])
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
