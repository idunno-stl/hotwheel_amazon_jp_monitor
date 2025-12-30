import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ================= CONFIG =================
AMAZON_URL = "https://www.amazon.co.jp/s?k=hotwheels+%E3%83%9B%E3%83%83%E3%83%88%E3%82%A6%E3%82%A3%E3%83%BC%E3%83%AB+%E4%BA%88%E7%B4%84&s=date-desc-rank"
DATA_FILE = "latest_seen.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IS_MANUAL = os.getenv("IS_MANUAL") == "true"
PROXY_URL = os.getenv("GOOGLE_PROXY_URL")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, data=payload, timeout=15)

def main():
    now = datetime.now().strftime("%H:%M")
    
    if IS_MANUAL:
        send_telegram("🚀 <b>Google Proxy Scan Started...</b>")

    # 1. Load Memory
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump([], f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try: memory_asins = {item["asin"] for item in json.load(f)}
        except: memory_asins = set()

    # 2. Fetch via Google Proxy
    try:
        # We send the Amazon URL as a parameter to our Google Script
        r = requests.get(PROXY_URL, params={'url': AMAZON_URL}, timeout=60)
        
        if r.status_code != 200:
            if IS_MANUAL: send_telegram(f"❌ Proxy Error: {r.status_code}")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        current_items = []
        results = soup.select("div[data-component-type='s-search-result']")
        
        for div in results:
            if any(x in div.get_text().lower() for x in ["sponsored", "スポンサー"]): continue
            asin = div.get("data-asin")
            title = div.select_one("h2 a span")
            if asin and title:
                current_items.append({"asin": asin, "title": title.get_text(strip=True), "link": f"https://www.amazon.co.jp/dp/{asin}"})
            if len(current_items) >= 5: break

        if not current_items:
            if IS_MANUAL: send_telegram("❌ Proxy worked, but no items found on page.")
            return

        # 3. Logic
        if IS_MANUAL:
            report = f"📋 <b>Current Top 5 (Via Google)</b>\n\n"
            for i, item in enumerate(current_items, 1):
                report += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n\n"
            send_telegram(report)
        else:
            for item in current_items:
                if item["asin"] not in memory_asins:
                    send_telegram(f"🚨 <b>NEW!</b>\n{item['title']}\n🔗 <a href='{item['link']}'>Link</a>")

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_items, f, ensure_ascii=False, indent=2)

    except Exception as e:
        if IS_MANUAL: send_telegram(f"❌ <b>Error:</b> {str(e)}")

    if IS_MANUAL:
        send_telegram("💤 <b>Scan Complete.</b> Resuming 15-min checks.")

if __name__ == "__main__":
    main()
