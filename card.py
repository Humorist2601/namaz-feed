"""Draw each day's namaz card: a transparent 1280x800 PNG ("glass tiles" design).

The card has no background of its own, so in Brief You it sits on the reader's
header tile and takes on the theme's colour. 1280x800 (16:10) matches Brief You's
header picture on a Pixel 9 Pro, so it shows sharp and uncropped.

Two colour themes: "dark" (light text, for dark-mode readers) and "light" (dark text,
for light-mode readers). Pick one with CARD_THEME in generate_feed.py.

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
JUMUAH = "Jumu'ah"

THEMES = {
    "dark": {"fg": "#EEE8F4", "muted": "#B8B0C6", "gold": "#E9C77E", "amber": "#F2A65A",
             "tile": "rgba(255,255,255,.055)", "line": "rgba(255,255,255,.10)",
             "panel": "rgba(255,255,255,.04)", "panel_line": "rgba(255,255,255,.08)",
             "jumuah": "rgba(233,199,126,.09)", "jumuah_line": "rgba(233,199,126,.60)"},
    "light": {"fg": "#1D1B20", "muted": "#57525F", "gold": "#7E5A12", "amber": "#A9480C",
              "tile": "rgba(0,0,0,.055)", "line": "rgba(0,0,0,.16)",
              "panel": "rgba(0,0,0,.04)", "panel_line": "rgba(0,0,0,.13)",
              "jumuah": "rgba(126,90,18,.11)", "jumuah_line": "rgba(126,90,18,.65)"},
}


def _css(theme="dark"):
    c = THEMES.get(theme, THEMES["dark"])
    f = FONTS.as_uri()
    return f"""
@font-face{{font-family:Amiri;src:url({f}/Amiri-Regular.ttf)}}
@font-face{{font-family:Amiri;font-weight:700;src:url({f}/Amiri-Bold.ttf)}}
@font-face{{font-family:Outfit;font-weight:100 900;src:url({f}/Outfit.ttf)}}
@font-face{{font-family:Cormorant;font-weight:300 700;src:url({f}/CormorantGaramond.ttf)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:transparent}}
body{{position:relative;font-family:Outfit,sans-serif;color:{c["fg"]};-webkit-font-smoothing:antialiased}}
.num{{font-variant-numeric:tabular-nums}}
.head{{position:absolute;left:64px;right:64px;top:34px;display:flex;justify-content:space-between;align-items:flex-start;gap:32px}}
.k{{font-size:28px;letter-spacing:.28em;color:{c["muted"]};font-weight:500;text-transform:uppercase;white-space:nowrap}}
.badge{{display:inline-block;margin-top:30px;padding:7px 20px;border-radius:999px;font-size:23px;letter-spacing:.14em;
  text-transform:uppercase;white-space:nowrap;color:{c["gold"]};background:{c["jumuah"]};border:2px solid {c["jumuah_line"]}}}
.d{{font-size:62px;font-weight:300;margin-top:2px;letter-spacing:-.01em;white-space:nowrap;line-height:1.1}}
.ttl{{font-family:Amiri;direction:rtl;font-size:58px;color:{c["gold"]};font-weight:700;line-height:1.3}}
.r{{position:absolute;right:0;top:0;display:flex;flex-direction:column;align-items:flex-end}}
.h{{font-family:Cormorant;font-style:italic;font-size:40px;color:{c["muted"]};white-space:nowrap;line-height:1.15}}
.row{{position:absolute;left:64px;right:64px;top:232px;display:flex;gap:16px}}
.c{{flex:1;height:290px;border-radius:40px;background:{c["tile"]};border:2px solid {c["line"]};
   display:flex;flex-direction:column;align-items:center;justify-content:center}}
.c.j{{background:{c["jumuah"]};border-color:{c["jumuah_line"]}}}
.a{{font-family:Amiri;direction:rtl;font-size:54px;color:{c["gold"]};font-weight:700;line-height:1.3}}
.en{{font-size:28px;letter-spacing:.14em;text-transform:uppercase;color:{c["muted"]};margin-top:4px;white-space:nowrap}}
.t{{font-size:74px;font-weight:400;margin-top:6px;letter-spacing:-.02em}}
.note{{font-size:25px;letter-spacing:.12em;text-transform:uppercase;color:{c["gold"]};margin-top:6px}}
.panel{{position:absolute;left:64px;right:64px;bottom:30px;height:204px;border-radius:32px;
  background:{c["panel"]};border:2px solid {c["panel_line"]};
  display:grid;grid-template-columns:repeat(4,1fr);align-content:center;row-gap:16px;padding:0 34px}}
