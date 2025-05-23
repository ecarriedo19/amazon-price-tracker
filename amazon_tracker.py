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
    },
    {
        "name": "Pulidora Orbital Trupper",
        "url":  "https://www.amazon.com.mx/gp/product/B0BNW5RQN6/ref=ox_sc_act_title_15?smid=AVDBXBAVVSXLQ&psc=1",
    },
    # …add more here
]

# ─────────── STORAGE PATHS ───────────
BASE_DIR     = os.getcwd()  # repo root
CSV_FILE     = os.path.join(BASE_DIR, "AmazonProductsPriceDataset.csv")
HISTORY_FILE = os.path.join(BASE_DIR, "AmazonLastPrices.csv")

# ─────────── TWILIO CLIENT ───────────
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

def send_whatsapp(title, price, prev_price):
    body = f"{title}\nAntes: ${prev_price:.2f} → Ahora: ${price:.2f}"
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
    headers = {"User-Agent": ua, "Accept-Language": "es-MX,es;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=(5, 15))
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.find(id="productTitle")
    title = title_el.get_text(strip=True) if title_el else name

    # try price selectors
    price_str = None
    for sel in ("#priceblock_ourprice", "#priceblock_dealprice", "#priceblock_saleprice"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            price_str = el.get_text(strip=True)
            break
    # fallbacks
    if not price_str:
        m = soup.find("meta", {"itemprop": "price"})
        price_str = m["content"] if m and m.get("content") else None
    if not price_str:
        off = soup.find("span", class_="a-offscreen")
        price_str = off.get_text(strip=True) if off else None
    if not price_str:
        w = soup.select_one("span.a-price-whole")
        f = soup.select_one("span.a-price-fraction")
        if w and f:
            price_str = f"{w.get_text(strip=True)}.{f.get_text(strip=True)}"

    if not price_str:
        return title, None

    cleaned = (
        price_str
        .replace("MX$", "")
        .replace("MXN", "")
        .replace("$", "")
        .replace(",", "")
        .replace("\xa0", "")
        .strip()
    )
    try:
        return title, float(cleaned)
    except ValueError:
        return title, None

def append_csv(record):
    os.makedirs(BASE_DIR, exist_ok=True)
    exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "name", "url", "price"])
        if not exists:
            w.writeheader()
        w.writerow(record)

def load_last_prices():
    last = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    last[row["name"]] = float(row["price"])
                except:
                    pass
    return last

def save_last_prices(prices):
    with open(HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "price"])
        w.writeheader()
        for key, price in prices.items():
            w.writerow({"name": key, "price": price})

def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    last_seen = load_last_prices()
    new_seen  = {}

    for prod in PRODUCTS:
        key = prod["name"]
        title, price = fetch_price(key, prod["url"])

        now = datetime.utcnow().isoformat()
        append_csv({"timestamp": now, "name": title, "url": prod["url"], "price": price})
        print(f"{now} | {title[:30]:30} | ${price}")

        prev = last_seen.get(key)
        if price is not None and prev is not None and price != prev:
            diff = price - prev
            arrow = "⬆️" if diff > 0 else "⬇️"
            print(f"Price changed ({arrow}{abs(diff):.2f}) → sending alert")
            send_whatsapp(arrow + " " + title, price, prev_price=prev)

        new_seen[key] = price
        time.sleep(random.uniform(5, 10))

    save_last_prices(new_seen)

if __name__ == "__main__":
    main()
