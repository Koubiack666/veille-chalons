import feedparser
import requests
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json
import re
import urllib.parse

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
SEEN_FILE = "seen.json"

# ========================================================
# SOURCES RSS
# ========================================================

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Ch%C3%A2lons+Agglo%22%29&hl=fr&gl=FR&ceid=FR:fr",
    "https://www.lunion.fr/rss.xml",
    "https://www.francebleu.fr/rss/champagne-ardenne",
    "https://france3-regions.francetvinfo.fr/rss/champagne-ardenne.xml",
    "https://www.francetvinfo.fr/titres.rss",
    "https://www.marne.gouv.fr/spip.php?page=backend"
    "https://www.lunion.fr/rss/115/cible_principale"
    "https://www.lunion.fr/rss/157257/cible_principale"
    "https://bm.chalonsenchampagne.fr/plui/actualites?format=feed&type=rs"
    "https://news.google.com/rss/search?q=(CNAC OR PALC OR Furies OR "arts du cirque")"
    "https://news.google.com/rss/search?q=("Châlons-en-Champagne")"
    "https://news.google.com/rss/search?q=("Achille Bisiaux" OR "Bisiaux Achille)"
    "https://news.google.com/rss/search?q=("Saint-Memmie" OR Fagnières OR Sarry OR Recy)"
    
]

# ========================================================
# CATÉGORIES
# ========================================================

CATEGORIES = {

    "🏘️ Communes Agglo": [
        "aigny", "aulnay-sur-marne", "baconnes", "bouy",
        "bussy-lettrée", "champigneul-champagne",
        "cheniers", "cherville", "compertrix",
        "condé-sur-marne", "coolus",
        "la neuville-au-temple",
        "dommartin-lettrée", "l'épine", "lepine",
        "fagnières", "les grandes-loges",
        "haussimont", "isse", "jâlons", "jalons",
        "juvigny", "lenharrée", "livry-louvercy",
        "matougues", "moncetz-longevas",
        "montépreux", "montepreux",
        "mourmelon-le-grand", "mourmelon-le-petit",
        "recy", "saint-étienne-au-temple",
        "saint etienne au temple",
        "saint-gibrien", "saint-martin-sur-le-pré",
        "saint-memmie", "saint-pierre",
        "sarry", "sommesous",
        "soudé", "soude", "soudron",
        "thibie", "vadenay",
        "vassimont-et-chapelaine",
        "vatry", "la veuve",
        "villers-le-château", "vraux"
    ],

    "🎪 Arts du cirque / CNAC / PALC / Furies": [
        "cirque",
        "cnac",
        "centre national des arts du cirque",
        "palc",
        "pole national des arts du cirque",
        "spectacle de rue",
        "theatre de rue",
        "festival du cirque",
        "furies"
    ],

    "🚨 Sécurité": [
        "accident",
        "incendie",
        "urgence",
        "police"
    ],

    "🏛️ Politique": [
        "maire",
        "élu",
        "conseil",
        "municipales",
        "apparu",
        "jesson",
        "bisiaux"
    ],

    "🎉 Événement": [
        "festival",
        "concert",
        "événement",
        "sport",
        "culture"
    ],

    "📊 Économie": [
        "entreprise",
        "emploi",
        "investissement"
    ]
}

EXCLUDED_KEYWORDS = [
    "reims",
    "troyes",
    "epernay",
    "football",
    "psg"
]

# ========================================================
# MÉMOIRE
# ========================================================

try:
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_urls = set(json.load(f))
except Exception:
    seen_urls = set()

initial_seen_urls = seen_urls.copy()



# ========================================================
# FONCTIONS
# ========================================================

def now_paris():
    return datetime.now(ZoneInfo("Europe/Paris"))

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""

def is_today(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        d = datetime(*entry.published_parsed[:6])
        return d.date() == now_paris().date()
    return True

def is_valid(entry):
    text = (
        entry.get("title", "") +
        " " +
        entry.get("summary", "")
    ).lower()

    return not any(word in text for word in EXCLUDED_KEYWORDS)

def categorize(text):
    text = text.lower()

    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "📰 Autres"

def get_real_url(entry):
    link = entry.get("link", "")

    try:
        parsed = urllib.parse.urlparse(link)
        query = urllib.parse.parse_qs(parsed.query)

        if "url" in query:
            return query["url"][0]

    except Exception:
        pass

    return link

# ========================================================
# DISCORD WEBHOOK
# ========================================================

def send_summary(total, category_count):

    lines = []

    for category, count in sorted(
        category_count.items(),
        key=lambda x: -x[1]
    ):
        lines.append(f"{category} : {count}")

    payload = {
        "content":
            f"📊 **Rapport de veille**\n"
            f"{total} articles détectés\n\n"
            f"{chr(10).join(lines)}"
    }

    requests.post(WEBHOOK_URL, json=payload, timeout=30)

def send_article(title, link, source, category):

    embed = {
        "title": title,
        "url": link,
        "description": f"{category}\nSource : {source}",
        "color": 3447003,
        "footer": {
            "text": f"Veille • {now_paris().strftime('%d/%m %H:%M')}"
        }
    }

    requests.post(
        WEBHOOK_URL,
        json={"embeds": [embed]},
        timeout=30
    )

# ========================================================
# TRAITEMENT
# ========================================================

articles = []
category_count = defaultdict(int)

for feed_url in RSS_FEEDS:

    try:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:

            if not is_today(entry):
                continue

            if not is_valid(entry):
                continue

            url = get_real_url(entry)

            if url in seen_urls:
                continue

            title = clean_text(entry.get("title", ""))

            category = categorize(
                title + " " + entry.get("summary", "")
            )

            articles.append({
                "title": title,
                "url": url,
                "source": feed.feed.get("title", feed_url),
                "category": category
            })

            category_count[category] += 1
            seen_urls.add(url)

    except Exception as e:
        print(f"Erreur flux RSS {feed_url}: {e}")

# ========================================================
# ENVOI
# ========================================================

if articles:

    send_summary(
        len(articles),
        category_count
    )

    for article in articles:

        send_article(
            article["title"],
            article["url"],
            article["source"],
            article["category"]
        )

else:

    requests.post(
        WEBHOOK_URL,
        json={
            "content":
            f"✅ Veille réalisée à "
            f"{now_paris().strftime('%Hh%M')} "
            f"— aucun nouvel article"
        },
        timeout=30
    )

# ========================================================
# SAUVEGARDE
# ========================================================


if seen_urls != initial_seen_urls:

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            sorted(seen_urls),
            f,
            ensure_ascii=False,
            indent=2
        )
