#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
STATIONS_DIR = REPO_ROOT / "namo-bharat" / "stations"
DATA_DIR = REPO_ROOT / "namo-bharat-stations-data"
TEMPLATE_PATH = STATIONS_DIR / "anand-vihar.html"

ASSET_START = "<!-- MGI_STATION_ASSETS_START -->"
ASSET_END = "<!-- MGI_STATION_ASSETS_END -->"
SECTION_START = "<!-- MGI_STATION_TEMPLATE_START -->"
SECTION_END = "<!-- MGI_STATION_TEMPLATE_END -->"
LEGACY_BLOCK_START = "<!-- RRTS_STATION_DATA_INJECT_START -->"
LEGACY_BLOCK_END = "<!-- RRTS_STATION_DATA_INJECT_END -->"
TRAINSTATION_SCHEMA_START = "<!-- TRAINSTATION_SCHEMA_INJECT_START -->"
TRAINSTATION_SCHEMA_END = "<!-- TRAINSTATION_SCHEMA_INJECT_END -->"

ALIASES = {
    "bhaisali-bus-adda": "bhaisali",
}

FACILITY_ORDER = [
    "washrooms",
    "drinking_water",
    "first_aid",
    "divyangjan_friendly",
    "premium_lounge",
    "lost_and_found",
]

FACILITY_META = {
    "washrooms": ("Washrooms", "gender-bigender"),
    "drinking_water": ("Drinking Water", "droplet"),
    "first_aid": ("First Aid", "first-aid-kit"),
    "divyangjan_friendly": ("Divyangjan Friendly", "wheelchair"),
    "premium_lounge": ("Premium Lounge", "armchair"),
    "lost_and_found": ("Lost & Found", "building-community"),
}

PARKING_TITLES = {
    "four_wheeler": "Four Wheeler Cars/SUV",
    "two_wheeler": "Two Wheelers",
    "helmet": "Helmet Charges",
    "bicycle": "Bicycle Charges",
}

DEFAULT_PEAK_HOURS = [
    {"time": "6:00 – 7:00 AM", "label": "Early morning", "level": "Low crowd", "percentage": 35},
    {"time": "7:00 – 9:30 AM", "label": "Morning rush", "level": "Very crowded", "percentage": 95},
    {"time": "9:30 AM – 4:30 PM", "label": "Off-peak midday", "level": "Comfortable", "percentage": 30},
    {"time": "4:30 – 7:00 PM", "label": "Evening rush", "level": "Very crowded", "percentage": 90},
    {"time": "7:00 – 9:00 PM", "label": "Post-rush taper", "level": "Moderate", "percentage": 55},
    {"time": "After 9:00 PM", "label": "Late night", "level": "Sparse", "percentage": 18},
]

DEFAULT_SAFETY_TIPS = [
    {
        "title": "Mind the gap",
        "description": "Step carefully while boarding. Stand behind the yellow line until the train fully stops.",
    },
    {
        "title": "Watch your belongings",
        "description": "Keep bags in front of you during peak hours. Report unattended luggage immediately.",
    },
    {
        "title": "No eating or drinking",
        "description": "Consuming food or beverages inside the train is prohibited and carries a fine.",
    },
    {
        "title": "Priority seating",
        "description": "Seats near doors are reserved for elderly, pregnant, and Divyangjan passengers.",
    },
    {
        "title": "Emergency helpline",
        "description": "Use the Talk-Back button in the coach or call NCRTC helpline 1800-209-0200.",
    },
    {
        "title": "No photography",
        "description": "Photography inside trains, platforms, or restricted areas is strictly prohibited.",
    },
]

DEFAULT_ECO_IMPACT = [
    {"icon": "leaf", "number": "8.3", "unit": "kg CO₂ saved", "description": "vs. driving Delhi–Meerut by private car"},
    {
        "icon": "flame-off",
        "number": "3.8",
        "unit": "litres fuel saved",
        "description": "that would have burned in Delhi–Meerut traffic",
    },
    {
        "icon": "road-off",
        "number": "~350",
        "unit": "cars off the road",
        "description": "every Namo Bharat coach removes ~350 cars per trip",
    },
    {
        "icon": "solar-panel",
        "number": "30%",
        "unit": "solar powered",
        "description": "NCRTC's energy mix includes renewable solar generation",
    },
]

