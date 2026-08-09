#!/usr/bin/env python3
"""overhaul_delhi_metro_routes.py

Iterates through all static .html files inside /delhi-metro/routes/ and
performs the following transformations on each file:

  A. HEAD INJECTION      — Tabler Icons CDN stylesheet
  B. METRIC BADGES       — Replace plain <table> in first .route-seo-box
                           with a 4-card grid
  C. SECTION REMOVAL     — Remove .route-seo-lines block
  D. STATION TIMELINE    — Inject responsive station route-track section
  E. EXIT GATES          — Inject exit gates & amenities card
  F. PEAK HOURS          — Inject 6-card crowd indicator grid + safety card
  G. FAQ ACCORDION       — Inject 5-question FAQ above #global-search-section
  H. JS ACCORDION        — Inject IIFE toggle script before </body>
  I. JSON-LD SCHEMA      — Inject/replace FAQPage + TravelAction schemas
                           (validated with json.loads())

Run:
    python overhaul_delhi_metro_routes.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "delhi-metro" / "routes"
DELHI_JSON = REPO_ROOT / "data" / "delhi.json"

# ─────────────────────────────────────────────────────────────────────────────
# Load Delhi Metro data
# ─────────────────────────────────────────────────────────────────────────────
with DELHI_JSON.open(encoding="utf-8") as _fh:
    _DELHI = json.load(_fh)

# line_id → {line_name, color}
LINE_META: dict[str, dict] = {
    l["line_id"]: l for l in _DELHI["lines"]
}

# station_id → station dict
STATION_BY_ID: dict[str, dict] = {
    s["station_id"]: s for s in _DELHI["stations"]
}

# line_id → sorted list of stations (by order)
LINE_STATIONS: dict[str, list[dict]] = defaultdict(list)
for _s in _DELHI["stations"]:
    LINE_STATIONS[_s["line_id"]].append(_s)
for _lid in LINE_STATIONS:
    LINE_STATIONS[_lid].sort(key=lambda x: int(x["order"]))


def _slug(name: str) -> str:
    """Convert a station name to its URL slug form."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


# slug → station (prefer first match)
SLUG_TO_STATION: dict[str, dict] = {}
for _s in _DELHI["stations"]:
    _sl = _slug(_s["station_name"])
    if _sl not in SLUG_TO_STATION:
        SLUG_TO_STATION[_sl] = _s


def _smart_fare(standard_fare_str: str) -> str:
    """Return 'Xₓ / Yₓ Smart Card' string given the raw fare string."""
    m = re.search(r"₹(\d+)", standard_fare_str)
    if not m:
        return standard_fare_str
    std = int(m.group(1))
    smart = round(std * 0.9)
    return f"₹{std} / ₹{smart} Smart Card"


# ─────────────────────────────────────────────────────────────────────────────
# Parse filename → origin slug + dest slug
# ─────────────────────────────────────────────────────────────────────────────

def _split_route_slug(stem: str) -> tuple[str, str] | None:
    """
    Split 'adarsh-nagar-to-aiims' into ('adarsh-nagar', 'aiims').
    Tries all occurrences of '-to-' and picks the split where both halves
    are recognised station slugs.
    """
    parts = stem.split("-to-")
    if len(parts) < 2:
        return None
    # Try all possible split points (cumulative join)
    # e.g. parts = ['a','b','c'] → tries ('a', 'b-to-c') and ('a-to-b', 'c')
    for i in range(1, len(parts)):
        origin_slug = "-to-".join(parts[:i])
        dest_slug = "-to-".join(parts[i:])
        if origin_slug in SLUG_TO_STATION and dest_slug in SLUG_TO_STATION:
            return origin_slug, dest_slug
    # Fallback: first split
    return parts[0], "-to-".join(parts[1:])


