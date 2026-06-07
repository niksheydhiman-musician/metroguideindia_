#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "routes"
ROUTE_JSON = REPO_ROOT / "data" / "rrts-routes.json"
TEMPLATE_ROUTE_PATH = ROUTES_DIR / "anand-vihar-to-begumpul.html"
PARKING_BLOG_URL = "https://metroguideindia.com/blog/rrts-parking-charges-monthly-pass-station-locations.html"
SITE_ROOT_URL = "https://metroguideindia.com"

BLOCK_START = "<!-- RRTS_ROUTE_DATA_INJECT_START -->"
BLOCK_END = "<!-- RRTS_ROUTE_DATA_INJECT_END -->"
SUMMARY_DETAILS_START = "<!-- RRTS_ROUTE_SUMMARY_DETAILS_START -->"
SUMMARY_DETAILS_END = "<!-- RRTS_ROUTE_SUMMARY_DETAILS_END -->"
RRTS_RED = "#C0392B"
MEERUT_METRO_GREEN = "#27764A"
DIRECT_INTERCHANGE_TEXT = "Direct (No Interchange)"
DIRECT_RRTS_ROUTE_SLUGS = {
    "sarai-kale-khan",
    "new-ashok-nagar",
    "anand-vihar",
    "sahibabad",
    "ghaziabad",
    "guldhar",
    "duhai",
    "muradnagar",
    "modinagar-south",
    "modinagar-north",
    "meerut-south",
    "shatabdi-nagar",
    "begumpul",
    "modipuram",
}
DIRECT_RRTS_HUB_SLUGS = {"meerut-south", "shatabdi-nagar", "begumpul", "modipuram"}
TABLER_ICONS_CDN = "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css"


@dataclass
class StationMeta:
    station_name: str
    service_type: str
    geographical_location: str
    operational_timings: dict[str, Any]
    exit_gates: Any
    parking_profile: dict[str, Any]
    special_facilities: dict[str, Any]
    control_room_contact: str = ""
    parking_tariff_summary: str = ""


@dataclass(frozen=True)
class MgiBlueprint:
    tabler_link: str
    style_block: str
    sections_block: str
    faq_script: str


def normalize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", value or "", flags=re.S)).strip()


def slug_variants(value: str) -> set[str]:
    base = normalize_slug(value)
    variants = {base}
    if "modi-nagar" in base:
        variants.add(base.replace("modi-nagar", "modinagar"))
    if "modinagar" in base:
        variants.add(base.replace("modinagar", "modi-nagar"))
    if "murad-nagar" in base:
        variants.add(base.replace("murad-nagar", "muradnagar"))
    if "muradnagar" in base:
        variants.add(base.replace("muradnagar", "murad-nagar"))
    return {variant for variant in variants if variant}


def find_station_meta(value: str, station_map: dict[str, StationMeta]) -> StationMeta | None:
    for variant in slug_variants(value):
        meta = station_map.get(variant)
        if meta:
            return meta
    return None


def slug_to_path(slug: str) -> Path:
    return ROUTES_DIR / f"{slug}.html"


def normalize_service_type(system_type: str | None) -> str:
    txt = (system_type or "").lower()
    if "dual" in txt:
        return "Dual-Service"
    if "metro" in txt and "namo bharat" not in txt and "rrts" not in txt:
        return "Metro"
    if "metro" in txt and "rrts" in txt:
        return "Dual-Service"
    return "RRTS"


def normalize_line_label(raw_line: str, is_direct_route: bool) -> str:
    line = clean_text(raw_line)
    if is_direct_route:
        return "Namo Bharat RRTS"
    if not line:
        return "Namo Bharat RRTS + Meerut Metro"
    if line == "RRTS + Metro":
        return "Namo Bharat RRTS + Meerut Metro"
    return line


def strip_existing_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def extract_step_stations(html: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", s).strip()
        for s in re.findall(r'<div class="step-name">(.*?)</div>', html, flags=re.S)
    ]


def parse_sub_line(html: str) -> dict[str, str]:
    m = re.search(r'<p class="rp-sub">(.*?)</p>', html, flags=re.S)
    if not m:
        return {}
    sub = re.sub(r"<.*?>", "", m.group(1))
    sub = re.sub(r"\s+", " ", sub).strip()
    parts = [segment.strip() for segment in sub.split("·") if segment.strip()]

    fare = ""
    est = ""
    distance = ""
    line = parts[0] if parts else ""
    fare_match = re.search(r"₹\s*([0-9,]+)", sub)
    if fare_match:
        fare = f"₹{fare_match.group(1)}"
    est_match = re.search(r"~\s*([0-9]+\s*min)", sub, flags=re.I)
    if est_match:
        est = est_match.group(1).replace("  ", " ").strip()
    distance_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*km", sub, flags=re.I)
    if distance_match:
        distance = distance_match.group(1)
    return {"standard_fare": fare, "estimated_time": est, "distance_km": distance, "line": line}


