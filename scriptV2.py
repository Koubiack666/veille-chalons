"""
🚀 VEILLE INTELLIGENTE MULTI-SOURCES
Agrège RSS, Reddit, HackerNews, Twitter, YouTube et envoie sur Discord
"""

import feedparser
import requests
import json
import urllib.parse
import re
import os
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Tuple
import logging

# ✅ CONFIGURATION
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBHOOK_CHALONS = os.environ.get("WEBHOOK_CHALONS")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
INVIDIOUS_INSTANCE = os.environ.get("INVIDIOUS_INSTANCE", "https://invidious.io")

SEEN_FILE = "seen.json"
KEYWORDS = [
    "Châlons-en-Champagne",
    "Châlons Agglo",
    "Marne",
    "Champagne-Ardenne"
]

EXCLUDED_KEYWORDS = [
    "reims", "troyes", "epernay", "football", "match", "psg"
]

# ✅ SOURCES RSS CLASSIQUES
RSS_FEEDS = {
    "google_news_territoire": "https://news.google.com/rss/search?q=%28%22Châlons-en-Champagne%22+OR+%22Châlons+Agglo%22%29&hl=fr&gl=FR",
    "google_news_radio": "https://news.google.com/rss/search?q=%28chalons%29+%28radio+OR+%22France+Bleu%22%29&hl=fr",
    "lunion": "https://www.lunion.fr/rss.xml",
    "francebleu": "https://www.francebleu.fr/rss/champagne-ardenne",
    "france3": "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml",
    "francetvinfo": "https://www.francetvinfo.fr/titres.rss",
    "gouvernement_marne": "https://www.marne.gouv.fr/spip.php?page=backend"
}

# ✅ CHAÎNES YOUTUBE À SURVEILLER (RSS)
YOUTUBE_CHANNELS = {
    "france_info": "UCpHMjvKLmhd1b2nRZL2j0Pw",  # Exemple: France Info
    "france3_bourgogne": "UC1234567890abcdef",     # À adapter
    "local_news": "UCxxxxxxxxxxxxxxxxxx"           # Ajoute tes propres chaînes
}

# ✅ SOURCES ALTERNATIVES
ALTERNATIVE_SOURCES = {
    "reddit": {
        "enabled": REDDIT_CLIENT_ID is not None,
        "subreddits": ["france", "Champagne", "ChampagneArdenne", "actualites"],
        "keywords": KEYWORDS
    },
    "hackernews": {
        "enabled": True,
        "url": "https://news.ycombinator.com/api/v0/topstories.json",
        "keywords": KEYWORDS
    },
    "twitter": {
        "enabled": TWITTER_BEARER_TOKEN is not None,
        "query": "Châlons OR Marne",
        "keywords": KEYWORDS
    },
    "invidious": {
        "enabled": True,
        "instance": INVIDIOUS_INSTANCE,
        "keywords": KEYWORDS
    }
}

# ✅ UTILITAIRES
def now_paris():
    return datetime.now(ZoneInfo('Europe/Paris'))

def clean_title(title: str) -> str:
    """Normalise un titre pour clustering"""
    text = re.sub(r'[^\w\s]', '', title.lower())
    return ' '.join(text.split())[:100]

def is_today(timestamp) -> bool:
    """Vérifie si un article est d'aujourd'hui"""
    if isinstance(timestamp, tuple):
        d = datetime(*timestamp[:6])
    elif isinstance(timestamp, datetime):
        d = timestamp
    else:
        return True
    
    now = now_paris()
    return d.date() == now.date()

def is_valid_article(title: str, summary: str = "") -> bool:
    """Filtrage intelligent d'articles"""
    text = (title + " " + summary).lower()
    
    # Exclusions
    for word in EXCLUDED_KEYWORDS:
        if word in text:
            return False
    
    # Au moins un keyword pertinent
    return any(kw.lower() in text for kw in KEYWORDS)

def get_real_url(link: str) -> str:
    """Extrait URL réelle depuis Google News"""
    try:
        parsed = urllib.parse.urlparse(link)
        query = urllib.parse.parse_qs(parsed.query)
        if "url" in query:
            return query["url"][0]
    except:
        pass
    return link

