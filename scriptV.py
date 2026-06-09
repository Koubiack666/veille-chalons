
import feedparser
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import logging
from urllib.parse import quote

# ✅ Configuration logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
SEEN_FILE = "seen_social.json"

# ✅ Mots-clés de recherche
SEARCH_KEYWORDS = [
    "Châlons-en-Champagne",
    "Châlons-Agglo",
    "chalons agglo",
    "chalons-en-champagne",
    "chalons champagne",
    "@chalonsagglo",
    "Benoist Apparu",
    "Jacques Jesson",
    "Jesson",
    "Apparu"
]

# ✅ Flux RSS sociaux
RSS_FEEDS = [

    # X/Twitter via Nitter
    {
        "url": "https://nitter.net/chalonsagglo/rss",
        "source": "X / Twitter"
    },

    {
        "url": "https://nitter.poast.org/chalonsagglo/rss",
        "source": "X / Twitter (Mirror)"
    },

    # Mastodon
    {
        "url": "https://mastodon.online/@chalonsagglo/feed.rss",
        "source": "Mastodon"
    },

    # Bluesky
    {
        "url": "https://bsky.app/profile/chalonsagglo.bsky.social/feed/rss",
        "source": "Bluesky"
    },

    # YouTube recherche globale
    {
        "url": "https://www.youtube.com/feeds/videos.xml?search_query=chalons+agglo+OR+chalons+champagne+OR+chalons",
        "source": "YouTube"
    },

    # Réseaux agrégés
    {
        "url": "https://www.rss-engine.com/search/?q=chalonsagglo",
        "source": "Réseaux Sociaux"
    },

    # Google Actualités
    {
        "url": f"https://news.google.com/rss/search?q={quote('Châlons-en-Champagne OR Châlons-Agglo')}&hl=fr&gl=FR&ceid=FR:fr",
        "source": "Google Actualités"
    },

    # Bing Actualités
    {
        "url": f"https://www.bing.com/news/search?q={quote('Châlons-en-Champagne Châlons-Agglo')}&format=rss",
        "source": "Bing Actualités"
    },

    # Lemmy
    {
        "url": "https://lemmy.ml/feeds/r/france.rss",
        "source": "Lemmy"
    }
]

# ✅ Keywords importants
IMPORTANT_KEYWORDS = [
    "projet",
    "lancement",
    "inauguration",
    "nouveau",
    "événement",
    "ouverture",
    "création",
    "investissement",
    "développement",
    "transport",
    "culture",
    "sport"
]

# ✅ Keywords alertes
ALERT_KEYWORDS = [
    "incident",
    "problème",
    "fermeture",
    "alerte",
    "annulation",
    "urgence",
    "accident",
    "crise",
    "danger",
    "risque"
]

# ✅ bruit / spam
EXCLUDED_KEYWORDS = [
    "jeu",
    "concours",
    "spam",
    "publicité",
    "crypto",
    "bitcoin",
    "nft",
    "trading"
]

# ✅ Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))

except FileNotFoundError:
    seen_urls = set()
    logger.info("seen_social.json créé")


# ✅ Heure Paris
def now_paris():
    return datetime.now(ZoneInfo("Europe/Paris"))


# ✅ Nettoyage texte
def clean_text(text):

    if not text:
        return ""

    return text.replace("\n", " ").strip()


# ✅ Vérif mots-clés
def contains_keywords(text, keywords):

    if not text:
        return False

    text = text.lower()

    return any(word.lower() in text for word in keywords)


# ✅ Vérifie si contenu du jour
def is_today(entry):

    if hasattr(entry, "published_parsed") and entry.published_parsed:

        try:
            d = datetime(*entry.published_parsed[:6])
            now = now_paris()

            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )

        except:
            return False

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:

        try:
            d = datetime(*entry.updated_parsed[:6])
            now = now_paris()

            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )

        except:
            return False

    return False


