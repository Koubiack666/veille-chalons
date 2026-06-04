import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os

# 🔐 Webhook sécurisé via GitHub Secret
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# 🔎 Flux RSS Google News
RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+-football+-match+-sport&hl=fr&gl=FR&ceid=FR:fr"

# 🔧 Nettoyage des titres (pour regrouper)
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# 🖼️ Extraction image
def extract_image(entry):
    # 1. image directe
    if "media_content" in entry:
        return entry.media_content[0].get("url")

    # 2. image dans le HTML du résumé
    if "summary" in entry:
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)

    return None

# 💬 Envoi Discord format embed
def send_to_discord(title, link, sources_txt, nb, image_url=None):

    embed = {
        "title": title,
        "description": f"🧠 {nb} articles sur ce sujet\n\n📊 Sources :\n{sources_txt}",
        "url": link,
        "color": 3447003,
        "footer": {
            "text": f"Veille Châlons • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    if image_url:
        embed["image"] = {"url": image_url}

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})
    else:
        print("⚠️ WEBHOOK_URL manquant")

# 📡 Lecture du flux
feed = feedparser.parse(RSS_URL)

clusters = defaultdict(list)

# 🔗 Regroupement des articles similaires
for entry in feed.entries:
    title = entry.get("title", "")
    key = clean_title(title)[:80]
    clusters[key].append(entry)

# 🧠 Analyse des groupes (sujets)
for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]

    sources = {}

    for art in articles:
        src = art.get("source", {})
        name = src.get("title", "inconnu")
        sources[name] = sources.get(name, 0) + 1

    # 📊 top 10 sources
    top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]
    sources_txt = ", ".join([f"{s} ({c})" for s, c in top_sources])

    # 🖼️ image
    image_url = extract_image(main)

    # 🚀 envoi
    send_to_discord(
        title=main.get("title", "Sans titre"),
        link=main.get("link", ""),
        sources_txt=sources_txt,
        nb=nb,
        image_url=image_url
    )
