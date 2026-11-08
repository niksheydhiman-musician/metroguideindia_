import html
import json
import re
import sys
import unittest
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import generate_bengaluru_routes as gen


class PageParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.json_scripts = []
        self.current_json = None
        self.canonical = None
        self.faqs = []
        self.faq_depth = 0
        self.text_target = None
        self.text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in self.VOID:
            self.stack.append(tag)
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.current_json = ""
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs["href"]
        if tag == "div" and attrs.get("class") == "mgi-faq-wrap":
            self.faq_depth = len(self.stack)
        if self.faq_depth and tag in ("summary", "p"):
            self.text_target = tag
            self.text = ""

    def handle_data(self, data):
        if self.current_json is not None:
            self.current_json += data
        if self.text_target:
            self.text += data

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append((tag, self.stack[-5:]))
            return
        if tag == "script" and self.current_json is not None:
            self.json_scripts.append(json.loads(self.current_json))
            self.current_json = None
        if self.text_target == tag:
            if tag == "summary":
                self.faqs.append([self.text])
            else:
                self.faqs[-1].append(self.text)
            self.text_target = None
        if self.faq_depth == len(self.stack) and tag == "div":
            self.faq_depth = 0
        self.stack.pop()


class BengaluruRouteTests(unittest.TestCase):
    def test_all_pages(self):
        pages = sorted(gen.ROUTES.glob("*.html"))
        self.assertEqual(len(pages), 681)
        for path in pages:
            with self.subTest(page=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"(?i)not listed|—|TBD")
                self.assertEqual(text, gen.render(path))
                self.assertIn('<link rel="stylesheet" href="/assets/css/main.css">', text)
                self.assertEqual(
                    len(re.findall(r'<table class="mgi-tbl"', text)),
                    len(re.findall(r'<div class="mgi-scroll">\s*<table class="mgi-tbl"', text)),
                )
                self.assertEqual(
                    text.count('<div class="mgi-map"'),
                    text.count('<div class="mgi-map-outer"><div class="mgi-map"'),
                )
                parser = PageParser()
                parser.feed(text)
                self.assertFalse(parser.errors)
                self.assertFalse(parser.stack)
                self.assertEqual(parser.canonical, f"https://metroguideindia.com/bengaluru-metro/routes/{path.name}")
                schemas = {s["@type"]: s for s in parser.json_scripts}
                self.assertEqual(set(schemas), {"BreadcrumbList", "FAQPage"})
                faq = schemas["FAQPage"]["mainEntity"]
                self.assertEqual(len(faq), 5)
                self.assertEqual(parser.faqs, [[q["name"], q["acceptedAnswer"]["text"]] for q in faq])
                for href in re.findall(r'href="([^"]+)"', text):
                    href = html.unescape(href)
                    if href.startswith("/"):
                        target = urlparse(href).path
                        self.assertTrue((ROOT / target.lstrip("/")).exists(), href)
                if "airport" in path.stem:
                    self.assertIn("Blue Line airport corridor is under construction", text)
                    self.assertIn("Vayu Vajra", text)
                origin_slug, dest_slug = path.stem.split("-to-")
                origin = gen.station(origin_slug)
                destination = (gen.station("kr-puram" if origin_slug == "kr-puram" else "silk-board")
                               if dest_slug == "airport" else gen.station(dest_slug))
                if origin["id"] == destination["id"]:
                    self.assertNotIn('id="savings"', text)
                    continue
                route = gen.segments(origin["id"], destination["id"])
                distance = Decimal(0)
                for line, ids in route:
                    for a, b in zip(ids, ids[1:]):
                        edge = next(e for e in gen.DATA["interstationDistances"][line]
                                    if {e["fromStationId"], e["toStationId"]} == {a, b})
                        distance += Decimal(str(edge["distanceKm"]))
                displayed = str(distance.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
                expected_fare = next(fare for upper, fare in SLABS if upper is None or distance <= upper)
                peak = Decimal(expected_fare) * Decimal("0.95")
                off_peak = Decimal(expected_fare) * Decimal("0.90")
                self.assertIn(f'<span>Distance</span><b>{displayed} km</b>', text)
                self.assertIn(f' · {displayed} km ·', text)
                self.assertIn(f'covers {displayed} km', faq[0]["acceptedAnswer"]["text"])
                self.assertIn(f'<span>Token Fare</span><b>₹{expected_fare}</b>', text)
                self.assertIn(f'{format_money(peak)} peak / {format_money(off_peak)} off-peak', text)
                self.assertIn('Smart Card (Peak 5%)', text)
                self.assertIn('Smart Card (Off-Peak 10%)', text)
                self.assertIn('Total Monthly Savings', text)
                self.assertIn('05:00–08:00, 11:00–16:30 and 20:00–23:00, and all day Sunday', text)
                self.assertNotIn('flat 5%', text.lower())
                for label, count in (("Per trip", 1), ("Daily round trip", 2), ("Weekly 6 days", 12), ("Monthly 24 workdays", 48)):
                    cells = f'<td>{label}</td><td>{format_money(Decimal(expected_fare) * count)}</td><td>{format_money(peak * count)}</td><td>{format_money(off_peak * count)}</td>'
                    self.assertIn(cells, text)
                monthly_savings = f'Peak {format_money((Decimal(expected_fare) - peak) * 48)} / off-peak {format_money((Decimal(expected_fare) - off_peak) * 48)}'
                self.assertIn(monthly_savings, text)
                self.assertIn(format_money(peak), faq[1]["acceptedAnswer"]["text"])
                self.assertIn(format_money(off_peak), faq[1]["acceptedAnswer"]["text"])

    def test_routes_and_fares(self):
        whitefield = gen.station("whitefield")["id"]
        electronic = gen.station("electronic-city")["id"]
        route = gen.segments(whitefield, electronic)
        self.assertEqual([x[0] for x in route], ["PURPLE", "GREEN", "YELLOW"])
        self.assertEqual([x[1][0] for x in route[1:]], [
            "nadaprabhu-kempegowda-station-majestic", "rashtreeya-vidyalaya-road-rv-road"])
        self.assertEqual(str(gen.distance_of(route)), "48.25")
        self.assertEqual(gen.fare_for(gen.distance_of(route)), 90)
        direct = gen.segments(whitefield, gen.station("challaghatta")["id"])
        self.assertEqual(gen.fare_for(gen.distance_of(direct)), 85)
        for i, (upper, fare) in enumerate(SLABS):
            if upper is None:
                continue
            self.assertEqual(gen.fare_for(upper), fare)
            self.assertEqual(gen.fare_for(upper + Decimal("0.01")), SLABS[i + 1][1])

    def test_reverse_links_and_special_connections(self):
        page = gen.render(gen.ROUTES / "national-college-to-majestic.html")
        href = html.unescape(re.search(r'<a class="mgi-btn" href="([^"]+)"', page).group(1))
        query = parse_qs(urlparse(href).query)
        self.assertEqual(query["city"], ["bengaluru"])
        self.assertEqual(query["from"], ["nadaprabhu-kempegowda-station-majestic"])
        self.assertEqual(query["to"], ["national-college"])
        same = gen.render(gen.ROUTES / "sandal-soap-factory-to-orion-mall.html")
        self.assertIn("No metro ride is needed", same)
        self.assertIn("Brigade Gateway skybridge", same)
        self.assertNotIn("Token Fare", same)


SLABS = [(Decimal(bound) if bound is not None else None, fare) for bound, fare in [
    (2, 10), (4, 15), (6, 20), (8, 25), (10, 30), (12, 35), (15, 40),
    (18, 45), (21, 50), (24, 55), (27, 60), (30, 65), (33, 70), (37, 75),
    (42, 80), (46, 85), (None, 90),
]]


def format_money(value):
    return "₹" + f"{value:,.2f}".rstrip("0").rstrip(".")


if __name__ == "__main__":
    unittest.main()
