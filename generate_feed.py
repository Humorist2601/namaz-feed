#!/usr/bin/env python3
"""Build an RSS feed of daily namaz timings from the Aladhan API.

To use a different city, edit the settings below. If TIMEZONE is left empty
it is detected from the city automatically.

Every run regenerates the last DAYS days. From NEXT_DAY_FROM (9 PM) onward
the newest item is tomorrow, so the next day's timings arrive the evening before.

Timings are saved a month at a time in data/ and fetched from the API only when a
month is missing or the settings changed; from PREFETCH_FROM (the 20th) onward, next
month is fetched ahead, so a night's item never depends on the API being up.
"""
import json
import os
import re
import shutil
import sys
import time
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
# Days to shift the Hijri date to match local moon sighting. The API calculates the
# Hijri date; Pakistan follows Ruet-e-Hilal, which is usually a day behind (-1).
# If the feed's Hijri date is ever a day off from Pakistan's, change this to 0 or -2.
HIJRI_ADJUST = -1
CARD_THEME = "dark"  # card and thumbnail colours: "dark" (for dark-mode readers) or "light"

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
API = "https://api.aladhan.com/v1/calendarByCity/{year}/{month}?{query}"
RETRY_WAITS = [5, 20, 60]  # seconds between attempts when the API fails
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))  # saved monthly timings
PREFETCH_FROM = 20  # from this day of the month, next month's timings are fetched ahead


