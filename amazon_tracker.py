import os
import csv
import random
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

# ─────────── CONFIG ───────────
PRODUCTS = [
    {
        "name": "karcher k2",
        "url":  "https://www.amazon.com.mx/gp/product/B0CM49Z6SN/ref=ox_sc_act_title_14?smid=AVDBXBAVVSXLQ&psc=1",
        "threshold": 2000.00
    },
    {
        "name": "Pulidora Orbital Trupper",
        "url":  "https://www.amazon.com.mx/gp/product/B0BNW5RQN6/ref=ox_sc_act_title_15?smid=AVDBXBAVVSXLQ&psc=1",
        "threshold": 1900.00
    },
    # …add more products here
]

# Where to store your logs & history
BASE_DIR     = "/tmp"  # change this to a persistent folder if running locally, e.g. r"C:\Users\usuario\…"
CSV_FILE     = os.path.join(BASE_DIR, "AmazonProductsPriceDataset.csv")
HISTORY_FILE = os.path.join(BASE_DIR, "AmazonLastPrices.csv")

# Twilio WhatsApp client (populated from GitHub Actions secrets or your local env vars)
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

def send_whatsapp(title, price):
    body = f"{title}\nPrecio: ${price:.2f} MXN"
    client.messages.create(
        body=body,
        from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_FROM')}",
        to=f"whatsapp:{os.getenv('WHATSAPP_TO')}"
    )

def fetch_price(name, url):
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    ]).encode('latin-1','ignore').decode('latin-1')
    headers = {"User-Agent": ua, "Accept-Language":"es-MX,es;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=(5,15))
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_el = soup.find(id="productTitle")
    title = title_el.get_text(strip=True) if title_el else name

    # Price selectors
    price_str = None
    for sel in ("#priceblock_ourprice","#priceblock_dealprice","#priceblock_saleprice"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            price_str = el.get_text(strip=True)
            break
    # Fallbacks
    if not price_str:
        m = soup.find("meta",{"itemprop":"price"})
        price_str = m["content"] if m and m.get("content") else None
    if not price_str:
        off = soup.find("span",class_="a-offscreen")
        price_str = off.get_text(strip=True) if off else None
    if not price_str:
        w = soup.select_one("span.a-price-whole")
        f = soup.select_one("span.a-price-fraction")
        if w and f:
            price_str = f"{w.get_text(strip=True)}.{f.get_text(strip=True)}"

    if not price_str:
        return title, None

    cleaned = (price_str
               .replace("MX$","")
               .replace("MXN","")
               .replace("$","")
               .replace(",","")
               .replace("\xa0","")
               .strip())
    try:
        return title, float(cleaned)
    except ValueError:
        return title, None

def append_csv(record):
    os.makedirs(BASE_DIR, exist_ok=True)
    exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE,"a",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=["timestamp","name","url","price"])
        if not exists: w.writeheader()
        w.writerow(record)

def load_last_prices():
    last = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE,newline="",encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    last[row["name"]] = float(row["price"])
                except:
                    pass
    return last

def save_last_prices(prices):
    with open(HISTORY_FILE,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=["name","price"])
        w.writeheader()
        for name, price in prices.items():
            w.writerow({"name": name, "price": price})

def main():
    # ensure BASE_DIR exists
    os.makedirs(BASE_DIR, exist_ok=True)

    # load last run prices
    last_seen = load_last_prices()
    new_seen  = {}

    for p in PRODUCTS:
        title, price = None, None
        try:
            title, price = fetch_price(p["name"], p["url"])
        except Exception as e:
            print(f"✖ Error fetching {p['name']}: {e}")
            continue

        now = datetime.utcnow().isoformat()
        append_csv({"timestamp": now, "name": title, "url": p["url"], "price": price})
        print(f"{now} | {title[:30]:30} | ${price}")

        prev = last_seen.get(title)
        # if we’ve seen it before and price changed:
        if price is not None and prev is not None and price != prev:
            diff      = price - prev
            direction = "⬆️" if diff > 0 else "⬇️"
            print(f"Price changed ({direction}{abs(diff):.2f}) → sending alert")
            send_whatsapp(f"{direction} {title}", price)

        # first time we ever see it:
        elif price is not None and prev is None:
            print("First check for this item → sending initial alert")
            send_whatsapp(f"✔️ {title}", price)

        new_seen[title] = price
        time.sleep(random.uniform(5,10))

    # save for next run
    save_last_prices(new_seen)

if __name__ == "__main__":
    main()
