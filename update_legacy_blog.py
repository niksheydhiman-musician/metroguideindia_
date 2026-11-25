"""Add shared blog features to the two independently authored legacy guides."""
import html
import re
from pathlib import Path
from urllib.parse import quote

from blog_content import prepare_html
from blog_faq import Node, Tree, clean
from blog_template import json_ld

PAGES = {
    'navigating-rajiv-chowk-interchange-guide': ('article', 'blog-body'),
    'noida-electronic-city-to-rajiv-chowk': ('main', 'blog-main'),
}
START = '<!-- mgi-shared-start -->'
END = '<!-- mgi-shared-end -->'


def walk(node):
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from walk(child)


def faq_items(fragment):
    result = []
    for item in walk(Tree(fragment).root):
        if 'faq-item' not in item.attrs.get('class', '').split():
            continue
        children = list(walk(item))
        question = next((n for n in children if 'faq-q' in n.attrs.get('class', '').split()), None)
        answer = next((n for n in children if 'faq-a' in n.attrs.get('class', '').split()), None)
        if question and answer and clean(question.text()) and clean(answer.text()):
            result.append({'@type': 'Question', 'name': clean(question.text()),
                           'acceptedAnswer': {'@type': 'Answer', 'text': clean(answer.text())}})
    return result


def toc_markup(slug, toc):
    links = ''.join('<li class="blog-toc-h%d"><a href="/blog/%s.html#%s">%s</a></li>' %
                    (level, quote(slug, safe='-._~'), html.escape(anchor, quote=True), html.escape(text))
                    for level, text, anchor in toc)
    return ('<nav class="blog-toc" aria-label="Table of contents">'
            '<div class="blog-toc-header">On this page</div><ul class="blog-toc-list">' +
            links + '</ul></nav>')


def update(slug, tag, class_name):
    path = Path('blog') / (slug + '.html')
    page = path.read_text(encoding='utf-8')
    page = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', page, flags=re.S)
    page = re.sub(r'<script id="mgi-legacy-faq" type="application/ld\+json">.*?</script>\n?',
                  '', page, flags=re.S)
    page = re.sub(r'<div class="mgi-scroll blog-table-wrap">(<table\b.*?</table\s*>)</div>',
                  r'\1', page, flags=re.S | re.I)
    pattern = r'(<%s class="%s"[^>]*>)(.*?)(</%s>)' % (tag, class_name, tag)
    match = re.search(pattern, page, re.S)
    if not match:
        raise ValueError('Missing legacy article: ' + slug)
    fragment, toc = prepare_html(match[2])
    faqs = faq_items(fragment)
    related = ('<section class="blog-related"><h2>Related Commuter Guides &amp; Transit Insights</h2>'
               '<div class="blog-related-grid">'
               '<a class="blog-related-card" href="/blog/rajiv-chowk-yellow-blue-line-interchange-guide.html">'
               '<h3 class="blog-related-title">Rajiv Chowk interchange guide</h3></a>'
               '<a class="blog-related-card" href="/blog/noida-electronic-city-to-rajiv-chowk-metro-route.html">'
               '<h3 class="blog-related-title">Noida Electronic City to Rajiv Chowk route</h3></a>'
               '</div></section>')
    fragment = START + toc_markup(slug, toc) + END + fragment + START + related + END
    page = page[:match.start()] + match[1] + fragment + match[3] + page[match.end():]
    head = ''
    if '/css/blog.css' not in page:
        head += '<link rel="stylesheet" href="/css/blog.css"/>\n'
    if slug == 'noida-electronic-city-to-rajiv-chowk':
        if 'rel="canonical"' not in page:
            head += '<link rel="canonical" href="https://metroguideindia.com/blog/' + slug + '.html"/>\n'
        if 'googletagmanager.com/gtag/js' not in page:
            head += '<script async src="https://www.googletagmanager.com/gtag/js?id=G-SV6378N2ZW"></script>\n'
    if faqs:
        schema = json_ld({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': faqs})
        head += schema.replace('<script ', '<script id="mgi-legacy-faq" ', 1) + '\n'
    page = page.replace('</head>', head + '</head>', 1)
    path.write_text(page, encoding='utf-8')


def main():
    for slug, (tag, class_name) in PAGES.items():
        update(slug, tag, class_name)


if __name__ == '__main__':
    main()