def extract_source(entry: Dict) -> str:
    """Extrait la source d'une entrée"""
    title = entry.get("title", "")
    parts = title.split(" - ")
    
    for part in reversed(parts):
        part = part.strip().lower()
        if "." in part:
            return part
    
    link = entry.get("link", entry.get("url", ""))
    if "://" in link:
        return link.split("/")[2].replace("www.", "")
    
    return "inconnu"

def load_seen_data() -> Tuple[Dict, set]:
    """Charge les articles déjà vus"""
    try:
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
            return data.get("topics", {}), set(data.get("urls", []))
    except:
        return {}, set()

def save_seen_data(topics: Dict, urls: set):
    """Sauvegarde les articles vus"""
    with open(SEEN_FILE, "w") as f:
        json.dump({
            "topics": topics,
            "urls": list(urls),
            "updated": now_paris().isoformat()
        }, f, ensure_ascii=False, indent=2)


# ✅ PARSERS MULTI-SOURCES

class ArticleSource:
    """Format unifié pour les articles"""
    def __init__(self, title: str, url: str, summary: str = "", source: str = "", 
                 published_at: datetime = None, image: str = None):
        self.title = title
        self.url = url
        self.summary = summary
        self.source = source
        self.published_at = published_at or now_paris()
        self.image = image

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "image": self.image
        }


def parse_rss_feeds() -> List[ArticleSource]:
    """Parse tous les flux RSS"""
    articles = []
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            logger.info(f"✅ RSS {source_name}: {len(feed.entries)} entries")
            
            for entry in feed.entries:
                if not is_today(entry.get("published_parsed")):
                    continue
                
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                
                if not is_valid_article(title, summary):
                    continue
                
                real_url = get_real_url(entry.get("link", ""))
                articles.append(ArticleSource(
                    title=title,
                    url=real_url,
                    summary=summary[:200],
                    source=extract_source(entry),
                    published_at=datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else now_paris()
                ))
        except Exception as e:
            logger.error(f"❌ Erreur RSS {source_name}: {e}")
    
    return articles


def parse_youtube_rss() -> List[ArticleSource]:
    """Parse les vidéos YouTube via RSS (API publique gratuite)"""
    articles = []
    
    try:
        for channel_name, channel_id in YOUTUBE_CHANNELS.items():
            # Format RSS officiel YouTube (gratuit, pas d'API key)
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            
            try:
                feed = feedparser.parse(feed_url)
                logger.info(f"✅ YouTube RSS {channel_name}: {len(feed.entries)} vidéos")
                
                for entry in feed.entries:
                    if not is_today(entry.get("published_parsed")):
                        continue
                    
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    
                    if not is_valid_article(title, summary):
                        continue
                    
                    # Format URL YouTube standard
                    video_id = entry.get("id", "").split(":")[-1]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    # Extract thumbnail
                    image = entry.get("media_thumbnail", [{}])[0].get("url") if entry.get("media_thumbnail") else None
                    
                    articles.append(ArticleSource(
                        title=title,
                        url=video_url,
                        summary=summary[:200],
                        source=f"YouTube - {channel_name}",
                        published_at=datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else now_paris(),
                        image=image
                    ))
            except Exception as e:
                logger.error(f"❌ Erreur YouTube RSS {channel_name}: {e}")
    
    except Exception as e:
        logger.error(f"❌ Erreur générale YouTube: {e}")
    
    return articles


