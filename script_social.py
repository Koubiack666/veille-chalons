import feedparser
import requests
from datetime import datetime
import os
import json

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")

# ✅ FLUX SOCIAUX
RSS_FEEDS = [

    # X / Twitter via Nitter
    "https://nitter.net/chalonsagglo/rss",

    # ✅ YouTube recherche globale
    "https://www.youtube.com/feeds/videos.xml?search_query=chalons+agglo+OR+chalons+champagne+OR+chalons"
]

SEEN_FILE = "seen_social.json"

# ✅ Mots clés
IMPORTANT_KEYWORDS = [
    "projet", "lancement", "inauguration",
    "nouveau", "événement", "ouverture"
]

ALERT_KEYWORDS = [
    "incident", "problème", "fermeture",
    "alerte", "annulation", "urgence"
]

EXCLUDED_KEYWORDS = [
    "jeu", "concours"
]

# ✅ Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
except:
    seen_urls = set()


# ✅ Nettoyage texte
def clean_text(text):
    return text.replace("\n", " ").strip()


# ✅ Détection mots-clés
def contains_keywords(text, keywords):
    text = text.lower()
    return any(word in text for word in keywords)


# ✅ Filtre aujourd’hui
def is_today(entry):

    if hasattr(entry, "published_parsed"):

        d = datetime(*entry.published_parsed[:6])
        now = datetime.now()

        return (
            d.year == now.year and
            d.month == now.month and
            d.day == now.day
        )

    return False


# ✅ Envoi Discord
def send_to_discord(title, link, source):

    text = title.lower()

    # 🚨 priorité
    if contains_keywords(text, ALERT_KEYWORDS):
        tag = "🚨 ALERTE"
        color = 15158332

    elif contains_keywords(text, IMPORTANT_KEYWORDS):
        tag = "⭐ IMPORTANT"
        color = 15844367

    else:
        tag = "📢 INFORMATION"
        color = 3447003

    embed = {
        "title": title,
        "url": link,
        "description": f"{tag}\n📱 Source : {source}",
        "color": color,
        "footer": {
            "text": f"Veille Réseaux • {datetime.now().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


# ✅ TRAITEMENT
sent_something = False

for feed_url in RSS_FEEDS:

    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")

        # ✅ filtre aujourd’hui
        if not is_today(entry):
            continue

        # ✅ filtre bruit
        if contains_keywords(title, EXCLUDED_KEYWORDS):
            continue

        # ✅ anti-doublon
        if link in seen_urls:
            continue

        # ✅ source
        if "nitter" in feed_url:
            source = "X / Twitter"
        elif "youtube" in feed_url:
            source = "YouTube"
        else:
            source = "Réseaux"

        # ✅ envoi
        send_to_discord(title, link, source)

        seen_urls.add(link)
        sent_something = True


# ✅ fallback si rien
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
