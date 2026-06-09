import feedparser
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import logging
from urllib.parse import quote

# =========================================================
# CONFIGURATION LOGS
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURATION
# =========================================================

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")
SEEN_FILE = "seen_social.json"

# =========================================================
# MOTS-CLÉS DE VEILLE
# =========================================================

SEARCH_KEYWORDS = [

    # Territoire
    "châlons-en-champagne",
    "chalons-en-champagne",
    "châlons agglo",
    "chalons agglo",
    "chalons champagne",
    "chalons",

    # Comptes / élus
    "@chalonsagglo",
    "benoist apparu",
    "jacques jesson",
    "apparu",
    "jesson"
]

# =========================================================
# SOURCES 100% RÉSEAUX SOCIAUX
# =========================================================

RSS_FEEDS = [

    # =========================================
    # X / TWITTER
    # =========================================

    {
        "url": "https://nitter.net/chalonsagglo/rss",
        "source": "X / Twitter"
    },

    {
        "url": "https://nitter.poast.org/chalonsagglo/rss",
        "source": "X / Twitter Mirror"
    },

    # =========================================
    # BLUESKY
    # =========================================

    {
        "url": "https://bsky.app/profile/chalonsagglo.bsky.social/feed/rss",
        "source": "Bluesky"
    },

    # =========================================
    # MASTODON
    # =========================================

    {
        "url": "https://mastodon.online/@chalonsagglo/feed.rss",
        "source": "Mastodon"
    },

    # =========================================
    # YOUTUBE
    # =========================================

    {
        "url": "https://www.youtube.com/feeds/videos.xml?search_query=chalons+agglo+OR+chalons+champagne+OR+chalons",
        "source": "YouTube"
    },

    # =========================================
    # REDDIT
    # =========================================

    {
        "url": "https://www.reddit.com/r/france/search.rss?q=chalons&sort=new",
        "source": "Reddit"
    },

    # =========================================
    # RÉSEAUX AGRÉGÉS
    # =========================================

    {
        "url": "https://www.rss-engine.com/search/?q=chalonsagglo",
        "source": "Agrégation Réseaux"
    }
]

# =========================================================
# PRIORITÉ CONTENU
# =========================================================

IMPORTANT_KEYWORDS = [
    "projet",
    "inauguration",
    "événement",
    "ouverture",
    "nouveau",
    "culture",
    "transport",
    "sport",
    "développement",
    "investissement",
    "festival",
    "concert"
]

ALERT_KEYWORDS = [
    "incident",
    "accident",
    "alerte",
    "urgence",
    "danger",
    "fermeture",
    "annulation",
    "crise",
    "grève"
]

EXCLUDED_KEYWORDS = [
    "crypto",
    "bitcoin",
    "nft",
    "spam",
    "publicité",
    "trading",
    "casino"
]

# =========================================================
# CHARGEMENT HISTORIQUE
# =========================================================

try:

    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))

except FileNotFoundError:

    seen_urls = set()

    logger.info("seen_social.json créé")

# =========================================================
# UTILITAIRES
# =========================================================

def now_paris():

    return datetime.now(ZoneInfo("Europe/Paris"))


def clean_text(text):

    if not text:
        return ""

    return text.replace("\n", " ").strip()


def contains_keywords(text, keywords):

    if not text:
        return False

    text = text.lower()

    return any(
        keyword.lower() in text
        for keyword in keywords
    )


# =========================================================
# FILTRE DATE
# =========================================================

def is_today(entry):

    now = now_paris()

    # published
    if hasattr(entry, "published_parsed") and entry.published_parsed:

        try:

            d = datetime(*entry.published_parsed[:6])

            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )

        except:
            return False

    # updated
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:

        try:

            d = datetime(*entry.updated_parsed[:6])

            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )

        except:
            return False

    return False

# =========================================================
# FILTRE PERTINENCE
# =========================================================

