"""Dependency-free rendering helpers for CMS blog content."""
import html
import json
import re
from html.parser import HTMLParser


def inline(text):
    def format_text(part):
        tokens = []

        def save(value):
            tokens.append(value)
            return f'\x00{len(tokens) - 1}\x00'

        part = re.sub(
            r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)',
            lambda m: save(f'<img src="{html.escape(m[2], quote=True)}" alt="{html.escape(m[1], quote=True)}" loading="lazy">'),
            part,
        )
        part = re.sub(
            r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)',
            lambda m: save(f'<a href="{html.escape(m[2], quote=True)}">{inline(m[1])}</a>'),
            part,
        )
        part = re.sub(r'`([^`]+)`', lambda m: save('<code>' + html.escape(m[1]) + '</code>'), part)
        part = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: '<strong>' + (m[1] or m[2]) + '</strong>', part)
        part = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', part)
        part = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'<em>\1</em>', part)
        return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], part)

    return ''.join(part if part.startswith('<') and part.endswith('>') else format_text(part)
                   for part in re.split(r'(<[^>]+>)', text))


def _document_fragment(document):
    body = re.search(r'<body\b[^>]*>(.*?)</body\s*>', document, re.I | re.S)
    if not body:
        raise ValueError('Embedded HTML document has no body')
    styles = re.findall(r'<style\b[^>]*>(.*?)</style\s*>', document, re.I | re.S)
    styles = [re.sub(r'html\s*,\s*body\s*\{[^}]*\}', '', s, flags=re.I) for s in styles]
    return ''.join('<style>' + s + '</style>' for s in styles) + body.group(1)


def _transit_flow(raw):
    flow = json.loads(raw)
    if flow.get('component') != 'transit-flow' or not isinstance(flow.get('stops'), list):
        raise ValueError('Invalid transit flow component')
    stops, transfers = flow['stops'], flow.get('transfers')
    tones = {'rrts': '#C0392B', 'pink': '#D91B5C', 'yellow': '#F5A623',
             'rapid': '#004B87', 'destination': '#27764A'}
    if len(stops) < 2 or not isinstance(transfers, list) or len(transfers) != len(stops) - 1:
        raise ValueError('Invalid transit flow stops or transfers')
    esc = lambda value: html.escape(str(value), quote=True)
    result = ['<div class="mgi-flow-container"><div class="mgi-flow-header"><div class="mgi-flow-title">',
              esc(flow['title']), '</div><span class="mgi-flow-badge">', esc(flow['badge']),
              '</span></div><div class="mgi-flow-timeline">']
    for i, stop in enumerate(stops):
        tone = stop['tone']
        if tone not in tones:
            raise ValueError('Invalid transit flow tone: ' + str(tone))
        extra = ' mgi-flow-node--destination' if tone == 'destination' else ''
        result.extend(['<div class="mgi-flow-node', extra, '" style="--dot-color:', tones[tone],
                       '"><div class="mgi-flow-bullet"></div><div class="mgi-stn-title"><span>',
                       esc(stop['name']), '</span><span class="mgi-tag">', esc(stop['tag']),
                       '</span></div><p class="mgi-stn-sub">', esc(stop['description']), '</p></div>'])
        if i < len(transfers):
            result.extend(['<div class="mgi-flow-transfer">', esc(transfers[i]), '</div>'])
    result.append('</div></div>')
    return ''.join(result)


def _is_bold_heading(text, previous, following, in_faq):
    if not following or len(text) > 140 or len(text.split()) > 18:
        return False
    if previous.lower() in ('and', 'or', 'then') or re.match(r'^(?:and|or|as)\b', following, re.I):
        return False
    if re.search(r'[↓↑→←▼│]', text + previous[-1:] + following[:1]):
        return False
    if in_faq and '?' in text:
        return True
    if previous.endswith(':') or text.endswith(('?', '!')):
        return False
    step = bool(re.match(r'^(?:step|phase)\s+\d+\b', text, re.I))
    if text.endswith('.') and not step:
        return False
    next_is_list_or_table = bool(re.match(r'^(?:\||[-*+]\s|\d+[.)]\s)', following))
    title_words = re.findall(r'\b[A-Z][A-Za-z]+\b', text)
    title_like = len(text.split()) >= 3 and len(title_words) >= 2
    return bool(next_is_list_or_table or step or title_like or (':' in text and not text.endswith(':')))


