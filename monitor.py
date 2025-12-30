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

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, data=payload, timeout=15)

def main():
    now = datetime.now().strftime("%H:%M")
    
    # 1. WELCOME MESSAGE (Manual Only)
    if IS_MANUAL:
        send_telegram("👋 <b>Welcome back!</b>\nStarting manual scan of Amazon Japan now...")

    # Load Memory
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
        memory_asins = set()
    else:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
                memory_asins = {item["asin"] for item in memory_data}
            except:
                memory_asins = set()

    # 2. FETCH FROM AMAZON
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "ja-JP"}
    try:
        # Small delay for authenticity
        if IS_MANUAL: time.sleep(2) 
        
        r = requests.get(AMAZON_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        search_results = soup.select("div[data-component-type='s-search-result']")
        
        for div in search_results:
            if any(x in div.get_text().lower() for x in ["sponsored", "スポンサー"]): continue
            asin, title_elem = div.get("data-asin"), div.select_one("h2 a span")
            if asin and title_elem:
                current_items.append({"asin": asin, "title": title_elem.get_text(strip=True), "link": f"https://www.amazon.co.jp/dp/{asin}"})
            if len(current_items) >= 5: break

        # 3. REPORTING
        if IS_MANUAL:
            report = f"📋 <b>Current Top 5 on Amazon</b>\nTime: <code>{now}</code>\n\n"
            for i, item in enumerate(current_items, 1):
                report += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n\n"
            send_telegram(report)
            
            # THE SLEEP MESSAGE
            send_telegram("💤 <b>Scan Complete.</b>\nGoing into sleep mode. I will continue checking every 15 minutes automatically.")
        
        else:
            # AUTOMATIC RUN: Only send if a NEW ASIN is found
            for item in current_items:
                if item["asin"] not in memory_asins:
                    alert = f"🚨 <b>NEW PRE-ORDER DETECTED!</b>\n\n{item['title']}\n🔗 <a href='{item['link']}'>Buy Now</a>"
                    send_telegram(alert)

        # 4. SAVE TO MEMORY
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ Error during manual scan: {e}")

if __name__ == "__main__":
    main()
