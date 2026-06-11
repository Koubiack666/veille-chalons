import feedparser
import requests
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import re

WEBHOOK_URL = os.environ.get("WEBHOOK_SOCIAL")
SEEN_FILE = "seen_social.json"

# ========================================================
# REDDIT UNIQUEMENT
# ========================================================

RSS_FEEDS = [

    "https://www.reddit.com/r/france/search.rss?q=chalons&sort=new",
    "https://www.reddit.com/r/grandest/search.rss?q=chalons&sort=new"
]

# ========================================================
# CATÉGORIES
# ========================================================

CATEGORIES = {

    "🏘️ Communes Agglo": [
        "aigny","aulnay-sur-marne","baconnes","bouy","bussy-lettrée",
        "champigneul-champagne","cheniers","cherville","compertrix",
        "condé-sur-marne","coolus","la neuville-au-temple",
        "dommartin-lettrée","l'épine","lepine","fagnières",
        "grandes-loges","haussimont","isse","jâlons","jalons",
        "juvigny","lenharrée","livry-louvercy","matougues",
        "moncetz-longevas","montépreux","montepreux",
        "mourmelon-le-grand","mourmelon-le-petit",
        "recy","saint-étienne-au-temple","saint-gibrien",
        "saint-martin-sur-le-pré","saint-memmie",
        "saint-pierre","sarry","sommesous",
        "soudé","soude","soudron","thibie","vadenay",
        "vassimont-et-chapelaine","vatry","la veuve",
        "villers-le-château","vraux"
    ],

    "🎪 Arts du cirque / CNAC / PALC / Furies": [
        "cirque", "cnac", "centre national des arts du cirque",
        "palc", "pole national des arts du cirque",
        "spectacle de rue", "theatre de rue",
        "festival du cirque", "furies"
    ],

    "🚨 Sécurité": [
        "accident", "incendie", "urgence", "police"
    ],

    "🏛️ Politique": [
        "maire", "élu", "conseil", "municipales",
        "apparu", "jesson"
    ],

    "🎉 Événement": [
        "festival", "concert", "événement", "sport", "culture"
    ],

    "📊 Économie": [
        "entreprise", "emploi", "investissement"
    ]
}

SEARCH_KEYWORDS = [
    "chalons",
    "châlons",
    "chalons en champagne",
    "chalons agglo",
    "apparu",
    "jesson"
]

EXCLUDED_KEYWORDS = [
    "crypto", "bitcoin", "nft", "trading"
]

# ========================================================
# MÉMOIRE
# ========================================================

try:
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
except:
    seen_urls = set()

# ========================================================
# UTILS
# ========================================================

def now_paris():
    return datetime.now(ZoneInfo("Europe/Paris"))

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip() if text else ""

def contains_keywords(text, keywords):
    text = text.lower()
    return any(k in text for k in keywords)

def is_relevant(text):
    text = text.lower()
    return contains_keywords(text, SEARCH_KEYWORDS) and not contains_keywords(text, EXCLUDED_KEYWORDS)

def categorize(text):

    text = text.lower()

    for cat, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            return cat

    return "📰 Autres"

# ========================================================
# DISCORD
# ========================================================

def send_summary(total, category_count):

    lines = []

    for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
        lines.append(f"{cat} : {count}")

    message = {
        "content":
        f"📱 **Rapport Réseaux (Reddit)**\n"
        f"{total} publications détectées\n\n"
        f"{chr(10).join(lines)}"
    }

    requests.post(WEBHOOK_URL, json=message)

def send_post(title, link, category):

    embed = {
        "title": title,
        "url": link,
        "description": f"{category} Reddit",
        "color": 15105570,
        "footer": {
            "text": f"Veille Reddit • {now_paris().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(WEBHOOK_URL, json={"embeds": [embed]})

# ========================================================
# TRAITEMENT
# ========================================================

posts = []
category_count = defaultdict(int)

for feed_url in RSS_FEEDS:

    feed = feedparser.parse(feed_url)

    for entry in feed.entries:

        link = entry.get("link", "")
        title = clean_text(entry.get("title", ""))

        if not link or link in seen_urls:
            continue

        if not is_relevant(title):
            continue

        category = categorize(title)

        posts.append({
            "title": title,
            "link": link,
            "category": category
        })

        category_count[category] += 1
        seen_urls.add(link)

# ========================================================
# DISCORD
# ========================================================

if posts:

    send_summary(len(posts), category_count)

    for post in posts:
        send_post(
            post["title"],
            post["link"],
            post["category"]
        )

else:

    requests.post(
        WEBHOOK_URL,
        json={
            "content": f"✅ Veille Reddit réalisée à {now_paris().strftime('%Hh%M')} — aucun nouveau contenu"
        }
    )

# ========================================================
# SAUVEGARDE
# ========================================================

with open(SEEN_FILE, "w") as f:
    json.dump(list(seen_urls), f)
