#!/usr/bin/env python3
"""Route/hub <head> SEO metadata builder and one-shot updater.

Used by inject_rrts_route_data.py so regenerated route pages keep the SEO
templates. Running this file directly updates routes/*.html (excluding
redirect stubs), the six hub pages, and bumps sitemap.xml lastmod values.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from html import escape
from pathlib import Path

SITE_ROOT = "https://metroguideindia.com"
REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "routes"
SITEMAP_PATH = REPO_ROOT / "sitemap.xml"
ROBOTS_CONTENT = "index, follow, max-snippet:-1, max-image-preview:large"

# Stations served only by Meerut Metro (not on the Namo Bharat RRTS corridor).
MEERUT_METRO_ONLY = {
    "partapur", "rithani", "brahmpuri", "meerut central",
    "bhaisali", "mes colony", "daurli", "meerut north",
}
DEFAULT_INTERCHANGE = "Meerut South"

HUB_PAGES = {
    "index.html": (
        "MetroGuideIndia: Namo Bharat RRTS, Delhi Metro & Namma Metro Route Planner 2026",
        "Fast, accurate 2026 route planner & fare calculator for Delhi–Meerut Namo Bharat RRTS, "
        "Meerut Metro, Delhi Metro (DMRC), and Bengaluru Namma Metro.",
    ),
    "namo-bharat/index.html": (
        "Namo Bharat RRTS & Meerut Metro Route Planner 2026: Fare, Timings & Parking",
        "Official 2026 rates for Delhi to Meerut Namo Bharat (Rapid Rail) & Meerut Metro. "
        "Check station-to-station Standard & Premium fares (₹20–₹210), timings & parking.",
    ),
    "delhi-metro/index.html": (
        "Delhi Metro Route Planner & Fare Calculator 2026 (DMRC Map, Gates & Timings)",
        "Find the fastest Delhi Metro (DMRC) route with 2026 fare slabs (₹11–₹64), Smart Card "
        "discounts, platform interchange guide, exit gates & first/last train timings.",
    ),
    "bengaluru-metro/index.html": (
        "Namma Metro Route Planner & Fare Calculator 2026 (All 83 Stations — Purple, Green & Yellow Line)",
        "Plan your Bengaluru Metro journey across all 83 stations on the Purple, Green & Yellow "
        "Lines. Check 2026 fares (₹10–₹90), timings & WhatsApp QR ticket booking.",
    ),
    "stations.html": (
        "All Namo Bharat RRTS, Meerut Metro, Delhi & Bengaluru Metro Stations List (2026)",
        "Browse all 15 Namo Bharat RRTS stations (Sarai Kale Khan to Modipuram), 13 Meerut Metro "
        "stations, Delhi Metro & Namma Metro stations with gates & parking.",
    ),
}


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", fragment)).strip()


def is_redirect_page(html: str) -> bool:
    return bool(re.search(r'<meta\s+http-equiv=["\']refresh["\']', html, flags=re.I))


def parse_route_data(html: str) -> dict:
    """Extract exact route data from the page's own rendered route summary."""
    sub = re.search(r'<p class="rp-sub"[^>]*>(.*?)</p>', html, flags=re.S)
    sub_text = _text(sub.group(1)) if sub else ""
    steps = [_text(s) for s in re.findall(r'<div class="step-name">(.*?)</div>', html, flags=re.S)]
    if len(steps) < 2:
        raise ValueError("route steps not found")
    fare = re.search(r"₹\s*([0-9,]+)", sub_text)
    time_m = re.search(r"~\s*([0-9]+)\s*min", sub_text, flags=re.I)
    dist = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*km", sub_text, flags=re.I)
    if not (fare and time_m and dist):
        raise ValueError(f"incomplete route summary: {sub_text!r}")
    xchange = re.search(r'<div class="xchange-name">(.*?)</div>', html, flags=re.S)
    std = int(fare.group(1).replace(",", ""))
    origin, destination = steps[0], steps[-1]
    local = [s.lower() in MEERUT_METRO_ONLY for s in (origin, destination)]
    if all(local):
        kind = "metro"
    elif any(local):
        kind = "combined"
    else:
        kind = "rrts"
    return {
        "origin": origin,
        "destination": destination,
        "std_fare": std,
        "prem_fare": int(std * 1.2 + 0.5),  # Math.round for positive values
        "time": int(time_m.group(1)),
        "dist": dist.group(1),
        "stops": len(steps),
        "kind": kind,
        "interchange": _text(xchange.group(1)) if xchange else DEFAULT_INTERCHANGE,
    }


def build_route_seo(slug: str, d: dict) -> dict[str, str]:
    o, de, fare = d["origin"], d["destination"], d["std_fare"]
    if d["kind"] == "rrts":
        title = f"{o} to {de} Namo Bharat RRTS Fare (₹{fare}), Timings & Route 2026"
        desc = (
            f"{o} to {de} Namo Bharat (Rapid Rail) route: Standard fare ₹{fare} (Premium ₹{d['prem_fare']}), "
            f"{d['time']} min travel time for {d['dist']} km across {d['stops']} stops. "
            "Check 2026 first/last train timings, gates & parking."
        )
    elif d["kind"] == "combined":
        title = f"{o} to {de} RRTS & Meerut Metro Route: ₹{fare} Fare & Timings"
        desc = (
            f"Travel from {o} to {de} via Namo Bharat RRTS & Meerut Metro in ~{d['time']} min ({d['dist']} km). "
            f"Ticket price ₹{fare}, platform transfer at {d['interchange']}, first/last train timings & parking."
        )
    else:
        title = f"{o} to {de} Meerut Metro Fare (₹{fare}), Route & Timings 2026"
        desc = (
            f"{o} to {de} Meerut Metro route guide: Ticket price ₹{fare}, ~{d['time']} min journey "
            f"({d['dist']} km, {d['stops']} stops). View 2026 train timings, exit gates, landmarks & parking charges."
        )
    return {"title": title, "description": desc, "url": f"{SITE_ROOT}/routes/{slug}.html"}


