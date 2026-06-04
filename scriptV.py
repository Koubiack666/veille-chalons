import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import urllib.parse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ✅ SOURCES RSS
RSS_FEEDS = [

    # Google News ciblé
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Ch%C3%A2lons+Agglo%22+OR+%22territoire+Ch%C3%A2lons+Agglo%22+OR+%22communaut%C3%A9+d%27agglom%C3%A9ration+de+Ch%C3%A2lons%22%29+when%3A1d&hl=fr&gl=FR&ceid=FR:fr",

    # Presse locale
    "https://www.lunion.fr/rss.xml",
    "https://www.francebleu.fr/rss/champagne-ardenne",
    "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml",

    # Institutionnel
    "https://www.marne.gouv.fr/spip.php?page=backend"
]

SEEN_FILE = "seen.json"

EXCLUDED_KEYWORDS = [
    "reims", "troyes", "epernay",
    "football", "match", "psg"
]

# ✅ Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        data = json.load(f)
        seen_topics = data.get("topics", {})
        seen_urls = set(data.get("urls", []))
except:
    seen_topics = {}
    seen_urls = set()

# ✅ Nettoyage titre
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# ✅ Heure Paris
def now_paris():
    return datetime.now(ZoneInfo('Europe/Paris'))

# ✅ Filtre aujourd’hui
def is_today(entry):

    if hasattr(entry, "published_parsed"):

        d = datetime(*entry.published_parsed[:6])
        now = now_paris()

        return (
            d.year == now.year and
            d.month == now.month and
            d.day == now.day
        )

    return True

# ✅ Filtrage contenu
def is_valid_article(entry):

    text = (
        entry.get("title", "") +
        entry.get("summary", "")
    ).lower()

    for word in EXCLUDED_KEYWORDS:
        if word in text:
            return False

    return True

# ✅ Vraie URL
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

# ✅ Source propre
def extract_real_source(entry):

    title = entry.get("title", "")
    parts = title.split(" - ")

    for part in reversed(parts):
        part = part.strip().lower()
        if "." in part:
            return part

    link = get_real_url(entry)
    if "://" in link:
        return link.split("/")[2].replace("www.", "")

    return "source"

# ✅ Envoi Discord
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

        if len(sources) >= 10:
            break

    sources_text = "\n".join(sources)

    # importance
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
            {
                "name": "🔗 Article principal",
                "value": main_link,
                "inline": False
            },
            {
                "name": "📰 Sources",
                "value": sources_text if sources_text else "Aucune source",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Veille • {now_paris().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# ✅ AGRÉGATION
clusters = defaultdict(list)
cluster_urls = defaultdict(set)

for feed_url in RSS_FEEDS:
    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        if not is_today(entry):
            continue

        if not is_valid_article(entry):
            continue

        real_url = get_real_url(entry)

        if real_url in seen_urls:
            continue

        key = clean_title(entry.get("title", ""))[:80]

        clusters[key].append(entry)
        cluster_urls[key].add(real_url)

# ✅ TRAITEMENT
sent_something = False

for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]

    if key not in seen_topics:
        send_to_discord(main.get("title", ""), articles)
        seen_topics[key] = nb
        seen_urls.update(cluster_urls[key])
        sent_something = True

    else:
        if nb > seen_topics[key] + 2:
            send_to_discord("🔄 Mise à jour : " + main.get("title", ""), articles)
            seen_topics[key] = nb
            seen_urls.update(cluster_urls[key])
            sent_something = True

# ✅ fallback
if not sent_something:
    requests.post(
        WEBHOOK_URL,
        json={
            "content": f"✅ Veille OK — aucun nouvel article ({now_paris().strftime('%H:%M')})"
        }
    )

# ✅ sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump({
        "topics": seen_topics,
        "urls": list(seen_urls)
    }, f)
