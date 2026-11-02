#!/usr/bin/env python3
"""Build an RSS feed of daily namaz timings from the Aladhan API.

Stateless: every run regenerates the last DAYS days (today included),
so RSS readers always see a short rolling window of daily items.
Standard library only.
"""
import json
import os
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


def to_12h(hhmm):
    hhmm = hhmm.split(" ")[0]  # drop any " (PKT)" suffix
    return datetime.strptime(hhmm, "%H:%M").strftime("%-I:%M %p")


def build_item(day, data, tz):
    t = data["timings"]
    h = data["date"]["hijri"]
    hijri = f'{h["day"]} {h["month"]["en"]} {h["year"]} AH'
    date_str = day.strftime("%A, %d %B %Y")

    rows = "".join(
        f"<tr><td><b>{p}</b></td><td>{to_12h(t[p])}</td></tr>" for p in PRAYERS
    )
    html = f"<p>{date_str} · {hijri}</p><table>{rows}</table>"
    plain = " · ".join(f"{p} {to_12h(t[p])}" for p in PRAYERS)

    pub = datetime(day.year, day.month, day.day, tzinfo=tz)
    guid = f"namaz-{CITY.lower()}-{day.isoformat()}"
    link = FEED_URL + "#" + day.isoformat() if FEED_URL else ""
    return f"""    <item>
      <title>{escape(f"Namaz timings – {CITY} – {date_str}")}</title>
      <description><![CDATA[{html}<p>{plain}</p>]]></description>
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
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(f"Namaz timings – {CITY}")}</title>
    <link>{escape(FEED_URL or "https://aladhan.com")}</link>
    <description>{escape(f"Daily prayer times for {CITY}, {COUNTRY} (Karachi method, Hanafi Asr)" if METHOD == "1" and SCHOOL == "1" else f"Daily prayer times for {CITY}, {COUNTRY}")}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>{self_link}
{chr(10).join(items)}
  </channel>
</rss>
"""
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"wrote {OUT} with {len(items)} items")


if __name__ == "__main__":
    main()
