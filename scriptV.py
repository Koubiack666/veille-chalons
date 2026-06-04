import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
import json
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# MULTI SOURCES
RSS_FEEDS = [
    # GLOBAL
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22+OR+%22Ch%C3%A2lons+Agglo%22+OR+%22Communaut%C3%A9+d%27agglom%C3%A9ration+de+Ch%C3%A2lons%22+OR+%22Benoist+Apparu%22+OR+%22Jacques+Jesson%22%29+when%3A1d&hl=fr&gl=FR&ceid=FR:fr",

    # ALERTES
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+%28accident+OR+violence+OR+plainte+OR+justice+OR+pol%C3%A9mique+OR+conflit%29+when%3A1d&hl=fr&gl=FR&ceid=FR:fr",

    # PRESSE LOCALE
    "https://www.lunion.fr/rss.xml",
    "https://www.francebleu.fr/rss/champagne-ardenne",
    "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml"
]

SEEN_FILE = "seen.json"

# Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen = json.load(f)
except:
    seen = {}

# Nettoyage titre (clustering)
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# EXTRACTION IMAGE (OPEN GRAPH + fallback)
def extract_image(entry):

    url = entry.get("link", "")

    # ✅ 1. tenter Open Graph (meilleur résultat)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            tag = soup.find("meta", property="og:image")

            if tag and tag.get("content"):
                return tag["content"]
    except:
        pass

    # ✅ 2. fallback RSS
    if "media_content" in entry:
        try:
            return entry.media_content[0].get("url")
        except:
            pass

    # ✅ 3. fallback summary
    if "summary" in entry:
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)

    return None

# Extraction domaine propre
def extract_real_source(entry):
    title = entry.get("title", "")

    parts = title.split(" - ")
    for part in reversed(parts):
        part = part.strip().lower()
        if "." in part and len(part) < 40:
            return part

    link = entry.get("link", "")
    if "://" in link:
        return link.split("/")[2].replace("www.", "")

    return "source"

# ENVOI DISCORD
def send_to_discord(title, articles, image_url):

    nb = len(articles)
    main = articles[0]
    main_link = main.get("link", "")

    # éviter doublon des médias
    seen_domains = set()
    source_lines = []

    for art in articles:
        domain = extract_real_source(art)

        if domain not in seen_domains:
            source_lines.append(f"• {domain}")
            seen_domains.add(domain)

        if len(source_lines) >= 10:
            break

    sources_display = "\n".join(source_lines)

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
                "value": sources_display if sources_display else "Aucune source",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Veille Châlons • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    # ✅ ajout image
    if image_url:
        embed["image"] = {"url": image_url}

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})

# AGRÉGATION
clusters = defaultdict(list)

for feed_url in RSS_FEEDS:
    feed = feedparser.parse(feed_url)

    for entry in feed.entries:
        title = entry.get("title", "")
        key = clean_title(title)[:80]
        clusters[key].append(entry)

# TRAITEMENT
for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]
    image_url = extract_image(main)

    # nouveau sujet
    if key not in seen:
        send_to_discord(
            title=main.get("title", "Sans titre"),
            articles=articles,
            image_url=image_url
        )
        seen[key] = nb

    else:
        old_nb = seen[key]

        # republie si le sujet grossit
        if nb > old_nb + 2:
            send_to_discord(
                title="🔄 Mise à jour : " + main.get("title", ""),
                articles=articles,
                image_url=image_url
            )
            seen[key] = nb

# sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
``
