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
MIN_PRICE = 100 
IS_MANUAL = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"

def get_now():
    return datetime.now().strftime("%H:%M:%S")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try: requests.post(url, data=payload, timeout=15)
    except: pass

def get_stealth_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.co.jp/"
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
                memory_asins = {item["asin"] for item in data.get("asins", [])}
                run_count = data.get("run_count", 0)
        except: pass

    # 2. HEARTBEAT
    run_count += 1
    if IS_MANUAL:
        send_telegram(f"🛰️ <b>[{timestamp}] Manual Scan Started...</b>")

    # 3. FETCH
    try:
        response = requests.get(AMAZON_URL, headers=get_stealth_headers(), timeout=30)
    except Exception as e:
        send_telegram(f"❌ Error: {str(e)}")
        return

    # 4. PARSE (Wider Net)
    soup = BeautifulSoup(response.text, "html.parser")
    valid_retail_items = []
    # Look for ALL result items
    results = soup.find_all("div", {"data-component-type": "s-search-result"})
    
    for div in results:
        # A. AD CHECK (Slightly more relaxed)
        if div.get("data-ad-details"): continue
        
        # B. KEYWORD CHECK (Broadened)
        title_node = div.select_one("h2")
        title = title_node.get_text(strip=True) if title_node else ""
        if not any(k in title.lower() for k in ["hot", "wheels", "ホットウィール"]):
            continue

        # C. PRICE EXTRACTION (Find ANY price on the card)
        price_val = 0
        price_text = div.get_text()
        # Look for "¥" or "￥" followed by numbers
        found_prices = re.findall(r'[¥￥](\d{1,3}(?:,\d{3})*)', price_text)
        
        if found_prices:
            # Take the first price found and clean it
            price_val = int(found_prices[0].replace(",", ""))
        else:
            # Fallback to standard classes if regex fails
            p_node = div.select_one(".a-price-whole")
            if p_node:
                price_val = int(re.sub(r'\D', '', p_node.get_text()))

        # D. FILTER
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
        # Force send everything on Manual run to see what the bot is seeing
        if IS_MANUAL or (item["asin"] not in memory_asins):
            send_telegram(f"🚨 <b>MATCH FOUND</b>\n{item['title']}\n💰 <b>Price: {item['price']}</b>\n🔗 <a href='{item['link']}'>Link</a>")
            new_found = True
            memory_asins.add(item["asin"])

    if not new_found and IS_MANUAL:
        send_telegram(f"💤 <b>No matches.</b> Prices found were likely too high or text didn't match.")

    # 6. SAVE
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"asins": valid_retail_items[:10], "run_count": run_count}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