def is_relevant(text):

    if not text:
        return False

    text = text.lower()

    # mots exclus
    if contains_keywords(text, EXCLUDED_KEYWORDS):
        return False

    # mots pertinents
    return any(
        keyword in text
        for keyword in SEARCH_KEYWORDS
    )

# =========================================================
# ENVOI DISCORD
# =========================================================

def send_to_discord(title, link, source, description=""):

    if not WEBHOOK_URL:

        logger.error("WEBHOOK_SOCIAL absent")
        return False

    try:

        text = title.lower() if title else ""

        # =========================================
        # PRIORITÉ
        # =========================================

        if contains_keywords(text, ALERT_KEYWORDS):

            tag = "🚨 ALERTE"
            color = 15158332

        elif contains_keywords(text, IMPORTANT_KEYWORDS):

            tag = "⭐ IMPORTANT"
            color = 15844367

        else:

            tag = "📢 INFORMATION"
            color = 3447003

        # =========================================
        # DESCRIPTION
        # =========================================

        desc = f"{tag}\n📱 Source : {source}"

        if description:

            desc += f"\n\n{description[:250]}"

        # =========================================
        # EMBED DISCORD
        # =========================================

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

# =========================================================
# TRAITEMENT RSS
# =========================================================

def process_rss_feed(feed_url, source):

    sent_count = 0

    try:

        logger.info(f"🔍 Analyse : {source}")

        feed = feedparser.parse(feed_url)

        if feed.bozo:

            logger.warning(f"⚠️ Flux mal formé : {source}")

        for entry in feed.entries[:20]:

            try:

                title = clean_text(entry.get("title", ""))
                description = clean_text(entry.get("summary", ""))
                link = entry.get("link", "")

                # anti doublon
                if not link or link in seen_urls:
                    continue

                # uniquement aujourd'hui
                if not is_today(entry):
                    continue

                # pertinence
                if not is_relevant(f"{title} {description}"):
                    continue

                # Discord
                if send_to_discord(
                    title=title,
                    link=link,
                    source=source,
                    description=description
                ):

                    seen_urls.add(link)
                    sent_count += 1

            except Exception as e:

                logger.error(f"Erreur entrée : {e}")

        return sent_count

    except Exception as e:

        logger.error(f"Erreur flux {source} : {e}")

        return 0

# =========================================================
# MAIN
# =========================================================

def main():

    logger.info("=" * 60)
    logger.info("🚀 Démarrage veille réseaux sociaux")
    logger.info(now_paris().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info("=" * 60)

    total_sent = 0

    # =========================================
    # PARCOURS DES FLUX
    # =========================================

    for feed_config in RSS_FEEDS:

        try:

            count = process_rss_feed(
                feed_config["url"],
                feed_config["source"]
            )

            total_sent += count

        except Exception as e:

            logger.error(f"Erreur critique : {e}")

    # =========================================
    # RÉSUMÉ
    # =========================================

    logger.info("=" * 60)
    logger.info(f"📊 {total_sent} publications détectées")
    logger.info("=" * 60)

    # =========================================
    # FALLBACK
    # =========================================

    if total_sent == 0 and WEBHOOK_URL:

        try:

            requests.post(
                WEBHOOK_URL,
                json={
                    "content": f"✅ Veille réalisée à {now_paris().strftime('%Hh%M')} — pas de nouveaux articles"
                },
                timeout=5
            )

            logger.info("✅ Message statut envoyé")

        except Exception as e:

            logger.error(f"Erreur fallback : {e}")

    # =========================================
    # SAUVEGARDE
    # =========================================

    try:

        with open(SEEN_FILE, "w") as f:

            json.dump(
                list(seen_urls),
                f,
                indent=2
            )

        logger.info(f"💾 {len(seen_urls)} URLs sauvegardées")

    except Exception as e:

        logger.error(f"Erreur sauvegarde : {e}")

# =========================================================
# LANCEMENT
# =========================================================

if __name__ == "__main__":

    main()
