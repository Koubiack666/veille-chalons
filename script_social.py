import feedparser
import requests
from datetime import datetime
import os
import json

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")

# ✅ flux sociaux
RSS_FEEDS = [

    # X / Twitter via Nitter
    "https://nitter.net/chalonsagglo/rss",

    # YouTube (remplace ID par la vraie chaîne)
    "https://www.youtube.com/feeds/videos.xml?channel_id=chalonsagglo"
]

SEEN_FILE = "seen_social.json"

# ✅ charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
except:
    seen_urls = set()


# ✅ nettoyage texte
def clean_text(text):
    return text.replace("\n", " ").strip()


# ✅ envoi discord
def send_to_discord(title, link, source):

    embed = {
        "title": title,
        "url": link,
        "description": f"📱 Source : {source}",
        "color": 3447003,
        "footer": {
            "text": f"Veille Réseaux • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# ✅ traitement
sent_something = False

for feed_url in RSS_FEEDS:

    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        link = entry.get("link", "")

        # ✅ anti-doublon strict
        if link in seen_urls:
            continue

        title = clean_text(entry.get("title", "Sans titre"))

        # ✅ identifier source
        if "nitter" in feed_url:
            source = "X / Twitter"
        elif "youtube" in feed_url:
            source = "YouTube"
        else:
            source = "Réseau"

        # ✅ envoi
        send_to_discord(title, link, source)

        seen_urls.add(link)
        sent_something = True


# ✅ fallback si aucun post
if not sent_something:
    requests.post(
        WEBHOOK_URL,
        json={
            "content": f"✅ Veille sociale OK — aucun nouveau post ({datetime.now().strftime('%H:%M')})"
        }
    )
# ✅ sauvegarde
with open(SEEN_FILE, "w") as f:
    json.dump(list(seen_urls), f)
