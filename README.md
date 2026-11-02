<p align="center"><img src="assets/icon.png" width="112" alt="Namaz Timings icon"></p>

<h1 align="center">Namaz Timings RSS</h1>

<p align="center">A daily RSS feed of prayer times for your city, delivered the evening before.<br>
Runs itself on GitHub for free; no server, no app, nothing to maintain.</p>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme-card-dark.png">
  <img src="assets/readme-card-light.png" alt="Example card: Friday's prayer times in glass tiles with Arabic and English names, and the extra times in a panel below" width="640">
</picture>
</p>

## What you get

Every evening at 21:00 a new item arrives with **tomorrow's** timings, titled like
`3 Nov · 22 Jumada al-Ula`.

**The card.** Each item opens with an image of the day: the five prayers in glass tiles
with their Arabic names, and the extra times in a panel below. It has no background of
its own, so it blends into your reader. Readers that show an item's first picture as a
header (like Brief You) put it at the top.

- Jumu'ah is tinted gold on Fridays; in Ramadan, Fajr (Sehri ends) and Maghrib (Iftar) are.
- Zawal, the time to avoid praying, is in amber.
- Special days get a gold badge under the Arabic title.

**The text.** Below the card, the same information as text you can read and copy:
the full Gregorian and Hijri dates, the five prayers, then the extra times, in two
aligned columns centred on the page. A collapsible *About these times*
explains each one.

| Prayers | Extra times |
|---|---|
| Fajr, Dhuhr (Jumu'ah on Fridays), Asr, Maghrib, Isha | Sunrise, Ishraq, Chasht, Zawal, Sunset, Midnight, Tahajjud, Day length |

**List and Triage views.** A wide strip of the five times as the thumbnail, and a
one-line summary: `Fajr 05:26 · Dhuhr 12:16 · … — Sunrise 06:47 · Sunset 17:43 · Tahajjud 02:26`.

**Special days.** A note in the text and the summary, and a badge on the card:

- 🗓️ Islamic New Year · 🤲 Tasu'a and Ashura · 🕌 12 Rabi-ul-Awwal
- ✨ Shab-e-Miraj · Shab-e-Barat · Shab-e-Qadr and the other odd nights of Ramadan
- 🏮 Ramadan begins · 🎉 Eid ul-Fitr · 🐑 Eid ul-Adha (both Eids with the Eid prayer window)
- 🕋 Day of Arafah · 📿 Takbeer-e-Tashreeq (9–13 Dhul Hijjah) · 🚫 Days of Tashreeq: no fasting
- 🤲 White days (13th–15th): sunnah fast · 📖 Fridays: Surah Al-Kahf
- 🌙 29th of each month: moon-sighting reminder

Nights such as Shab-e-Barat are noted on the day whose evening they begin. All times
are 24-hour; the feed keeps the last 7 days.

## Setup (about 5 minutes)

1. Create a **public** GitHub repo, e.g. `namaz-feed`, and add these files.
2. Set your city at the top of `generate_feed.py` (see [Settings](#settings)).
3. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to **Actions → Update namaz feed → Run workflow** to build it the first time.
5. Add this URL to your RSS reader:

   ```
   https://<your-github-username>.github.io/namaz-feed/feed.xml
   ```

Optionally, set `assets/icon.png` as the feed's icon in your reader.

## Settings

Everything is at the top of `generate_feed.py`. Committing a change rebuilds the feed
straight away.

| Setting | Default | What it does |
|---|---|---|
| `CITY` | `"Quetta"` | Any city Aladhan recognises. The feed is named `Namaz Timings (<City>)` |
| `COUNTRY` | `"Pakistan"` | Country name or code, e.g. `"UK"` |
| `TIMEZONE` | `""` | Leave empty to detect it from the city |
| `METHOD` | `"1"` | Calculation method: 1 Karachi, 2 ISNA, 3 Muslim World League, 4 Umm al-Qura, 5 Egypt ([all IDs](https://api.aladhan.com/v1/methods)) |
| `SCHOOL` | `"1"` | Asr: 1 = Hanafi, 0 = Shafi'i |
| `DAYS` | `7` | How many recent days the feed keeps |
| `NEXT_DAY_FROM` | `21` | From this hour (local time), the newest item is tomorrow |
| `HIJRI_ADJUST` | `-1` | Days to shift the Hijri date to match local moon sighting (see below) |
| `CARD_THEME` | `"dark"` | `"dark"` for dark-mode readers, `"light"` for light-mode readers |

**Another time zone?** The evening run is set for 21:00 Pakistan time. Change the `cron`
time in `.github/workflows/feed.yml` (it's in UTC) and `NEXT_DAY_FROM` to match.

## How it works

**Hijri date.** The Hijri date is calculated, then shifted by `HIJRI_ADJUST` to match
Pakistan's Ruet-e-Hilal moon sighting, which is usually a day behind the calculation.
On the 29th of each month the item carries a 🌙 note: compare the next day's Hijri date
with the announcement, and if it's off, change `HIJRI_ADJUST` to `0` or `-2`. Special
days follow this date, so it's the one thing worth checking.

**Saved timings (`data/`).** Prayer times are fixed by astronomy, so they're fetched a
month at a time and saved in `data/YYYY-MM.json`. The nightly run reads these files and
normally makes no network calls at all. A month is fetched only when its file is missing
(from the 20th, next month is fetched ahead, leaving about 10 nights to retry if the
service is down) or when you change the city or method. The run saves new months
itself and deletes ones it no longer needs.

**Cards.** `card.py` draws each day's card and strip with headless Chromium, using the
open-licence fonts in `assets/fonts`. If drawing ever fails, the feed still goes out
with text only.

**Staying on.** GitHub pauses scheduled jobs in repos without activity for 60 days; the
workflow re-enables itself on every run. If the feed ever stops updating, open the
Actions tab and re-enable the workflow.

## Accuracy

Times come from the free [Aladhan API](https://aladhan.com) using the University of
Islamic Sciences, Karachi method (Fajr and Isha at 18°) with Hanafi Asr: the standard
for Pakistan. They're beginning times, without safety margins, and match Pakistani
timetables such as Express Tribune and HamariWeb to the minute. Some sites, like
IslamicFinder, add a precautionary minute or two (three for Maghrib).

How the extra times are worked out:

- **Ishraq**: 20 minutes after sunrise, once the disliked period has passed.
- **Chasht**: a quarter of the day (sunrise to sunset) after sunrise.
- **Zawal**: from the midpoint of Fajr and Maghrib until Dhuhr (Hanafi).
- **Midnight**: halfway between sunset and sunrise.
- **Tahajjud**: the start of the last third of the night.

## Files

| File | |
|---|---|
| `generate_feed.py` | Settings, timings, notes and the feed itself |
| `card.py` | Draws the card and the thumbnail strip |
| `.github/workflows/feed.yml` | The nightly run and deployment to GitHub Pages |
| `data/` | Saved monthly timings (managed automatically) |
| `assets/` | Icon, fonts (with their licences) and README images |
