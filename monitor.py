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
    
    if IS_MANUAL:
        send_telegram("👋 <b>Manual Scan Started...</b>")

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

    # Enhanced Headers to look like a real Chrome browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.amazon.co.jp/",
        "DNT": "1"
    }

    try:
        # Randomized delay
        time.sleep(random.uniform(3, 7))
        
        session = requests.Session()
        r = session.get(AMAZON_URL, headers=headers, timeout=30)
        
        if r.status_code != 200:
            if IS_MANUAL: send_telegram(f"⚠️ Amazon returned Error {r.status_code}. They might be blocking the request.")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        
        # Look for search results
        search_results = soup.select("div[data-component-type='s-search-result']")
        
        for div in search_results:
            if any(x in div.get_text().lower() for x in ["sponsored", "スポンサー"]): continue
            asin = div.get("data-asin")
            title_elem = div.select_one("h2 a span")
            
            if asin and title_elem:
                current_items.append({
                    "asin": asin, 
                    "title": title_elem.get_text(strip=True), 
                    "link": f"https://www.amazon.co.jp/dp/{asin}"
                })
            if len(current_items) >= 5: break

        # 3. VERIFICATION & REPORTING
        if not current_items:
            if IS_MANUAL: send_telegram("❌ <b>Check Failed:</b> Could not find any products. Amazon might be showing a Captcha.")
        else:
            if IS_MANUAL:
                report = f"📋 <b>Current Top 5 on Amazon</b>\nTime: <code>{now}</code>\n\n"
                for i, item in enumerate(current_items, 1):
                    report += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n\n"
                send_telegram(report)
            else:
                # AUTO MODE: Only alert on NEW items
                for item in current_items:
                    if item["asin"] not in memory_asins:
                        send_telegram(f"🚨 <b>NEW!</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")

            # Update Memory only if we actually found items
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(current_items, f, ensure_ascii=False, indent=2)

        if IS_MANUAL:
            send_telegram("💤 <b>Scan Complete.</b> Resuming 15-min auto-checks.")

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ <b>Error:</b> {str(e)}")

if __name__ == "__main__":
    main()
