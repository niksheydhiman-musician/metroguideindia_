import json
import re
import unittest

from blog_content import prepare
from blog_faq import extract_faq
from blog_template import render


class BlogRenderingTests(unittest.TestCase):
    def test_tables_headings_and_inline_content(self):
        body = """# Journey

## Route

This is **important**, not a heading. See [the guide](/blog/test.html).

| Station | Fare |
| Alpha | ₹20 |
| Beta | ₹30 |

### Transfer

## Route
"""
        output, toc = prepare(body, 'Journey')
        self.assertIn('<p>This is <strong>important</strong>, not a heading.', output)
        self.assertIn('<a href="/blog/test.html">the guide</a>', output)
        self.assertIn('<div class="mgi-scroll blog-table-wrap"><table>', output)
        self.assertIn('<td>₹30</td>', output)
        self.assertEqual([x[2] for x in toc], ['route', 'transfer', 'route-2'])

    def test_faqs_come_from_rendered_headings_and_complete_answers(self):
        body = """## Frequently Asked Questions

### Is this direct?

Yes, it is **direct**.

Extra information.

**Can I bring a bag?**

Yes.

- A small bag
- A suitcase

## Further reading

Unrelated text.
"""
        output, _ = prepare(body, 'Journey')
        faqs = extract_faq(output)
        self.assertEqual([f['name'] for f in faqs], ['Is this direct?', 'Can I bring a bag?'])
        self.assertEqual(faqs[0]['acceptedAnswer']['text'], 'Yes, it is direct. Extra information.')
        self.assertIn('A small bag', faqs[1]['acceptedAnswer']['text'])
        self.assertNotIn('Unrelated text', faqs[1]['acceptedAnswer']['text'])

    def test_faq_subcategories_keep_all_questions_but_not_related_guides(self):
        body = """## Frequently Asked Questions

**Is this direct?** Yes.

### Purple Line Specific

**Q: Where is the station?** At the airport.

### Related Articles

- [Read another guide](/blog/guide.html)
"""
        output, _ = prepare(body, 'Journey')
        faqs = extract_faq(output)
        self.assertEqual([f['name'] for f in faqs],
                         ['Is this direct?', 'Q: Where is the station?'])

    def test_embedded_blocks_and_genuine_code(self):
        flow = {'component': 'transit-flow', 'title': 'Route', 'badge': 'Two stops',
                'stops': [{'name': 'Start', 'tag': 'RRTS', 'tone': 'rrts', 'description': 'Board'},
                          {'name': 'End', 'tag': 'Metro', 'tone': 'destination', 'description': 'Exit'}],
                'transfers': ['Walk']}
        body = ('<div class="visual">\n<span>Transit</span>\n</div>\n\n'
                '```mgi-transit-flow\n' + json.dumps(flow) + '\n```\n\n'
                '```plain\n<!DOCTYPE html><html><body><p>Calculator</p></body></html>\n```\n\n'
                '```python\nprint("hello")\n```')
        output, _ = prepare(body, 'Journey')
        self.assertIn('<div class="visual">\n<span>Transit</span>\n</div>', output)
        self.assertIn('class="mgi-flow-container"', output)
        self.assertIn('class="blog-embed"', output)
        self.assertIn('<pre><code>print(&quot;hello&quot;)</code></pre>', output)

    def test_bold_subheadings_do_not_promote_emphasis_or_diagrams(self):
        body = """## Airport routes

**Travel Time and Cost Comparison: RRTS + Metro vs. Cab vs. Bus**

| Mode | Time |
| Metro | 90 minutes |

This sentence contains **important advice** for passengers.

**Do not assume the train will wait.**

**This is important**

Please check before travelling.

**New Delhi Railway Station**

↓

**New Delhi Metro**

and

**10–15 minutes for Namo Bharat entry/security**

as a reasonable buffer.

**Step 1: Enter the station.**
Use the main entrance.
"""
        output, toc = prepare(body, 'Journey')
        self.assertIn('<h3 id="travel-time-and-cost-comparison-rrts-metro-vs-cab-vs-bus">', output)
        self.assertIn('Travel Time and Cost Comparison: RRTS + Metro vs. Cab vs. Bus',
                      [item[1] for item in toc])
        self.assertIn('<p>This sentence contains <strong>important advice</strong>', output)
        self.assertIn('<p><strong>Do not assume the train will wait.</strong></p>', output)
        self.assertIn('<p><strong>This is important</strong></p>', output)
        self.assertIn('<p><strong>New Delhi Railway Station</strong></p>', output)
        self.assertIn('<p><strong>New Delhi Metro</strong></p>', output)
        self.assertIn('<p><strong>10–15 minutes for Namo Bharat entry/security</strong></p>', output)
        self.assertIn('<h3 id="step-1-enter-the-station">Step 1: Enter the station.</h3>', output)

    def test_html_visual_fences_and_explicit_html_code(self):
        body = """```html
<div class="transit-flow"><span>Board here</span></div>
```

```html
<style>.callout { color: red; }</style>
<div class="callout">Metro guide</div>
```

```html-code
<div class="example">Show this source</div>
```

```html
<a href="/blog">An inline HTML example</a>
```
"""
        output, _ = prepare(body, 'Journey')
        self.assertIn('<div class="transit-flow"><span>Board here</span></div>', output)
        self.assertIn('class="blog-embed"', output)
        self.assertIn('&lt;style&gt;.callout', output)
        self.assertIn('<pre><code>&lt;div class=&quot;example&quot;&gt;', output)
        self.assertIn('<pre><code>&lt;a href=&quot;/blog&quot;&gt;', output)

    def test_html_bold_subheadings_do_not_change_nested_component_or_emphasis(self):
        body = ('<h1>Journey</h1><h2>Route</h2>'
                '<p id="fare-comparison"><strong>Travel Time and Cost Comparison</strong></p>'
                '<table><tr><th>Mode</th></tr><tr><td>Metro</td></tr></table>'
                '<p>This is <strong>important</strong> to remember.</p>'
                '<p><strong>Do not assume the train will wait.</strong></p>'
                '<div><p><strong>Styled Component Label</strong></p></div>')
        output, toc = prepare(body, 'Journey')
        self.assertIn('<h3 id="fare-comparison">', output)
        self.assertIn('Travel Time and Cost Comparison', [entry[1] for entry in toc])
        self.assertIn('<p>This is <strong>important</strong> to remember.</p>', output)
        self.assertIn('<p><strong>Do not assume the train will wait.</strong></p>', output)
        self.assertIn('<div><p><strong>Styled Component Label</strong></p></div>', output)

    def test_schema_is_standalone_and_matches_visible_content(self):
        post = {'title': 'Journey', 'description': 'A trip', 'date': '2026-01-01',
                'body': '## FAQs\n\n### Where?\n\nAt **the station**.', 'tags': []}
        page = render('journey', post, {'journey': post})
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page)
        schemas = [json.loads(block) for block in blocks]
        faq = next(s for s in schemas if s['@type'] == 'FAQPage')
        self.assertEqual(faq['mainEntity'][0]['acceptedAnswer']['text'], 'At the station.')
        self.assertIn('<p>At <strong>the station</strong>.</p>', page)
        self.assertIn('/blog/journey.html#faqs', page)
        no_faq = render('journey', dict(post, body='## Route\n\nNo questions.'), {'journey': post})
        self.assertNotIn('"FAQPage"', no_faq)


if __name__ == '__main__':
    unittest.main()
