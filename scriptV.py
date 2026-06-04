import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
import json
import urllib.parse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# ✅ FLUX CIBLÉ AGGLO
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+Fagni%C3%A8res+OR+Sarry+OR+Saint-Memmie+OR+Compertrix+OR+%22Saint-Martin-sur-le-Pr%C3%A9%22+OR+Recy+OR+J%C3%A2lons+OR+Juvigny+OR+%22Mourmelon-le-Grand%22+OR+%22Mourmelon-le-Petit%22+OR+Vatry+OR+Bussy-Lettr%C3%A9e+OR+Sommesous+OR+Coolus+OR+Matougues+OR+%22La+Veuve%22%29+when%3A1d&hl=fr&gl=FR&ceid=FR:fr",

    "https://www.lunion.fr/rss.xml",
    "https://www.francebleu.fr/rss/champagne-ardenne",
    "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml"
]

SEEN_FILE = "seen.json"

# ✅ mots exclus
EXCLUDED_KEYWORDS = ["reims", "troyes", "epernay"]

# Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen = json.load(f)
except:
    seen = {}

# Nettoyage titre
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# ✅ Vérifier si article du jour
def is_today(entry):

    if hasattr(entry, "published_parsed"):

        article_date = datetime(*entry.published_parsed[:6])
        today = datetime.now()

        return (
            article_date.year == today.year and
            article_date.month == today.month and
            article_date.day == today.day
        )

    return True  # fallback si pas de date

# ✅ Filtrage territorial
def is_valid_article(entry):

    text = (
        entry.get("title", "") +
        entry.get("summary", "")
    ).lower()

    for word in EXCLUDED_KEYWORDS:
        if word in text:
            return False

    return True

# ✅ vraie URL (évite Google News)
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

# ✅ source propre
def extract_real_source(entry):

    title = entry.get("title", "")
    parts = title.split(" - ")

    for part in reversed(parts):
        part = part.strip().lower()
        if "." in part and len(part) < 40:
            return part

    link = get_real_url(entry)
    if "://" in link:
        return link.split("/")[2].replace("www.", "")

    return "source"

# ✅ envoi discord
def send_to_discord(title, articles):

    nb = len(articles)
    main = articles[0]

    main_link = get_real_url(main)

    # ✅ sources sans doublons
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
            "text": f"Veille Châlons • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# ✅ AGRÉGATION
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

# ✅ TRAITEMENT
for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]

    if key not in seen:
        send_to_discord(main.get("title", ""), articles)
        seen[key] = nb

    else:
        if nb > seen[key] + 2:
            send_to_discord("🔄 Mise à jour : " + main.get("title", ""), articles)
            seen[key] = nb

# ✅ sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