# ✅ Vérifie pertinence Châlons
def is_relevant(text):

    if not text:
        return False

    text = text.lower()

    has_keyword = any(
        keyword.lower() in text
        for keyword in SEARCH_KEYWORDS
    )

    if contains_keywords(text, EXCLUDED_KEYWORDS):
        return False

    return has_keyword


# ✅ Envoi Discord
def send_to_discord(title, link, source, description=""):

    if not WEBHOOK_URL:
        logger.error("WEBHOOK_SOCIAL absent")
        return False

    try:

        text = title.lower() if title else ""

        # priorité
        if contains_keywords(text, ALERT_KEYWORDS):
            tag = "🚨 ALERTE"
            color = 15158332

        elif contains_keywords(text, IMPORTANT_KEYWORDS):
            tag = "⭐ IMPORTANT"
            color = 15844367

        else:
            tag = "📢 INFORMATION"
            color = 3447003

        desc = f"{tag}\n📱 Source : {source}"

        if description:
            desc += f"\n\n{description[:200]}"

        embed = {
            "title": title[:256] if title else "Sans titre",
            "url": link,
            "description": desc,
            "color": color,
            "footer": {
                "text": f"Veille Réseaux • {now_paris().strftime('%d/%m %H:%M')}"
            }
        }

        response = requests.post(
            WEBHOOK_URL,
            json={"embeds": [embed]},
            timeout=5
        )

        if response.status_code == 204:
            logger.info(f"✅ Envoyé : {title[:60]}")
            return True

        logger.error(f"Erreur Discord : {response.status_code}")
        return False

    except Exception as e:
        logger.error(f"Erreur Discord : {e}")
        return False


# ✅ Traitement flux RSS
def process_rss_feed(feed_url, source):

    sent_count = 0

    try:

        logger.info(f"Flux : {source}")

        feed = feedparser.parse(feed_url)

        if feed.bozo:
            logger.warning(f"Flux mal formé : {source}")

        for entry in feed.entries[:20]:

            try:

                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                description = clean_text(entry.get("summary", ""))

                # anti doublon
                if not link or link in seen_urls:
                    continue

                # aujourd'hui seulement
                if not is_today(entry):
                    continue

                # pertinence territoriale
                if not is_relevant(f"{title} {description}"):
                    continue

                # Discord
                if send_to_discord(
                    title,
                    link,
                    source,
                    description
                ):

                    seen_urls.add(link)
                    sent_count += 1

            except Exception as e:
                logger.error(f"Erreur entrée : {e}")
                continue

        return sent_count

    except Exception as e:
        logger.error(f"Erreur flux {source} : {e}")
        return 0


# ✅ MAIN
def main():

    logger.info("=" * 60)
    logger.info("🔍 Démarrage veille réseaux")
    logger.info(now_paris().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info("=" * 60)

    total_sent = 0

    for feed_config in RSS_FEEDS:

        try:

            sent = process_rss_feed(
                feed_config["url"],
                feed_config["source"]
            )

            total_sent += sent

        except Exception as e:
            logger.error(f"Erreur critique : {e}")

    logger.info("=" * 60)
    logger.info(f"📊 {total_sent} posts envoyés")
    logger.info("=" * 60)

    # ✅ fallback
    if total_sent == 0 and WEBHOOK_URL:

        try:

            requests.post(
                WEBHOOK_URL,
                json={
                    "content": f"✅ Veille sociale OK — aucun nouveau post ({now_paris().strftime('%H:%M')})"
                },
                timeout=5
            )

            logger.info("✅ Message statut envoyé")

        except Exception as e:
            logger.error(f"Erreur message statut : {e}")

    # ✅ sauvegarde
    try:

        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_urls), f, indent=2)

        logger.info(f"💾 {len(seen_urls)} URLs sauvegardées")

    except Exception as e:
        logger.error(f"Erreur sauvegarde : {e}")


if __name__ == "__main__":
    main()