def fetch_month(year, month):
    """Every day of one month for the city (one API call, retried if it fails)."""
    params = {"city": CITY, "country": COUNTRY, "method": METHOD, "school": SCHOOL}
    if TIMEZONE:
        params["timezonestring"] = TIMEZONE
    url = API.format(year=year, month=month, query=urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": "namaz-rss/1.0"})
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
            if payload.get("code") != 200:
                raise RuntimeError(f"API error for {year}-{month:02d}: {payload}")
            return payload["data"]
        except Exception as e:
            if attempt == len(RETRY_WAITS):
                raise
            wait = RETRY_WAITS[attempt]
            print(f"warning: {year}-{month:02d} attempt {attempt + 1} failed ({e}); retrying in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)


def fetch_settings():
    """What a saved month was fetched with; if any of these change, the month is fetched again."""
    return {"city": CITY, "country": COUNTRY, "method": METHOD, "school": SCHOOL,
            "timezone": TIMEZONE}


class Calendar:
    """Day-by-day data, a month at a time, saved in DATA_DIR (data/YYYY-MM.json).

    Prayer times are fixed by astronomy, so each month is fetched from the API once and
    reused every night after that. A month is fetched again only if its file is missing
    or was saved with different settings (city, country, method, school, time zone).
    """

    def __init__(self):
        self.months = {}
        self.saved = []  # month files written this run (the workflow commits them)

    def _path(self, year, month):
        return os.path.join(DATA_DIR, f"{year}-{month:02d}.json")

    def _load(self, year, month):
        try:
            with open(self._path(year, month), encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return None
        return saved["days"] if saved.get("settings") == fetch_settings() else None

    def _save(self, year, month, days):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self._path(year, month), "w", encoding="utf-8") as f:
            json.dump({"settings": fetch_settings(),
                       "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "days": days}, f, ensure_ascii=False, separators=(",", ":"))
        self.saved.append(f"{year}-{month:02d}")

    def month(self, year, month):
        """The month's days by date: from its saved file, or fetched and saved."""
        key = (year, month)
        if key not in self.months:
            days = self._load(year, month)
            if days is None:
                days = fetch_month(year, month)
                self._save(year, month, days)
            self.months[key] = {
                datetime.strptime(d["date"]["gregorian"]["date"], "%d-%m-%Y").date(): d
                for d in days
            }
        return self.months[key]

    def get(self, day):
        return self.month(day.year, day.month)[day]

    def prefetch_next_month(self, today):
        """From PREFETCH_FROM onward, make sure next month is saved. A failure here is only
        a warning: the next night's run tries again, with days to spare."""
        if today.day < PREFETCH_FROM:
            return
        nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        try:
            self.month(nxt.year, nxt.month)
        except Exception as e:
            print(f"warning: couldn't fetch {nxt:%Y-%m} yet, will try again next run: {e}",
                  file=sys.stderr)

    def prune(self, keep_from):
        """Delete saved months that end before keep_from (they're no longer needed)."""
        if not os.path.isdir(DATA_DIR):
            return
        for name in os.listdir(DATA_DIR):
            try:
                y, m = map(int, name.removesuffix(".json").split("-"))
            except ValueError:
                continue
            month_end = (datetime(y, m, 1) + timedelta(days=32)).replace(day=1).date()
            if month_end <= keep_from:
                os.remove(os.path.join(DATA_DIR, name))
                print(f"removed old data file {name}")

    def day(self, day):
        """The day's data, with its Hijri date shifted by HIJRI_ADJUST."""
        data = dict(self.get(day))
        if HIJRI_ADJUST:
            shifted = self.get(day + timedelta(days=HIJRI_ADJUST))
            data["date"] = {**data["date"], "hijri": shifted["date"]["hijri"]}
        return data


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
    # Names and times form two fixed-width columns, centred on the page as one group, so
    # every line lines up. Plain divs rather than a table, because readers restyle tables
    # (Brief You indents them and turns rows into blocks). Without styles: "Fajr 05:23".
    return (f'<div style="display:flex;justify-content:center;padding:2px 0">'
            f'<span style="flex:0 1 {NAME_COL}">{text}</span> '
            f'<span style="flex:0 0 {TIME_COL};white-space:nowrap;font-variant-numeric:tabular-nums">'
            f'{time}</span></div>')


NAME_COL, TIME_COL = "7.5em", "5.5em"  # fit "Fajr (Sehri ends)" and "11:35–12:16"


def prayer_list(day, data):
    """(name, time, note) for the five prayers, with Jumu'ah and Ramadan labels."""
    t = data["timings"]
    ramadan = int(data["date"]["hijri"]["month"]["number"]) == 9
    friday = day.weekday() == 4
    return [
        ("Fajr", hm(t["Fajr"]), "Sehri ends" if ramadan else ""),
        ("Jumu'ah" if friday else "Dhuhr", hm(t["Dhuhr"]), ""),
        ("Asr", hm(t["Asr"]), ""),
        ("Maghrib", hm(t["Maghrib"]), "Iftar" if ramadan else ""),
        ("Isha", hm(t["Isha"]), ""),
    ]


def clock(total_minutes):
    """Minutes after midnight -> 'HH:MM'."""
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def extras_list(t):
    """(label, value) for the extra times, in the order shown on the card and in the text.

    Ishraq: 20 minutes after sunrise, once the disliked period after sunrise has passed.
    Chasht (Duha): a quarter of the day (sunrise to sunset) after sunrise.
    Zawal: the Hanafi disliked time before Dhuhr, from the midpoint between Fajr and
    Maghrib (dahwa kubra) until Dhuhr begins.
    """
    sunrise, sunset = minutes(t["Sunrise"]), minutes(t["Sunset"])
    length = (sunset - sunrise) % (24 * 60)
    zawal_from = (minutes(t["Fajr"]) + minutes(t["Maghrib"])) // 2
    return [
        ("Sunrise", hm(t["Sunrise"])),
        ("Ishraq", clock(sunrise + 20)),
        ("Chasht", clock(sunrise + length // 4)),
        ("Zawal", f"{clock(zawal_from)}–{hm(t['Dhuhr'])}"),
        ("Sunset", hm(t["Sunset"])),
        ("Midnight", hm(t["Midnight"])),
        ("Tahajjud", hm(t["Lastthird"])),
        ("Day length", f"{length // 60}h {length % 60:02d}m"),
    ]


# A collapsed explanation at the end of each item: one tappable line, closed by default.
ABOUT_TIMES = (
    "<details><summary><i>About these times</i></summary><ul>"
    "<li><b>Sunrise</b>: Fajr ends. Don't start a prayer for about 15–20 minutes after it.</li>"
    "<li><b>Ishraq</b>: voluntary prayer once the sun has fully risen (20 minutes after sunrise).</li>"
    "<li><b>Chasht</b> (Duha): mid-morning voluntary prayer; can be prayed from Ishraq until "
    "Zawal, preferred after a quarter of the day (the time shown).</li>"
    "<li><b>Zawal</b>: around midday, praying is disliked (Hanafi: from the midpoint of Fajr "
    "and Maghrib until Dhuhr).</li>"
    "<li><b>Sunset</b>: Maghrib begins.</li>"
    "<li><b>Midnight</b>: halfway between sunset and sunrise; the preferred limit for Isha.</li>"
    "<li><b>Tahajjud</b>: the last third of the night begins, the best time for the night "
    "prayer and du'a.</li>"
    "<li><b>Day length</b>: sunrise to sunset.</li>"
    "</ul><p><small>Karachi method (18°/18°), Hanafi Asr; beginning times without safety "
    "margins.</small></p></details>"
)


def occasions(day, h, t=None):
    """Notes for special days: (emoji, short label for the card, sentence for the text).

    The first entry is the main one (shown on the card). Islamic nights begin at sunset,
    so a night is noted on the day whose evening it starts. Follows the feed's Hijri date
    (HIJRI_ADJUST). t (the day's timings) adds the Eid prayer window to the Eid notes."""
    month, d = int(h["month"]["number"]), int(h["day"])
    eid_window = ""
    if t is not None:
        # Eid salah: from when the sun has fully risen (Ishraq) until Zawal begins.
        ex = dict(extras_list(t))
        eid_window = f" Eid prayer from {ex['Ishraq']} until {ex['Zawal'].split('–')[0]}."
    notes = {
        (1, 1): ("🗓️", "Islamic New Year", "1 Muharram: the Islamic New Year."),
        (1, 9): ("🤲", "Tasu'a", "9 Muharram: the day before Ashura (sunnah to fast with Ashura)."),
        (1, 10): ("🤲", "Ashura", "10 Muharram: the Day of Ashura."),
        (3, 12): ("🕌", "12 Rabi-ul-Awwal", "12 Rabi-ul-Awwal: Eid Milad-un-Nabi, a public holiday in Pakistan."),
        (7, 26): ("✨", "Shab-e-Miraj tonight", "Shab-e-Miraj begins this evening (night of 27 Rajab)."),
        (8, 14): ("✨", "Shab-e-Barat tonight", "Shab-e-Barat begins this evening (night of 15 Shaban)."),
        (9, 1): ("🏮", "Ramadan begins", "1 Ramadan: Ramadan Mubarak."),
        (9, 26): ("✨", "Shab-e-Qadr tonight", "Shab-e-Qadr: the 27th night of Ramadan begins this "
                                                "evening, widely observed as Laylat al-Qadr."),
        (10, 1): ("🎉", "Eid ul-Fitr", f"1 Shawwal: Eid ul-Fitr. Eid Mubarak!{eid_window}"),
        (12, 9): ("🕋", "Day of Arafah", "9 Dhul Hijjah: the Day of Arafah (sunnah to fast)."),
        (12, 10): ("🐑", "Eid ul-Adha", f"10 Dhul Hijjah: Eid ul-Adha. Eid Mubarak!{eid_window}"),
    }
    out = []
    if (month, d) in notes:
        out.append(notes[(month, d)])
    if month == 9 and d in (20, 22, 24, 28):
        out.append(("✨", "Odd night tonight", f"An odd night of the last ten begins this evening "
                                                f"(night of {d + 1} Ramadan): seek Laylat al-Qadr."))
    if month == 12 and d in (11, 12, 13):
        out.append(("🚫", "Days of Tashreeq", f"{d} Dhul Hijjah: one of the Days of Tashreeq; "
                                              f"fasting is not permitted."))
    if month == 12 and 9 <= d <= 13:
        out.append(("📿", "Takbeer-e-Tashreeq", "Takbeer-e-Tashreeq after every fard prayer, from "
                                                "Fajr on 9 to Asr on 13 Dhul Hijjah."))
    if d in (13, 14, 15) and month != 9 and (month, d) != (12, 13):
        out.append(("🤲", "White day fast", f"{d} {HIJRI_MONTHS[month - 1]}: one of the white days "
                                            f"(Ayyam al-Beed), sunnah to fast."))
    if day.weekday() == 4:
        out.append(("📖", "Jumu'ah", "Jumu'ah: sunnah to recite Surah Al-Kahf today."))
    return out


def strip_for(day, data):
    """The HTML for this day's thumbnail strip (see card.py)."""
    import card

    return card.strip_html(prayer_list(day, data), CARD_THEME)


def card_for(day, data):
    """The HTML for this day's card image (see card.py)."""
    import card

    t = data["timings"]
    h = data["date"]["hijri"]
    month_no = int(h["month"]["number"])
    prayers = prayer_list(day, data)
    extras = [("Day" if k == "Day length" else k, v) for k, v in extras_list(t)]
    hijri = f'{int(h["day"])} {HIJRI_MONTHS[month_no - 1]} {h["year"]} AH'
    # Special-day label above the date: the main one only, so it fits on one line (the
    # text lists them all; Fridays already show Jumu'ah on the Dhuhr tile).
    occasion = next((short for _, short, _ in occasions(day, h, t) if short != "Jumu'ah"), "")
    # Short date on the card ("Wed, 30 Sep 2026"); the text below gives it in full.
    return card.card_html(CITY, f"{day:%a}, {day.day} {day:%b %Y}", hijri, prayers, extras,
                          occasion, CARD_THEME)


def build_item(day, data, tz, card_url=None, strip_url=None):
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
    extras = [row(k, v, dim=True) for k, v in extras_list(t)]
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
    # On the 29th, Ruet-e-Hilal meets that evening to decide when the next month begins:
    # a nudge to compare their announcement with tomorrow's Hijri date in this feed.
    moon_note = ""
    if int(h["day"]) == 29:
        next_month = HIJRI_MONTHS[month_no % 12]
        moon_note = (f"{next_month} moon sighting tonight. If tomorrow's Hijri date "
                     f"is off, change HIJRI_ADJUST.")
    note_html = f"<p><small><i>🌙 {escape(moon_note)}</i></small></p>" if moon_note else ""
    special = occasions(day, h, t)
    note_html += "".join(f"<p>{icon} {escape(sentence)}</p>" for icon, _, sentence in special)
    html = (f"{img}<p><b>{heading}</b><br>{hijri}{' · Ramadan Mubarak' if ramadan else ''}</p>"
            f"{note_html}<hr><div>{''.join(prayers)}</div>"
            f"<hr><div>{''.join(extras)}</div>"
            f"<hr>{ABOUT_TIMES}")

    title = f'{day.day} {day:%b} · {int(h["day"])} {hijri_month}'
    # Each day's item is "published" the evening before, when it first appears.
    eve = day - timedelta(days=1)
    pub = datetime(eve.year, eve.month, eve.day, NEXT_DAY_FROM, tzinfo=tz)
    # Letters, digits and dashes only, so any city name gives a valid, stable ID.
    slug = re.sub(r"[^a-z0-9]+", "-", CITY.lower()).strip("-")
    guid = f"namaz-{slug}-{day.isoformat()}"
    link = f"{FEED_URL}#{day.isoformat()}" if FEED_URL else ""
    link_tag = f"\n      <link>{escape(link)}</link>" if link else ""
    # A short, readable summary for list and Triage views (they show <description> as
    # plain text); the full article, card first, goes in <content:encoded>.
    summary = " · ".join(f"{n} {tm}" for n, tm, _ in prayer_list(day, data))
    summary += (f" — Sunrise {hm(t['Sunrise'])} · Sunset {hm(t['Sunset'])} · "
                f"Tahajjud {hm(t['Lastthird'])}")
    if special:
        summary = " · ".join(f"{icon} {short}" for icon, short, _ in special) + f" — {summary}"
    if moon_note:
        summary = f"🌙 Moon-sighting evening: check tomorrow's Hijri date. {summary}"
    thumb = (f'\n      <media:thumbnail url="{escape(strip_url)}" width="1200" height="480"/>'
             if strip_url else "")
    return f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(summary)}</description>
      <content:encoded><![CDATA[{html}]]></content:encoded>{thumb}
      <pubDate>{format_datetime(pub)}</pubDate>
      <guid isPermaLink="false">{guid}</guid>{link_tag}
    </item>"""


def main():
    cal = Calendar()
    tz_name = TIMEZONE
    if not tz_name:  # let the API tell us the city's time zone (this month is needed anyway)
        tz_name = cal.get(datetime.now(timezone.utc).date())["meta"]["timezone"]
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    newest = now_local.date()
    if now_local.hour >= NEXT_DAY_FROM:
        newest += timedelta(days=1)  # evening run: publish tomorrow's timings

    days = []
    for i in range(DAYS):
        day = newest - timedelta(days=i)
        try:
            days.append((day, cal.day(day)))
        except Exception as e:  # keep going; the newest day is what matters most
            print(f"warning: {day}: {e}", file=sys.stderr)
            if i == 0:
                raise
    meta = days[0][1]["meta"]

    # Keep next month ready ahead of time, and drop months the feed no longer shows.
    cal.prefetch_next_month(now_local.date())
    cal.prune(days[-1][0] - timedelta(days=abs(HIJRI_ADJUST) + 1))
    print(f"timings: {'fetched and saved ' + ', '.join(cal.saved) if cal.saved else 'all from saved files, no API call'}")

    # Draw each day's card. If that fails, the feed still goes out with text only.
    out_dir = os.path.dirname(OUT) or "."
    cards = set()
    try:
        import card
        jobs = []
        for day, data in days:
            jobs.append((f"{day.isoformat()}.png", card_for(day, data)))
            jobs.append((f"{day.isoformat()}-strip.png", strip_for(day, data),
                         (card.STRIP_W, card.STRIP_H)))
        cards = set(card.render_cards(jobs, os.path.join(out_dir, "cards")))
    except Exception as e:
        print(f"warning: cards not drawn, feed is text only: {e}", file=sys.stderr)

    def url_for(name):
        if name not in cards:
            return None
        return f"{SITE_URL}cards/{name}" if SITE_URL else f"cards/{name}"

    items = []
    for day, data in days:
        d = day.isoformat()
        items.append(build_item(day, data, tz, url_for(f"{d}.png"), url_for(f"{d}-strip.png")))

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
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:sy="http://purl.org/rss/1.0/modules/syndication/">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(SITE_URL or "https://aladhan.com")}</link>
    <description>{escape(desc)}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>
    <sy:updatePeriod>daily</sy:updatePeriod>
    <sy:updateFrequency>1</sy:updateFrequency>{self_link}{image}
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
