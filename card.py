"""Draw each day's namaz card: a transparent 1280x800 PNG ("glass tiles" design).

The card has no background of its own, so in Brief You it sits on the reader's
header tile and takes on the theme's colour. 1280x800 (16:10) matches Brief You's
header picture on a Pixel 9 Pro, so it shows sharp and uncropped.

Rendered with headless Chromium (Playwright) from HTML, using the fonts in assets/fonts.
"""
import os
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "assets" / "fonts"
W, H = 1280, 800

ARABIC = {"Fajr": "الفجر", "Dhuhr": "الظهر", "Jumu'ah": "الجمعة", "Asr": "العصر",
          "Maghrib": "المغرب", "Isha": "العشاء"}
TITLE = "مواقيت الصلاة"
FG, MUTED, GOLD = "#EEE8F4", "#B8B0C6", "#E9C77E"


def _css():
    f = FONTS.as_uri()
    return f"""
@font-face{{font-family:Amiri;src:url({f}/Amiri-Regular.ttf)}}
@font-face{{font-family:Amiri;font-weight:700;src:url({f}/Amiri-Bold.ttf)}}
@font-face{{font-family:Outfit;font-weight:100 900;src:url({f}/Outfit.ttf)}}
@font-face{{font-family:Cormorant;font-weight:300 700;src:url({f}/CormorantGaramond.ttf)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:transparent}}
body{{position:relative;font-family:Outfit,sans-serif;color:{FG};-webkit-font-smoothing:antialiased}}
.num{{font-variant-numeric:tabular-nums}}
.head{{position:absolute;left:64px;right:64px;top:40px;display:flex;justify-content:space-between;align-items:flex-start}}
.k{{font-size:29px;letter-spacing:.28em;color:{MUTED};font-weight:500;text-transform:uppercase}}
.d{{font-size:58px;font-weight:300;margin-top:8px;letter-spacing:-.01em;white-space:nowrap}}
.ttl{{font-family:Amiri;direction:rtl;font-size:58px;color:{GOLD};font-weight:700;text-align:right;line-height:1.35}}
.h{{font-family:Cormorant;font-style:italic;font-size:38px;color:{MUTED};text-align:right;margin-top:2px;white-space:nowrap}}
.row{{position:absolute;left:64px;right:64px;top:250px;display:flex;gap:16px}}
.c{{flex:1;height:390px;border-radius:40px;background:rgba(255,255,255,.055);border:2px solid rgba(255,255,255,.10);
   display:flex;flex-direction:column;align-items:center;justify-content:center}}
.a{{font-family:Amiri;direction:rtl;font-size:54px;color:{GOLD};font-weight:700;line-height:1.3}}
.en{{font-size:28px;letter-spacing:.14em;text-transform:uppercase;color:{MUTED};margin-top:4px;white-space:nowrap}}
.t{{font-size:74px;font-weight:400;margin-top:6px;letter-spacing:-.02em}}
.note{{font-size:25px;letter-spacing:.12em;text-transform:uppercase;color:{GOLD};margin-top:6px;opacity:.9}}
.ex{{position:absolute;left:64px;right:64px;bottom:36px;display:flex;justify-content:space-between;font-size:32px;color:{MUTED}}}
.ex i{{font-style:normal;letter-spacing:.02em}}
.ex b{{color:{FG};font-weight:500;margin-left:6px}}
"""


def card_html(city, date_line, hijri_line, prayers, extras):
    """prayers: list of (english name, time, note or ""); extras: list of (label, value)."""
    tiles = "".join(
        f'<div class="c"><div class="a">{ARABIC.get(name, "")}</div><div class="en">{escape(name)}</div>'
        f'<div class="t num">{time}</div>{f"<div class=note>{escape(note)}</div>" if note else ""}</div>'
        for name, time, note in prayers)
    ex = "".join(f'<span><i>{escape(k)}</i><b class="num">{escape(v)}</b></span>' for k, v in extras)
    # Long dates ("Wednesday, 30 September 2026") get a slightly smaller size so they fit.
    size = 58 if len(date_line) <= 24 else 50
    return (f'<!doctype html><meta charset="utf-8"><style>{_css()}</style>'
            f'<div class="head"><div><div class="k">Namaz · {escape(city)}</div>'
            f'<div class="d" style="font-size:{size}px">{escape(date_line)}</div></div>'
            f'<div><div class="ttl">{TITLE}</div><div class="h">{escape(hijri_line)}</div></div></div>'
            f'<div class="row">{tiles}</div><div class="ex">{ex}</div>')


def render_cards(cards, out_dir):
    """cards: list of (filename, html). Writes transparent PNGs into out_dir; returns the names written."""
    import tempfile
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for name, html in cards:
            src = Path(tmp) / "card.html"  # a file page, so it may load the local fonts
            src.write_text(html, encoding="utf-8")
            page.goto(src.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=os.path.join(out_dir, name), omit_background=True)
            written.append(name)
        browser.close()
    return written
