import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
import json

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+-football+-match+-sport&hl=fr&gl=FR&ceid=FR:fr"

SEEN_FILE = "seen.json"

# Charger historique
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

# Extraction du vrai nom de site depuis le titre
def extract_real_source(entry):
    title = entry.get("title", "")
    parts = title.split(" - ")

    for part in reversed(parts):
        part = part.strip().lower()
        if "." in part and len(part) < 40:
            return part

    return "source"

# Envoi Discord (VERSION PRO)
def send_to_discord(title, articles, image_url):

    nb = len(articles)
    main = articles[0]
    main_link = main.get("link", "")

    # ✅ éviter doublons de médias
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
                "value": f"🔗 {main_link}\n\n{sources_display}",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Veille Châlons • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    # Image
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

    if key not in seen:
        send_to_discord(
            title=main.get("title", "Sans titre"),
            articles=articles,
            image_url=image_url
        )
        seen[key] = nb

    else:
        old_nb = seen[key]

        # republier si le sujet évolue
        if nb > old_nb + 2:
            send_to_discord(
                title="🔄 Mise à jour : " + main.get("title", ""),
                articles=articles,
                image_url=image_url
            )
            seen[key] = nb

# Sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