.xl{{font-size:22px;letter-spacing:.2em;text-transform:uppercase;color:{c["muted"]}}}
.xv{{font-size:40px;margin-top:2px;white-space:nowrap}}
.xv.avoid{{color:{c["amber"]}}}
"""


def card_html(city, date_line, hijri_line, prayers, extras, occasion="", theme="dark"):
    """prayers: list of (english name, time, note or ""); extras: list of (label, value),
    shown in a panel of two rows of four (Zawal, the time to avoid, in amber);
    occasion: a special-day label shown as a gold badge under the Arabic title. Gold-tinted tiles mark Jumu'ah on
    Fridays and Sehri/Iftar (Fajr/Maghrib) in Ramadan."""
    tiles = "".join(
        f'<div class="c{" j" if name == JUMUAH or note else ""}"><div class="a">{ARABIC.get(name, "")}</div>'
        f'<div class="en">{escape(name)}</div><div class="t num">{time}</div>'
        f'{f"<div class=note>{escape(note)}</div>" if note else ""}</div>'
        for name, time, note in prayers)
    panel = "".join(
        f'<div><div class="xl">{escape(k)}</div>'
        f'<div class="xv num{" avoid" if k == "Zawal" else ""}">{escape(v)}</div></div>'
        for k, v in extras)
    badge = f'<div class="badge">{escape(occasion)}</div>' if occasion else ""
    return (f'<!doctype html><meta charset="utf-8"><style>{_css(theme)}</style>'
            f'<div class="head"><div><div class="k">Namaz · {escape(city)}</div>'
            f'<div class="d">{escape(date_line)}</div><div class="h">{escape(hijri_line)}</div></div>'
            f'<div class="r"><div class="ttl">{TITLE}</div>{badge}</div></div>'
            f'<div class="row">{tiles}</div><div class="panel">{panel}</div>')


STRIP_W, STRIP_H = 1200, 480


def strip_html(prayers, theme="dark"):
    """A wide strip of just the five tiles (2.5:1), used as the item's thumbnail.

    Brief You's Triage shows thumbnails in a 150 dp tall, full-width frame, which would
    crop the 16:10 card; this strip fills that frame. The date is in the item's title.
    """
    tiles = "".join(
        f'<div class="c{" j" if name == JUMUAH or note else ""}"><div class="a">{ARABIC.get(name, "")}</div>'
        f'<div class="en">{escape(name)}</div><div class="t num">{time}</div></div>'
        for name, time, note in prayers)
    return (f'<!doctype html><meta charset="utf-8"><style>{_css(theme)}'
            f'html,body{{width:{STRIP_W}px;height:{STRIP_H}px}}'
            f'.row{{left:56px;right:56px;top:24px;bottom:24px;gap:14px}}'
            f'.c{{height:auto}} .a{{font-size:54px}} .en{{font-size:26px}} .t{{font-size:70px;margin-top:4px}}'
            f'</style><div class="row">{tiles}</div>')


def _shrink(path):
    """Re-save as a 256-colour PNG with transparency: about a third of the size, same look."""
    try:
        from PIL import Image
    except ImportError:
        return  # Pillow missing: keep the full-colour PNG
    im = Image.open(path).convert("RGBA")
    small = im.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    small.save(path, optimize=True)


def render_cards(cards, out_dir):
    """cards: list of (filename, html) or (filename, html, (width, height)).

    Writes transparent PNGs into out_dir; returns the names written."""
    import tempfile
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for job in cards:
            name, html = job[0], job[1]
            w, h = job[2] if len(job) > 2 else (W, H)
            page.set_viewport_size({"width": w, "height": h})
            src = Path(tmp) / "card.html"  # a file page, so it may load the local fonts
            src.write_text(html, encoding="utf-8")
            page.goto(src.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            path = os.path.join(out_dir, name)
            page.screenshot(path=path, omit_background=True)
            _shrink(path)
            written.append(name)
        browser.close()
    return written
