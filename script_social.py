import feedparser
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import logging
from urllib.parse import quote
from bs4 import BeautifulSoup
import re

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")
SEEN_FILE = "seen_social.json"

# Mots-clés de recherche
SEARCH_KEYWORDS = [
    "Châlons-en-Champagne",
    "Châlons-Agglo",
    "chalons agglo",
    "chalons-en-champagne",
    "chalons champagne",
    "@chalonsagglo"
]

# Sources RSS : feeds publiques et gratuites
RSS_FEEDS = [
    # X/Twitter via Nitter (instances publiques)
    {
        "url": "https://nitter.net/chalonsagglo/rss",
        "source": "X / Twitter",
        "type": "rss"
    },
    {
        "url": "https://nitter.poast.org/chalonsagglo/rss",
        "source": "X / Twitter (Mirror)",
        "type": "rss"
    },
    # Mastodon instances publiques (Châlons, Champagne-Ardenne)
    {
        "url": "https://mastodon.online/@chalonsagglo/feed.rss",
        "source": "Mastodon",
        "type": "rss"
    },
    # Bluesky RSS (via feedproxy)
    {
        "url": "https://bsky.app/profile/chalonsagglo.bsky.social/feed/rss",
        "source": "Bluesky",
        "type": "rss"
    },
    # Instagram via Picuki (pas de RSS officiel, mais accessible)
    # Note: Remplacer par le compte Instagram réel si disponible
    # YouTube - Canal officiel Châlons-Agglo si disponible
    {
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCH1L5Wz9P2d9_3XDkYpfMQQ",
        "source": "YouTube",
        "type": "rss"
    },
    # TikTok - via rss.inoreader.com (agrégateur public)
    {
        "url": "https://www.rss-engine.com/search/?q=chalonsagglo",
        "source": "Réseaux Sociaux (Agrégé)",
        "type": "rss"
    },
    # Google Actualités RSS
    {
        "url": f"https://news.google.com/rss/search?q={quote('Châlons-en-Champagne OR Châlons-Agglo')}&ceid=FR:fr",
        "source": "Google Actualités",
        "type": "rss"
    },
    # Bing Actualités RSS
    {
        "url": f"https://www.bing.com/news/search?q={quote('Châlons-en-Champagne Châlons-Agglo')}&format=rss",
        "source": "Bing Actualités",
        "type": "rss"
    },
    # Lemmy (Fédéverse)
    {
        "url": "https://lemmy.ml/feeds/r/france.rss",
        "source": "Lemmy - France",
        "type": "rss"
    },
    # Reddit (si la communauté Champagne-Ardenne existe)
    {
        "url": "https://www.reddit.com/r/france/search?q=chalons&sort=new&restrict_sr=on&limit=100",
        "source": "Reddit",
        "type": "rss"
    },
    # Wikipedia Actualités (actuellement Châlons)
    {
        "url": "https://en.m.wikipedia.org/w/api.php?action=query&list=recentchanges&rctitle=Châlons-en-Champagne&rcnamespace=0&format=json",
        "source": "Wikipedia",
        "type": "json"
    },
]

IMPORTANT_KEYWORDS = [
    "projet", "lancement", "inauguration",
    "nouveau", "événement", "ouverture", "création",
    "investissement", "développement", "infrastructure",
    "transport", "école", "santé", "culture", "sport",
    "initiative", "programme", "rénovation"
]

ALERT_KEYWORDS = [
    "incident", "problème", "fermeture",
    "alerte", "annulation", "urgence", "accident",
    "crise", "situation d'urgence", "perturbation",
    "grève", "blocage", "danger", "risque"
]

EXCLUDED_KEYWORDS = [
    "jeu", "concours", "spam", "publicité",
    "crypto", "bitcoin", "nft", "trading"
]

# Charger historique
try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
except FileNotFoundError:
    seen_urls = set()
    logger.info("Fichier seen_social.json créé")


