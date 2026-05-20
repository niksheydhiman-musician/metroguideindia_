#!/usr/bin/env python3
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

from inject_rrts_route_data import (
    ROUTE_JSON,
    StationMeta,
    list_facilities,
    load_route_payload,
    normalize_exit_items,
    normalize_slug,
    parse_first_last_train,
    summarize_parking,
)

REPO_ROOT = Path(__file__).resolve().parent
STATIONS_DIR = REPO_ROOT / "namo-bharat" / "stations"
BLOCK_START = "<!-- RRTS_STATION_DATA_INJECT_START -->"
BLOCK_END = "<!-- RRTS_STATION_DATA_INJECT_END -->"


def strip_existing_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def extract_station_name(html: str) -> str:
    m = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', html, flags=re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()


def build_station_block(meta: StationMeta) -> str:
    first_train, last_train = parse_first_last_train(meta.operational_timings)
    parking_summary = summarize_parking(meta)
    facilities = list_facilities(meta)
    exits = normalize_exit_items({}, meta)

    if facilities:
        facilities_html = "".join(f"<li>{escape(item)}</li>" for item in facilities[:10])
        if len(facilities) > 10:
            facilities_html += f"<li>+{len(facilities) - 10} more facilities</li>"
    else:
        facilities_html = "<li>Facilities data is currently not listed for this station.</li>"

    if exits:
        exits_html = "".join(
            f"<li><strong>{escape(gate)}</strong>: {escape(landmark)}</li>"
            for _, gate, landmark in exits[:10]
        )
        if len(exits) > 10:
            exits_html += f"<li>+{len(exits) - 10} more exits</li>"
    else:
        exits_html = "<li>Exit gate details are currently not listed for this station.</li>"

    return f"""
{BLOCK_START}
<section class="route-seo-box" style="margin-bottom:28px">
  <div class="route-seo-title">Station Facilities & Access</div>
  <p class="route-seo-lead">Live station metadata sourced from the RRTS station dataset.</p>
  <div class="route-seo-lines" style="display:grid;gap:8px">
    <div><strong>Parking:</strong> {escape(parking_summary)}</div>
    <div><strong>First Train:</strong> {escape(first_train)}</div>
    <div><strong>Last Train:</strong> {escape(last_train)}</div>
  </div>
  <div style="margin-top:12px">
    <h2 class="sec-head" style="font-size:1rem;margin:0 0 8px">Key Facilities</h2>
    <ul style="margin:0;padding-left:18px;display:grid;gap:6px">{facilities_html}</ul>
  </div>
  <div style="margin-top:12px">
    <h2 class="sec-head" style="font-size:1rem;margin:0 0 8px">Exit Gate Blueprint</h2>
    <ul style="margin:0;padding-left:18px;display:grid;gap:6px">{exits_html}</ul>
  </div>
</section>
{BLOCK_END}
""".strip()


def inject_station_block(html: str, block: str) -> str:
    clean = strip_existing_block(html)
    rp_sub = re.search(r'(<p class="rp-sub"[^>]*>.*?</p>)', clean, flags=re.S)
    if rp_sub:
        insert_at = rp_sub.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix
    return clean


def iter_station_pages() -> list[Path]:
    return sorted(p for p in STATIONS_DIR.glob("*.html") if p.stem != "index")


def run(write: bool = True) -> int:
    _, station_map = load_route_payload(ROUTE_JSON)
    pages = iter_station_pages()
    updated = 0

    print(f"[station-inject] station pages found: {len(pages)}")
    print(f"[station-inject] station records parsed: {len(station_map)}")

    for path in pages:
        original = path.read_text(encoding="utf-8")
        station_name = extract_station_name(original)
        meta = station_map.get(normalize_slug(path.stem)) or station_map.get(normalize_slug(station_name))
        if not meta:
            meta = StationMeta(
                station_name=station_name or path.stem.replace("-", " ").title(),
                service_type="RRTS",
                operational_timings={},
                exit_gates=[],
                parking_profile={},
                special_facilities={},
            )

        block = build_station_block(meta)
        result = inject_station_block(original, block)

        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[station-inject] pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
