import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
import json
from urllib.parse import urlparse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+-football+-match+-sport&hl=fr&gl=FR&ceid=FR:fr"

SEEN_FILE = "seen.json"

# Charger l'historique
try:
    with open(SEEN_FILE, "r") as f:
        seen = json.load(f)
except:
    seen = {}

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

# Domaine propre
def get_domain(url):
    try:
        domain = urlparse(url).netloc.replace("www.", "")
        return domain
    except:
        return "source"

# Envoi Discord
def send_to_discord(title, articles, image_url):

    nb = len(articles)
    main = articles[0]
    main_link = main.get("link", "")

    # Sources propres cliquables
    source_lines = []
    for art in articles[:10]:
        link = art.get("link", "")
        domain = get_domain(link)
        source_lines.append(f"• {link}")

    sources_display = "\n".join(source_lines)

    # Importance
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
                "name": "📰 Sources",
                "value": sources_display if sources_display else "Aucune source",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Veille Châlons • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    if image_url:
        embed["image"] = {"url": image_url}

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# Lecture RSS
feed = feedparser.parse(RSS_URL)

clusters = defaultdict(list)

# Regroupement
for entry in feed.entries:
    title = entry.get("title", "")
    key = clean_title(title)[:80]
    clusters[key].append(entry)

# Traitement intelligent
for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]
    image_url = extract_image(main)

    # Si jamais vu → publier
    if key not in seen:
        send_to_discord(
            title=main.get("title", "Sans titre"),
            articles=articles,
            image_url=image_url
        )
        seen[key] = nb

    else:
        # ✅ REPUBLICATION SI LE SUJET PREND DE L’IMPORTANCE
        old_nb = seen[key]

        if nb > old_nb + 2:  # seuil d'évolution
            send_to_discord(
                title="🔄 Mise à jour : " + main.get("title", ""),
                articles=articles,
                image_url=image_url
            )
            seen[key] = nb

# Sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
