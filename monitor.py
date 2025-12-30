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

def get_amazon_items():
    # A list of real User-Agents to rotate
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    for attempt in range(3): # Try 3 times
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Referer": "https://www.google.co.jp/", # Pretend we came from Google
            "Device-Memory": "8",
        }
        
        try:
            time.sleep(random.uniform(5, 10)) # Longer wait between retries
            r = requests.get(AMAZON_URL, headers=headers, timeout=30)
            
            if "api-services-support@amazon.com" in r.text or "not a robot" in r.text:
                print(f"Attempt {attempt+1}: Blocked by Captcha")
                continue # Try again

            soup = BeautifulSoup(r.text, "html.parser")
            items = []
            results = soup.select("div[data-component-type='s-search-result']")
            
            for div in results:
                if any(x in div.get_text().lower() for x in ["sponsored", "スポンサー"]): continue
                asin = div.get("data-asin")
                title = div.select_one("h2 a span")
                if asin and title:
                    items.append({"asin": asin, "title": title.get_text(strip=True), "link": f"https://www.amazon.co.jp/dp/{asin}"})
                if len(items) >= 5: break
            
            if items: return items # Success!
            
        except Exception as e:
            print(f"Error on attempt {attempt}: {e}")
            
    return []

def main():
    if IS_MANUAL:
        send_telegram("👋 <b>Manual Scan Started...</b>\n<i>(Trying to bypass Amazon security...)</i>")

    # Load Memory
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    # 2. Get Items
    current_items = get_amazon_items()

    # 3. Handle Results
    if not current_items:
        if IS_MANUAL: send_telegram("❌ <b>All 3 attempts failed.</b> Amazon is being very tough today. We might need a proxy.")
    else:
        if IS_MANUAL:
            report = f"📋 <b>Current Top 5 on Amazon</b>\n\n"
            for i, item in enumerate(current_items, 1):
                report += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n\n"
            send_telegram(report)
        else:
            for item in current_items:
                if item["asin"] not in memory_asins:
                    send_telegram(f"🚨 <b>NEW!</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")

        # Save only if successful
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    if IS_MANUAL:
        send_telegram("💤 <b>Scan Complete.</b> Resuming 15-min auto-checks.")

if __name__ == "__main__":
    main()
