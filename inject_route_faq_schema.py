#!/usr/bin/env python3
"""inject_route_faq_schema.py

Scans every HTML file in /routes/ and replaces any existing FAQPage JSON-LD
structured-data block with a canonical set of three general Namo Bharat RRTS
FAQ questions covering bicycle policy, luggage limits, and payment methods.

Existing blocks are located via the <!-- FAQ_SCHEMA_INJECT_START/END -->
comment markers written by inject_faq_schema.py.  If no markers are found
the script falls back to a regex scan for any <script type="application/ld+json">
block whose body contains "@type": "FAQPage".

The injected JSON is validated with json.loads() before each file is written.

Run:
    python inject_route_faq_schema.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "routes"

BLOCK_START = "<!-- FAQ_SCHEMA_INJECT_START -->"
BLOCK_END = "<!-- FAQ_SCHEMA_INJECT_END -->"

# ---------------------------------------------------------------------------
# Fixed FAQ payload — three canonical Namo Bharat RRTS general questions
# ---------------------------------------------------------------------------

FIXED_FAQ_SCHEMA: dict = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {
            "@type": "Question",
            "name": "Can I carry a bicycle on the Namo Bharat RRTS?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "Bicycles are allowed in the designated coach during non-peak hours. "
                    "Folding cycles in a bag are permitted at all times. "
                    "Check the Namo Bharat app for coach-specific rules before boarding."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "Is there a luggage size limit on Namo Bharat?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "Luggage up to 60 cm \u00d7 45 cm \u00d7 25 cm and 15 kg is permitted. "
                    "Oversized goods are not allowed. "
                    "All bags are scanned at the entry gate."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "What payment methods are accepted?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "You can pay using the Namo Bharat app, NCMC (National Common Mobility Card), "
                    "UPI, or purchase a single-journey token at the station counter. "
                    "Cash is accepted at the counter."
                ),
            },
        },
    ],
}

# Pre-render and validate once at import time
_SCHEMA_JSON_STR: str = json.dumps(FIXED_FAQ_SCHEMA, ensure_ascii=False, indent=2)
json.loads(_SCHEMA_JSON_STR)  # raises if invalid — acts as a module-level guard

_SCRIPT_TAG: str = f'<script type="application/ld+json">\n{_SCHEMA_JSON_STR}\n</script>'
_INJECT_BLOCK: str = f"{BLOCK_START}\n{_SCRIPT_TAG}\n{BLOCK_END}"


# ---------------------------------------------------------------------------
# HTML manipulation helpers
# ---------------------------------------------------------------------------

def _strip_marker_block(html: str) -> str:
    """Remove an existing <!-- FAQ_SCHEMA_INJECT_START/END --> wrapper."""
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def _strip_faqpage_script(html: str) -> str:
    """Remove any bare <script type="application/ld+json"> block containing FAQPage."""
    return re.sub(
        r'<script\s+type=["\']application/ld\+json["\'][^>]*>(?:(?!</script>).)*"@type"\s*:\s*"FAQPage"(?:(?!</script>).)*</script>',
        "",
        html,
        flags=re.S,
    )


def process_file(path: Path, write: bool = True) -> bool:
    """Return True if the file was (or would be) updated."""
    original = path.read_text(encoding="utf-8")

    if BLOCK_START in original:
        cleaned = _strip_marker_block(original)
    else:
        cleaned = _strip_faqpage_script(original)

    if "</head>" not in cleaned:
        print(f"  [skip] {path.name} — no </head> tag found")
        return False

    # Validate the schema JSON one more time before injection
    json.loads(_SCHEMA_JSON_STR)

    result = cleaned.replace("</head>", _INJECT_BLOCK + "\n</head>", 1)

    if result == original:
        return False

    if write:
        path.write_text(result, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(write: bool = True) -> int:
    html_files = sorted(ROUTES_DIR.glob("*.html"))
    if not html_files:
        print(f"[route-faq] No HTML files found in {ROUTES_DIR}")
        return 1

    print(f"[route-faq] Processing {len(html_files)} route page(s) in {ROUTES_DIR}")

    updated = 0
    skipped = 0
    for path in html_files:
        changed = process_file(path, write=write)
        if changed:
            updated += 1
            print(f"  [ok] {path.name}")
        else:
            skipped += 1

    print(
        f"[route-faq] Done — updated: {updated}, unchanged/skipped: {skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run(write=True))
