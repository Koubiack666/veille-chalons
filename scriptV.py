import feedparser
import requests
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import re
import urllib.parse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
SEEN_FILE = "seen.json"

# ========================================================
# SOURCES RSS
# ========================================================

RSS_FEEDS = [

    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Ch%C3%A2lons+Agglo%22%29&hl=fr&gl=FR&ceid=FR:fr",
    "https://www.lunion.fr/rss.xml",
    "https://www.francebleu.fr/rss/champagne-ardenne",
    "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml",
    "https://www.francetvinfo.fr/titres.rss",
    "https://www.marne.gouv.fr/spip.php?page=backend"
]

# ========================================================
# CATÉGORIES (NOUVELLES)
# ========================================================

CATEGORIES = {

    "🎪 Arts du cirque / CNAC / PALC / Furies": [
        "cirque", "cnac", "centre national des arts du cirque",
        "palc", "pole national des arts du cirque",
        "spectacle de rue", "theatre de rue",
        "festival du cirque", "furies"
    ],

    "🚨 Sécurité": [
        "accident", "incendie", "urgence", "police"
    ],

    "🏛️ Politique": [
        "maire", "élu", "conseil", "municipales",
        "apparu", "jesson"
    ],

    "🎉 Événement": [
        "festival", "concert", "événement", "sport", "culture"
    ],

    "📊 Économie": [
        "entreprise", "emploi", "investissement"
    ]
}

EXCLUDED_KEYWORDS = [
    "reims", "troyes", "epernay",
    "football", "psg"
]

# ========================================================
# MÉMOIRE
# ========================================================

try:
    with open(SEEN_FILE, "r") as f:
        data = json.load(f)
        seen_urls = set(data)
except:
    seen_urls = set()

# ========================================================
# FONCTIONS
# ========================================================

def now_paris():
    return datetime.now(ZoneInfo("Europe/Paris"))

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip() if text else ""

def is_today(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        d = datetime(*entry.published_parsed[:6])
        now = now_paris()
        return d.date() == now.date()
    return True

def is_valid(entry):
    text = (entry.get("title", "") + entry.get("summary", "")).lower()
    return not any(word in text for word in EXCLUDED_KEYWORDS)

def categorize(text):
    text = text.lower()

    for cat, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            return cat

    return "📰 Autres"

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

def send_summary(total, category_count):

    lines = []

    for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
        lines.append(f"{cat} : {count}")

    text = "\n".join(lines)

    message = {
        "content":
        f"📊 **Rapport de veille**\n"
        f"{total} articles détectés\n\n"
        f"{text}"
    }

    requests.post(WEBHOOK_URL, json=message)

def send_article(title, link, source):

    embed = {
        "title": title,
        "url": link,
        "description": f"📰 Source : {source}",
        "color": 3447003,
        "footer": {
            "text": f"Veille • {now_paris().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})

# ========================================================
# TRAITEMENT
# ========================================================

articles = []
category_count = defaultdict(int)

for feed_url in RSS_FEEDS:

    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        if not is_today(entry):
            continue

        if not is_valid(entry):
            continue

        url = get_real_url(entry)

        if url in seen_urls:
            continue

        title = clean_text(entry.get("title", ""))

        category = categorize(title)

        articles.append({
            "title": title,
            "url": url,
            "source": feed_url,
            "category": category
        })

        category_count[category] += 1
        seen_urls.add(url)

# ========================================================
# ENVOI DISCORD
# ========================================================

if articles:

    send_summary(len(articles), category_count)

    for art in articles:
        send_article(
            art["title"],
            art["url"],
            art["source"]
        )

else:

    requests.post(
        WEBHOOK_URL,
        json={
            "content": f"✅ Veille réalisée à {now_paris().strftime('%Hh%M')} — pas de nouveaux articles"
        }
    )

# ========================================================
# SAUVEGARDE
# ========================================================

with open(SEEN_FILE, "w") as f:
    json.dump(list(seen_urls), f)
