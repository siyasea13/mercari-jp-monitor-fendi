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
        url = "https://jp.mercari.com/search"
        params = {
            "category_id": search["category_id"],
            "brand_id": search["brand_id"],
            "sort": "created_time",
            "order": "desc",
            "status": "on_sale",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja-JP,ja;q=0.9",
            "Referer": "https://jp.mercari.com/",
        }
        r = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Parse item IDs from the page HTML
        import re
        ids = re.findall(r'"id":"(m\d+)"', r.text)
        names = re.findall(r'"name":"([^"]{5,80})"', r.text)
        prices = re.findall(r'"price":(\d+)', r.text)
        thumbs = re.findall(r'"(https://static\.mercdn\.net/item/detail/orig/photos/[^"]+)"', r.text)
        
        items = []
        for i, iid in enumerate(ids[:30]):
            items.append({
                "id": iid,
                "name": names[i] if i < len(names) else "Fendi Item",
                "price": prices[i] if i < len(prices) else "0",
                "thumb": thumbs[i] if i < len(thumbs) else "",
            })
        
        log.info(f"[{search['name']}] Fetched {len(items)} items")
        return items
    except Exception as e:
        log.error(f"Fetch error: {e}")
        return []

def send_email(subject, html):
    if not EMAIL_PASSWORD:
        log.warning("No email password set")
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
        thumb = item.get("thumb", "")
        img = f'<img src="{thumb}" width="70" height="70" style="border-radius:6px;object-fit:cover">' if thumb else "📦"
        rows += f"""<tr>
            <td style="padding:10px;border-bottom:1px solid #eee;vertical-align:top">{img}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;vertical-align:top">
                <b>{item.get('name','')}</b><br>
                <span style="color:#e03;font-size:16px;font-weight:bold">{price}</span><br><br>
                <a href="https://jp.mercari.com/item/{iid}" style="background:#e03;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none">View on Mercari →</a>
            </td></tr>"""
    return f"""<html><body style="font-family:sans-serif;margin:0;padding:20px;background:#f5f5f5">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:10px;overflow:hidden">
        <div style="background:#e03;padding:20px"><h2 style="color:white;margin:0">🛍️ {len(items)} new {name} on Mercari Japan</h2></div>
        <table style="width:100%;border-collapse:collapse">{rows}</table>
        <div style="padding:12px;text-align:center;color:#aaa;font-size:12px">Checks every {POLL_INTERVAL//60} minutes</div>
        </div></body></html>"""

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
