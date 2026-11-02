#!/usr/bin/env python3
"""Build an RSS feed of daily namaz timings from the Aladhan API.

To use a different city, edit the settings below. If TIMEZONE is left empty
it is detected from the city automatically.

Stateless: every run regenerates the last DAYS days. From NEXT_DAY_FROM
(9 PM) onward the newest item is tomorrow, so the next day's timings
arrive the evening before.
Standard library only.
"""
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo


# ---- Settings: edit these to change the city ----
CITY = "Quetta"
COUNTRY = "Pakistan"
TIMEZONE = ""      # empty = detect from the city, or e.g. "Asia/Karachi"
METHOD = "1"       # 1 Karachi, 2 ISNA, 3 Muslim World League, 4 Umm al-Qura, 5 Egypt
SCHOOL = "1"       # Asr: 1 = Hanafi, 0 = Shafi'i
DAYS = 7           # how many recent days the feed keeps
NEXT_DAY_FROM = 21 # from this hour (local time), the newest item is tomorrow

# Set automatically by the GitHub workflow; no need to edit.
FEED_URL = os.environ.get("FEED_URL", "")
OUT = os.environ.get("OUT", "public/feed.xml")

HIJRI_MONTHS = ["Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani",
                "Jumada al-Ula", "Jumada al-Akhirah", "Rajab", "Shaban",
                "Ramadan", "Shawwal", "Dhul Qadah", "Dhul Hijjah"]
FEED_TITLE = f"Namaz Timings ({CITY})"
SITE_URL = FEED_URL.rsplit("/", 1)[0] + "/" if FEED_URL else ""
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PNG = os.path.join(HERE, "assets", "icon.png")
API = "https://api.aladhan.com/v1/timingsByCity/{date}?{query}"


