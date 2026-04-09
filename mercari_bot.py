import json, time, smtplib, logging, os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import requests

EMAIL_SENDER = os.environ.get("ALERT_EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("ALERT_EMAIL_TO", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
STATE_FILE = Path(__file__).parent / "seen.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

SEARCHES = [{"name": "Fendi Ladies Handbags", "category_id": 208, "brand_id": 1026}]

def load_seen():
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return {}

def save_seen(data):
    STATE_FILE.write_text(json.dumps(data))

def fetch(search):
    try:
        r = requests.post("https://api.mercari.jp/v2/entities:search", json={
            "userId": "", "pageToken": "",
            "searchCondition": {
                "keyword": "", "excludeKeyword": "",
                "sort": "SORT_CREATED_TIME", "order": "ORDER_DESC",
                "status": ["STATUS_SELLING"],
                "categoryId": [search["category_id"]],
                "brandId": [search["brand_id"]],
                "sizeId": [], "priceMin": 0, "priceMax": 0,
                "itemConditionId": [], "shippingPayerId": [],
                "shippingFromArea": [], "shippingMethod": [],
                "colorId": [], "hasCoupon": False,
                "attributes": [], "thumbnailTypes": [], "itemTypes": [],
            },
            "defaultDatasets": [], "serviceFrom": "suruga",
            "withItemBrand": True, "withItemSize": False,
            "withItemThumbnail": True, "useDynamicAttribute": True,
            "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
        }, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Platform": "web",
            "DPoP": "dummy",
        }, timeout=15)
        items = r.json().get("items", [])
        log.info(f"[{search['name']}] Fetched {len(items)} items")
        return items
    except Exception as e:
        log.error(f"Fetch error: {e}")
        return []

def send_email(subject, html):
    if not EMAIL_PASSWORD:
        log.warning("No email password — skipping")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        log.info(f"Email sent: {subject}")
    except Exception as e:
        log.error(f"Email error: {e}")

def make_html(name, items):
    rows = ""
    for item in items:
        iid = item.get("id", "")
        price = f"¥{int(item.get('price',0)):,}"
        thumb = (item.get("thumbnails") or [""])[0]
        img = f'<img src="{thumb}" width="70" height="70" style="border-radius:6px">' if thumb else "📦"
        rows += f"""<tr>
            <td style="padding:10px;border-bottom:1px solid #eee">{img}</td>
            <td style="padding:10px;border-bottom:1px solid #eee">
                <b>{item.get('name','')}</b><br>
                <span style="color:#e03;font-size:16px">{price}</span><br><br>
                <a href="https://jp.mercari.com/item/{iid}" style="background:#e03;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none">View →</a>
            </td></tr>"""
    return f"""<html><body style="font-family:sans-serif">
        <h2 style="background:#e03;color:#fff;padding:16px">🛍️ {len(items)} new {name}</h2>
        <table>{rows}</table></body></html>"""

def run():
    log.info("🚀 Mercari Monitor started")
    while True:
        seen = load_seen()
        for s in SEARCHES:
            key = s["name"]
            known = set(seen.get(key, []))
            items = fetch(s)
            current = {i.get("id") for i in items}
            new_ids = current - known
            if new_ids and known:
                new_items = [i for i in items if i.get("id") in new_ids]
                log.info(f"🆕 {len(new_items)} new items!")
                send_email(f"🛍️ {len(new_items)} new {key} on Mercari Japan", make_html(key, new_items))
            elif not known:
                log.info(f"First run — memorised {len(current)} listings")
            seen[key] = list(current)
        save_seen(seen)
        log.info(f"Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run()
