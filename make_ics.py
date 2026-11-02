#!/usr/bin/env python3
"""Build a standalone .ics of daily prayer, sunrise and sunset times (Aladhan API)."""
import json, sys, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

CITY, COUNTRY, TZ = "Quetta", "Pakistan", "Asia/Karachi"
METHOD, SCHOOL = 1, 1  # Karachi, Hanafi
START, END = date(2026, 11, 2), date(2027, 12, 31)
EVENTS = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Sunset", "Maghrib", "Isha"]
DURATION = {"Sunrise": 0, "Sunset": 0}  # minutes; others default to 10

def month_data(y, m):
    q = urllib.parse.urlencode({"city": CITY, "country": COUNTRY, "method": METHOD,
                                "school": SCHOOL, "timezonestring": TZ})
    url = f"https://api.aladhan.com/v1/calendarByCity/{y}/{m}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "namaz-ics/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        p = json.load(r)
    assert p["code"] == 200, p
    return p["data"]

def fold(line):  # RFC 5545 line folding at 75 octets
    out, b = [], line.encode()
    while len(b) > 75:
        cut = 75
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode()); b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//namaz-ics//Quetta//EN",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         f"X-WR-CALNAME:Namaz times · {CITY}", f"X-WR-TIMEZONE:{TZ}",
         "BEGIN:VTIMEZONE", f"TZID:{TZ}", "BEGIN:STANDARD", "DTSTART:19700101T000000",
         "TZOFFSETFROM:+0500", "TZOFFSETTO:+0500", "TZNAME:PKT", "END:STANDARD", "END:VTIMEZONE"]

count, days = 0, 0
y, m = START.year, START.month
while (y, m) <= (END.year, END.month):
    for d in month_data(y, m):
        day = datetime.strptime(d["date"]["gregorian"]["date"], "%d-%m-%Y").date()
        if not (START <= day <= END):
            continue
        days += 1
        h = d["date"]["hijri"]
        hijri = f'{h["day"]} {h["month"]["en"]} {h["year"]} AH'
        for name in EVENTS:
            hhmm = d["timings"][name].split(" ")[0]
            start = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time())
            end = start + timedelta(minutes=DURATION.get(name, 10))
            lines += ["BEGIN:VEVENT",
                      f"UID:{name.lower()}-{day.isoformat()}-quetta@namaz-ics",
                      f"DTSTAMP:{stamp}",
                      f"DTSTART;TZID={TZ}:{start:%Y%m%dT%H%M%S}",
                      f"DTEND;TZID={TZ}:{end:%Y%m%dT%H%M%S}",
                      f"SUMMARY:{name} {start:%-I:%M %p}",
                      f"DESCRIPTION:{name} in {CITY} · {hijri} (Karachi method\\, Hanafi Asr)",
                      "TRANSP:TRANSPARENT", "END:VEVENT"]
            count += 1
    m += 1
    if m > 12:
        y, m = y + 1, 1

lines.append("END:VCALENDAR")
out = sys.argv[1] if len(sys.argv) > 1 else "namaz-quetta.ics"
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("\r\n".join(fold(l) for l in lines) + "\r\n")
print(f"{out}: {days} days, {count} events")
