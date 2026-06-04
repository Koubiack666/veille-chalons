import feedparser
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")

RSS_FEEDS = [
    "https://nitter.net/chalonsagglo/rss",
    "https://www.youtube.com/feeds/videos.xml?search_query=chalons+agglo+OR+chalons+champagne+OR+chalons"
]

SEEN_FILE = "seen_social.json"

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

# charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
except:
    seen_urls = set()


def clean_text(text):
    return text.replace("\n", " ").strip()


def contains_keywords(text, keywords):
    text = text.lower()
    return any(word in text for word in keywords)


def is_today(entry):

    if hasattr(entry, "published_parsed"):
        d = datetime(*entry.published_parsed[:6])
        now = datetime.now(ZoneInfo("Europe/Paris"))

        return (
            d.year == now.year and
            d.month == now.month and
            d.day == now.day
        )

    return False


def send_to_discord(title, link, source):

    text = title.lower()

    if contains_keywords(text, ALERT_KEYWORDS):
        tag = "🚨 ALERTE"
        color = 15158332

    elif contains_keywords(text, IMPORTANT_KEYWORDS):
        tag = "⭐ IMPORTANT"
        color = 15844367

    else:
        tag = "📢 INFORMATION"
        color = 3447003

    now_paris = datetime.now(ZoneInfo("Europe/Paris"))

    embed = {
        "title": title,
        "url": link,
        "description": f"{tag}\n📱 Source : {source}",
        "color": color,
        "footer": {
            "text": f"Veille Réseaux • {now_paris.strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


sent_something = False

for feed_url in RSS_FEEDS:

    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")

        if not is_today(entry):
            continue

        if contains_keywords(title, EXCLUDED_KEYWORDS):
            continue

        if link in seen_urls:
            continue

        if "nitter" in feed_url:
            source = "X / Twitter"
        elif "youtube" in feed_url:
            source = "YouTube"
        else:
            source = "Réseaux"

        send_to_discord(title, link, source)

        seen_urls.add(link)
        sent_something = True


if not sent_something:
    now_paris = datetime.now(ZoneInfo("Europe/Paris"))

    requests.post(
        WEBHOOK_URL,
        json={
            "content": f"✅ Veille sociale OK — aucun nouveau post ({now_paris.strftime('%H:%M')})"
        }
    )


with open(SEEN_FILE, "w") as f:
    json.dump(list(seen_urls), f)