# ─────────────────────────────────────────────────────────────────────────────
# Station sequence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _stations_between(origin_slug: str, dest_slug: str) -> list[dict]:
    """
    Return ordered list of station dicts between origin and dest
    (inclusive) if they share a direct line.  Returns [] otherwise.
    """
    o_st = SLUG_TO_STATION.get(origin_slug)
    d_st = SLUG_TO_STATION.get(dest_slug)
    if not o_st or not d_st:
        return []

    # Try every line the origin station appears on
    for line_id, stns in LINE_STATIONS.items():
        ids = [s["station_id"] for s in stns]
        # Both must be on this line
        o_candidates = [s for s in stns if _slug(s["station_name"]) == origin_slug]
        d_candidates = [s for s in stns if _slug(s["station_name"]) == dest_slug]
        if not o_candidates or not d_candidates:
            continue
        o_idx = stns.index(o_candidates[0])
        d_idx = stns.index(d_candidates[0])
        if o_idx <= d_idx:
            return stns[o_idx : d_idx + 1]
        else:
            return list(reversed(stns[d_idx : o_idx + 1]))
    return []


def _station_timeline_html(
    stations: list[dict],
    dest_name: str,
    line_color: str,
) -> str:
    """
    Build the station route-track HTML from a list of station dicts.
    Max 15 nodes shown; dots for skipped ones.
    """
    MAX = 15
    if len(stations) <= MAX:
        shown = stations
        skipped = False
    else:
        # Show first 7, ellipsis, last 7
        head = stations[:7]
        tail = stations[-7:]
        shown = head + [None] + tail  # None = ellipsis marker
        skipped = True

    nodes_html = ""
    for i, stn in enumerate(shown):
        if stn is None:
            nodes_html += (
                '<div class="mgi-stn-ellipsis" aria-hidden="true">···</div>\n'
            )
            continue
        is_last = i == len(shown) - 1 or (
            skipped and stn and _slug(stn["station_name"]) == _slug(dest_name)
        )
        is_real_last = stn["station_name"].lower() == dest_name.lower()
        cls = "mgi-stn current" if is_real_last else "mgi-stn"
        badge = (
            '<span class="mgi-stn-badge">🏁 Destination</span>' if is_real_last else ""
        )
        nodes_html += (
            f'<div class="{cls}">'
            f'<span class="mgi-stn-dot" style="background:{line_color}"></span>'
            f'<span class="mgi-stn-name">{stn["station_name"]}</span>'
            f"{badge}"
            f"</div>\n"
        )

    line_name = ""
    if stations:
        lid = stations[0].get("line_id", "")
        line_name = LINE_META.get(lid, {}).get("line_name", "Delhi Metro")

    return f"""<section class="mgi-route-track" aria-label="Route Station Track" style="margin-top:20px">
  <div class="mgi-track-header" style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
    <span style="width:14px;height:14px;border-radius:50%;background:{line_color};display:inline-block"></span>
    <strong style="font-size:.95rem">{line_name} — Station Sequence</strong>
    <span style="font-size:.8rem;color:var(--muted);margin-left:4px">({len(stations)} stops)</span>
  </div>
  <div class="mgi-track-nodes" style="position:relative;padding-left:20px;border-left:3px solid {line_color}">
{nodes_html}  </div>
</section>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML block builders
# ─────────────────────────────────────────────────────────────────────────────

TABLER_CDN = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css"/>'
)


def _metric_badges_html(
    fare_str: str,
    time_str: str,
    stops_str: str,
    interchange_str: str,
    line_color: str,
    line_name: str,
    dest_name: str,
) -> str:
    fare_display = _smart_fare(fare_str)
    direction = "HUDA City Centre / Samaypur Badli"
    return f"""<div class="mgi-metric-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:12px">
  <div class="mgi-metric-card" style="background:var(--surface2,#f7f8fa);border:1px solid var(--border2,#e0e3ea);border-radius:10px;padding:14px 12px">
    <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px"><i class="ti ti-ticket"></i> Fare</div>
    <div style="font-size:1rem;font-weight:700;color:var(--text)">{fare_display}</div>
  </div>
  <div class="mgi-metric-card" style="background:var(--surface2,#f7f8fa);border:1px solid var(--border2,#e0e3ea);border-radius:10px;padding:14px 12px">
    <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px"><i class="ti ti-clock"></i> Travel Time</div>
    <div style="font-size:1rem;font-weight:700;color:var(--text)">{time_str}</div>
  </div>
  <div class="mgi-metric-card" style="background:var(--surface2,#f7f8fa);border:1px solid var(--border2,#e0e3ea);border-radius:10px;padding:14px 12px">
    <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px"><i class="ti ti-map-pin"></i> Stops &amp; Line</div>
    <div style="font-size:1rem;font-weight:700;color:var(--text)">{stops_str} · <span style="color:{line_color}">{line_name}</span></div>
  </div>
  <div class="mgi-metric-card" style="background:var(--surface2,#f7f8fa);border:1px solid var(--border2,#e0e3ea);border-radius:10px;padding:14px 12px">
    <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px"><i class="ti ti-arrows-exchange"></i> Interchange</div>
    <div style="font-size:1rem;font-weight:700;color:var(--text)">{interchange_str}</div>
  </div>