def parse_invidious() -> List[ArticleSource]:
    """Parse Invidious API (alternative décentralisée YouTube, API publique)"""
    articles = []
    
    if not ALTERNATIVE_SOURCES["invidious"]["enabled"]:
        return []
    
    try:
        instance = ALTERNATIVE_SOURCES["invidious"]["instance"]
        
        # Recherche sur Invidious (public, pas de clé)
        for keyword in KEYWORDS:
            try:
                params = {
                    "q": keyword,
                    "type": "video",
                    "sort_by": "upload_date",
                    "duration": "long"
                }
                
                response = requests.get(
                    f"{instance}/api/v1/search",
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    for video in response.json()[:15]:  # Limite à 15 résultats
                        title = video.get("title", "")
                        description = video.get("description", "")
                        
                        if not is_valid_article(title, description):
                            continue
                        
                        video_id = video.get("videoId", "")
                        
                        articles.append(ArticleSource(
                            title=title,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            summary=description[:200],
                            source="Invidious",
                            image=video.get("videoThumbnails", [{}])[0].get("url")
                        ))
                        
                logger.info(f"✅ Invidious '{keyword}': {len(articles)} vidéos")
            except Exception as e:
                logger.error(f"❌ Erreur Invidious pour '{keyword}': {e}")
    
    except Exception as e:
        logger.error(f"❌ Erreur générale Invidious: {e}")
    
    return articles


def parse_reddit() -> List[ArticleSource]:
    """Parse Reddit via API officielle"""
    if not ALTERNATIVE_SOURCES["reddit"]["enabled"]:
        return []
    
    articles = []
    
    try:
        auth = requests.auth.HTTPBasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
        headers = {"User-Agent": "Veille-Bot/1.0"}
        
        data = {
            "grant_type": "password",
            "username": os.environ.get("REDDIT_USERNAME"),
            "password": os.environ.get("REDDIT_PASSWORD")
        }
        
        r = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers)
        token = r.json()["access_token"]
        headers["Authorization"] = f"bearer {token}"
        
        for subreddit in ALTERNATIVE_SOURCES["reddit"]["subreddits"]:
            url = f"https://oauth.reddit.com/r/{subreddit}/hot"
            response = requests.get(url, headers=headers, params={"limit": 50})
            
            for post in response.json()["data"]["children"]:
                data = post["data"]
                title = data["title"]
                
                if not is_valid_article(title):
                    continue
                
                articles.append(ArticleSource(
                    title=title,
                    url=f"https://reddit.com{data['permalink']}",
                    summary=data.get("selftext", "")[:200],
                    source=f"r/{subreddit}",
                    image=data.get("thumbnail")
                ))
        
        logger.info(f"✅ Reddit: {len(articles)} articles")
    except Exception as e:
        logger.error(f"❌ Erreur Reddit: {e}")
    
    return articles


def parse_hackernews() -> List[ArticleSource]:
    """Parse HackerNews (articles tech/startups locaux)"""
    articles = []
    
    try:
        response = requests.get(ALTERNATIVE_SOURCES["hackernews"]["url"])
        story_ids = response.json()[:30]
        
        for story_id in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            item = requests.get(item_url).json()
            
            title = item.get("title", "")
            if not is_valid_article(title):
                continue
            
            articles.append(ArticleSource(
                title=title,
                url=item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                summary="",
                source="HackerNews"
            ))
        
        logger.info(f"✅ HackerNews: {len(articles)} articles")
    except Exception as e:
        logger.error(f"❌ Erreur HackerNews: {e}")
    
    return articles


def parse_twitter() -> List[ArticleSource]:
    """Parse Twitter via API v2"""
    if not ALTERNATIVE_SOURCES["twitter"]["enabled"]:
        return []
    
    articles = []
    
    try:
        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
            "User-Agent": "Veille-Bot/1.0"
        }
        
        params = {
            "query": ALTERNATIVE_SOURCES["twitter"]["query"],
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics",
            "expansions": "author_id,attachments.media_keys",
            "media.fields": "preview_image_url",
            "user.fields": "username"
        }
        
        response = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            for tweet in data.get("data", []):
                articles.append(ArticleSource(
                    title=tweet["text"][:200],
                    url=f"https://twitter.com/i/web/status/{tweet['id']}",
                    summary=tweet["text"],
                    source="Twitter"
                ))
            logger.info(f"✅ Twitter: {len(articles)} tweets")
        else:
            logger.warning(f"⚠️ Twitter API: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erreur Twitter: {e}")
    
    return articles


# ✅ AGRÉGATION & CLUSTERING

def aggregate_articles(articles: List[ArticleSource], seen_urls: set) -> Dict[str, List[ArticleSource]]:
    """Agrège les articles par sujet (clustering)"""
    clusters = defaultdict(list)
    
    for article in articles:
        if article.url in seen_urls:
            continue
        
        # Clustering par titre normalisé
        key = clean_title(article.title)
        clusters[key].append(article)
    
    return clusters