def parse_interchanges(html: str) -> str:
    patterns = [
        r"Interchanges:</strong>\s*([^<.]+)",
        r"Interchanges:\s*<strong>([^<]+)</strong>",
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return "Not listed"


def extract_route_terminals(html: str, slug: str) -> tuple[str, str]:
    stations = extract_step_stations(html)
    if len(stations) >= 2:
        return stations[0], stations[-1]

    h1_match = re.search(r'<h1 class="rp-title">(.*?)</h1>', html, flags=re.S)
    if h1_match:
        h1_text = re.sub(r"<.*?>", "", h1_match.group(1))
        h1_text = re.sub(r"\s+", " ", h1_text).strip()
        if "→" in h1_text:
            parts = [part.strip() for part in h1_text.split("→", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                return parts[0], parts[1]

    if "-to-" in slug:
        origin_slug, destination_slug = slug.split("-to-", 1)
        origin = origin_slug.replace("-", " ").title().strip()
        destination = destination_slug.replace("-", " ").title().strip()
        return origin, destination

    return "Origin", "Destination"


def find_div_block_bounds(html: str, start_marker: str, start_at: int = 0) -> tuple[int, int] | None:
    start = html.find(start_marker, start_at)
    if start == -1:
        return None

    token_re = re.compile(r"<div\b[^>]*>|</div>", flags=re.I)
    depth = 0
    for match in token_re.finditer(html, start):
        token = match.group(0)
        if token.lower().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start, match.end()
    return None


def replace_div_block(html: str, start_marker: str, replacement: str) -> str:
    bounds = find_div_block_bounds(html, start_marker)
    if not bounds:
        return html
    start, end = bounds
    return html[:start] + replacement + html[end:]


def remove_div_blocks(html: str, start_marker: str) -> str:
    result = html
    while True:
        bounds = find_div_block_bounds(result, start_marker)
        if not bounds:
            return result
        start, end = bounds
        result = result[:start] + result[end:]


def is_direct_rrts_route(slug: str) -> bool:
    if "-to-" not in slug:
        return False
    origin_slug, destination_slug = slug.split("-to-", 1)
    return (
        origin_slug in DIRECT_RRTS_ROUTE_SLUGS
        and destination_slug in DIRECT_RRTS_ROUTE_SLUGS
        and (origin_slug in DIRECT_RRTS_HUB_SLUGS or destination_slug in DIRECT_RRTS_HUB_SLUGS)
    )


def normalize_direct_route_steps(html: str) -> str:
    bounds = find_div_block_bounds(html, '<div class="rc-steps">')
    if not bounds:
        return html

    start, end = bounds
    block = html[start:end]
    block = remove_div_blocks(block, '<div class="step step-xchange">')
    block = block.replace(MEERUT_METRO_GREEN, RRTS_RED)
    block = block.replace(">Meerut Metro<", ">Namo Bharat RRTS<")
    return html[:start] + block + html[end:]


def normalize_direct_route_copy(html: str) -> str:
    updated = normalize_direct_route_steps(html)
    updated = re.sub(
        r'(<p class="rp-sub">)(.*?)( · )',
        r"\1Namo Bharat RRTS\3",
        updated,
        count=1,
        flags=re.S,
    )
    updated = re.sub(
        r'(<div class="route-seo-box"[^>]*data-system=")[^"]+(")',
        r"\1Namo Bharat RRTS\2",
        updated,
        count=1,
    )
    updated = re.sub(r"\s*<div class=\"route-seo-note\">.*?</div>\s*", "\n", updated, flags=re.S)

    replacements = {
        "Namo Bharat RRTS + Meerut Metro": "Namo Bharat RRTS",
        "RRTS + Metro": "Namo Bharat RRTS",
        "combined Namo Bharat RRTS route": "direct Namo Bharat RRTS route",
        " (RRTS–Metro Interchange)": "",
        " (Metro Interchange)": "",
        "1 (With Interchange)": DIRECT_INTERCHANGE_TEXT,
        "0 (Direct Route)": DIRECT_INTERCHANGE_TEXT,
        "None (Direct)": DIRECT_INTERCHANGE_TEXT,
        "1 interchange": DIRECT_INTERCHANGE_TEXT,
    }
    for old, new in replacements.items():
        updated = updated.replace(old, new)

    updated = updated.replace(
        "before you switch to the standard Meerut Metro coach.",
        "on this direct Namo Bharat RRTS route.",
    )
    updated = re.sub(
        r'(<strong>Interchanges:</strong>\s*)[^<.]+(\.?)',
        rf"\1{DIRECT_INTERCHANGE_TEXT}\2",
        updated,
        count=1,
    )
    updated = re.sub(
        r'(<li>Interchanges:\s*<strong>).*?(</strong></li>)',
        rf"\1{DIRECT_INTERCHANGE_TEXT}\2",
        updated,
        count=1,
        flags=re.S,
    )
    updated = re.sub(
        r'("text":\s*")Interchanges on the .*? route: .*?(")',
        rf'\1Interchanges on this route: {DIRECT_INTERCHANGE_TEXT}.\2',
        updated,
        count=1,
        flags=re.S,
    )
    return updated


def build_rrts_meta(
    origin: str, destination: str, estimated_time: str, line: str, distance_km: str, standard_fare: str
) -> dict[str, str]:
    clean_origin = re.sub(r"\s+", " ", origin).strip() or "Origin"
    clean_destination = re.sub(r"\s+", " ", destination).strip() or "Destination"
    clean_time = re.sub(r"\s+", " ", estimated_time).strip() or "the expected travel time"
    clean_line = re.sub(r"\s+", " ", line).strip() or "Namo Bharat RRTS corridor"
    clean_distance = re.sub(r"\s+", " ", distance_km).strip()
    clean_fare = re.sub(r"\s+", " ", standard_fare).strip() or "the latest"

    title = f"{clean_origin} to {clean_destination} RRTS Route: Fare, Time & Stations (Updated)"
    description = (
        f"Traveling from {clean_origin} to {clean_destination}? The journey takes roughly {clean_time} "
        f"via the {clean_line}. Click for the 2026 fare chart, first/last train timings, "
        f"and the exact exit gate map for {clean_destination} Station."
    )
    og_title = f"{clean_origin} to {clean_destination} Route | MetroGuideIndia"
    og_distance = f"{clean_distance} km, " if clean_distance else ""
    og_description = f"{clean_origin} to {clean_destination}: {og_distance}~{clean_time}, {clean_fare} fare."
    canonical = f"{SITE_ROOT_URL}/routes/{normalize_slug(clean_origin)}-to-{normalize_slug(clean_destination)}.html"

    return {
        "title": title,
        "description": description,
        "og_title": og_title,
        "og_description": og_description,
        "canonical": canonical,
    }


def replace_or_insert_meta(html: str, pattern: str, replacement: str) -> str:
    if re.search(pattern, html, flags=re.S):
        return re.sub(pattern, replacement, html, count=1, flags=re.S)
    return re.sub(r"(</head>)", replacement + "\n\\1", html, count=1, flags=re.S)


def replace_canonical_meta(html: str, canonical_url: str) -> str:
    canonical_tag = f'<link rel="canonical" href="{escape(canonical_url, quote=True)}"/>'
    clean = re.sub(r"\s*<link rel=\"canonical\" href=\".*?\"\s*/?>", "", html, flags=re.I)
    if re.search(r'<meta name="description" content=".*?"\s*/?>', clean, flags=re.S):
        return re.sub(
            r'(<meta name="description" content=".*?"\s*/?>)',
            r"\1\n  " + canonical_tag,
            clean,
            count=1,
            flags=re.S,
        )
    return re.sub(r"(</head>)", "  " + canonical_tag + "\n\\1", clean, count=1, flags=re.S)


def inject_meta_template(html: str, meta: dict[str, str]) -> str:
    escaped_title = escape(meta["title"])
    escaped_description = escape(meta["description"], quote=True)
    escaped_og_title = escape(meta["og_title"], quote=True)
    escaped_og_description = escape(meta["og_description"], quote=True)

    updated = replace_or_insert_meta(html, r"<title>.*?</title>", f"<title>{escaped_title}</title>")
    updated = replace_or_insert_meta(
        updated,
        r'<meta name="description" content=".*?"\s*/?>',
        f'<meta name="description" content="{escaped_description}"/>',
    )
    updated = replace_canonical_meta(updated, meta["canonical"])
    updated = replace_or_insert_meta(
        updated,
        r'<meta property="og:title" content=".*?"\s*/?>',
        f'<meta property="og:title" content="{escaped_og_title}"/>',
    )
    updated = replace_or_insert_meta(
        updated,
        r'<meta property="og:description" content=".*?"\s*/?>',
        f'<meta property="og:description" content="{escaped_og_description}"/>',
    )
    return updated


def parse_first_last_train(timings: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(timings, dict) or not timings:
        return "Not listed", "Not listed"

    first_candidates: list[str] = []
    last_candidates: list[str] = []
    for key, value in timings.items():
        if not isinstance(value, str):
            continue
        key_l = key.lower()
        clean_label = re.sub(r"^(first|last)(?:_train)?_?", "", key_l).strip("_")
        label = clean_label.replace("_", " ").strip().title()
        pair = f"{label}: {value}" if label else value
        if "first" in key_l:
            first_candidates.append(pair)
        elif "last" in key_l:
            last_candidates.append(pair)

    first = " | ".join(first_candidates) if first_candidates else "Not listed"
    last = " | ".join(last_candidates) if last_candidates else "Not listed"
    return first, last


def normalize_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def summarize_parking(origin_station: StationMeta | None) -> str:
    if not origin_station or not isinstance(origin_station.parking_profile, dict) or not origin_station.parking_profile:
        return "Not listed"
    profile = origin_station.parking_profile
    parts: list[str] = []
    available = profile.get("parking_available")
    if isinstance(available, bool):
        parts.append("Available" if available else "Not available")
    zone = profile.get("zone")
    if zone:
        parts.append(f"Zone: {zone}")
    live = profile.get("live_capacity")
    if isinstance(live, dict) and live:
        caps = []
        for key, value in live.items():
            if value in (None, "", [], {}):
                continue
            caps.append(f"{normalize_label(str(key))} {value}")
        if caps:
            parts.append("Capacity: " + ", ".join(caps))
    if origin_station.parking_tariff_summary:
        parts.append(f"Tariff: {origin_station.parking_tariff_summary}")
    return " | ".join(parts) if parts else "Not listed"


def list_facilities(origin_station: StationMeta | None) -> list[str]:
    if not origin_station or not isinstance(origin_station.special_facilities, dict) or not origin_station.special_facilities:
        return []
    details: list[str] = []
    for key, value in origin_station.special_facilities.items():
        label = normalize_label(str(key))
        if value is True:
            details.append(label)
        elif value in (False, None, "", [], {}):
            continue
        elif isinstance(value, list):
            joined = ", ".join(str(v) for v in value if v not in (None, "", [], {}))
            if joined:
                details.append(f"{label}: {joined}")
        else:
            details.append(f"{label}: {value}")
    return details


def summarize_facilities(origin_station: StationMeta | None, limit: int | None = None) -> str:
    facilities = list_facilities(origin_station)
    if not facilities:
        return "Not listed"
    if not limit or len(facilities) <= limit:
        return ", ".join(facilities)
    return ", ".join(facilities[:limit]) + f", +{len(facilities) - limit} more"


def get_station_route_details(
    html: str, route: dict[str, Any], station_map: dict[str, StationMeta]
) -> tuple[str, str, list[tuple[str, str, str]], StationMeta | None]:
    fallback_stations = extract_step_stations(html)
    origin_name = fallback_stations[0] if fallback_stations else ""
    origin_meta = find_station_meta(origin_name, station_map) if origin_name else None

    first_train, last_train = parse_first_last_train(
        route.get("timings") if isinstance(route.get("timings"), dict) else (origin_meta.operational_timings if origin_meta else {})
    )
    exits = normalize_exit_items(route, origin_meta)
    return first_train, last_train, exits, origin_meta


def summarize_exit_blueprints(exits: list[tuple[str, str, str]], limit: int | None = None) -> str:
    if not exits:
        return "Not listed"
    clipped = exits[:limit] if limit else exits
    text = "; ".join(f"{st} — {gate}: {landmark}" for st, gate, landmark in clipped)
    if limit and len(exits) > limit:
        text += f"; +{len(exits) - limit} more"
    return text


def strip_existing_summary_details(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(SUMMARY_DETAILS_START)}.*?{re.escape(SUMMARY_DETAILS_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def build_route_summary_details_html(
    first_train: str, last_train: str, exit_summary: str, parking_summary: str, facilities_summary: str
) -> str:
    parking_text = escape(parking_summary)
    parking_link = (
        f'<a href="{escape(PARKING_BLOG_URL)}" target="_blank" rel="noopener noreferrer" '
        'style="color:#B42318;font-weight:700;text-decoration:none">Read parking charges, passes & station locations ↗</a>'
    )
    return f"""
{SUMMARY_DETAILS_START}
<div class="rc-route-meta" style="margin-top:12px;padding:12px 14px;border:1px solid var(--border2,#e2e8f0);border-radius:14px;background:linear-gradient(180deg,#fff,#fcfcfd);box-shadow:0 6px 24px rgba(2,6,23,.03);display:grid;gap:0">
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">First Train:</strong> {escape(first_train)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Last Train:</strong> {escape(last_train)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Exit Gate Blueprint:</strong> {escape(exit_summary)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Parking:</strong> {parking_text}<br><span style="display:inline-block;margin-top:6px">{parking_link}</span></div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5"><strong style="font-size:1.02rem">Facilities:</strong> {escape(facilities_summary)}</div>
</div>
{SUMMARY_DETAILS_END}
""".strip()


def inject_route_summary_details(
    html: str, first_train: str, last_train: str, exit_summary: str, parking_summary: str, facilities_summary: str
) -> str:
    clean = strip_existing_summary_details(html)
    clean = re.sub(r"\n{3,}(\s*<div class=\"route-seo-box\")", r"\n\n\1", clean)
    clean = re.sub(r"\n{3,}(\s*<div class=\"quick-facts\")", r"\n\n\1", clean)
    details = build_route_summary_details_html(first_train, last_train, exit_summary, parking_summary, facilities_summary)

    if '<div class="rc-steps">' in clean and re.search(r'<div class="route-seo-box"(?:\s|>)', clean):
        return re.sub(
            r'(\s*<div class="route-seo-box"(?:\s|>))',
            "\n" + details + r"\1",
            clean,
            count=1,
            flags=re.S,
        )

    if '<div class="rc-steps">' in clean and re.search(r'<div class="quick-facts"(?:\s|>)', clean):
        return re.sub(
            r'(\s*<div class="quick-facts"(?:\s|>))',
            "\n" + details + r"\1",
            clean,
            count=1,
            flags=re.S,
        )

    fallback_pattern = r'(<div class="rc-summary">.*?</div>\s*)(<div class="rc-steps">)'
    fallback_replacement = r"\1\n" + details + r"\n      \2"
    return re.sub(fallback_pattern, fallback_replacement, clean, count=1, flags=re.S)


@lru_cache(maxsize=1)
def load_mgi_blueprint() -> MgiBlueprint:
    html = TEMPLATE_ROUTE_PATH.read_text(encoding="utf-8")
    tabler_match = re.search(
        rf'(<link rel="stylesheet" href="{re.escape(TABLER_ICONS_CDN)}"\s*/?>)',
        html,
        flags=re.I,
    )
    style_match = re.search(r"(<style>\s*.*?\.mgi-sections\s*\{.*?</style>)", html, flags=re.S)
    sections_match = re.search(r'(<div class="mgi-sections">.*?<!-- end \.mgi-sections -->)', html, flags=re.S)
    faq_script_match = re.search(
        r"(<script>\s*\(function \(\) \{\s*document\.querySelectorAll\('\[data-mgi-faq\]'\).*?</script>)",
        html,
        flags=re.S,
    )
    if not (tabler_match and style_match and sections_match and faq_script_match):
        raise RuntimeError(f"Could not extract full mgi blueprint from {TEMPLATE_ROUTE_PATH}")
    return MgiBlueprint(
        tabler_link=tabler_match.group(1).strip(),
        style_block=style_match.group(1).strip(),
        sections_block=sections_match.group(1).strip(),
        faq_script=faq_script_match.group(1).strip(),
    )


def strip_existing_mgi_sections(html: str) -> str:
    return re.sub(r'\n?\s*<div class="mgi-sections">.*?<!-- end \.mgi-sections -->\s*\n?', "\n", html, flags=re.S)


def ensure_mgi_head_assets(html: str, blueprint: MgiBlueprint) -> str:
    clean = re.sub(
        rf"\s*<link rel=\"stylesheet\" href=\"{re.escape(TABLER_ICONS_CDN)}\"\s*/?>\s*",
        "\n",
        html,
        flags=re.I,
    )
    clean = re.sub(r"\s*<style>\s*.*?\.mgi-sections\s*\{.*?</style>\s*", "\n", clean, count=1, flags=re.S)
    insertion = f"  {blueprint.tabler_link}\n  {blueprint.style_block}\n"
    return re.sub(r"(</head>)", insertion + r"\1", clean, count=1, flags=re.S)


def ensure_mgi_faq_script(html: str, blueprint: MgiBlueprint) -> str:
    clean = re.sub(
        r"\s*<script>\s*\(function \(\) \{\s*document\.querySelectorAll\('\[data-mgi-faq\]'\).*?</script>\s*",
        "\n",
        html,
        count=1,
        flags=re.S,
    )
    return re.sub(r"(</body>)", "\n" + blueprint.faq_script + "\n\\1", clean, count=1, flags=re.S)


def inject_mgi_sections(html: str, block: str) -> str:
    clean = strip_existing_mgi_sections(html)
    for pattern in (
        r'(\s*<!-- RRTS_ROUTE_SUMMARY_DETAILS_START -->)',
        r'(\s*<div class="rc-route-meta"(?:\s|>))',
        r'(\s*<div class="route-seo-box"(?:\s|>))',
        r'(\s*<div class="quick-facts"(?:\s|>))',
        r'(\s*<section id="global-search-section"(?:\s|>))',
        r"(</main>)",
    ):
        if re.search(pattern, clean, flags=re.S):
            return re.sub(pattern, "\n" + block + "\n" + r"\1", clean, count=1, flags=re.S)
    return clean.rstrip() + "\n" + block + "\n"


def parse_distance_km(value: str) -> float:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value or "")
    return float(match.group(1)) if match else 0.0


def parse_gate_capacity(profile: dict[str, Any]) -> list[tuple[str, list[str]]]:
    live_capacity = profile.get("live_capacity") if isinstance(profile.get("live_capacity"), dict) else {}
    grouped: dict[str, list[str]] = {}
    for key, value in live_capacity.items():
        match = re.match(r"gate_(\d+)_(four|two)_wheelers", str(key))
        if not match or value in (None, "", [], {}):
            continue
        gate_name = f"Gate {match.group(1)}"
        lane = "4W" if match.group(2) == "four" else "2W"
        grouped.setdefault(gate_name, []).append(f"{lane} parking {value}")
    return [(gate, grouped[gate]) for gate in sorted(grouped, key=lambda item: int(item.split()[-1]))]


def facility_badge(value: Any) -> tuple[str, str]:
    if value is True:
        return ("Available", "mgi-b-green")
    if isinstance(value, str) and value.strip():
        return ("Available", "mgi-b-green")
    if isinstance(value, list) and value:
        return ("Limited", "mgi-b-amber")
    return ("Unavailable", "mgi-b-red")


def build_amenities_section(destination_meta: StationMeta | None) -> str:
    facilities = destination_meta.special_facilities if destination_meta else {}
    parking = destination_meta.parking_profile if destination_meta else {}
    cards = [
        ("Washrooms", "ti-gender-bigender", facilities.get("washrooms")),
        ("Drinking Water", "ti-droplet", facilities.get("drinking_water")),
        ("First Aid", "ti-first-aid-kit", facilities.get("first_aid")),
        ("Food Stalls", "ti-tools-kitchen-2", facilities.get("food_stalls")),
        ("Divyangjan Friendly", "ti-wheelchair", facilities.get("divyangjan_friendly")),
        ("Parking", "ti-parking-circle", parking.get("parking_available")),
    ]
    card_html = []
    for label, icon, value in cards:
        badge_text, badge_class = facility_badge(value)
        card_html.append(
            f"""      <div class="mgi-card mgi-fac-card">
        <div class="mgi-icon-wrap"><i class="ti {icon}" aria-hidden="true"></i></div>
        <span class="mgi-fac-label">{escape(label)}</span>
        <span class="mgi-badge {badge_class}">{escape(badge_text)}</span>
      </div>"""
        )
    return """  <section aria-label="Station amenities">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Station Amenities</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-fac-grid">
{cards}
    </div>
  </section>""".format(cards="\n".join(card_html))


def build_exit_gates_section(destination_label: str, destination_meta: StationMeta | None) -> str:
    gate_groups = parse_gate_capacity(destination_meta.parking_profile if destination_meta else {})
    accessible = bool(destination_meta and destination_meta.special_facilities.get("divyangjan_friendly"))
    location = clean_text(destination_meta.geographical_location if destination_meta else "") or f"{destination_label} station concourse"
    if not gate_groups:
        gate_groups = [("Gate Info", ["Official gate metrics are not published yet"])]

    cards = []
    for gate_name, tags in gate_groups:
        tag_html = [f'          <span class="mgi-badge mgi-b-blue">{escape(tag)}</span>' for tag in tags]
        if accessible:
            tag_html.append('          <span class="mgi-badge mgi-b-green">Accessible</span>')
        cards.append(
            f"""      <div class="mgi-card mgi-exit-card">
        <div class="mgi-exit-hd">
          <div class="mgi-exit-icon"><i class="ti ti-door-exit" aria-hidden="true"></i></div>
          <span class="mgi-exit-name">{escape(gate_name)}</span>
        </div>
        <span class="mgi-exit-sub">{escape(location)}</span>
        <div class="mgi-exit-tags">
{chr(10).join(tag_html)}
        </div>
      </div>"""
        )
    return """  <section aria-label="Exit gates">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Exit Gates — {destination} Station</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-exit-grid">
{cards}
    </div>
  </section>""".format(destination=escape(destination_label), cards="\n".join(cards))


def build_peak_hours_section(is_direct_route: bool, estimated_time: str) -> str:
    long_trip = parse_distance_km(estimated_time) > 50 or "6" in estimated_time
    slots = [
        ("6:00 – 7:00 AM", "Early morning", "35%", "green", "Low crowd"),
        ("7:00 – 9:30 AM", "Morning rush", "95%" if is_direct_route or long_trip else "88%", "", "Very crowded"),
        ("9:30 AM – 4:30 PM", "Off-peak midday", "30%", "green", "Comfortable"),
        ("4:30 – 7:00 PM", "Evening rush", "90%" if is_direct_route else "84%", "", "Very crowded"),
        ("7:00 – 9:00 PM", "Post-rush taper", "55%", "amber", "Moderate"),
        ("After 9:00 PM", "Late night", "18%", "green", "Sparse"),
    ]
    cards = []
    for time_range, label, width, fill_class, badge in slots:
        badge_class = "mgi-b-red"
        if badge in {"Low crowd", "Comfortable", "Sparse"}:
            badge_class = "mgi-b-green"
        elif badge == "Moderate":
            badge_class = "mgi-b-amber"
        fill_attr = f" {fill_class}" if fill_class else ""
        cards.append(
            f"""      <div class="mgi-card mgi-peak-card">
        <span class="mgi-peak-time">{escape(time_range)}</span>
        <span class="mgi-peak-lbl">{escape(label)}</span>
        <div class="mgi-peak-bar"><div class="mgi-peak-fill{fill_attr}" style="width:{escape(width)}"></div></div>
        <span class="mgi-badge {badge_class}" style="width:fit-content;margin-top:4px">{escape(badge)}</span>
      </div>"""
        )
    return """  <section aria-label="Peak traveling hours">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Peak Traveling Hours</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-peak-grid">
{cards}
    </div>
  </section>""".format(cards="\n".join(cards))


def extract_visual_route_stations(html: str) -> list[tuple[str, bool]]:
    bounds = find_div_block_bounds(html, '<div class="rc-steps">')
    if not bounds:
        return []
    block = html[bounds[0] : bounds[1]]
    items: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<div class="(step-name|xchange-name)">(.*?)</div>', block, flags=re.S):
        name = clean_text(match.group(2))
        key = normalize_slug(name)
        if not name or key in seen:
            continue
        items.append((name, match.group(1) == "xchange-name"))
        seen.add(key)
    return items


def station_color(meta: StationMeta | None, interchange: bool) -> str:
    if interchange:
        return "#BA7517"
    if meta and meta.service_type == "Metro":
        return MEERUT_METRO_GREEN
    return RRTS_RED


def build_route_map_section(
    html: str, destination_label: str, system_label: str, station_map: dict[str, StationMeta]
) -> str:
    visual_stations = extract_visual_route_stations(html)
    if not visual_stations:
        visual_stations = [(destination_label, False)]
    nodes = []
    for idx, (name, interchange) in enumerate(visual_stations):
        meta = find_station_meta(name, station_map)
        color = station_color(meta, interchange)
        current = idx == len(visual_stations) - 1
        marker = '<span class="mgi-you">DEST</span>\n' if current else ""
        dot_style = f"border-color:{color}" + (f";background:{color}" if current else "")
        label_style = f"font-size:10.5px;font-weight:600;color:{color if current else '#666'};text-align:center;max-width:72px;line-height:1.3"
        nodes.append(
            f"""          <div class="mgi-stn{' current' if current else ''}" role="listitem">
            {marker}            <div class="dot" style="{dot_style}"></div>
            <span class="sname" style="{label_style}">{escape(name)}</span>
          </div>"""
        )
        if idx < len(visual_stations) - 1:
            nodes.append(f'          <div class="mgi-conn" style="background:{color}"></div>')
    return """  <section aria-label="{system} route map">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Route Map — {system}</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-card mgi-map-outer">
      <div class="mgi-map-scroll">
        <div class="mgi-map-track" role="list">
{nodes}
        </div>
      </div>
      <div class="mgi-map-legend">
        <span><i class="mgi-dot-red"></i> Namo Bharat / direct stops</span>
        <span><i class="mgi-dot-gray" style="background:{metro_color}"></i> Metro / destination</span>
      </div>
    </div>
  </section>""".format(
        system=escape(system_label), nodes="\n".join(nodes), metro_color=MEERUT_METRO_GREEN
    )


def build_safety_section(
    interchange_station: str | None,
    helpline_number: str,
) -> str:
    transfer_title = "Follow interchange signage" if interchange_station else "Watch platform markings"
    transfer_copy = (
        f"At {interchange_station}, follow the marked transfer path and platform boards before changing services."
        if interchange_station
        else "Stand behind the yellow line and wait for coach doors to align before boarding."
    )
    cards = [
        ("#FCEBEB", "ti-alert-triangle", "#A32D2D", "Mind the gap", "Step carefully while boarding. Stand behind the yellow line until the train fully stops."),
        ("#E6F1FB", "ti-map-pin-route", "#185FA5", transfer_title, transfer_copy),
        ("#FAEEDA", "ti-briefcase", "#854F0B", "Watch your belongings", "Keep bags in front of you during rush periods and report unattended luggage immediately."),
        ("#EAF3DE", "ti-heart-handshake", "#3B6D11", "Priority seating", "Seats near doors are reserved for elderly, pregnant, and Divyangjan passengers."),
        ("#FAEEDA", "ti-phone-call", "#854F0B", "Emergency helpline", f"For any safety concern, use the Talk-Back button in the coach or call {helpline_number}."),
        ("#FCEBEB", "ti-camera-off", "#A32D2D", "No photography", "Photography inside trains, platforms, or restricted operational areas is prohibited."),
    ]
    card_html = []
    for bg, icon, color, title, body in cards:
        card_html.append(
            f"""      <div class="mgi-card mgi-safety-card">
        <div class="mgi-icon-wrap" style="background:{bg}"><i class="ti {icon}" aria-hidden="true" style="color:{color}"></i></div>
        <div class="mgi-safety-text"><h4>{escape(title)}</h4><p>{escape(body)}</p></div>
      </div>"""
        )
    return """  <section aria-label="Safety tips">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Safety Tips</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-safety-grid">
{cards}
    </div>
  </section>""".format(cards="\n".join(card_html))


def build_eco_section(distance_km: str) -> str:
    distance_value = max(parse_distance_km(distance_km), 1.0)
    co2_saved = round(distance_value * 0.151, 1)
    fuel_saved = round(distance_value * 0.069, 1)
    tree_work = int(round(co2_saved * 7.5))
    cars_removed = int(round(max(distance_value * 6.3, 45)))
    cards = [
        ("ti-leaf", "8.3" if distance_value == 55 else f"{co2_saved:g}", "kg CO₂ saved", f"vs. driving {distance_value:g} km by private car"),
        ("ti-flame-off", f"{fuel_saved:g}", "litres fuel saved", "that would otherwise burn in corridor traffic"),
        ("ti-trees", str(tree_work), "trees' daily work", "CO₂ absorbed per 1,000 riders on this route daily"),
        ("ti-road-off", f"~{cars_removed}", "cars off the road", "when one full coach replaces private vehicle trips"),
        ("ti-solar-panel", "30%", "solar powered", "NCRTC's energy mix includes renewable solar generation"),
    ]
    card_html = []
    for icon, number, unit, desc in cards:
        card_html.append(
            f"""      <div class="mgi-card mgi-eco-card">
        <div class="mgi-eco-iwrap"><i class="ti {icon}" aria-hidden="true"></i></div>
        <span class="mgi-eco-num">{escape(number)}</span>
        <span class="mgi-eco-unit">{escape(unit)}</span>
        <span class="mgi-eco-desc">{escape(desc)}</span>
      </div>"""
        )
    return """  <section aria-label="Environmental impact of this ride">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Taking this ride means</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-eco-grid">
{cards}
    </div>
  </section>""".format(cards="\n".join(card_html))


def build_faq_section(
    origin_label: str,
    destination_label: str,
    system_label: str,
    distance_km: str,
    standard_fare: str,
    estimated_time: str,
    first_train: str,
    last_train: str,
    exit_gate_summary: str,
) -> str:
    items = [
        (
            f"What is the distance from {origin_label} to {destination_label} by {system_label}?",
            f"The distance from {origin_label} to {destination_label} on {system_label} is approximately {distance_km or 'the listed corridor distance'}.",
        ),
        (
            f"What is the fare from {origin_label} to {destination_label} on {system_label}?",
            f"The standard fare from {origin_label} to {destination_label} on {system_label} is approximately {standard_fare or 'the current listed fare'}.",
        ),
        (
            f"How long does it take to travel from {origin_label} to {destination_label}?",
            f"The estimated travel time from {origin_label} to {destination_label} is about {estimated_time or 'the listed journey time'}.",
        ),
        (
            f"What is the first train from {origin_label} for this route?",
            f"The first train information for departures from {origin_label} is: {first_train}.",
        ),
        (
            f"What is the last train from {origin_label} for this route?",
            f"The last train information for departures from {origin_label} is: {last_train}.",
        ),
        (
            f"Which exit gates are useful at {destination_label} station?",
            f"Current gate guidance for {destination_label} is: {exit_gate_summary}.",
        ),
    ]
    item_html = []
    for question, answer in items:
        item_html.append(
            f"""      <div class="mgi-faq-item">
        <button class="mgi-faq-q" aria-expanded="false" data-mgi-faq>{escape(question)}<i class="ti ti-chevron-down mgi-chev" aria-hidden="true"></i></button>
        <div class="mgi-faq-a">{escape(answer)}</div>
      </div>"""
        )
    return """  <section aria-label="Frequently asked questions">
    <div class="mgi-sec-head">
      <div class="mgi-sec-line"></div>
      <h2 class="mgi-sec-title">Frequently Asked Questions</h2>
      <div class="mgi-sec-line"></div>
    </div>
    <div class="mgi-card mgi-faq-wrap">
{items}
    </div>
  </section>""".format(items="\n".join(item_html))


def build_mgi_sections_html(
    slug: str,
    html: str,
    origin_label: str,
    destination_label: str,
    system_label: str,
    distance_km: str,
    standard_fare: str,
    estimated_time: str,
    first_train: str,
    last_train: str,
    exit_gate_summary: str,
    destination_meta: StationMeta | None,
    station_map: dict[str, StationMeta],
) -> str:
    if slug == TEMPLATE_ROUTE_PATH.stem:
        return load_mgi_blueprint().sections_block
    interchange_station = next((name for name, is_interchange in extract_visual_route_stations(html) if is_interchange), None)
    helpline_number = (
        destination_meta.control_room_contact
        if destination_meta and destination_meta.control_room_contact and destination_meta.control_room_contact != "0"
        else "1800-209-0200"
    )
    sections = [
        build_amenities_section(destination_meta),
        build_exit_gates_section(destination_label, destination_meta),
        build_peak_hours_section(is_direct_rrts_route(slug), estimated_time),
        build_route_map_section(html, destination_label, system_label, station_map),
        build_safety_section(interchange_station, helpline_number),
        build_eco_section(distance_km),
        build_faq_section(
            origin_label,
            destination_label,
            system_label,
            distance_km,
            standard_fare,
            estimated_time,
            first_train,
            last_train,
            exit_gate_summary,
        ),
    ]
    return '<div class="mgi-sections">\n\n' + "\n\n".join(sections) + "\n\n</div>\n<!-- end .mgi-sections -->"


def format_inr(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return f"₹{int(value)}"
    return f"₹{value:.2f}".rstrip("0").rstrip(".")


def summarize_zone_tariff(zone_name: str, zone_data: dict[str, Any]) -> str:
    def lane_values(four_val: str, two_val: str) -> str:
        parts: list[str] = []
        if four_val:
            parts.append(f"{four_val} (4W)")
        if two_val:
            parts.append(f"{two_val} (2W)")
        return ", ".join(parts)

    zone = zone_name.lower()
    if "delhi" in zone:
        four_daily = format_inr(zone_data.get("four_wheeler_daily_inr"))
        two_daily = format_inr(zone_data.get("two_wheeler_daily_inr"))
        four_monthly = format_inr(zone_data.get("four_wheeler_monthly_pass_inr"))
        two_monthly = format_inr(zone_data.get("two_wheeler_monthly_pass_inr"))
        parts = []
        daily = lane_values(four_daily, two_daily)
        monthly = lane_values(four_monthly, two_monthly)
        if daily:
            parts.append(f"Daily {daily}")
        if monthly:
            parts.append(f"Monthly {monthly}")
        return "; ".join(p for p in parts if p).strip()

    if "uttar pradesh" in zone:
        four = zone_data.get("four_wheelers") if isinstance(zone_data.get("four_wheelers"), dict) else {}
        two = zone_data.get("two_wheelers") if isinstance(zone_data.get("two_wheelers"), dict) else {}
        up_to_6h_four = format_inr(four.get("up_to_6_hours_inr"))
        up_to_6h_two = format_inr(two.get("up_to_6_hours_inr"))
        up_to_12h_four = format_inr(four.get("up_to_12_hours_inr"))
        up_to_12h_two = format_inr(two.get("up_to_12_hours_inr"))
        monthly_four = format_inr(four.get("monthly_pass_no_time_limit_inr"))
        monthly_two = format_inr(two.get("monthly_pass_no_time_limit_inr"))
        parts = []
        upto6h = lane_values(up_to_6h_four, up_to_6h_two)
        upto12h = lane_values(up_to_12h_four, up_to_12h_two)
        monthly = lane_values(monthly_four, monthly_two)
        if upto6h:
            parts.append(f"Up to 6h {upto6h}")
        if upto12h:
            parts.append(f"Up to 12h {upto12h}")
        if monthly:
            parts.append(f"Monthly {monthly}")
        return "; ".join(p for p in parts if p).strip()

    return ""


def extract_object_for_key(raw: str, key: str) -> dict[str, Any]:
    key_pat = re.compile(rf'"{re.escape(key)}"\s*:\s*\{{', flags=re.I)
    m = key_pat.search(raw)
    if not m:
        return {}
    start = raw.find("{", m.start())
    if start == -1:
        return {}
    depth = 0
    end = None
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return {}
    chunk = raw[start : end + 1]
    chunk = re.sub(r":\s*,", ": [],", chunk)
    try:
        parsed = json.loads(chunk)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_station_objects_from_malformed_json(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    i = 0
    while True:
        idx = raw.find('"station_code"', i)
        if idx == -1:
            break
        start = raw.rfind("{", 0, idx)
        if start == -1:
            i = idx + 1
            continue

        depth = 0
        end = None
        for j in range(start, len(raw)):
            ch = raw[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            break

        chunk = raw[start : end + 1]
        chunk = chunk.replace('"exit_gates":,', '"exit_gates": [] ,')
        chunk = re.sub(r":\s*,", ": [],", chunk)
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict) and obj.get("station_name"):
                items.append(obj)
        except json.JSONDecodeError:
            pass
        i = end + 1
    return items


def load_route_payload(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, StationMeta]]:
    raw = path.read_text(encoding="utf-8")

    route_map: dict[str, dict[str, Any]] = {}
    station_map: dict[str, StationMeta] = {}
    parking_tariff_by_zone: dict[str, str] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        tariff_structure = (
            data.get("standard_parking_tariff_structure")
            if isinstance(data.get("standard_parking_tariff_structure"), dict)
            else {}
        )
        if tariff_structure:
            delhi_zone = (
                tariff_structure.get("delhi_stations_zone")
                if isinstance(tariff_structure.get("delhi_stations_zone"), dict)
                else {}
            )
            up_zone = (
                tariff_structure.get("uttar_pradesh_stations_zone")
                if isinstance(tariff_structure.get("uttar_pradesh_stations_zone"), dict)
                else {}
            )
            if delhi_zone:
                parking_tariff_by_zone["delhi"] = summarize_zone_tariff("delhi", delhi_zone)
            if up_zone:
                parking_tariff_by_zone["uttar pradesh"] = summarize_zone_tariff("uttar pradesh", up_zone)
    else:
        delhi_zone = extract_object_for_key(raw, "delhi_stations_zone")
        up_zone = extract_object_for_key(raw, "uttar_pradesh_stations_zone")
        if delhi_zone:
            parking_tariff_by_zone["delhi"] = summarize_zone_tariff("delhi", delhi_zone)
        if up_zone:
            parking_tariff_by_zone["uttar pradesh"] = summarize_zone_tariff("uttar pradesh", up_zone)

    if isinstance(data, dict):
        if isinstance(data.get("routes"), dict):
            for k, v in data["routes"].items():
                if isinstance(v, dict):
                    route_map[normalize_slug(k)] = v
        for k, v in data.items():
            if "-to-" in k and isinstance(v, dict):
                route_map[normalize_slug(k)] = v
        stations = data.get("stations")
        if isinstance(stations, list):
            for st in stations:
                if not isinstance(st, dict):
                    continue
                name = (st.get("station_name") or "").strip()
                if not name:
                    continue
                parking_profile = st.get("parking_profile") if isinstance(st.get("parking_profile"), dict) else {}
                zone_name = str(parking_profile.get("zone") or "").strip().lower()
                station_map[normalize_slug(name)] = StationMeta(
                    station_name=name,
                    service_type=normalize_service_type(st.get("system_type")),
                    geographical_location=str(st.get("geographical_location") or "").strip(),
                    operational_timings=st.get("operational_timings")
                    if isinstance(st.get("operational_timings"), dict)
                    else {},
                    exit_gates=st.get("exit_gates"),
                    parking_profile=parking_profile,
                    special_facilities=st.get("special_facilities")
                    if isinstance(st.get("special_facilities"), dict)
                    else {},
                    control_room_contact=str(st.get("control_room_contact") or "").strip(),
                    parking_tariff_summary=parking_tariff_by_zone.get(zone_name, ""),
                )

    if not station_map:
        for st in extract_station_objects_from_malformed_json(raw):
            name = (st.get("station_name") or "").strip()
            if not name:
                continue
            parking_profile = st.get("parking_profile") if isinstance(st.get("parking_profile"), dict) else {}
            zone_name = str(parking_profile.get("zone") or "").strip().lower()
            station_map[normalize_slug(name)] = StationMeta(
                station_name=name,
                service_type=normalize_service_type(st.get("system_type")),
                geographical_location=str(st.get("geographical_location") or "").strip(),
                operational_timings=st.get("operational_timings")
                if isinstance(st.get("operational_timings"), dict)
                else {},
                exit_gates=st.get("exit_gates"),
                parking_profile=parking_profile,
                special_facilities=st.get("special_facilities")
                if isinstance(st.get("special_facilities"), dict)
                else {},
                control_room_contact=str(st.get("control_room_contact") or "").strip(),
                parking_tariff_summary=parking_tariff_by_zone.get(zone_name, ""),
            )

    return route_map, station_map


def normalize_timeline(route: dict[str, Any], fallback_stations: list[str], station_map: dict[str, StationMeta]) -> list[dict[str, str]]:
    timeline = route.get("stations_timeline")
    normalized: list[dict[str, str]] = []

    if isinstance(timeline, list) and timeline:
        for node in timeline:
            if isinstance(node, str):
                name = node.strip()
                meta = find_station_meta(name, station_map)
                item = {
                    "station_name": name,
                    "service_type": (route.get("service_type") or (meta.service_type if meta else "RRTS")),
                    "interchange_info": "",
                }
                normalized.append(item)
                continue
            if isinstance(node, dict):
                name = str(node.get("station_name") or node.get("station") or node.get("name") or "").strip()
                if not name:
                    continue
                meta = find_station_meta(name, station_map)
                item = {
                    "station_name": name,
                    "service_type": str(node.get("service_type") or (meta.service_type if meta else route.get("service_type") or "RRTS")),
                    "interchange_info": str(node.get("interchange_info") or "").strip(),
                }
                normalized.append(item)

    if normalized:
        return normalized

    for st in fallback_stations:
        meta = find_station_meta(st, station_map)
        interchange = ""
        if meta and meta.service_type == "Dual-Service":
            interchange = "Cross-network transfer available"
        normalized.append(
            {
                "station_name": st,
                "service_type": meta.service_type if meta else "RRTS",
                "interchange_info": interchange,
            }
        )
    return normalized


def normalize_exit_items(route: dict[str, Any], origin_station: StationMeta | None) -> list[tuple[str, str, str]]:
    gates = route.get("exit_gates")
    if gates in (None, "", []):
        gates = origin_station.exit_gates if origin_station else None

    entries: list[tuple[str, str, str]] = []

    if isinstance(gates, dict):
        for station_name, values in gates.items():
            if isinstance(values, list):
                for idx, v in enumerate(values, 1):
                    if isinstance(v, dict):
                        gate = str(v.get("gate") or v.get("gate_no") or f"Gate {idx}")
                        landmark = str(v.get("landmark") or v.get("location") or v.get("towards") or "Not listed")
                    else:
                        gate = f"Gate {idx}"
                        landmark = str(v)
                    entries.append((str(station_name), gate, landmark))
            elif isinstance(values, dict):
                for gate, landmark in values.items():
                    entries.append((str(station_name), str(gate), str(landmark)))
            else:
                entries.append((str(station_name), "Gate", str(values)))
        return entries

    if isinstance(gates, list):
        for idx, item in enumerate(gates, 1):
            if isinstance(item, dict):
                station_name = str(item.get("station_name") or item.get("station") or (origin_station.station_name if origin_station else "Route"))
                gate = str(item.get("gate") or item.get("gate_no") or f"Gate {idx}")
                landmark = str(item.get("landmark") or item.get("location") or item.get("towards") or "Not listed")
            else:
                station_name = origin_station.station_name if origin_station else "Route"
                gate = f"Gate {idx}"
                landmark = str(item)
            entries.append((station_name, gate, landmark))

    return entries


def build_component_html(slug: str, html: str, route: dict[str, Any], station_map: dict[str, StationMeta]) -> str:
    fallback = parse_sub_line(html)
    fallback_stations = extract_step_stations(html)
    first_train, last_train, exits, origin_meta = get_station_route_details(html, route, station_map)
    parking_summary = summarize_parking(origin_meta)
    facilities_summary = summarize_facilities(origin_meta)

    timeline = normalize_timeline(route, fallback_stations, station_map)

    timeline_html = []
    for idx, node in enumerate(timeline, 1):
        label = ""
        info = node.get("interchange_info", "").strip()
        if info:
            label = f'<div class="rrts-chip rrts-chip-int">Transfer: {escape(info)}</div>'
        timeline_html.append(
            """
            <li class="rrts-stop">
              <span class="rrts-pill">{idx}</span>
              <div class="rrts-stop-body">
                <div class="rrts-stop-name">{name}</div>
                <div class="rrts-chip-row">
                  <div class="rrts-chip">Service: {service}</div>
                  {label}
                </div>
              </div>
            </li>
            """.format(
                idx=idx,
                name=escape(node.get("station_name", "")),
                service=escape(node.get("service_type", "RRTS")),
                label=label,
            )
        )

    if exits:
        exit_items = "".join(
            f"<li><strong>{escape(st)}</strong> — {escape(gate)}: {escape(landmark)}</li>"
            for st, gate, landmark in exits
        )
    else:
        exit_items = "<li>Exit gate landmarks are currently not published for this route.</li>"

    return f"""
{BLOCK_START}
<section class="rrts-route-injected" data-route="{escape(slug)}">
  <style>
    .rrts-route-injected{{margin:16px 0 24px;padding:14px;border:1px solid var(--border2,#e2e8f0);border-radius:12px;background:var(--surface2,#fff)}}
    .rrts-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
    .rrts-card{{border:1px solid var(--border2,#e2e8f0);border-radius:10px;padding:10px;background:#fff}}
    .rrts-title{{font-size:1rem;font-weight:700;margin:0 0 10px}}
    .rrts-meta-key{{font-size:.72rem;color:var(--muted,#64748b);text-transform:uppercase;letter-spacing:.04em}}
    .rrts-meta-val{{font-size:.96rem;font-weight:600}}
    .rrts-timeline{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}}
    .rrts-stop{{display:flex;gap:10px;align-items:flex-start}}
    .rrts-pill{{min-width:26px;height:26px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#C0392B;color:#fff;font-size:.78rem;font-weight:700}}
    .rrts-stop-body{{border:1px solid var(--border2,#e2e8f0);border-radius:9px;padding:8px 10px;flex:1}}
    .rrts-stop-name{{font-weight:700}}
    .rrts-chip-row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}}
    .rrts-chip{{font-size:.72rem;border:1px solid #d1d5db;border-radius:999px;padding:2px 8px;background:#f8fafc}}
    .rrts-chip-int{{border-color:#f59e0b;background:#fffbeb;color:#92400e}}
    .rrts-exits{{margin:0;padding-left:18px;display:grid;gap:6px}}
    @media (max-width:700px){{.rrts-grid{{grid-template-columns:1fr}}}}
  </style>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Live Route Timeline</h2>
    <ol class="rrts-timeline">
      {''.join(timeline_html)}
    </ol>
  </div>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Terminal Timings</h2>
    <div class="rrts-grid">
      <div><div class="rrts-meta-key">First Train (Origin)</div><div class="rrts-meta-val">{escape(first_train)}</div></div>
      <div><div class="rrts-meta-key">Last Train (Origin)</div><div class="rrts-meta-val">{escape(last_train)}</div></div>
    </div>
  </div>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Origin Station Amenities</h2>
    <div class="rrts-grid">
      <div><div class="rrts-meta-key">Parking</div><div class="rrts-meta-val">{escape(parking_summary)}</div></div>
      <div><div class="rrts-meta-key">Facilities</div><div class="rrts-meta-val">{escape(facilities_summary)}</div></div>
    </div>
  </div>

  <div class="rrts-card">
    <h2 class="rrts-title">Exit Gate Blueprint</h2>
    <ul class="rrts-exits">{exit_items}</ul>
  </div>
</section>
{BLOCK_END}
""".strip()


def inject_in_main_block(html: str, block: str) -> str:
    clean = strip_existing_block(html)

    rp_sub = re.search(r'(<p class="rp-sub"[^>]*>.*?</p>)', clean, flags=re.S)
    if rp_sub:
        insert_at = rp_sub.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    wrap_open = re.search(r'(<div class="wrap"[^>]*>)', clean)
    if wrap_open:
        insert_at = wrap_open.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    main_open = re.search(r'(<main[^>]*>)', clean)
    if main_open:
        insert_at = main_open.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    return clean + "\n" + block + "\n"


def fallback_route_data_from_html(html: str) -> dict[str, Any]:
    sub = parse_sub_line(html)
    return {
        "estimated_time": sub.get("estimated_time", "Not listed"),
        "standard_fare": sub.get("standard_fare", "Not listed"),
        "interchanges": parse_interchanges(html),
        "total_stations": len(extract_step_stations(html)),
    }


def iter_route_pages() -> list[Path]:
    return sorted(ROUTES_DIR.glob("*.html"))


def run(write: bool = True) -> int:
    route_map, station_map = load_route_payload(ROUTE_JSON)
    blueprint = load_mgi_blueprint()

    route_pages = iter_route_pages()
    updated = 0

    print(f"[inject] route pages found: {len(route_pages)}")
    print(f"[inject] route keys found in JSON: {len(route_map)}")
    print(f"[inject] station records parsed: {len(station_map)}")

    for path in route_pages:
        slug = path.stem
        original = path.read_text(encoding="utf-8")
        is_direct_route = is_direct_rrts_route(slug)
        working_html = normalize_direct_route_copy(original) if is_direct_route else original
        route_data = route_map.get(slug) or fallback_route_data_from_html(working_html)
        endpoints = extract_route_terminals(working_html, slug)
        sub_data = parse_sub_line(working_html)
        line_label = normalize_line_label(str(route_data.get("line") or sub_data.get("line") or ""), is_direct_route)
        meta = build_rrts_meta(
            origin=endpoints[0],
            destination=endpoints[1],
            estimated_time=str(route_data.get("estimated_time") or sub_data.get("estimated_time") or ""),
            line=line_label,
            distance_km=str(route_data.get("distance_km") or sub_data.get("distance_km") or ""),
            standard_fare=str(route_data.get("standard_fare") or sub_data.get("standard_fare") or ""),
        )

        first_train, last_train, exits, origin_meta = get_station_route_details(working_html, route_data, station_map)
        exit_summary = summarize_exit_blueprints(exits)
        parking_summary = summarize_parking(origin_meta)
        facilities_summary = summarize_facilities(origin_meta)
        destination_meta = find_station_meta(endpoints[1], station_map)
        if not destination_meta and "-to-" in slug:
            destination_meta = find_station_meta(slug.split("-to-", 1)[1], station_map)

        meta["canonical"] = f"{SITE_ROOT_URL}/routes/{slug}.html"
        result = inject_meta_template(working_html, meta)
        result = ensure_mgi_head_assets(result, blueprint)
        result = strip_existing_block(result)
        result = inject_mgi_sections(
            result,
            build_mgi_sections_html(
                slug=slug,
                html=working_html,
                origin_label=endpoints[0],
                destination_label=endpoints[1],
                system_label=line_label,
                distance_km=str(route_data.get("distance_km") or sub_data.get("distance_km") or ""),
                standard_fare=str(route_data.get("standard_fare") or sub_data.get("standard_fare") or ""),
                estimated_time=str(route_data.get("estimated_time") or sub_data.get("estimated_time") or ""),
                first_train=first_train,
                last_train=last_train,
                exit_gate_summary=exit_summary,
                destination_meta=destination_meta,
                station_map=station_map,
            ),
        )
        result = inject_route_summary_details(
            result, first_train, last_train, exit_summary, parking_summary, facilities_summary
        )
        result = ensure_mgi_faq_script(result, blueprint)

        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[inject] pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
