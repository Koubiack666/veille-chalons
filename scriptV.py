import feedparser
import requests
from collections import defaultdict
import re
from datetime import datetime
import os

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

RSS_URL = "https://news.google.com/rss/search?q=%28%22Ch%C3%A2lons-en-Champagne%22+OR+%22Chalons+Champagne%22%29&hl=fr&gl=FR&ceid=FR:fr"

def clean_title(title):
    return re.sub(r'[^\w\s]', '', title.lower())

def extract_image(entry):
    # 1. Essayer media_content
    if "media_content" in entry:
        return entry.media_content[0]["url"]

    # 2. Essayer dans le résumé HTML
    if "summary" in entry:
        match = re.search(r'art.get("source", name = src.get("title", "inconnu")
        sources[name] = sources.get(name, 0) + 1

    top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]
    sources_txt = ", ".join([f"{s} ({c})" for s,c in top_sources])

    image_url = extract_image(main)

    send_to_discord(
        title=main.get("title", "Sans titre"),
        link=main.get("link", ""),
        sources_txt=sources_txt,
        nb=nb,
        image_url=image_url
    )
