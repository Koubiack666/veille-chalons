import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime

WEBHOOK_URL = "https://discord.com/api/webhooks/1512008622610317454/cO80pEoNrgP3Ak0hXnqiAUqdRyi3j3mps5HPOwrB6gmGsczaUbg79GBf3c1bdXsKuABK"

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29&hl=fr&gl=FR&ceid=FR:fr"

def clean_title(title):
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    return title

def send_to_discord(message):
    requests.post(WEBHOOK_URL, json={"content": message})

feed = feedparser.parse(RSS_URL)

clusters = defaultdict(list)

for entry in feed.entries:
    key = clean_title(entry.title)[:80]
    clusters[key].append(entry)

for key, articles in clusters.items():

    nb = len(articles)
    main = articles[0]

    sources = {}

    for art in articles:
        src = getattr(art, "source", {}).get("title", "inconnu") if hasattr(art, "source") else "inconnu"
        sources[src] = sources.get(src, 0) + 1

    top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]

    sources_txt = ", ".join([f"{s} ({c})" for s,c in top_sources])

    message = f"""
📰 VEILLE CHÂLONS – {datetime.now().strftime('%d/%m %H:%M')}

**{main.title}**

🧠 {nb} articles sur ce sujet

📊 Sources principales :
{sources_txt}

🔗 {main.link}
"""

    send_to_discord(message)
