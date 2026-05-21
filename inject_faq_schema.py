#!/usr/bin/env python3
"""inject_faq_schema.py

Reads transit data from data/rrts-routes.json and dynamically constructs
and injects a FAQPage JSON-LD structured-data block into the <head> of:

  • namo-bharat/stations/*.html  — station pages (RRTS / Meerut Metro)
  • routes/*.html                — Namo Bharat RRTS route pages
  • bengaluru-metro/routes/*.html — Bengaluru Metro (BMRCL) route pages

Run:
    python inject_faq_schema.py
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from inject_rrts_route_data import (
    ROUTE_JSON,
    StationMeta,
    extract_step_stations,
    list_facilities,
    load_route_payload,
    normalize_slug,
    parse_first_last_train,
    parse_interchanges,
    parse_sub_line,
    summarize_parking,
)

REPO_ROOT = Path(__file__).resolve().parent
STATIONS_DIR = REPO_ROOT / "namo-bharat" / "stations"
RRTS_ROUTES_DIR = REPO_ROOT / "routes"
BLR_ROUTES_DIR = REPO_ROOT / "bengaluru-metro" / "routes"

BLOCK_START = "<!-- FAQ_SCHEMA_INJECT_START -->"
BLOCK_END = "<!-- FAQ_SCHEMA_INJECT_END -->"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def strip_existing_faq_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def build_faq_jsonld(questions: list[dict[str, str]]) -> str:
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": q["answer"],
                },
            }
            for q in questions
        ],
    }
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'


def inject_faq_into_head(html: str, script_tag: str) -> str:
    """Strip any existing block, then inject before </head>."""
    clean = strip_existing_faq_block(html)
    block = f"{BLOCK_START}\n{script_tag}\n{BLOCK_END}"
    if "</head>" in clean:
        return clean.replace("</head>", block + "\n</head>", 1)
    return clean


# ---------------------------------------------------------------------------
# Station FAQ builder  (namo-bharat/stations/*.html)
# ---------------------------------------------------------------------------

def build_station_faq(meta: StationMeta) -> list[dict[str, str]]:
    name = meta.station_name
    first_train, last_train = parse_first_last_train(meta.operational_timings)
    facilities = list_facilities(meta)
    parking_summary = summarize_parking(meta)

    faqs: list[dict[str, str]] = []

    if first_train != "Not listed":
        faqs.append({
            "question": f"What is the first train timing at {name} station?",
            "answer": (
                f"The first train at {name} RRTS/Metro station departs at: {first_train}."
            ),
        })

    if last_train != "Not listed":
        faqs.append({
            "question": f"What is the last train timing at {name} station?",
            "answer": (
                f"The last train at {name} RRTS/Metro station departs at: {last_train}."
            ),
        })

    profile = meta.parking_profile if isinstance(meta.parking_profile, dict) else {}
    if "parking_available" in profile:
        if profile["parking_available"]:
            faqs.append({
                "question": f"Is parking available at {name} RRTS station?",
                "answer": (
                    f"Yes, parking is available at {name} station. {parking_summary}."
                ),
            })
        else:
            faqs.append({
                "question": f"Is parking available at {name} RRTS station?",
                "answer": f"No dedicated parking facility is available at {name} station.",
            })

    if facilities:
        facility_text = ", ".join(facilities)
        faqs.append({
            "question": f"What facilities are available at {name} RRTS station?",
            "answer": (
                f"{name} station offers the following facilities: {facility_text}."
            ),
        })

    if "Dual" in meta.service_type:
        faqs.append({
            "question": f"Which metro systems serve {name} station?",
            "answer": (
                f"{name} is a dual-service hub served by both Namo Bharat RRTS "
                f"(long-distance rapid transit) and the Meerut Metro (local city service)."
            ),
        })

    return faqs


# ---------------------------------------------------------------------------
# RRTS route FAQ builder  (routes/*.html)
# ---------------------------------------------------------------------------

def _extract_route_endpoints(html: str) -> tuple[str, str]:
    """Return (origin, destination) from the page h1."""
    m = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', html, flags=re.S)
    if not m:
        return "", ""
    text = re.sub(r"<.*?>", "", m.group(1)).strip()
    text = re.sub(r"\s+", " ", text)
    # Try arrow separator first, then fall back to " to "
    parts = re.split(r"\s*[→➔>]\s*", text, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    parts = re.split(r"\s+to\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return text, ""


def build_rrts_route_faq(
    html: str, origin_meta: StationMeta | None
) -> list[dict[str, str]]:
    origin, destination = _extract_route_endpoints(html)
    if not origin or not destination:
        return []

    sub = parse_sub_line(html)
    fare = sub.get("standard_fare", "")
    est_time = sub.get("estimated_time", "")

    distance = ""
    m = re.search(r'<p class="rp-sub"[^>]*>(.*?)</p>', html, flags=re.S)
    if m:
        sub_text = re.sub(r"<.*?>", "", m.group(1))
        d_match = re.search(r"([\d.]+)\s*km", sub_text, flags=re.I)
        if d_match:
            distance = d_match.group(1) + " km"

    interchanges = parse_interchanges(html)

    faqs: list[dict[str, str]] = []

    if distance:
        faqs.append({
            "question": (
                f"What is the distance from {origin} to {destination} by Namo Bharat RRTS?"
            ),
            "answer": (
                f"The distance from {origin} to {destination} on Namo Bharat RRTS "
                f"is approximately {distance}."
            ),
        })

    if fare:
        faqs.append({
            "question": (
                f"What is the fare from {origin} to {destination} on Namo Bharat RRTS?"
            ),
            "answer": (
                f"The standard fare from {origin} to {destination} on Namo Bharat RRTS "
                f"is approximately {fare}. Premium coach fares are about 20% higher."
            ),
        })

    if est_time:
        faqs.append({
            "question": (
                f"How long does it take to travel from {origin} to {destination} "
                f"on Namo Bharat RRTS?"
            ),
            "answer": (
                f"The estimated travel time from {origin} to {destination} on Namo Bharat "
                f"RRTS is approximately {est_time}."
            ),
        })

    if origin_meta:
        first_train, last_train = parse_first_last_train(origin_meta.operational_timings)
        if first_train != "Not listed":
            faqs.append({
                "question": (
                    f"What is the first train from {origin} station for the "
                    f"{origin} to {destination} route?"
                ),
                "answer": f"The first train from {origin} departs at: {first_train}.",
            })
        if last_train != "Not listed":
            faqs.append({
                "question": (
                    f"What is the last train from {origin} for the "
                    f"{origin} to {destination} route?"
                ),
                "answer": f"The last train from {origin} departs at: {last_train}.",
            })

    if interchanges and interchanges.lower() not in ("not listed", "0 (direct route)", "none (direct)"):
        faqs.append({
            "question": (
                f"Are there any interchanges on the {origin} to {destination} route?"
            ),
            "answer": (
                f"Interchanges on the {origin} to {destination} Namo Bharat route: "
                f"{interchanges}."
            ),
        })
    else:
        faqs.append({
            "question": (
                f"Is the {origin} to {destination} a direct route on Namo Bharat RRTS?"
            ),
            "answer": (
                f"Yes, the {origin} to {destination} route is a direct route on "
                f"Namo Bharat RRTS with no interchange required."
            ),
        })

    return faqs


# ---------------------------------------------------------------------------
# Bengaluru route FAQ builder  (bengaluru-metro/routes/*.html)
# ---------------------------------------------------------------------------

def _parse_table_value(html: str, label_pattern: str) -> str:
    """Extract the second <td> value for a table row whose first <td> matches label_pattern."""
    m = re.search(
        rf'<td[^>]*>{label_pattern}.*?</td>\s*<td[^>]*>(.*?)</td>',
        html,
        flags=re.S | re.I,
    )
    if not m:
        return ""
    return re.sub(r"<.*?>", "", m.group(1)).strip()


def build_bengaluru_route_faq(html: str) -> list[dict[str, str]]:
    origin, destination = _extract_route_endpoints(html)
    if not origin or not destination:
        return []

    time_val = _parse_table_value(html, r"Approx[\.\s]*Time")
    interchange_val = _parse_table_value(html, r"Interchanges?")
    fare_val = _parse_table_value(html, r"BMRCL\s+Fare")

    # Fallback: parse from rp-sub paragraph (e.g. "Namma Metro · 11 stations · ~14 min · ₹30")
    if not time_val or not fare_val:
        sub = parse_sub_line(html)
        if not time_val:
            time_val = sub.get("estimated_time", "")
        if not fare_val:
            fare_val = sub.get("standard_fare", "")

    faqs: list[dict[str, str]] = []

    if time_val:
        faqs.append({
            "question": (
                f"How long does it take to travel from {origin} to {destination} "
                f"on Bengaluru Metro?"
            ),
            "answer": (
                f"The estimated travel time from {origin} to {destination} on "
                f"Bengaluru Metro (Namma Metro) is approximately {time_val}."
            ),
        })

    if interchange_val:
        if re.search(r"\b0\b|no interchange|direct", interchange_val, re.I):
            faqs.append({
                "question": (
                    f"Is the {origin} to {destination} route a direct route on "
                    f"Bengaluru Metro?"
                ),
                "answer": (
                    f"Yes, the {origin} to {destination} route on Bengaluru Metro "
                    f"is a direct route with no interchange required."
                ),
            })
        else:
            faqs.append({
                "question": (
                    f"How many interchanges are there from {origin} to {destination} "
                    f"on Bengaluru Metro?"
                ),
                "answer": (
                    f"The {origin} to {destination} journey on Bengaluru Metro "
                    f"requires {interchange_val}."
                ),
            })

    if fare_val:
        faqs.append({
            "question": (
                f"What is the fare from {origin} to {destination} on Bengaluru Metro?"
            ),
            "answer": (
                f"The fare from {origin} to {destination} on Bengaluru Metro (BMRCL) "
                f"is approximately {fare_val} (standard/smart card)."
            ),
        })

    faqs.append({
        "question": (
            f"How do I buy a ticket for {origin} to {destination} on Bengaluru Metro?"
        ),
        "answer": (
            f"You can purchase tickets at any Bengaluru Metro (BMRCL) station counter, "
            f"via token vending machines, or using a BMRCL smart card. "
            f"The official website is bmrc.co.in for fare tables and trip planning."
        ),
    })

    return faqs


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def _iter_html_pages(directory: Path, skip_stems: set[str] | None = None) -> list[Path]:
    skips = skip_stems or set()
    return sorted(p for p in directory.glob("*.html") if p.stem not in skips)


def run(write: bool = True) -> int:
    _, station_map = load_route_payload(ROUTE_JSON)

    station_pages = _iter_html_pages(STATIONS_DIR, skip_stems={"index"})
    rrts_route_pages = _iter_html_pages(RRTS_ROUTES_DIR)
    blr_route_pages = _iter_html_pages(BLR_ROUTES_DIR) if BLR_ROUTES_DIR.is_dir() else []

    print(
        f"[faq-inject] station pages: {len(station_pages)}, "
        f"RRTS route pages: {len(rrts_route_pages)}, "
        f"Bengaluru route pages: {len(blr_route_pages)}"
    )

    updated = 0

    # --- Station pages ---
    for path in station_pages:
        original = path.read_text(encoding="utf-8")
        meta = station_map.get(normalize_slug(path.stem))
        if not meta:
            m = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', original, flags=re.S)
            if m:
                name = re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()
                meta = station_map.get(normalize_slug(name))
        if not meta:
            print(f"  [skip] {path.name} — no station data found")
            continue

        faqs = build_station_faq(meta)
        if not faqs:
            print(f"  [skip] {path.name} — no FAQs generated")
            continue

        result = inject_faq_into_head(original, build_faq_jsonld(faqs))
        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1
            print(f"  [ok] {path.name} ({len(faqs)} FAQs)")

    # --- RRTS route pages ---
    for path in rrts_route_pages:
        original = path.read_text(encoding="utf-8")
        stations = extract_step_stations(original)
        origin_name = stations[0] if stations else ""
        origin_meta = station_map.get(normalize_slug(origin_name)) if origin_name else None

        faqs = build_rrts_route_faq(original, origin_meta)
        if not faqs:
            print(f"  [skip] {path.name} — no FAQs generated")
            continue

        result = inject_faq_into_head(original, build_faq_jsonld(faqs))
        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1
            print(f"  [ok] {path.name} ({len(faqs)} FAQs)")

    # --- Bengaluru route pages ---
    for path in blr_route_pages:
        original = path.read_text(encoding="utf-8")

        faqs = build_bengaluru_route_faq(original)
        if not faqs:
            print(f"  [skip] {path.name} — no FAQs generated")
            continue

        result = inject_faq_into_head(original, build_faq_jsonld(faqs))
        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1
            print(f"  [ok] {path.name} ({len(faqs)} FAQs)")

    print(f"[faq-inject] total pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
