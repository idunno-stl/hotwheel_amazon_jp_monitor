import requests
import json
import os
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
BASE_URL = "https://www.amazon.co.jp/s?k=%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+car+culture&i=toys&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MAX_PRICE = 1000 
IS_MANUAL = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def get_human_headers():
    # Rotating User Agents to help avoid 503 errors
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(uas),
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

def scrape_page(url):
    items = {}
    try:
        session = requests.Session()
        time.sleep(random.uniform(2.0, 5.0)) # Longer delay to avoid 503
        res = session.get(url, headers=get_human_headers(), timeout=30)
        
        if res.status_code == 503:
            print("Status 503: Amazon is throttling this IP.")
            return None # Return None to signal a block
            
        if res.status_code != 200:
            return items
        
        soup = BeautifulSoup(res.text, "html.parser")
        results = soup.select(".s-result-item[data-asin]")
        
        for div in results:
            asin = div.get("data-asin")
            if not asin or len(asin) < 5: continue
            if "Sponsored" in div.text: continue

            price_val = 99999
            p_node = div.select_one(".a-price-whole") or div.select_one(".a-offscreen")
            if p_node:
                raw_p = p_node.get_text(strip=True).replace(",", "")
                digits = "".join(filter(str.isdigit, raw_p))
                if digits: price_val = int(digits)

            t_node = div.select_one("h2")
            title = t_node.get_text(strip=True) if t_node else "Hot Wheels"

            items[asin] = {"title": title[:100], "price": price_val, "link": f"https://www.amazon.co.jp/dp/{asin}"}
    except Exception as e:
        print(f"Scrape error: {e}")
    return items

def main():
    # 1. LOAD DATABASE Safely
    db = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict): db = content
        except: db = {}

    # 2. SCANNING
    scanned_items = {}
    if IS_MANUAL and (not db or len(db) < 5):
        send_telegram("🛰️ <b>Deep Scan Started...</b>")
        p1 = scrape_page(BASE_URL + "&page=1")
        if p1 is None: return # Stop if blocked
        scanned_items.update(p1)
        
        time.sleep(random.randint(5, 10))
        
        p2 = scrape_page(BASE_URL + "&page=2")
        if p2 is not None: scanned_items.update(p2)
        
        send_telegram(f"✅ Cached {len(scanned_items)} items.")
    else:
        res = scrape_page(BASE_URL + "&page=1")
        if res is None: return # Stop if blocked
        scanned_items = res

    # 3. COMPARE & NOTIFY
    for asin, info in scanned_items.items():
        new_p = info["price"]
        old_p = db.get(asin, {}).get("price", 99999)
        
        if new_p <= MAX_PRICE:
            if asin not in db or old_p > MAX_PRICE:
                send_telegram(f"🚨 <b>RETAIL FIND</b>\n{info['title']}\n💰 <b>Price: ¥{new_p}</b>\n🔗 <a href='{info['link']}'>Link</a>")

    # 4. SYNC & SAVE Safely
    db.update(scanned_items)
    if len(db) > 300:
        db = dict(list(db.items())[-300:])
        
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