def fetch_day(day, tz_name=None):
    params = {"city": CITY, "country": COUNTRY, "method": METHOD, "school": SCHOOL}
    if tz_name:
        params["timezonestring"] = tz_name
    url = API.format(date=day.strftime("%d-%m-%Y"), query=urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": "namaz-rss/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("code") != 200:
        raise RuntimeError(f"API error for {day}: {payload}")
    return payload["data"]


def hm(value):
    """'05:25 (PKT)' -> '05:25' (24-hour)."""
    return value.split(" ")[0]


def minutes(value):
    h, m = hm(value).split(":")
    return int(h) * 60 + int(m)


def row(label, time, note="", dim=False):
    text = f"{label} <small>({note})</small>" if note else label
    if dim:
        text, time = f"<i>{text}</i>", f"<i>{time}</i>"
    else:
        text = f"<b>{text}</b>"
    # Fixed name-column width: some readers (Brief You) make each table row its own block,
    # so without it the times don't line up in a column.
    return (f'<tr><td style="padding:2px 24px 2px 0;width:7em;min-width:7em">{text}</td>'
            f'<td align="right" style="padding:2px 0;font-variant-numeric:tabular-nums">{time}</td></tr>')


def card_for(day, data):
    """The HTML for this day's card image (see card.py)."""
    import card

    t = data["timings"]
    h = data["date"]["hijri"]
    month_no = int(h["month"]["number"])
    ramadan = month_no == 9
    friday = day.weekday() == 4
    prayers = [
        ("Fajr", hm(t["Fajr"]), "Sehri ends" if ramadan else ""),
        ("Jumu'ah" if friday else "Dhuhr", hm(t["Dhuhr"]), ""),
        ("Asr", hm(t["Asr"]), ""),
        ("Maghrib", hm(t["Maghrib"]), "Iftar" if ramadan else ""),
        ("Isha", hm(t["Isha"]), ""),
    ]
    length = (minutes(t["Sunset"]) - minutes(t["Sunrise"])) % (24 * 60)
    extras = [("Sunrise", hm(t["Sunrise"])), ("Sunset", hm(t["Sunset"])),
              ("Midnight", hm(t["Midnight"])), ("Tahajjud", hm(t["Lastthird"])),
              ("Day", f"{length // 60}h {length % 60:02d}m")]
    hijri = f'{int(h["day"])} {HIJRI_MONTHS[month_no - 1]} {h["year"]} AH'
    return card.card_html(CITY, f"{day:%A}, {day.day} {day:%B %Y}", hijri, prayers, extras)


def build_item(day, data, tz, card_url=None):
    t = data["timings"]
    h = data["date"]["hijri"]
    month_no = int(h["month"]["number"])
    hijri_month = HIJRI_MONTHS[month_no - 1]
    hijri = f'{int(h["day"])} {hijri_month} {h["year"]} AH'
    ramadan = month_no == 9
    friday = day.weekday() == 4

    prayers = [
        row("Fajr", hm(t["Fajr"]), "Sehri ends" if ramadan else ""),
        row("Jumu'ah" if friday else "Dhuhr", hm(t["Dhuhr"])),
        row("Asr", hm(t["Asr"])),
        row("Maghrib", hm(t["Maghrib"]), "Iftar" if ramadan else ""),
        row("Isha", hm(t["Isha"])),
    ]
    length = (minutes(t["Sunset"]) - minutes(t["Sunrise"])) % (24 * 60)
    extras = [
        row("Sunrise", hm(t["Sunrise"]), dim=True),
        row("Sunset", hm(t["Sunset"]), dim=True),
        row("Midnight", hm(t["Midnight"]), dim=True),
        row("Tahajjud", hm(t["Lastthird"]), dim=True),
        row("Day length", f"{length // 60}h {length % 60:02d}m", dim=True),
    ]
    heading = f"{day:%A}, {day.day} {day:%B %Y}"
    if friday:
        heading += " · Jumu'ah"
    # The card goes first, so Brief You shows it as the article's header picture.
    img = ""
    if card_url:
        names = ["Fajr", "Jumu'ah" if friday else "Dhuhr", "Asr", "Maghrib", "Isha"]
        keys = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        alt = f"Namaz timings for {CITY}, {heading}: " + ", ".join(
            f"{n} {hm(t[k])}" for n, k in zip(names, keys))
        img = (f'<p><img src="{escape(card_url)}" width="1280" height="800" '
               f'alt="{escape(alt, {chr(34): "&quot;"})}"></p>')
    html = (f"{img}<p><b>{heading}</b><br>{hijri}{' · Ramadan Mubarak' if ramadan else ''}</p>"
            f"<hr><table>{''.join(prayers)}"
            f'<tr><td colspan="2"><hr></td></tr>'
            f"{''.join(extras)}</table>")

    title = f'{day.day} {day:%b} · {int(h["day"])} {hijri_month}'
    # Each day's item is "published" the evening before, when it first appears.
    eve = day - timedelta(days=1)
    pub = datetime(eve.year, eve.month, eve.day, NEXT_DAY_FROM, tzinfo=tz)
    guid = f"namaz-{CITY.lower().replace(' ', '-')}-{day.isoformat()}"
    link = f"{FEED_URL}#{day.isoformat()}" if FEED_URL else ""
    link_tag = f"\n      <link>{escape(link)}</link>" if link else ""
    return f"""    <item>
      <title>{escape(title)}</title>
      <description><![CDATA[{html}]]></description>
      <pubDate>{format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">{guid}</guid>{link_tag}
    </item>"""


def main():
    tz_name = TIMEZONE
    if not tz_name:  # let the API tell us the city's time zone
        probe = fetch_day(datetime.now(timezone.utc).date())
        tz_name = probe["meta"]["timezone"]
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    newest = now_local.date()
    if now_local.hour >= NEXT_DAY_FROM:
        newest += timedelta(days=1)  # evening run: publish tomorrow's timings

    days, meta = [], None
    for i in range(DAYS):
        day = newest - timedelta(days=i)
        try:
            data = fetch_day(day, tz_name)
            meta = meta or data["meta"]
            days.append((day, data))
        except Exception as e:  # keep going; the newest day is what matters most
            print(f"warning: {day}: {e}", file=sys.stderr)
            if i == 0:
                raise

    # Draw each day's card. If that fails, the feed still goes out with text only.
    out_dir = os.path.dirname(OUT) or "."
    cards = set()
    try:
        import card
        cards = set(card.render_cards(
            [(f"{day.isoformat()}.png", card_for(day, data)) for day, data in days],
            os.path.join(out_dir, "cards")))
    except Exception as e:
        print(f"warning: cards not drawn, feed is text only: {e}", file=sys.stderr)

    items = []
    for day, data in days:
        name = f"{day.isoformat()}.png"
        url = f"{SITE_URL}cards/{name}" if SITE_URL else f"cards/{name}"
        items.append(build_item(day, data, tz, url if name in cards else None))

    method_name = meta["method"]["name"] if meta else ""
    school = "Hanafi Asr" if SCHOOL == "1" else "Shafi'i Asr"
    desc = f"Daily prayer times for {CITY}, {COUNTRY} ({method_name}; {school})"

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
    if os.path.exists(ICON_PNG):
        shutil.copy(ICON_PNG, os.path.join(out_dir, "icon.png"))
        shutil.copy(ICON_PNG, os.path.join(out_dir, "apple-touch-icon.png"))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(FEED_TITLE)}</title>
<link rel="icon" type="image/png" href="icon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{escape(FEED_TITLE)}" href="feed.xml">
</head><body style="font-family:sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem">
<h1>{escape(FEED_TITLE)}</h1><p>{escape(desc)}.</p>
<p>Subscribe: <a href="feed.xml">feed.xml</a></p></body></html>
""")
    print(f"wrote {OUT} with {len(items)} items for {CITY} ({tz_name})")


if __name__ == "__main__":
    main()