# ✅ DISCORD

def get_color_by_importance(count: int) -> int:
    """Détermine la couleur selon l'importance"""
    if count >= 15:
        return 16711680  # 🔴 Rouge
    elif count >= 10:
        return 16776960  # 🟡 Jaune
    elif count >= 5:
        return 16744448  # 🟠 Orange
    else:
        return 3066993   # 🟢 Vert

def get_importance_label(count: int) -> str:
    """Label d'importance"""
    if count >= 15:
        return "🔴 CRITIQUE"
    elif count >= 10:
        return "🔥 Majeur"
    elif count >= 5:
        return "🟠 Important"
    else:
        return "🟢 Mineur"

def send_to_discord(title: str, articles: List[ArticleSource], update: bool = False):
    """Envoie un embed Discord"""
    if not WEBHOOK_CHALONS:
        logger.warning("⚠️ WEBHOOK_CHALONS non défini")
        return
    
    count = len(articles)
    importance = get_importance_label(count)
    color = get_color_by_importance(count)
    
    # Collecte les sources uniques
    sources_set = set()
    for article in articles[:10]:
        sources_set.add(article.source)
    sources_text = "\n".join([f"• {src}" for src in sorted(sources_set)])
    
    # Collecte les URLs
    urls_text = "\n".join([f"[{art.source}]({art.url})" for art in articles[:5]])
    
    embed = {
        "title": ("🔄 MAJ: " if update else "") + title[:256],
        "url": articles[0].url,
        "description": f"{importance}\n\n📊 **{count} articles** • {', '.join(set(art.source for art in articles))}",
        "color": color,
        "fields": [
            {
                "name": "🔗 Sources principales",
                "value": sources_text or "Aucune source",
                "inline": False
            },
            {
                "name": "📰 Premiers articles",
                "value": urls_text or "Aucun lien",
                "inline": False
            }
        ],
        "thumbnail": {
            "url": articles[0].image if articles[0].image else None
        } if articles[0].image else {},
        "footer": {
            "text": f"Veille • {now_paris().strftime('%d/%m %H:%M')}"
        }
    }
    
    try:
        requests.post(WEBHOOK_CHALONS, json={"embeds": [embed]}, timeout=10)
        logger.info(f"✅ Discord: '{title[:50]}' envoyé")
    except Exception as e:
        logger.error(f"❌ Erreur Discord: {e}")


# ✅ MAIN

def main():
    logger.info("🚀 Démarrage de la veille...")
    
    seen_topics, seen_urls = load_seen_data()
    
    # Agrège toutes les sources
    all_articles = []
    all_articles.extend(parse_rss_feeds())
    all_articles.extend(parse_youtube_rss())      # YouTube RSS (API publique)
    all_articles.extend(parse_invidious())         # Invidious (API publique)
    all_articles.extend(parse_reddit())
    all_articles.extend(parse_hackernews())
    all_articles.extend(parse_twitter())
    
    logger.info(f"📊 Total: {len(all_articles)} articles collectés")
    
    # Clustering
    clusters = aggregate_articles(all_articles, seen_urls)
    logger.info(f"🧩 {len(clusters)} clusters trouvés")
    
    sent_count = 0
    
    for key, articles in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(articles)
        
        if key not in seen_topics:
            # Nouveau sujet
            send_to_discord(articles[0].title, articles)
            seen_topics[key] = count
            for art in articles:
                seen_urls.add(art.url)
            sent_count += 1
        
        elif count > seen_topics[key] + 3:
            # Évolution significative
            send_to_discord(articles[0].title, articles, update=True)
            seen_topics[key] = count
            for art in articles:
                seen_urls.add(art.url)
            sent_count += 1
    
    # Fallback
    if sent_count == 0:
        requests.post(
            WEBHOOK_CHALONS,
            json={"content": f"✅ Veille OK — {len(all_articles)} articles analysés, aucune nouveauté ({now_paris().strftime('%H:%M')})"},
            timeout=10
        )
    
    save_seen_data(seen_topics, seen_urls)
    logger.info(f"✅ Veille terminée ({sent_count} notifications)")


if __name__ == "__main__":
    main()
