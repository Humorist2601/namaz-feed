#!/usr/bin/env python3
"""Build an RSS feed of daily namaz timings from the Aladhan API.

Stateless: every run regenerates the last DAYS days (today included),
so RSS readers always see a short rolling window of daily items.
Standard library only.
"""
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# ---- Settings (override with environment variables if you like) ----
CITY = os.environ.get("CITY", "Quetta")
COUNTRY = os.environ.get("COUNTRY", "Pakistan")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Karachi")
METHOD = os.environ.get("METHOD", "1")   # 1 = University of Islamic Sciences, Karachi
SCHOOL = os.environ.get("SCHOOL", "1")   # 1 = Hanafi Asr, 0 = Shafi'i
DAYS = int(os.environ.get("DAYS", "7"))
FEED_URL = os.environ.get("FEED_URL", "")  # e.g. https://<user>.github.io/<repo>/feed.xml
OUT = os.environ.get("OUT", "public/feed.xml")

PRAYERS = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
HIJRI_MONTHS = ["Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani",
                "Jumada al-Ula", "Jumada al-Akhirah", "Rajab", "Shaban",
                "Ramadan", "Shawwal", "Dhul Qadah", "Dhul Hijjah"]
FEED_TITLE = f"Namaz Timings ({CITY})"
SITE_URL = FEED_URL.rsplit("/", 1)[0] + "/" if FEED_URL else ""
ICON_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
API = "https://api.aladhan.com/v1/timingsByCity/{date}?{query}"


def fetch_day(day):
    query = urllib.parse.urlencode({
        "city": CITY, "country": COUNTRY, "method": METHOD,
        "school": SCHOOL, "timezonestring": TIMEZONE,
    })
    url = API.format(date=day.strftime("%d-%m-%Y"), query=query)
    req = urllib.request.Request(url, headers={"User-Agent": "namaz-rss/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("code") != 200:
        raise RuntimeError(f"API error for {day}: {payload}")
    return payload["data"]


def fmt_time(hhmm):
    return hhmm.split(" ")[0]  # 24-hour HH:MM; drop any " (PKT)" suffix


def build_item(day, data, tz):
    t = data["timings"]
    h = data["date"]["hijri"]
    hijri_month = HIJRI_MONTHS[int(h["month"]["number"]) - 1]
    hijri = f'{int(h["day"])} {hijri_month} {h["year"]} AH'

    title = f'{day.day} {day:%b} · {int(h["day"])} {hijri_month}'
    rows = "".join(
        f"<tr><td><b>{p}</b></td><td>{fmt_time(t[p])}</td></tr>" for p in PRAYERS
    )
    html = f"<p>{day:%A}, {day.day} {day:%B %Y} · {hijri}</p><table>{rows}</table>"

    pub = datetime(day.year, day.month, day.day, tzinfo=tz)
    guid = f"namaz-{CITY.lower()}-{day.isoformat()}"
    link = FEED_URL + "#" + day.isoformat() if FEED_URL else ""
    return f"""    <item>
      <title>{escape(title)}</title>
      <description><![CDATA[{html}]]></description>
      <pubDate>{format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">{guid}</guid>{f'''
      <link>{escape(link)}</link>''' if link else ''}
    </item>"""


def main():
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    items = []
    for i in range(DAYS):
        day = today - timedelta(days=i)
        try:
            items.append(build_item(day, fetch_day(day), tz))
        except Exception as e:  # keep going; today is what matters most
            print(f"warning: {day}: {e}", file=sys.stderr)
            if i == 0:
                raise

    now = format_datetime(datetime.now(tz))
    self_link = (f'\n    <atom:link href="{escape(FEED_URL)}" rel="self" '
                 f'type="application/rss+xml"/>') if FEED_URL else ""
    image = (f"""
    <image>
      <url>{escape(SITE_URL)}icon.png</url>
      <title>{escape(FEED_TITLE)}</title>
      <link>{escape(SITE_URL)}</link>
      <width>144</width>
      <height>144</height>
    </image>""") if SITE_URL else ""
    desc = f"Daily prayer times for {CITY}, {COUNTRY}"
    if METHOD == "1" and SCHOOL == "1":
        desc += " (Karachi method, Hanafi Asr)"
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(SITE_URL or "https://aladhan.com")}</link>
    <description>{escape(desc)}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>{self_link}{image}
{chr(10).join(items)}
  </channel>
</rss>
"""
    out_dir = os.path.dirname(OUT) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(feed)

    # Small home page + icons so readers that use the site favicon pick it up too
    if os.path.exists(ICON_SRC):
        shutil.copy(ICON_SRC, os.path.join(out_dir, "icon.png"))
        shutil.copy(ICON_SRC, os.path.join(out_dir, "apple-touch-icon.png"))
        svg = ICON_SRC[:-3] + "svg"
        if os.path.exists(svg):
            shutil.copy(svg, os.path.join(out_dir, "favicon.svg"))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(FEED_TITLE)}</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="icon" type="image/png" href="icon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{escape(FEED_TITLE)}" href="feed.xml">
</head><body style="font-family:sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem">
<h1>{escape(FEED_TITLE)}</h1><p>{escape(desc)}.</p>
<p>Subscribe: <a href="feed.xml">feed.xml</a></p></body></html>
""")
    print(f"wrote {OUT} with {len(items)} items")


if __name__ == "__main__":
    main()
