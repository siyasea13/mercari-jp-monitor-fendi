import json, time, smtplib, logging, os, re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import requests

EMAIL_SENDER = os.environ.get("ALERT_EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("ALERT_EMAIL_TO", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
SCRAPER_KEY = os.environ.get("SCRAPER_API_KEY", "")
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
        target = "https://jp.mercari.com/search?category_id=" + str(search["category_id"]) + "&brand_id=" + str(search["brand_id"]) + "&sort=created_time&order=desc&status=on_sale"
        if SCRAPER_KEY:
            url = "http://api.scraperapi.com?api_key=" + SCRAPER_KEY + "&url=" + target + "&country_code=jp"
            r = requests.get(url, timeout=60)
        else:
            r = requests.get(target, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15", "Accept-Language": "ja-JP,ja;q=0.9"}, timeout=15)
        ids = re.findall(r'"id":"(m\d+)"', r.text)
        names = re.findall(r'"name":"([^"]{5,80})"', r.text)
        prices = re.findall(r'"price":(\d+)', r.text)
        thumbs = re.findall(r'https://static\.mercdn\.net/item/detail/orig/photos/[^"\'\\]+', r.text)
        items = []
        for i in range(min(len(ids), 30)):
            items.append({
                "id": ids[i],
                "name": names[i] if i < len(names) else "Fendi Item",
                "price": prices[i] if i < len(prices) else "0",
                "thumb": thumbs[i] if i < len(thumbs) else "",
            })
        log.info("[" + search["name"] + "] Fetched " + str(len(items)) + " items")
        return items
    except Exception as e:
        log.error("Fetch error: " + str(e))
        return []

def send_email(subject, html):
    if not EMAIL_PASSWORD:
        log.warning("No email password")
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
        log.info("Email sent: " + subject)
    except Exception as e:
        log.error("Email error: " + str(e))

def make_html(name, items):
    rows = ""
    for item in items:
        iid = item.get("id", "")
        price = "Y" + str(int(item.get("price", 0)))
        thumb = item.get("thumb", "")
        img = '<img src="' + thumb + '" width="70" height="70" style="border-radius:6px;object-fit:cover">' if thumb else "bag"
        rows += "<tr><td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top'>" + img + "</td><td style='padding:10px;border-bottom:1px solid #eee;vertical-align:top'><b>" + item.get("name", "") + "</b><br><span style='color:#e03;font-size:16px'>" + price + "</span><br><br><a href='https://jp.mercari.com/item/" + iid + "' style='background:#e03;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none'>View</a></td></tr>"
    return "<html><body style='font-family:sans-serif'><h2 style='background:#e03;color:#fff;padding:16px'>" + str(len(items)) + " new " + name + "</h2><table>" + rows + "</table></body></html>"

def run():
    log.info("Mercari Monitor started")
    while True:
        seen = load_seen()
        for s in SEARCHES:
            key = s["name"]
            known = set(seen.get(key, []))
            items = fetch(s)
            current = set(i.get("id") for i in items)
            new_ids = current - known
            if new_ids and known:
                new_items = [i for i in items if i.get("id") in new_ids]
                log.info("NEW: " + str(len(new_items)) + " items!")
                send_email(str(len(new_items)) + " new " + key + " on Mercari Japan", make_html(key, new_items))
            elif not known:
                log.info("First run - memorised " + str(len(current)) + " listings")
            seen[key] = list(current)
        save_seen(seen)
        log.info("Sleeping " + str(POLL_INTERVAL) + "s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run()