def _set_tag(html: str, pattern: str, tag: str, after: str | None = None) -> str:
    """Replace all matches of pattern with a single tag, or insert it."""
    matches = list(re.finditer(pattern, html, flags=re.S | re.I))
    if matches:
        first = matches[0]
        for m in reversed(matches[1:]):
            html = html[:m.start()] + html[m.end():]
        return html[:first.start()] + tag + html[first.end():]
    if after:
        m = re.search(after, html, flags=re.S | re.I)
        if m:
            return html[:m.end()] + "\n  " + tag + html[m.end():]
    return re.sub(r"</head>", "  " + tag + "\n</head>", html, count=1, flags=re.I)


def apply_head_meta(html: str, title: str, description: str, url: str | None = None, robots: bool = False) -> str:
    t, dsc = escape(title, quote=False), escape(description, quote=True)
    t_attr = escape(title, quote=True)
    desc_re = r'<meta\s+name="description"\s+content="[^"]*"\s*/?>'
    html = _set_tag(html, r"<title>.*?</title>", f"<title>{t}</title>")
    html = _set_tag(html, desc_re, f'<meta name="description" content="{dsc}"/>', after=r"<title>.*?</title>")
    anchor = desc_re
    if url:
        html = _set_tag(html, r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
                        f'<link rel="canonical" href="{url}"/>', after=anchor)
        anchor = r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>'
    if robots:
        html = _set_tag(html, r'<meta\s+name="robots"\s+content="[^"]*"\s*/?>',
                        f'<meta name="robots" content="{ROBOTS_CONTENT}"/>', after=anchor)
        anchor = r'<meta\s+name="robots"\s+content="[^"]*"\s*/?>'
    social = [
        ("property", "og:title", t_attr),
        ("property", "og:description", dsc),
    ]
    if url:
        social.append(("property", "og:url", url))
    social += [("name", "twitter:title", t_attr), ("name", "twitter:description", dsc)]
    for attr, key, val in social:
        html = _set_tag(
            html,
            rf'<meta\s+{attr}="{re.escape(key)}"\s+content="[^"]*"\s*/?>',
            f'<meta {attr}="{key}" content="{val}"/>',
            after=anchor,
        )
        anchor = rf'<meta\s+{attr}="{re.escape(key)}"\s+content="[^"]*"\s*/?>'
    if not re.search(r'<meta\s+name="twitter:card"', html, flags=re.I):
        html = _set_tag(html, r'<meta\s+name="twitter:card"[^>]*>', '<meta name="twitter:card" content="summary"/>', after=anchor)
    return html


def apply_route_seo(html: str, slug: str) -> str:
    seo = build_route_seo(slug, parse_route_data(html))
    return apply_head_meta(html, seo["title"], seo["description"], seo["url"], robots=True)


def update_routes() -> tuple[list[str], int]:
    changed, skipped = [], 0
    for path in sorted(ROUTES_DIR.glob("*.html")):
        original = path.read_text(encoding="utf-8")
        if is_redirect_page(original):
            skipped += 1
            continue
        result = apply_route_seo(original, path.stem)
        if result != original:
            path.write_text(result, encoding="utf-8")
            changed.append(f"{SITE_ROOT}/routes/{path.name}")
    return changed, skipped


def update_hubs() -> list[str]:
    changed = []
    for rel, (title, desc) in HUB_PAGES.items():
        path = REPO_ROOT / rel
        original = path.read_text(encoding="utf-8")
        canon = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', original)
        result = apply_head_meta(original, title, desc, canon.group(1) if canon else None)
        if result != original:
            path.write_text(result, encoding="utf-8")
            url = canon.group(1) if canon else f"{SITE_ROOT}/{rel}"
            changed.append(url)
    return changed


def update_sitemap(urls: list[str]) -> int:
    today = date.today().isoformat()
    text = SITEMAP_PATH.read_text(encoding="utf-8")
    count = 0
    candidates = set()
    for u in urls:
        candidates.add(u)
        candidates.add(re.sub(r"/index\.html$", "/", u))
    for u in candidates:
        pat = re.compile(rf"(<loc>{re.escape(u)}</loc>\s*<lastmod>)[^<]*(</lastmod>)")
        text, n = pat.subn(rf"\g<1>{today}\g<2>", text)
        count += n
    SITEMAP_PATH.write_text(text, encoding="utf-8")
    return count


def main() -> int:
    routes, skipped = update_routes()
    hubs = update_hubs()
    bumped = update_sitemap(routes + hubs)
    print(f"[seo] routes updated: {len(routes)} (redirects skipped: {skipped})")
    print(f"[seo] hub pages updated: {len(hubs)}")
    print(f"[seo] sitemap lastmod bumped: {bumped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
