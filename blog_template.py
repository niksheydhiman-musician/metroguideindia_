"""Static blog pages built from the site's existing post template."""
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

from blog_content import prepare
from blog_faq import extract_faq

SITE = 'https://metroguideindia.com'


def json_ld(value):
    return '<script type="application/ld+json">' + json.dumps(
        value, ensure_ascii=False).replace('<', '\\u003c') + '</script>'


def render(slug, post, posts, canonical_slug=None, source_slug=None):
    title = str(post.get('title') or slug)
    description = str(post.get('description') or '')
    body = post.get('body') or ('## Overview\n\n' + description if description else '')
    body_html, toc = prepare(body, title)
    canonical = SITE + '/blog/' + quote(canonical_slug or slug, safe='-._~') + '.html'
    page_title = title + ' | MetroGuideIndia'
    article = {
        '@context': 'https://schema.org', '@type': 'BlogPosting',
        'headline': title, 'description': description,
        'datePublished': post.get('date', ''),
        'author': {'@type': 'Organization', 'name': post.get('author') or 'MetroGuideIndia'},
        'mainEntityOfPage': canonical,
    }
    if post.get('image'):
        article['image'] = post['image']
    faqs = extract_faq(body_html)
    schemas = json_ld(article)
    if faqs:
        schemas += '\n' + json_ld({'@context': 'https://schema.org', '@type': 'FAQPage',
                                   'mainEntity': faqs})
    tags = post.get('tags') or []
    tag_html = ''.join('<span class="post-tag' +
                       (' post-tag--meerut' if 'meerut metro' in str(tag).lower() else '') +
                       '">' + html.escape(str(tag)) + '</span>' for tag in tags)
    toc_html = ''
    if toc:
        items = ''.join(
            '<li class="blog-toc-h%d"><a href="/blog/%s.html#%s">%s</a></li>' %
            (level, quote(slug, safe='-._~'), html.escape(anchor, quote=True), html.escape(text))
            for level, text, anchor in toc)
        toc_html = ('<nav class="blog-toc" aria-label="Table of contents">'
                    '<div class="blog-toc-header">On this page</div><ul class="blog-toc-list">'
                    + items + '</ul></nav>')
    tag_set = {str(t).casefold() for t in tags}
    candidates = []
    for candidate_slug, candidate in posts.items():
        if candidate_slug == (source_slug or slug):
            continue
        overlap = len(tag_set & {str(t).casefold() for t in candidate.get('tags', []) or []})
        candidates.append((overlap, str(candidate.get('date') or ''), candidate_slug, candidate))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]), reverse=True)
    cards = ''.join(
        '<a class="blog-related-card" href="/blog/%s.html"><h3 class="blog-related-title">%s</h3>'
        '<p>%s</p></a>' % (quote(other_slug, safe='-._~'), html.escape(str(other.get('title') or other_slug)),
                           html.escape(str(other.get('description') or '')))
        for _, _, other_slug, other in candidates[:3])
    related = ('<section class="blog-related" aria-labelledby="related-heading">'
               '<h2 id="related-heading">Related Commuter Guides &amp; Transit Insights</h2>'
               '<div class="blog-related-grid">' + cards + '</div></section>') if cards else ''
    image = ('<img class="post-feature-image" src="%s" alt="%s" loading="eager">' %
             (html.escape(str(post['image']), quote=True), html.escape(title, quote=True))) if post.get('image') else ''
    read_time = max(1, round(len(re.findall(r'\S+', body)) / 200))
    content = (
        '<div id="post-content"><header class="post-header"><div class="post-tags">' + tag_html +
        '</div><h1 class="post-title">' + html.escape(title) + '</h1><div class="post-meta"><span>' +
        html.escape(str(post.get('author') or 'MetroGuideIndia')) + '</span><span>' +
        html.escape(str(post.get('date') or '')) + '</span><span>' + str(read_time) +
        ' min read</span></div></header><hr class="post-divider">' + image +
        '<div class="post-grid"><div class="blog-article"><article class="blog-body" id="blog-article">' +
        body_html + '</article>' + related + '</div>' + toc_html + '</div></div>')

    template = Path('post.html').read_text(encoding='utf-8')
    template = re.sub(r'\s*<style>\s*html\.blog-loading main,.*?</style>\s*'
                      r'<script>document\.documentElement\.classList\.add\(\'blog-loading\'\);.*?</script>',
                      '', template, count=1, flags=re.S)
    replacements = [
        (r'<title>.*?</title>', '<title>' + html.escape(page_title) + '</title>'),
        (r'<meta name="description" content="[^"]*"\s*/?>',
         '<meta name="description" content="' + html.escape(description, quote=True) + '"/>'),
        (r'<link rel="canonical" href="[^"]*"\s*/?>',
         '<link rel="canonical" href="' + html.escape(canonical, quote=True) + '"/>'),
        (r'<meta property="og:title" content="[^"]*"\s*/?>',
         '<meta property="og:title" content="' + html.escape(page_title, quote=True) + '"/>'),
        (r'<meta property="og:description" content="[^"]*"\s*/?>',
         '<meta property="og:description" content="' + html.escape(description, quote=True) + '"/>'),
        (r'<div id="post-content">.*?</div>', content),
        (r"<script>BlogBridge\.openStaticPost\('post-content'\);</script>",
         '<script>BlogBridge.enhanceArticle(document.getElementById("blog-article"));</script>'),
    ]
    for pattern, replacement in replacements:
        template, count = re.subn(pattern, lambda _: replacement, template, count=1, flags=re.S)
        if count != 1:
            raise ValueError('Post template is missing expected element: ' + pattern)
    result = template.replace('</head>', '<link rel="stylesheet" href="/css/blog.css"/>\n' +
                              schemas + '\n</head>', 1)
    return re.sub(r'(?m)^[ \t]+$', '', result)
