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
    try: return json.loads(STATE_FILE.read_text())
    except: return {}

def save_seen(data):
    STATE_FILE.write_text(json.dumps(data))

def fetch(search):
    try:
        target = f"https://jp.mercari.com/search?category_id={search['category_id']}&brand_id={search['brand_id']}&sort=created_time&order=desc&status=on_sale"
        
        if SCRAPER_KEY:
            # Use ScraperAPI to bypass blocks
            url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target}&country_code=jp"
            r = requests.get(url, timeout=60)
        else:
            r = requests.get(target, headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                "Accept-Language": "ja-JP,ja;q=0.9",
            }, timeout=15)

        ids = re.findall(r'"id":"(m\d+)"', r.text)
        names = re.findall(r'"name":"([^"]{5,80})"', r.text)
        prices = re.findall(r'"price":(\d+)', r.text)
        thumbs = re.findall(r'(https://static\.mercdn\.net/item/detail/orig/photos/[^"\'\\]+)', r.text)

        items = [{"id": ids[i], "name": names[i] if i < len(names) else "Fendi Item",
                  "price": prices[i] if i < len(prices) else "0",
                  "thumb": thumbs[i] if i < len(thumbs) el
