# ... (Imports and Headers stay the same) ...

def main():
    # 1. LOAD MEMORY
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump({"asins": [], "run_count": 0}, f)
    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
            # Store ASINs in a set for lightning-fast lookup
            memory_asins = {item["asin"] for item in data.get("asins", [])}
            run_count = data.get("run_count", 0)
        except:
            memory_asins, run_count = set(), 0

    # ... (Heartbeat and Fetch logic stay the same) ...

    # 4. PARSE & DEEP FILTER
    soup = BeautifulSoup(response.text, "html.parser")
    valid_retail_items = []
    results = soup.select("div[data-component-type='s-search-result']")
    
    for div in results:
        # A. Filter "Promo Shit"
        if div.get("data-ad-details") or div.select_one(".puis-sponsored-label-text"):
            continue
        
        # B. Filter Unrelated (Keyword Check)
        title_node = div.select_one("h2 a span") or div.select_one("h2")
        title = title_node.get_text(strip=True) if title_node else ""
        if not any(k in title.lower() for k in ["hot wheels", "ホットウィール", "hotwheels"]):
            continue

        # C. Price Check (Retail Only)
        price_val = 99999 
        price_node = div.select_one(".a-price-whole")
        if price_node:
            try:
                price_val = int(re.sub(r'\D', '', price_node.get_text()))
            except: pass

        if price_val > MAX_PRICE:
            continue

        asin = div.get("data-asin")
        if not asin: continue
        
        # If we made it here, it's a real Hot Wheels car at a retail price
        valid_retail_items.append({
            "asin": asin, 
            "title": title, 
            "price": f"¥{price_val}", 
            "link": f"https://www.amazon.co.jp/dp/{asin}"
        })

    # 5. NOTIFY & MEMORY UPDATE
    # Even if the restock is at the bottom of the page, it's now in valid_retail_items
    new_found = False
    for item in valid_retail_items:
        if item["asin"] not in memory_asins:
            send_telegram(f"🚨 <b>RETAIL FIND @ {get_now()}</b>\n{item['title']}\n💰 <b>Price: {item['price']}</b>\n🔗 <a href='{item['link']}'>Link</a>")
            new_found = True
            # Add to temporary memory so we don't double-ping in one run
            memory_asins.add(item["asin"])
            time.sleep(2)

    if not new_found and IS_MANUAL:
        send_telegram(f"💤 <b>[{get_now()}] No new retail items on page 1.</b>")

    # 6. SAVE (Only keep the Top 5 most recent to keep the file tidy)
    # This ensures that if a restocked item is old, it eventually leaves memory 
    # so you can be alerted again in the future if it restocks again.
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"asins": valid_retail_items[:5], "run_count": run_count}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