def _promote_bold_headings(lines):
    """Recognize standalone section labels, without turning emphasis into headings."""
    output = list(lines)
    in_faq = False
    has_section = False
    in_fence = False
    raw_tag = None
    raw_depth = 0
    for i, line in enumerate(lines):
        if re.match(r'^\s*```', line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if raw_tag == 'document':
            if re.search(r'</html\s*>', line, re.I):
                raw_tag = None
            continue
        if not raw_tag and re.match(r'^\s*<!doctype\s+html\b', line, re.I):
            if not re.search(r'</html\s*>', line, re.I):
                raw_tag = 'document'
            continue
        if not raw_tag:
            block = re.match(r'^\s*<(div|section|figure|table|style|script|details|aside|svg)\b', line, re.I)
            if block:
                raw_tag = block[1]
                raw_depth = 0
        if raw_tag:
            for token in re.finditer(r'</?' + raw_tag + r'\b[^>]*>', line, re.I):
                if token.group().startswith('</'):
                    raw_depth -= 1
                elif not token.group().endswith('/>'):
                    raw_depth += 1
            if raw_depth <= 0:
                raw_tag = None
            continue
        heading = re.match(r'^\s*(#{1,6})\s+(.+)', line)
        if heading:
            title = re.sub(r'[*_]', '', heading[2])
            if re.search(r'\b(?:frequently asked questions|faqs?)\b', title, re.I):
                in_faq = True
            elif len(heading[1]) <= 2:
                in_faq = False
            if len(heading[1]) >= 2:
                has_section = True
            continue
        match = re.fullmatch(r'\s*(?:\*\*(?!\*)([^*]+)\*\*|__([^_]+)__)\s*', line)
        if not match or (i and lines[i - 1].strip()):
            continue
        text = (match[1] or match[2]).strip()
        step = bool(re.match(r'^(?:step|phase)\s+\d+\b', text, re.I))
        if i + 1 < len(lines) and lines[i + 1].strip() and not step:
            continue
        previous = next((value.strip() for value in reversed(lines[:i]) if value.strip()), '')
        following = next((value.strip() for value in lines[i + 1:] if value.strip()), '')
        if _is_bold_heading(text, previous, following, in_faq):
            output[i] = ('### ' if has_section else '## ') + text
    return output


class _TopLevelBlocks(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.line_offsets = [0]
        for match in re.finditer('\n', source):
            self.line_offsets.append(match.end())
        self.stack = []
        self.blocks = []
        self.start = 0
        self.feed(source)

    def position(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if not self.stack:
            self.start = self.position()
        if tag in self.VOID:
            if not self.stack:
                self.blocks.append((tag, self.start, self.position() + len(self.get_starttag_text())))
        else:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self.stack:
            start = self.position()
            self.blocks.append((tag, start, start + len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            if current == tag:
                break
        if not self.stack:
            end = self.source.find('>', self.position()) + 1
            self.blocks.append((tag, self.start, end))


def _promote_html_headings(source):
    blocks = _TopLevelBlocks(source).blocks
    replacements = []
    in_faq = False
    has_section = False

    def text(block):
        return html.unescape(re.sub(r'<[^>]+>', '', source[block[1]:block[2]])).strip()

    for i, block in enumerate(blocks):
        tag, start, end = block
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            if re.search(r'\b(?:frequently asked questions|faqs?)\b', text(block), re.I):
                in_faq = True
            elif tag in ('h1', 'h2'):
                in_faq = False
            if tag != 'h1':
                has_section = True
            continue
        if tag != 'p' or i + 1 == len(blocks):
            continue
        match = re.fullmatch(r'<p\b([^>]*)>\s*<(strong|b)>([^<>]+)</\2>\s*</p\s*>',
                             source[start:end], re.I | re.S)
        if not match:
            continue
        title = html.unescape(match[3]).strip()
        previous = text(blocks[i - 1]) if i else ''
        following_block = blocks[i + 1]
        following = '| table' if following_block[0] == 'table' else (
            '- list' if following_block[0] in ('ul', 'ol') else text(following_block))
        if _is_bold_heading(title, previous, following, in_faq):
            level = 3 if has_section else 2
            replacements.append((start, end, f'<h{level}{match[1]}>{match[3]}</h{level}>'))
    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    return source


def _visual_html(raw, language):
    if language == 'mgi-html':
        return True
    if language != 'html':
        return False
    return bool(re.search(
        r'<(?:!doctype\s+html|html|div|section|article|aside|figure|table|svg|style|script|details)\b'
        r'|<(?:span|p)\b[^>]*\b(?:class|style|id)\s*=',
        raw, re.I))


def _embedded_document(raw):
    if not re.match(r'\s*(?:<!doctype\s+html|<html\b)', raw, re.I):
        raw = '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + raw + '</body></html>'
    return ('<iframe class="blog-embed" title="Interactive transit visual" '
            'sandbox="allow-scripts" srcdoc="' + html.escape(raw, quote=True) + '"></iframe>')


def markdown(body):
    if not body:
        return ''
    if body.lstrip().startswith('<h1') or body.lstrip().startswith('<p'):
        return _promote_html_headings(inline(body))

    lines = _promote_bold_headings(body.splitlines())
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if re.match(r'^<!doctype html', stripped, re.I):
            chunk = []
            while i < len(lines):
                chunk.append(lines[i])
                i += 1
                if re.search(r'</html\s*>', chunk[-1], re.I):
                    break
            out.append(_document_fragment('\n'.join(chunk)))
            continue
        if re.match(r'^```', stripped):
            language = stripped[3:].strip().lower()
            code = []
            i += 1
            while i < len(lines) and not re.match(r'^\s*```', lines[i]):
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError('Unclosed fenced code block')
            i += 1
            raw = '\n'.join(code)
            if language == 'mgi-transit-flow':
                out.append(_transit_flow(raw))
            elif ((language == 'plain' and re.match(r'\s*(?:<!doctype\s+html|<html\b)', raw, re.I))
                  or _visual_html(raw, language)):
                if re.match(r'\s*(?:<!doctype\s+html|<html\b)', raw, re.I) or re.search(r'<(?:style|script)\b', raw, re.I):
                    out.append(_embedded_document(raw))
                else:
                    out.append(raw)
            elif language == 'plain':
                out.append('<figure class="mgi-diagram"><pre>' + html.escape(raw) + '</pre></figure>')
            else:
                out.append('<pre><code>' + html.escape(raw) + '</code></pre>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', stripped)
        if heading:
            level = len(heading[1])
            out.append(f'<h{level}>{inline(heading[2])}</h{level}>')
            i += 1
            continue
        if re.fullmatch(r'(?:-{3,}|\*{3,}|_{3,})', stripped):
            out.append('<hr>')
            i += 1
            continue
        separator = r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$'
        if i + 1 < len(lines) and '|' in line and (
                re.match(separator, lines[i + 1]) or
                (stripped.startswith('|') and lines[i + 1].strip().startswith('|'))):
            def cells(row):
                return [inline(cell.strip().replace(r'\|', '|'))
                        for cell in re.split(r'(?<!\\)\|', row.strip().strip('|'))]
            headers = cells(line)
            i += 1
            if i < len(lines) and re.match(separator, lines[i]):
                i += 1
            rows = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip() and (
                    lines[i].strip().startswith('|') or not stripped.startswith('|')):
                rows.append(cells(lines[i]))
                i += 1
            out.append('<table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in headers)
                       + '</tr></thead><tbody>' + ''.join(
                           '<tr>' + ''.join('<td>' + c + '</td>' for c in row) + '</tr>'
                           for row in rows) + '</tbody></table>')
            continue
        list_match = re.match(r'^([-*+]|\d+[.)])\s+(.+)', stripped)
        if list_match:
            ordered = list_match[1][0].isdigit()
            items = []
            while i < len(lines):
                item = re.match(r'^\s*([-*+]|\d+[.)])\s+(.+)', lines[i])
                if not item or item[1][0].isdigit() != ordered:
                    break
                items.append('<li>' + inline(item[2]) + '</li>')
                i += 1
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(items) + f'</{tag}>')
            continue
        if stripped.startswith('>'):
            parts = []
            while i < len(lines) and lines[i].lstrip().startswith('>'):
                parts.append(inline(re.sub(r'^\s*>\s?', '', lines[i])))
                i += 1
            out.append('<blockquote class="blog-note">' + '<br>'.join(parts) + '</blockquote>')
            continue
        block = re.match(r'<(div|section|figure|table|style|script|details|aside|svg)\b', stripped, re.I)
        if block:
            tag = block[1]
            depth, chunk = 0, []
            while i < len(lines):
                current = lines[i]
                chunk.append(current)
                for token in re.finditer(r'</?' + tag + r'\b[^>]*>', current, re.I):
                    if token.group().startswith('</'):
                        depth -= 1
                    elif not token.group().endswith('/>'):
                        depth += 1
                i += 1
                if depth <= 0:
                    break
            if depth:
                raise ValueError('Unclosed embedded HTML block: ' + tag)
            out.append('\n'.join(chunk))
            continue
        if stripped.startswith('<') and re.match(r'</?[A-Za-z!]', stripped):
            out.append(line)
            i += 1
            continue
        parts = [inline(stripped)]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r'^\s*(?:#{1,6}\s|```|>|[-*+]\s|\d+[.)]\s|<)', lines[i]):
            if i + 1 < len(lines) and '|' in lines[i] and (
                    re.match(separator, lines[i + 1]) or
                    (lines[i].strip().startswith('|') and lines[i + 1].strip().startswith('|'))):
                break
            parts.append(inline(lines[i].strip()))
            i += 1
        out.append('<p>' + ' '.join(parts) + '</p>')
    return '\n'.join(out)


def prepare_html(rendered, title=''):
    used = set()
    toc = []
    first_heading = True

    def heading(match):
        nonlocal first_heading
        level = int(match[1])
        attrs, content = match[2], match[3]
        text = html.unescape(re.sub(r'<[^>]+>', '', content)).strip()
        if not text:
            return ''
        if level == 1 and first_heading and text.casefold() == title.strip().casefold():
            first_heading = False
            return ''
        first_heading = False
        level = 2 if level == 1 or re.search(r'\b(?:frequently asked questions|faqs?)\b', text, re.I) else min(level, 3)
        existing = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs)
        base = existing[1] if existing else re.sub(r'[-\s]+', '-', re.sub(r'[^\w\s-]', '', text.lower())).strip('-')
        base = base or 'section'
        slug, suffix = base, 2
        while slug in used:
            slug = f'{base}-{suffix}'
            suffix += 1
        used.add(slug)
        attrs = re.sub(r'\s+id\s*=\s*["\'][^"\']*["\']', '', attrs)
        toc.append((level, text, slug))
        return f'<h{level}{attrs} id="{html.escape(slug, quote=True)}">{content}</h{level}>'

    rendered = re.sub(r'<h([1-6])\b([^>]*)>(.*?)</h\1\s*>', heading, rendered, flags=re.I | re.S)
    rendered = re.sub(r'(<table\b[^>]*>.*?</table\s*>)',
                      r'<div class="mgi-scroll blog-table-wrap">\1</div>', rendered, flags=re.I | re.S)
    return rendered, toc


def prepare(body, title):
    return prepare_html(markdown(body), title)