SAFETY_STYLES = {
    "mind the gap": ("alert-triangle", "#FCEBEB", "#A32D2D"),
    "watch your belongings": ("briefcase", "#E6F1FB", "#185FA5"),
    "no eating or drinking": ("ban", "#FAEEDA", "#854F0B"),
    "priority seating": ("heart-handshake", "#EAF3DE", "#3B6D11"),
    "emergency helpline": ("phone-call", "#FAEEDA", "#854F0B"),
    "no photography": ("camera-off", "#FCEBEB", "#A32D2D"),
}


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def strip_block(html: str, start: str, end: str) -> str:
    return re.sub(
        rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def extract_display_name(html: str) -> str:
    match = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', html, flags=re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", match.group(1))).strip()


def load_template_assets() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    link_match = re.search(
        r'(<link[^>]+href="https://cdn\.jsdelivr\.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons\.min\.css"[^>]*>)',
        template,
    )
    style_match = re.search(r"(<style>.*?</style>)", template, flags=re.S)
    if not link_match or not style_match:
        raise RuntimeError("Could not extract station template assets from anand-vihar.html")
    return f"{link_match.group(1)}\n{style_match.group(1)}"


def load_station_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "all_stations_structured.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records[normalize_key(path.stem)] = payload
        name = payload.get("name")
        if isinstance(name, str) and name.strip():
            records.setdefault(normalize_key(name), payload)
    return records


def find_record(page_slug: str, display_name: str, records: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    keys = [
        normalize_key(ALIASES.get(page_slug, page_slug)),
        normalize_key(page_slug.replace("-", "_")),
        normalize_key(display_name),
        normalize_key(ALIASES.get(display_name.lower(), display_name)),
    ]
    for key in keys:
        if key and key in records:
            return records[key]
    return None


def facility_badge_class(status: str) -> str:
    lowered = status.lower()
    if "not available" in lowered:
        return "mgi-b-red"
    if "control room" in lowered:
        return "mgi-b-gray"
    if "platform" in lowered:
        return "mgi-b-blue"
    if "available" in lowered:
        return "mgi-b-green"
    return "mgi-b-blue"


def status_badge_class(status: str) -> str:
    lowered = status.lower()
    if "closed" in lowered or "not available" in lowered:
        return "mgi-b-red"
    if "open" in lowered or "available" in lowered:
        return "mgi-b-green"
    return "mgi-b-gray"


def peak_badge_class(level: str) -> str:
    lowered = level.lower()
    if "moderate" in lowered:
        return "mgi-b-amber"
    if "very crowded" in lowered:
        return "mgi-b-red"
    return "mgi-b-green"


def peak_fill_class(percentage: int) -> str:
    if percentage < 40:
        return " green"
    if percentage < 70:
        return " amber"
    return ""


def format_charge_label(entry: dict[str, Any]) -> str:
    duration = str(entry.get("duration", "") or "").strip()
    description = str(entry.get("description", "") or "").strip()
    if description:
        if description.lower() == "pick-up & drop off":
            return f"{duration} only for {description}".strip()
        return f"{duration} — {description}".strip(" —")
    return duration


def render_rows(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '<tr><td>Currently unavailable</td><td>—</td></tr>'
    rows = []
    for entry in entries:
        label = escape(format_charge_label(entry))
        price = escape(str(entry.get("price", "—") or "—"))
        rows.append(f"          <tr><td>{label}</td><td>{price}</td></tr>")
    return "\n".join(rows)


def render_amenities(facilities: dict[str, Any]) -> str:
    cards = []
    for key in FACILITY_ORDER:
        label, icon = FACILITY_META[key]
        status = str(facilities.get(key, "Not Available") or "Not Available")
        cards.append(
            "\n".join(
                [
                    '      <div class="mgi-card mgi-fac-card">',
                    f'        <div class="mgi-icon-wrap"><i class="ti ti-{icon}" aria-hidden="true"></i></div>',
                    f"        <span class=\"mgi-fac-label\">{escape(label)}</span>",
                    f"        <span class=\"mgi-badge {facility_badge_class(status)}\">{escape(status)}</span>",
                    "      </div>",
                ]
            )
        )
    return "\n".join(cards)


def render_parking(parking: dict[str, Any]) -> str:
    cards: list[str] = []
    for key in ("four_wheeler", "two_wheeler", "helmet", "bicycle"):
        details = parking.get(key)
        if not isinstance(details, dict) or not details:
            continue
        title = PARKING_TITLES[key]
        if key == "helmet":
            cards.append(
                "\n".join(
                    [
                        '      <div class="mgi-card mgi-park-card">',
                        f"        <h3>{escape(title)}</h3>",
                        f'        <table class="mgi-park-table" aria-label="{escape(title)}">',
                        render_rows(details.get("charges") or []),
                        "        </table>",
                        "      </div>",
                    ]
                )
            )
            continue

        chunks = [
            '      <div class="mgi-card mgi-park-card">',
            f"        <h3>{escape(title)}</h3>",
        ]
        for heading, attr, aria in (
            ("Day Charges", "day_charges", f"{title} day charges"),
            ("Night Charges", "night_charges", f"{title} night charges"),
            ("Monthly Charges", "monthly_charges", f"{title} monthly charges"),
        ):
            entries = details.get(attr) or []
            if not entries:
                continue
            chunks.extend(
                [
                    f'        <div class="mgi-park-sub">{heading}</div>',
                    f'        <table class="mgi-park-table" aria-label="{escape(aria)}">',
                    render_rows(entries),
                    "        </table>",
                ]
            )
        chunks.append("      </div>")
        cards.append("\n".join(chunks))

    if cards:
        return "\n".join(cards)
    return "\n".join(
        [
            '      <div class="mgi-card mgi-park-card">',
            "        <h3>Parking Updates</h3>",
            "        <p style=\"margin:0;color:#666;font-size:12px;line-height:1.6\">Parking tariff details are currently unavailable for this station.</p>",
            "      </div>",
        ]
    )


def render_gates(gates: list[dict[str, Any]], display_name: str) -> str:
    if not gates:
        return "\n".join(
            [
                '      <div class="mgi-card mgi-exit-card">',
                '        <div class="mgi-exit-hd"><div class="mgi-exit-icon"><i class="ti ti-door-exit" aria-hidden="true"></i></div><span class="mgi-exit-name">Gate details coming soon</span></div>',
                f"        <span class=\"mgi-exit-sub\">Exit information for {escape(display_name)} Station is currently being updated.</span>",
                "      </div>",
            ]
        )

    cards = []
    for gate in gates:
        name = str(gate.get("name") or f"Gate {gate.get('number', '')}").strip()
        location = str(gate.get("location") or "Location details not listed").strip()
        status = str(gate.get("status") or "Status not listed").strip()
        features = [str(item).strip() for item in gate.get("features") or [] if str(item).strip()]
        tags = [f'          <span class="mgi-badge {status_badge_class(status)}">{escape(status)}</span>']
        tags.extend(f'          <span class="mgi-badge mgi-b-blue">{escape(feature)}</span>' for feature in features)
        cards.append(
            "\n".join(
                [
                    '      <div class="mgi-card mgi-exit-card">',
                    '        <div class="mgi-exit-hd">',
                    '          <div class="mgi-exit-icon"><i class="ti ti-door-exit" aria-hidden="true"></i></div>',
                    f"          <span class=\"mgi-exit-name\">{escape(name)}</span>",
                    "        </div>",
                    f"        <span class=\"mgi-exit-sub\">{escape(location)}</span>",
                    '        <div class="mgi-exit-tags">',
                    *tags,
                    "        </div>",
                    "      </div>",
                ]
            )
        )
    return "\n".join(cards)


def render_peak_hours(peak_hours: list[dict[str, Any]]) -> str:
    cards = []
    for item in peak_hours or DEFAULT_PEAK_HOURS:
        time = str(item.get("time", "") or "")
        label = str(item.get("label", "") or "")
        level = str(item.get("level", "") or "")
        percentage = int(item.get("percentage", 0) or 0)
        cards.append(
            "\n".join(
                [
                    '      <div class="mgi-card mgi-peak-card">',
                    f"        <span class=\"mgi-peak-time\">{escape(time)}</span>",
                    f"        <span class=\"mgi-peak-lbl\">{escape(label)}</span>",
                    f'        <div class="mgi-peak-bar"><div class="mgi-peak-fill{peak_fill_class(percentage)}" style="width:{percentage}%"></div></div>',
                    f'        <span class="mgi-badge {peak_badge_class(level)}" style="width:fit-content;margin-top:4px">{escape(level)}</span>',
                    "      </div>",
                ]
            )
        )
    return "\n".join(cards)


def render_safety_tips(tips: list[dict[str, Any]], control_room: str | None) -> str:
    cards = []
    for tip in tips or DEFAULT_SAFETY_TIPS:
        title = str(tip.get("title", "") or "").strip()
        description = str(tip.get("description", "") or "").strip()
        if title.lower() == "emergency helpline" and control_room and control_room not in description:
            description = f"{description} Station Control Room: {control_room}."
        icon, bg, color = SAFETY_STYLES.get(title.lower(), ("shield", "#F1EFE8", "#5F5E5A"))
        cards.append(
            "\n".join(
                [
                    '      <div class="mgi-card mgi-safety-card">',
                    f'        <div class="mgi-icon-wrap" style="background:{bg}"><i class="ti ti-{icon}" aria-hidden="true" style="color:{color}"></i></div>',
                    '        <div class="mgi-safety-text">',
                    f"          <h4>{escape(title)}</h4>",
                    f"          <p>{escape(description)}</p>",
                    "        </div>",
                    "      </div>",
                ]
            )
        )
    return "\n".join(cards)


def render_eco_impact(items: list[dict[str, Any]]) -> str:
    cards = []
    for item in items or DEFAULT_ECO_IMPACT:
        cards.append(
            "\n".join(
                [
                    '      <div class="mgi-card mgi-eco-card">',
                    f'        <div class="mgi-eco-iwrap"><i class="ti ti-{escape(str(item.get("icon", "leaf")))}" aria-hidden="true"></i></div>',
                    f"        <span class=\"mgi-eco-num\">{escape(str(item.get('number', '')))}</span>",
                    f"        <span class=\"mgi-eco-unit\">{escape(str(item.get('unit', '')))}</span>",
                    f"        <span class=\"mgi-eco-desc\">{escape(str(item.get('description', '')))}</span>",
                    "      </div>",
                ]
            )
        )
    return "\n".join(cards)


def build_sections(display_name: str, record: dict[str, Any]) -> str:
    facilities = record.get("facilities") or {}
    parking = record.get("parking") or {}
    gates = record.get("gates") or []
    peak_hours = record.get("peak_hours") or DEFAULT_PEAK_HOURS
    safety_tips = record.get("safety_tips") or DEFAULT_SAFETY_TIPS
    eco_impact = record.get("eco_impact") or DEFAULT_ECO_IMPACT
    control_room = str((record.get("contact") or {}).get("control_room") or "").strip() or None

    return "\n".join(
        [
            SECTION_START,
            '<div class="mgi-sections">',
            " ",
            "  <!-- 1. STATION AMENITIES -->",
            '  <section aria-label="Station amenities">',
            '    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Station Amenities</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-fac-grid">',
            render_amenities(facilities),
            "    </div>",
            "  </section>",
            " ",
            "  <!-- 2. PARKING -->",
            '  <section aria-label="Parking charges">',
            '    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Parking Charges</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-park-grid">',
            render_parking(parking),
            "    </div>",
            "  </section>",
            " ",
            "  <!-- 3. EXIT GATES -->",
            '  <section aria-label="Exit gates">',
            f'    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Exit Gates — {escape(display_name)} Station</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-exit-grid">',
            render_gates(gates, display_name),
            "    </div>",
            "  </section>",
            " ",
            "  <!-- 4. PEAK HOURS -->",
            '  <section aria-label="Peak traveling hours">',
            '    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Peak Traveling Hours</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-peak-grid">',
            render_peak_hours(peak_hours),
            "    </div>",
            "  </section>",
            " ",
            "  <!-- 5. SAFETY TIPS -->",
            '  <section aria-label="Safety tips">',
            '    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Safety Tips</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-safety-grid">',
            render_safety_tips(safety_tips, control_room),
            "    </div>",
            "  </section>",
            " ",
            "  <!-- 6. ECO IMPACT -->",
            '  <section aria-label="Environmental impact">',
            '    <div class="mgi-sec-head"><div class="mgi-sec-line"></div><h2 class="mgi-sec-title">Taking Namo Bharat means</h2><div class="mgi-sec-line"></div></div>',
            '    <div class="mgi-eco-grid">',
            render_eco_impact(eco_impact),
            "    </div>",
            "  </section>",
            " ",
            "</div>",
            SECTION_END,
        ]
    )


def update_metadata(html: str, path: Path, display_name: str, record: dict[str, Any]) -> str:
    title = f"{display_name} Namo Bharat Station Routes: How to Travel from {display_name} to Anywhere in Delhi-NCR | MetroGuideIndia"
    description = (
        f"Planning your journey from {display_name} Namo Bharat? Find the best routes from {display_name} "
        "to popular destinations in Delhi-NCR with direct route guides, interchanges, and travel tips."
    )
    canonical = f"https://metroguideindia.com/namo-bharat/stations/{path.stem}.html"
    system = str(record.get("system") or "Namo Bharat RRTS").strip()

    html = re.sub(r"<title>.*?</title>", f"<title>{escape(title)}</title>", html, count=1, flags=re.S)
    html = re.sub(
        r'<meta name="description" content=".*?"/>',
        f'<meta name="description" content="{escape(description, quote=True)}"/>',
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r'<link rel="canonical" href=".*?"/>',
        f'<link rel="canonical" href="{escape(canonical, quote=True)}"/>',
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r'(<p class="rp-sub"[^>]*>).*?(</p>)',
        r"\1Namo Bharat RRTS · Station Guide\2",
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r"<div><strong>System:</strong>.*?</div>",
        f"<div><strong>System:</strong> {escape(system)}.</div>",
        html,
        count=1,
        flags=re.S,
    )
    return html


def update_schema(html: str, canonical: str, display_name: str, record: dict[str, Any]) -> str:
    pattern = re.compile(
        rf"({re.escape(TRAINSTATION_SCHEMA_START)}\s*<script type=\"application/ld\+json\">\s*)(.*?)(\s*</script>\s*{re.escape(TRAINSTATION_SCHEMA_END)})",
        flags=re.S,
    )
    match = pattern.search(html)
    if not match:
        return html

    try:
        schema = json.loads(match.group(2))
    except json.JSONDecodeError:
        return html

    schema["name"] = display_name
    schema["url"] = canonical
    schema["@id"] = f"{canonical}#trainstation"
    schema["description"] = (
        f"{display_name} is part of the Namo Bharat RRTS corridor. Use this page to discover direct route pages and quickly plan your trip."
    )

    lat = ((record.get("coordinates") or {}).get("latitude"))
    lng = ((record.get("coordinates") or {}).get("longitude"))
    if lat is not None and lng is not None:
        schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": lat,
            "longitude": lng,
        }

    properties = [item for item in schema.get("additionalProperty", []) if isinstance(item, dict)]
    properties = [
        item
        for item in properties
        if item.get("name") not in {"Station Code", "System", "Station Type"}
    ]

    if record.get("code"):
        properties.append({"@type": "PropertyValue", "name": "Station Code", "value": record["code"]})
    if record.get("system"):
        properties.append({"@type": "PropertyValue", "name": "System", "value": record["system"]})
    if record.get("type"):
        properties.append({"@type": "PropertyValue", "name": "Station Type", "value": str(record["type"]).title()})
    if properties:
        schema["additionalProperty"] = properties

    replacement = f'{match.group(1)}{json.dumps(schema, ensure_ascii=False, indent=2)}{match.group(3)}'
    return html[: match.start()] + replacement + html[match.end() :]


def inject_assets(html: str, assets: str) -> str:
    clean = strip_block(html, ASSET_START, ASSET_END)
    block = f"{ASSET_START}\n{assets}\n{ASSET_END}"
    canonical_link = re.search(r'<link rel="canonical" href=".*?"/>', clean)
    if canonical_link:
        return clean[: canonical_link.start()] + block + "\n" + clean[canonical_link.start() :]
    return clean


def inject_sections(html: str, block: str) -> str:
    clean = strip_block(html, SECTION_START, SECTION_END)
    clean = strip_block(clean, LEGACY_BLOCK_START, LEGACY_BLOCK_END)
    anchor = re.search(r"(\n</div>\s*)(<section id=\"global-search-section\")", clean, flags=re.S)
    if anchor:
        return clean[: anchor.start(2)] + block + "\n\n" + clean[anchor.start(2) :]
    main_close = re.search(r"</main>", clean, flags=re.S)
    if main_close:
        return clean[: main_close.start()] + "\n" + block + "\n" + clean[main_close.start() :]
    return clean


def iter_station_pages() -> list[Path]:
    return sorted(p for p in STATIONS_DIR.glob("*.html") if p.stem != "index")


def run(write: bool = True) -> int:
    assets = load_template_assets()
    records = load_station_records()
    pages = iter_station_pages()
    updated = 0
    skipped = 0

    print(f"[station-inject] station pages found: {len(pages)}")
    print(f"[station-inject] station records parsed: {len(records)}")

    for path in pages:
        original = path.read_text(encoding="utf-8")
        display_name = extract_display_name(original) or path.stem.replace("-", " ").title()
        record = find_record(path.stem, display_name, records)
        if not record:
            skipped += 1
            print(f"[station-inject] skipped {path.name} (no matching JSON record)")
            continue

        canonical = f"https://metroguideindia.com/namo-bharat/stations/{path.stem}.html"
        sections = build_sections(display_name, record)

        result = original
        result = update_metadata(result, path, display_name, record)
        result = update_schema(result, canonical, display_name, record)
        result = inject_assets(result, assets)
        result = inject_sections(result, sections)

        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[station-inject] pages updated: {updated}")
    print(f"[station-inject] pages skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