def clean_text(text):
    """Nettoie le texte"""
    if not text:
        return ""
    return text.replace("\n", " ").strip()


def contains_keywords(text, keywords):
    """Vérifie si le texte contient les mots-clés"""
    if not text:
        return False
    text_lower = text.lower()
    return any(word.lower() in text_lower for word in keywords)


def is_today(entry):
    """Vérifie si l'entrée est d'aujourd'hui"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            d = datetime(*entry.published_parsed[:6])
            now = datetime.now(ZoneInfo("Europe/Paris"))
            
            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )
        except (TypeError, ValueError):
            return False
    
    # Fallback : vérifier la clé 'updated'
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            d = datetime(*entry.updated_parsed[:6])
            now = datetime.now(ZoneInfo("Europe/Paris"))
            
            return (
                d.year == now.year and
                d.month == now.month and
                d.day == now.day
            )
        except (TypeError, ValueError):
            return False
    
    return False


def is_relevant(text):
    """Vérifie si le contenu est pertinent pour Châlons"""
    if not text:
        return False
    text_lower = text.lower()
    
    # Vérifier si contient keywords de recherche
    has_relevant_keywords = any(
        keyword.lower() in text_lower for keyword in SEARCH_KEYWORDS
    )
    
    # Exclure si contient mots exclus
    if contains_keywords(text, EXCLUDED_KEYWORDS):
        return False
    
    return has_relevant_keywords


def extract_image_url(entry, original_link):
    """Extrait l'URL de l'image de l'article original, pas de Google/Bing"""
    image_url = None
    
    try:
        # 1. Chercher dans les médias de l'entrée RSS
        if hasattr(entry, "media_content"):
            for media in entry.media_content:
                if media.get("medium") == "image":
                    return media.get("url")
        
        # 2. Chercher dans les liens media_thumbnail
        if hasattr(entry, "media_thumbnail"):
            for thumb in entry.media_thumbnail:
                if "url" in thumb:
                    image_url = thumb.get("url")
                    break
        
        # 3. Chercher dans les tags image du summary
        if hasattr(entry, "summary") and entry.summary:
            soup = BeautifulSoup(entry.summary, "html.parser")
            img_tag = soup.find("img")
            if img_tag and img_tag.get("src"):
                candidate_url = img_tag.get("src")
                # Vérifier que ce n'est pas une image de Google/Bing
                if not any(domain in candidate_url.lower() for domain in ["google", "gstatic", "bing", "msn"]):
                    image_url = candidate_url
        
        # 4. Essayer de scraper l'article original si on a le lien
        if not image_url and original_link:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = requests.get(original_link, timeout=5, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # Chercher open graph image
                    og_image = soup.find("meta", property="og:image")
                    if og_image and og_image.get("content"):
                        return og_image.get("content")
                    
                    # Chercher twitter:image
                    twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
                    if twitter_image and twitter_image.get("content"):
                        return twitter_image.get("content")
                    
                    # Chercher la première image pertinente
                    img_tag = soup.find("img", attrs={"alt": re.compile(".*", re.I)})
                    if img_tag and img_tag.get("src"):
                        img_src = img_tag.get("src")
                        # Convertir URL relative en absolute
                        if img_src.startswith("http"):
                            return img_src
                        elif img_src.startswith("/"):
                            from urllib.parse import urljoin
                            return urljoin(original_link, img_src)
            except Exception as e:
                logger.debug(f"Erreur lors du scraping d'image : {e}")
        
        return image_url
        
    except Exception as e:
        logger.debug(f"Erreur extraction image : {e}")
        return None


def send_to_discord(title, link, source, description="", image_url=""):
    """Envoie une notification Discord avec image"""
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL non configurée")
        return False
    
    try:
        text = title.lower() if title else ""
        
        if contains_keywords(text, ALERT_KEYWORDS):
            tag = "🚨 ALERTE"
            color = 15158332  # Rouge
        elif contains_keywords(text, IMPORTANT_KEYWORDS):
            tag = "⭐ IMPORTANT"
            color = 15844367  # Orange
        else:
            tag = "📢 INFORMATION"
            color = 3447003   # Bleu
        
        now_paris = datetime.now(ZoneInfo("Europe/Paris"))
        
        desc = f"{tag}\n📱 Source : {source}"
        if description:
            desc += f"\n\n{description[:200]}"  # Limiter à 200 chars
        
        embed = {
            "title": title[:256] if title else "Sans titre",
            "url": link if link else None,
            "description": desc,
            "color": color,
            "footer": {
                "text": f"Veille Réseaux • {now_paris.strftime('%d/%m %H:%M')}"
            }
        }
        
        # Ajouter l'image si trouvée
        if image_url:
            embed["image"] = {
                "url": image_url
            }
            logger.info(f"📸 Image détectée : {image_url[:80]}")
        
        response = requests.post(
            WEBHOOK_URL,
            json={"embeds": [embed]},
            timeout=5
        )
        
        if response.status_code == 204:
            logger.info(f"✅ Post envoyé : {title[:50]}")
            return True
        else:
            logger.error(f"Erreur Discord : {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi Discord : {e}")
        return False


def process_rss_feed(feed_url, source):
    """Traite un flux RSS"""
    sent_count = 0
    try:
        logger.info(f"Traitement du flux : {source}")
        feed = feedparser.parse(feed_url)
        
        if feed.bozo:
            logger.warning(f"⚠️ Flux mal formé ({source}): {feed.bozo_exception}")
        
        for entry in feed.entries[:20]:  # Limiter à 20 entrées par flux
            try:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                description = clean_text(entry.get("summary", ""))
                
                # Vérifications
                if not link or link in seen_urls:
                    continue
                
                if not is_today(entry):
                    continue
                
                if not is_relevant(f"{title} {description}"):
                    continue
                
                # Extraire l'image de l'article original
                image_url = extract_image_url(entry, link)
                
                # Envoyer vers Discord
                if send_to_discord(title, link, source, description, image_url):
                    seen_urls.add(link)
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Erreur traitement entrée : {e}")
                continue
        
        return sent_count
        
    except Exception as e:
        logger.error(f"Erreur traitement flux {source} : {e}")
        return 0


def main():
    """Fonction principale"""
    logger.info("=" * 60)
    logger.info("🔍 Démarrage de la veille réseaux sociaux")
    logger.info(f"⏰ {datetime.now(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 60)
    
    total_sent = 0
    successful_feeds = 0
    
    for feed_config in RSS_FEEDS:
        try:
            feed_url = feed_config["url"]
            source = feed_config["source"]
            
            sent = process_rss_feed(feed_url, source)
            total_sent += sent
            
            if sent > 0:
                successful_feeds += 1
                
        except Exception as e:
            logger.error(f"Erreur critique sur {feed_config['source']} : {e}")
            continue
    
    # Résumé
    logger.info("=" * 60)
    logger.info(f"📊 Résumé : {total_sent} posts envoyés sur {len(RSS_FEEDS)} sources")
    logger.info("=" * 60)
    
    # Message de statut si rien n'a été envoyé
    if total_sent == 0 and WEBHOOK_URL:
        try:
            now_paris = datetime.now(ZoneInfo("Europe/Paris"))
            requests.post(
                WEBHOOK_URL,
                json={
                    "content": f"✅ Veille sociale OK — aucun nouveau post ({now_paris.strftime('%H:%M')})"
                },
                timeout=5
            )
            logger.info("✅ Message de statut envoyé")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message de statut : {e}")
    
    # Sauvegarder l'historique
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_urls), f, indent=2)
        logger.info(f"💾 Historique sauvegardé ({len(seen_urls)} URLs)")
    except Exception as e:
        logger.error(f"Erreur sauvegarde : {e}")


if __name__ == "__main__":
    main()
