# Namaz timings RSS – Quetta

A daily RSS feed of prayer times for Quetta, Pakistan
(Karachi calculation method, Hanafi Asr), from the free Aladhan API.

Each day gets one feed item listing Fajr, Sunrise, Dhuhr, Asr, Maghrib and Isha,
plus the Hijri date. The feed keeps the last 7 days.

## Setup (about 5 minutes)

1. Create a new **public** GitHub repo, e.g. `namaz-feed`.
2. Upload `generate_feed.py` and `.github/workflows/feed.yml` (keep that folder path).
3. In the repo go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to **Actions → Update namaz feed → Run workflow** to build it the first time.
5. Add this URL to your RSS reader:

   `https://<your-github-username>.github.io/namaz-feed/feed.xml`

After that it rebuilds itself every night at 00:05 Quetta time.

## Changing settings

Edit the defaults at the top of `generate_feed.py`:

| Setting   | Default        | Notes                                      |
|-----------|----------------|--------------------------------------------|
| `CITY`    | Quetta         | Any city Aladhan recognises                |
| `COUNTRY` | Pakistan       |                                            |
| `TIMEZONE`| Asia/Karachi   |                                            |
| `METHOD`  | 1              | 1 = Karachi; see aladhan.com for others    |
| `SCHOOL`  | 1              | 1 = Hanafi Asr, 0 = Shafi'i                |
| `DAYS`    | 7              | How many recent days the feed keeps        |

GitHub normally pauses scheduled jobs in repos with no activity for 60 days.
The workflow re-enables itself on every nightly run to prevent that. If the feed
ever stops updating anyway, open the Actions tab and re-enable the workflow.

## Offline calendar file

`make_ics.py` builds a standalone `.ics` file (Fajr, Sunrise, Dhuhr, Asr, Sunset,
Maghrib, Isha) for importing into an offline calendar. Edit `START`/`END` at the
top and run `python make_ics.py namaz.ics`.