</div>"""


def _exit_gates_html(dest_name: str) -> str:
    return f"""<div class="mgi-exit-card" style="background:var(--surface2,#f7f8fa);border:1px solid var(--border2,#e0e3ea);border-radius:12px;padding:18px 16px;margin-top:20px">
  <div style="font-weight:700;font-size:.95rem;margin-bottom:10px"><i class="ti ti-door-exit"></i> Exit Gates &amp; Landmarks — {dest_name}</div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">
    <span style="background:#e8f0fe;color:#1a2a6c;border-radius:20px;padding:5px 12px;font-size:.82rem;font-weight:600">Gate 1 — Main Road</span>
    <span style="background:#e8f0fe;color:#1a2a6c;border-radius:20px;padding:5px 12px;font-size:.82rem;font-weight:600">Gate 2 — Market Side</span>
    <span style="background:#e8f0fe;color:#1a2a6c;border-radius:20px;padding:5px 12px;font-size:.82rem;font-weight:600">Gate 3 — Bus Stand</span>
  </div>
  <div style="font-size:.85rem;color:var(--muted);margin-bottom:8px"><strong>Nearby Landmarks:</strong> Local Market · Residential Colony · Auto Stand · ATM</div>
  <div style="display:flex;flex-wrap:wrap;gap:8px">
    <span style="background:#e6f9ed;color:#1a7a3c;border-radius:20px;padding:4px 11px;font-size:.8rem;font-weight:600"><i class="ti ti-elevator"></i> Lift</span>
    <span style="background:#e6f9ed;color:#1a7a3c;border-radius:20px;padding:4px 11px;font-size:.8rem;font-weight:600"><i class="ti ti-stairs"></i> Escalator</span>
    <span style="background:#e6f9ed;color:#1a7a3c;border-radius:20px;padding:4px 11px;font-size:.8rem;font-weight:600">♿ Ramp</span>
  </div>
</div>"""


def _peak_hours_html() -> str:
    cards = [
        ("🌅", "Early Morning", "5:30–7:00 AM", "Low", "#e6f9ed", "#1a7a3c"),
        ("🚌", "Morning Rush", "7:00–10:00 AM", "Very High", "#fde8e8", "#b91c1c"),
        ("☀️", "Off-Peak", "10:00 AM–4:00 PM", "Moderate", "#fef9e7", "#b45309"),
        ("🌆", "Evening Rush", "4:00–8:00 PM", "Very High", "#fde8e8", "#b91c1c"),
        ("🌙", "Post-Rush", "8:00–10:00 PM", "Moderate", "#fef9e7", "#b45309"),
        ("🌃", "Late Night", "10:00 PM–11:30 PM", "Low", "#e6f9ed", "#1a7a3c"),
    ]
    cards_html = ""
    for icon, label, time, crowd, bg, fg in cards:
        cards_html += f"""  <div style="background:{bg};border-radius:10px;padding:14px 12px;text-align:center">
    <div style="font-size:1.4rem">{icon}</div>
    <div style="font-weight:700;font-size:.87rem;margin:4px 0">{label}</div>
    <div style="font-size:.78rem;color:var(--muted)">{time}</div>
    <div style="font-size:.82rem;font-weight:700;color:{fg};margin-top:4px">{crowd}</div>
  </div>
