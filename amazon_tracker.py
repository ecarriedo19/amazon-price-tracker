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
    # …add more products here as needed
]

BASE_DIR = "/tmp"  # GitHub Actions uses an ephemeral filesystem
CSV_FILE = os.path.join(BASE_DIR, "AmazonProductsPriceDataset.csv")

# Twilio WhatsApp client (secrets will be provided in Actions)
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
    # Rotate user-agent
    ua = random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    ]).encode('latin-1', 'ignore').decode('latin-1')
    headers = {"User-Agent": ua, "Accept-Language": "es-MX,es;q=0.9"}

    resp = requests.get(url, headers=headers, timeout=(5, 15))
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Get product title
    title_el = soup.find(id="productTitle")
    title = title_el.get_text(strip=True) if title_el else name

    # Try standard price selectors
    price_str = None
    for sel in ("#priceblock_ourprice", "#priceblock_dealprice", "#priceblock_saleprice"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            price_str = el.get_text(strip=True)
            break

    # Fallbacks
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

    cleaned = (price_str
               .replace("MX$", "")
               .replace("MXN", "")
               .replace("$", "")
               .replace(",", "")
               .replace("\xa0", "")
               .strip())
    try:
        return title, float(cleaned)
    except ValueError:
        return title, None

def append_csv(record):
    os.makedirs(BASE_DIR, exist_ok=True)
    exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "name", "url", "price"])
        if not exists:
            writer.writeheader()
        writer.writerow(record)

def main():
    for p in PRODUCTS:
        try:
            title, price = fetch_price(p["name"], p["url"])
        except Exception as e:
            print(f"✖ Error fetching {p['name']}: {e}")
            continue

        now = datetime.utcnow().isoformat()
        append_csv({"timestamp": now, "name": title, "url": p["url"], "price": price})
        print(f"{now} | {title[:30]:30} | ${price}")

        if price is not None and price <= p["threshold"]:
            send_whatsapp(title, price)
            print("→ WhatsApp alert sent!")

        time.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    main()
