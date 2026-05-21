#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inject_rrts_route_data import ROUTE_JSON, load_route_payload, normalize_exit_items, normalize_slug

REPO_ROOT = Path(__file__).resolve().parent
RRTS_DATA_JSON = REPO_ROOT / "data" / "rrts.json"
STATIONS_DIR = REPO_ROOT / "namo-bharat" / "stations"

BLOCK_START = "<!-- TRAINSTATION_SCHEMA_INJECT_START -->"
BLOCK_END = "<!-- TRAINSTATION_SCHEMA_INJECT_END -->"


@dataclass
class StationSchemaMeta:
    name: str
    city: str = ""
    latitude: str = ""
    longitude: str = ""
    lines: set[str] = field(default_factory=set)
    operators: set[str] = field(default_factory=set)
    landmarks: set[str] = field(default_factory=set)


def strip_existing_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def inject_schema_into_head(html: str, script_tag: str) -> str:
    clean = strip_existing_block(html)
    block = f"{BLOCK_START}\n{script_tag}\n{BLOCK_END}"
    if "</head>" in clean:
        return clean.replace("</head>", block + "\n</head>", 1)
    return clean


def extract_h1_station_name(html: str) -> str:
    m = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', html, flags=re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()


def extract_station_description(html: str) -> str:
    m = re.search(
        r'<div class="route-seo-title">\s*About\s+.*?\s+Station\s*</div>\s*<p class="route-seo-lead">(.*?)</p>',
        html,
        flags=re.S | re.I,
    )
    if not m:
        m = re.search(r'<p class="route-seo-lead">(.*?)</p>', html, flags=re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()


def extract_canonical_url(html: str, fallback_slug: str) -> str:
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html, flags=re.I)
    if m:
        return m.group(1).strip()
    return f"https://metroguideindia.com/namo-bharat/stations/{fallback_slug}.html"


def build_trainstation_jsonld(
    path: Path,
    html: str,
    meta: StationSchemaMeta | None,
) -> str:
    station_name = extract_h1_station_name(html) or (meta.name if meta else path.stem.replace("-", " ").title())
    canonical_url = extract_canonical_url(html, path.stem)
    description = extract_station_description(html)

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "TrainStation",
        "@id": f"{canonical_url}#trainstation",
        "name": station_name,
        "url": canonical_url,
    }

    if description:
        schema["description"] = description

    if meta:
        if meta.city:
            schema["containedInPlace"] = {
                "@type": "City",
                "name": meta.city,
            }

        if meta.operators:
            schema["provider"] = {
                "@type": "Organization",
                "name": " / ".join(sorted(meta.operators)),
            }

        additional: list[dict[str, str]] = []
        if meta.lines:
            additional.append(
                {
                    "@type": "PropertyValue",
                    "name": "Lines",
                    "value": ", ".join(sorted(meta.lines)),
                }
            )
        if meta.landmarks:
            additional.append(
                {
                    "@type": "PropertyValue",
                    "name": "Nearby Landmarks",
                    "value": "; ".join(sorted(meta.landmarks)),
                }
            )
        if additional:
            schema["additionalProperty"] = additional

        lat = str(meta.latitude).strip()
        lon = str(meta.longitude).strip()
        if lat and lon:
            try:
                schema["geo"] = {
                    "@type": "GeoCoordinates",
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
            except ValueError:
                pass

    return '<script type="application/ld+json">\n' + json.dumps(schema, ensure_ascii=False, indent=2) + "\n</script>"


def load_station_metadata() -> dict[str, StationSchemaMeta]:
    payload = json.loads(RRTS_DATA_JSON.read_text(encoding="utf-8"))
    stations = payload.get("stations") if isinstance(payload, dict) else []
    lines = payload.get("lines") if isinstance(payload, dict) else []
    systems = payload.get("systems") if isinstance(payload, dict) else []

    line_name_by_id: dict[str, str] = {}
    for item in lines if isinstance(lines, list) else []:
        if not isinstance(item, dict):
            continue
        line_id = str(item.get("line_id") or "").strip()
        line_name = str(item.get("line_name") or "").strip()
        if line_id and line_name:
            line_name_by_id[line_id] = line_name

    operator_by_system_id: dict[str, str] = {}
    for item in systems if isinstance(systems, list) else []:
        if not isinstance(item, dict):
            continue
        system_id = str(item.get("system_id") or "").strip()
        operator = str(item.get("operator") or item.get("system_name") or "").strip()
        if system_id and operator:
            operator_by_system_id[system_id] = operator

    station_map: dict[str, StationSchemaMeta] = {}
    for item in stations if isinstance(stations, list) else []:
        if not isinstance(item, dict):
            continue

        name = str(item.get("station_name") or "").strip()
        if not name:
            continue
        key = normalize_slug(name)

        row = station_map.get(key)
        if not row:
            row = StationSchemaMeta(name=name)
            station_map[key] = row

        row.city = row.city or str(item.get("city") or "").strip()
        row.latitude = row.latitude or str(item.get("latitude") or "").strip()
        row.longitude = row.longitude or str(item.get("longitude") or "").strip()

        line_id = str(item.get("line_id") or "").strip()
        if line_id and line_id in line_name_by_id:
            row.lines.add(line_name_by_id[line_id])

        system_id = str(item.get("system_id") or "").strip()
        if system_id and system_id in operator_by_system_id:
            row.operators.add(operator_by_system_id[system_id])

    _, route_station_map = load_route_payload(ROUTE_JSON)
    for key, route_station_meta in route_station_map.items():
        row = station_map.get(key)
        if not row:
            row = StationSchemaMeta(name=route_station_meta.station_name)
            station_map[key] = row
        exits = normalize_exit_items({}, route_station_meta)
        for _, _, landmark in exits:
            clean = re.sub(r"\s+", " ", str(landmark)).strip(" .")
            if clean:
                row.landmarks.add(clean)

    return station_map


def iter_station_pages() -> list[Path]:
    return sorted(p for p in STATIONS_DIR.glob("*.html") if p.stem != "index")


def run(write: bool = True) -> int:
    station_map = load_station_metadata()
    pages = iter_station_pages()
    updated = 0
    print(f"[trainstation-schema] station records parsed: {len(station_map)}")
    print(f"[trainstation-schema] station pages found: {len(pages)}")

    for path in pages:
        original = path.read_text(encoding="utf-8")
        name = extract_h1_station_name(original)
        key = normalize_slug(path.stem)
        meta = station_map.get(key)
        if not meta and name:
            meta = station_map.get(normalize_slug(name))

        script_tag = build_trainstation_jsonld(path, original, meta)
        result = inject_schema_into_head(original, script_tag)
        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[trainstation-schema] pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