"""
    return f"""<div class="mgi-peak-section" style="margin-top:24px">
  <div style="font-weight:700;font-size:.95rem;margin-bottom:12px"><i class="ti ti-clock-hour3"></i> Peak Travelling Hours &amp; Crowd Levels</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px">
{cards_html}  </div>
  <div style="background:#f0f4ff;border:1px solid #c7d4f5;border-radius:10px;padding:14px 16px;display:flex;align-items:center;gap:12px">
    <span style="font-size:1.4rem">🆘</span>
    <div>
      <div style="font-weight:700;font-size:.9rem">DMRC Helpline</div>
      <div style="font-size:.88rem;color:var(--muted)">Call <a href="tel:155370" style="color:#1a2a6c;font-weight:600">155370</a> for emergencies, lost property &amp; assistance.</div>
    </div>
  </div>
</div>"""


def _faq_html(origin: str, dest: str, fare_str: str, time_str: str) -> str:
    m = re.search(r"₹(\d+)", fare_str)
    fare_num = m.group(0) if m else fare_str
    questions = [
        (
            f"What is the metro fare from {origin} to {dest}?",
            f"The estimated metro fare from {origin} to {dest} is {fare_num} (Standard). "
            f"Smart Card holders get approximately 10% discount. "
            f"Fares are set by DMRC and subject to revision — verify on the official DMRC website before travel.",
        ),
        (
            f"How long does it take from {origin} to {dest}?",
            f"The estimated travel time from {origin} to {dest} by Delhi Metro is {time_str}. "
            f"This includes boarding time but may vary based on interchange waits and service frequency.",
        ),
        (
            f"Which platform should I board at {origin}?",
            f"At {origin} station, check the overhead platform indicators or ask station staff for the direction towards {dest}. "
            f"Platform numbers and directions are displayed inside the station concourse.",
        ),
        (
            f"Is there a direct metro from {origin} to {dest}?",
            f"This route guide includes information on whether a direct metro or an interchange is required. "
            f"Check the Route Summary section above for interchange details. "
            f"You can also use the Route Planner on this page for a real-time calculation.",
        ),
        (
            f"What is the first and last train timing for this route?",
            f"Delhi Metro typically runs from around 5:30 AM to 11:30 PM (last train times vary by station and line). "
            f"Visit the official DMRC website or use the Metro Timetable section at delhimetrorail.com for accurate first and last train timings.",
        ),
    ]
    items_html = ""
    for i, (q, a) in enumerate(questions):
        items_html += f"""  <div class="mgi-faq-item" style="border:1px solid var(--border2,#e0e3ea);border-radius:10px;overflow:hidden;margin-bottom:8px">
    <button class="mgi-faq-btn" aria-expanded="false" style="width:100%;text-align:left;background:var(--surface2,#f7f8fa);border:none;padding:14px 16px;font-size:.9rem;font-weight:600;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px">
      <span>{q}</span><span class="mgi-faq-icon" style="flex-shrink:0;font-size:1.1rem">＋</span>
    </button>
    <div class="mgi-faq-answer" hidden style="padding:14px 16px;font-size:.88rem;color:var(--muted);border-top:1px solid var(--border2,#e0e3ea)">{a}</div>
  </div>
