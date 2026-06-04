import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+-football+-match+-sport&hl=fr&gl=FR&ceid=FR:fr"

# Nettoyage titre
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# Extraction image
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")

    if "summary" in entry:
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)

    return None

# Récupération source
def get_source(entry):
    src = entry.get("source", {})
    return src.get("title", "Source inconnue")

# Envoi Discord (format amélioré)
def send_to_discord(title, articles, image_url):

    nb = len(articles)

    # Classement sources
    sources = {}
    for art in articles:
        name = get_source(art)
        sources[name] = sources.get(name, 0) + 1

    sorted_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)

    # 🔗 sources avec liens intégrés
    source_links = []
    for art in articles[:10]:
        name = get_source(art)
        link = art.get("link", "")
        source_links.append(f"• {link}")

    sources_display = "\n".join(source_links)

    # 📊 indicateur importance
    if nb >= 10:
        niveau = "🔥 Sujet majeur"
    elif nb >= 5:
        niveau = "🟠 Sujet important"
    else:
        niveau = "🟢 Sujet mineur"

    embed = {
        "title": title,
        "url": articles[0].get("link", ""),
        "color": 15844367 if nb >= 5 else 3447003,
        "author": {
            "name": "Veille Châlons-en-Champagne"
        },
        "description": f"{niveau}\n\n🧠 **{nb} articles** sur ce sujet",
        "fields": [
            {
                "name": "📰 Sources principales",
                "value": sources_display[:1000] if sources_display else "Aucune source",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Mise à jour : {datetime.now().strftime('%d/%m %H:%M:%S')}"
        }
    }

    if image_url:
        embed["image"] = {"url": image_url}

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})

# Lecture RSS
feed = feedparser.parse(RSS_URL)

clusters = defaultdict(list)

# Regroupement
for entry in feed.entries:
    title = entry.get("title", "")
    key = clean_title(title)[:80]
    clusters[key].append(entry)

# Traitement
for key, articles in clusters.items():

    main = articles[0]
    image_url = extract_image(main)

    send_to_discord(
        title=main.get("title", "Sans titre"),
        articles=articles,
        image_url=image_url
        
}
    )
