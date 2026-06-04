import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os
from urllib.parse import urlparse

WEBHOOK_URL = https://discord.com/api/webhooks/1512008622610317454/cO80pEoNrgP3Ak0hXnqiAUqdRyi3j3mps5HPOwrB6gmGsczaUbg79GBf3c1bdXsKuABK

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29+-football+-match+-sport&hl=fr&gl=FR&ceid=FR:fr"

# Nettoyage titre
def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

# Extraction image
def extract_image(entry):
    # image directe
    if "media_content" in entry:
        return entry.media_content[0].get("url")

    # image dans HTML
    if "summary" in entry:
        match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if match:
            return match.group(1)

    return None

# Extraction domaine (ex: lunion.fr)
def get_domain(url):
    try:
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        return domain
    except:
        return "source"

# Envoi Discord
def send_to_discord(title, articles, image_url):

    nb = len(articles)
    main = articles[0]
    main_link = main.get("link", "")

    # Construction liste des sources cliquables
    source_lines = []
    for art in articles[:10]:
        link = art.get("link", "")
        domain = get_domain(link)

        # format markdown discord
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

    # IMAGE CLIQUABLE via lien du titre (et fallback dans description)
    image_block = ""
    if image_url:
        image_block = f"{main_link}"

    embed = {
        "title": title,
        "url": main_link,
        "description": f"{niveau}\n\n🧠 **{nb} articles** sur ce sujet\n{image_block}",
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
        embed["image"] = {
            "url": image_url
        }

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
    )