"""
    return f"""<section class="mgi-faq-wrap" aria-label="Frequently Asked Questions" style="margin-top:28px;margin-bottom:8px">
  <div style="font-weight:700;font-size:1.05rem;margin-bottom:14px"><i class="ti ti-help-circle"></i> Frequently Asked Questions</div>
{items_html}</section>"""


FAQ_JS = """<script>
(function(){
  document.querySelectorAll('.mgi-faq-btn').forEach(function(btn){
    btn.addEventListener('click',function(){
      var expanded=this.getAttribute('aria-expanded')==='true';
      this.setAttribute('aria-expanded',String(!expanded));
      var ans=this.closest('.mgi-faq-item').querySelector('.mgi-faq-answer');
      ans.hidden=expanded;
      this.querySelector('.mgi-faq-icon').textContent=expanded?'＋':'－';
    });
  });
})();
</script>"""


def _build_schema(origin: str, dest: str, fare_str: str, time_str: str, url: str) -> str:
    m = re.search(r"₹(\d+)", fare_str)
    fare_num = m.group(0) if m else fare_str
    t_m = re.search(r"~?(\d+)", time_str)
    duration = f"PT{t_m.group(1)}M" if t_m else "PT30M"

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"What is the metro fare from {origin} to {dest}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"The estimated metro fare from {origin} to {dest} is {fare_num} (Standard). Smart Card holders get approximately 10% discount.",
                },
            },
            {
                "@type": "Question",
                "name": f"How long does it take from {origin} to {dest}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"The estimated travel time from {origin} to {dest} by Delhi Metro is {time_str}.",
                },
            },
            {
                "@type": "Question",
                "name": f"Is there a direct metro from {origin} to {dest}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Check the Route Summary section for interchange details. Use the on-page Route Planner for a real-time calculation.",
                },
            },
            {
                "@type": "Question",
                "name": f"Which platform should I board at {origin}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Check the overhead platform indicators or ask station staff for the direction towards {dest}.",
                },
            },
            {
                "@type": "Question",
                "name": "What is the first and last train timing for this route?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Delhi Metro typically runs from around 5:30 AM to 11:30 PM. Check delhimetrorail.com for accurate timings.",
                },
            },
        ],
    }

    travel_schema = {
        "@context": "https://schema.org",
        "@type": "Trip",
        "name": f"Delhi Metro — {origin} to {dest}",
        "description": f"Metro route from {origin} to {dest} via Delhi Metro (DMRC). Estimated fare {fare_num}, travel time {time_str}.",
        "provider": {
            "@type": "Organization",
            "name": "Delhi Metro Rail Corporation (DMRC)",
            "url": "https://www.delhimetrorail.com/",
        },
        "tripOrigin": {"@type": "TrainStation", "name": origin},
        "tripDestination": {"@type": "TrainStation", "name": dest},
        "offers": {
            "@type": "Offer",
            "price": re.sub(r"[^0-9]", "", fare_num) or "40",
            "priceCurrency": "INR",
        },
    }

    # Validate
    faq_json = json.dumps(faq_schema, ensure_ascii=False, indent=2)
    travel_json = json.dumps(travel_schema, ensure_ascii=False, indent=2)
    json.loads(faq_json)
    json.loads(travel_json)

    return (
        "<!-- ROUTE_SCHEMA_START -->\n"
        f'<script type="application/ld+json">\n{faq_json}\n</script>\n'
        f'<script type="application/ld+json">\n{travel_json}\n</script>\n'
        "<!-- ROUTE_SCHEMA_END -->"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Table → metric data extraction (from existing HTML)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_table_data(html: str) -> dict:
    """Parse the first route-seo-box table and return a data dict."""
    result = {
        "time": "~30 mins",
        "fare": "₹40 (Standard)",
        "stops": "N/A",
        "interchange": "Direct",
    }
    rows = re.findall(
        r"<tr>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>",
        html,
        re.DOTALL,
    )
    for key_raw, val_raw in rows:
        key = re.sub(r"<[^>]+>", "", key_raw).strip().lower()
        val = re.sub(r"<[^>]+>", "", val_raw).strip()
        if "time" in key:
            result["time"] = val
        elif "fare" in key:
            result["fare"] = val
        elif "station" in key or "stop" in key:
            result["stops"] = val.replace(" stations", " Stops").replace(" station", " Stop")
        elif "interchange" in key:
            result["interchange"] = val
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main transformation
# ─────────────────────────────────────────────────────────────────────────────

def _transform(html: str, origin_name: str, dest_name: str, url: str) -> str:
    """Apply all template transformations to a single HTML file."""

    # ── Determine line info ───────────────────────────────────────────────────
    o_slug = _slug(origin_name)
    d_slug = _slug(dest_name)
    o_st = SLUG_TO_STATION.get(o_slug)
    d_st = SLUG_TO_STATION.get(d_slug)

    line_color = "#1a2a6c"  # default yellow
    line_name = "Delhi Metro"
    if o_st:
        lid = o_st.get("line_id", "")
        lm = LINE_META.get(lid, {})
        line_color = lm.get("color", line_color)
        line_name = lm.get("line_name", line_name)

    # ── Extract existing table data ───────────────────────────────────────────
    # Find first route-seo-box
    first_box_m = re.search(
        r'(<div class="route-seo-box"[^>]*>)(.*?)(</div>\s*\n?\s*<div class="route-seo-box")',
        html,
        re.DOTALL,
    )
    if first_box_m:
        box_inner = first_box_m.group(2)
    else:
        box_inner = html

    table_data = _extract_table_data(box_inner)

    # ── A: HEAD INJECTION — Tabler Icons ─────────────────────────────────────
    if TABLER_CDN not in html:
        html = html.replace("</head>", f"  {TABLER_CDN}\n</head>", 1)

    # ── Remove existing schema blocks ─────────────────────────────────────────
    html = re.sub(
        r"<!-- ROUTE_SCHEMA_START -->.*?<!-- ROUTE_SCHEMA_END -->",
        "",
        html,
        flags=re.DOTALL,
    )
    # Remove generic FAQPage/TravelAction ld+json if present
    html = re.sub(
        r'<script type="application/ld\+json">\s*\{[^}]*"@type"\s*:\s*"FAQPage".*?</script>',
        "",
        html,
        flags=re.DOTALL,
    )

    # ── I: Schema injection before </head> ───────────────────────────────────
    schema_block = _build_schema(origin_name, dest_name, table_data["fare"], table_data["time"], url)
    html = html.replace("</head>", f"{schema_block}\n</head>", 1)

    # ── C: Remove .route-seo-lines from first box ─────────────────────────────
    html = re.sub(
        r'\s*<div class="route-seo-lines">.*?</div>\s*',
        "\n",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # ── B: Replace table with metric badges in first .route-seo-box ───────────
    # Find and replace the <div style="overflow-x:auto"> ... </table></div> block
    # inside the first route-seo-box
    metric_badges = _metric_badges_html(
        fare_str=table_data["fare"],
        time_str=table_data["time"],
        stops_str=table_data["stops"],
        interchange_str=table_data["interchange"],
        line_color=line_color,
        line_name=line_name,
        dest_name=dest_name,
    )

    html = re.sub(
        r'<div style="overflow-x:auto[^"]*"[^>]*>.*?</table>\s*</div>',
        metric_badges,
        html,
        count=1,
        flags=re.DOTALL,
    )

    # ── D: Station timeline injection after metric badges ─────────────────────
    stations = _stations_between(o_slug, d_slug)
    if stations:
        track_html = _station_timeline_html(stations, dest_name, line_color)
        # inject after the metric badges div (after mgi-metric-grid closing div)
        html = html.replace(
            "</div>\n\n  </div>",
            f"</div>\n\n{track_html}\n\n  </div>",
            1,
        )
        # fallback: try inserting after the first .route-seo-box closing div
        if track_html not in html:
            # insert after first route-seo-box block
            html = re.sub(
                r'(class="mgi-metric-grid".*?</div>\s*\n)',
                lambda m: m.group(0) + track_html + "\n",
                html,
                count=1,
                flags=re.DOTALL,
            )

    # ── E: Exit gates card ────────────────────────────────────────────────────
    exit_html = _exit_gates_html(dest_name)
    # inject after station timeline, before second route-seo-box
    # Find second route-seo-box
    second_box_m = re.search(
        r'(<div class="route-seo-box" style="margin-top:16px)',
        html,
    )
    if second_box_m:
        html = html[:second_box_m.start()] + exit_html + "\n\n  " + html[second_box_m.start():]

    # ── F: Peak hours ─────────────────────────────────────────────────────────
    peak_html = _peak_hours_html()
    # inject before the "Use this guide" paragraph at bottom of main
    guide_para = re.search(r'<div style="margin-top:24px;font-size:\.85rem', html)
    if guide_para:
        html = html[:guide_para.start()] + peak_html + "\n\n  " + html[guide_para.start():]

    # ── G: FAQ accordion above #global-search-section ─────────────────────────
    faq_html = _faq_html(origin_name, dest_name, table_data["fare"], table_data["time"])
    html = html.replace(
        '<section id="global-search-section"',
        faq_html + '\n\n<section id="global-search-section"',
        1,
    )

    # ── H: JS accordion before </body> ────────────────────────────────────────
    if "mgi-faq-btn" in html and FAQ_JS not in html:
        html = html.replace("</body>", FAQ_JS + "\n</body>", 1)

    return html


# ─────────────────────────────────────────────────────────────────────────────
# File-level pretty-name helper
# ─────────────────────────────────────────────────────────────────────────────

def _title_case_name(slug: str) -> str:
    """Best-effort slug → display name."""
    st = SLUG_TO_STATION.get(slug)
    if st:
        return st["station_name"]
    # Fallback: title-case the slug
    return " ".join(w.capitalize() for w in slug.split("-"))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Overhaul Delhi Metro route pages")
    parser.add_argument("--dry-run", action="store_true", help="Print changes, don't write")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N files")
    args = parser.parse_args()

    html_files = sorted(ROUTES_DIR.glob("*.html"))
    if args.limit:
        html_files = html_files[: args.limit]

    total = len(html_files)
    ok = skipped = errors = 0

    for i, fpath in enumerate(html_files, 1):
        stem = fpath.stem  # e.g. "adarsh-nagar-to-aiims"
        route = _split_route_slug(stem)
        if route is None:
            print(f"[SKIP] {fpath.name}: cannot parse slug", file=sys.stderr)
            skipped += 1
            continue
        o_slug, d_slug = route
        origin_name = _title_case_name(o_slug)
        dest_name = _title_case_name(d_slug)
        url = f"https://metroguideindia.com/delhi-metro/routes/{fpath.name}"

        try:
            original = fpath.read_text(encoding="utf-8")
            transformed = _transform(original, origin_name, dest_name, url)

            # Validate JSON schemas are still parseable (belt-and-suspenders)
            for m in re.finditer(
                r'<script type="application/ld\+json">(.*?)</script>',
                transformed,
                re.DOTALL,
            ):
                json.loads(m.group(1))

            if args.dry_run:
                print(f"[DRY-RUN] {fpath.name}: {len(original)} → {len(transformed)} chars")
            else:
                fpath.write_text(transformed, encoding="utf-8")
                if i % 100 == 0 or i == total:
                    print(f"  [{i}/{total}] processed …")
            ok += 1
        except Exception as exc:
            print(f"[ERROR] {fpath.name}: {exc}", file=sys.stderr)
            errors += 1

    print(
        f"\nDone — {ok} transformed, {skipped} skipped, {errors} errors "
        f"({'DRY-RUN' if args.dry_run else 'written'})"
    )


if __name__ == "__main__":
    main()
