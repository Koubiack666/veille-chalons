import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
import json
import urllib.parse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Ch%C3%A2lons+Agglo%22+OR+%22territoire+Ch%C3%A2lons+Agglo%22+OR+%22communaut%C3%A9+d%27agglom%C3%A9ration+de+Ch%C3%A2lons%22%29+when%3A1d&hl=fr&gl=FR&ceid=FR:fr"
]

SEEN_FILE = "seen.json"
EXCLUDED_KEYWORDS = ["reims", "troyes", "epernay"]

# Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen = json.load(f)
except:
    seen = {}

def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

def is_today(entry):

    if hasattr(entry, "published_parsed"):
        d = datetime(*entry.published_parsed[:6])
        now = datetime.now()

        return (
            d.year == now.year and
            d.month == now.month and
            d.day == now.day
        )

    return True

def is_valid_article(entry):

    text = (
        entry.get("title", "") +
        entry.get("summary", "")
    ).lower()

    for word in EXCLUDED_KEYWORDS:
        if word in text:
            return False

    return True

def get_real_url(entry):

    link = entry.get("link", "")

    try:
        parsed = urllib.parse.urlparse(link)
        query = urllib.parse.parse_qs(parsed.query)

        if "url" in query:
            return query["url"][0]
    except:
        pass

    return link

def extract_real_source(entry):

    title = entry.get("title", "")
    parts = title.split(" - ")

    for part in reversed(parts):
        if "." in part:
            return part.strip().lower()

    link = get_real_url(entry)
    return link.split("/")[2].replace("www.", "")

def send_to_discord(title, articles):

    nb = len(articles)
    main = articles[0]
    main_link = get_real_url(main)

    seen_domains = set()
    sources = []

    for art in articles:
        domain = extract_real_source(art)

        if domain not in seen_domains:
            sources.append(f"• {domain}")
            seen_domains.add(domain)

    sources_text = "\n".join(sources)

    if nb >= 10:
        niveau = "🔥 Sujet majeur"
        color = 15158332
    elif nb >= 5:
        niveau = "🟠 Sujet important"
        color = 15844367
    else:
        niveau = "🟢 Sujet mineur"
        color = 3066993

    embed = {
        "title": title,
        "url": main_link,
        "description": f"{niveau}\n\n🧠 **{nb} articles** sur ce sujet",
        "color": color,
        "fields": [
            {"name": "🔗 Article principal", "value": main_link, "inline": False},
            {"name": "📰 Sources", "value": sources_text, "inline": False}
        ],
        "footer": {
            "text": f"Veille OK • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# --- EXÉCUTION ---
clusters = defaultdict(list)

for feed_url in RSS_FEEDS:
    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        if not is_today(entry):
            continue

        if not is_valid_article(entry):
            continue

        key = clean_title(entry.get("title", ""))[:80]
        clusters[key].append(entry)


sent_something = False

for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]

    if key not in seen:
        send_to_discord(main.get("title", ""), articles)
        seen[key] = nb
        sent_something = True

    else:
        if nb > seen[key] + 2:
            send_to_discord("🔄 Mise à jour : " + main.get("title", ""), articles)
            seen[key] = nb
            sent_something = True


# ✅ message si rien
if not sent_something:
    requests.post(
        WEBHOOK_URL,
        json={"content": f"✅ Veille OK — aucun nouvel article ({datetime.now().strftime('%H:%M')})"}
    )

# ✅ sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
