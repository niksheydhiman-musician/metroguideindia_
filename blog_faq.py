"""Extract FAQ data from the same rendered HTML that readers see."""

from html.parser import HTMLParser
import re


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def text(self):
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children)


class Tree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def clean(value):
    return re.sub(r'\s+', ' ', value).strip()


def is_question(value):
    value = clean(value)
    return '?' in value or bool(re.match(
        r'^(?:q\d*[:.]\s*)?(?:who|what|when|where|why|how|is|are|can|does|do|will|which|should|may|has|have)\b',
        value, re.I))


def extract_faq(html):
    """Return only identifiable question/answer pairs in FAQ sections."""
    root = Tree(html).root
    result = []

    def walk(node):
        for child in node.children:
            if isinstance(child, Node):
                yield child
                yield from walk(child)

    def add(question, answer):
        question, answer = clean(question), clean(answer)
        if is_question(question) and answer:
            result.append({'@type': 'Question', 'name': question,
                           'acceptedAnswer': {'@type': 'Answer', 'text': answer}})

    for heading in walk(root):
        if heading.tag not in ('h2', 'h3') or not re.search(
                r'\b(?:frequently asked questions|faqs?)\b', heading.text(), re.I):
            continue
        siblings = heading.parent.children
        index = siblings.index(heading) + 1
        question, answers = '', []

        def flush():
            nonlocal question, answers
            add(question, ' '.join(answers))
            question, answers = '', []

        for offset, node in enumerate(siblings[index:], start=index):
            if not isinstance(node, Node):
                continue
            if node.tag == 'h2':
                break
            if node.tag == 'h3' and not is_question(node.text()):
                flush()
                has_questions = False
                for following in siblings[offset + 1:]:
                    if not isinstance(following, Node):
                        continue
                    if following.tag in ('h2', 'h3'):
                        break
                    for child in following.children:
                        if isinstance(child, Node) and child.tag in ('strong', 'b') and is_question(child.text()):
                            has_questions = True
                            break
                    if has_questions:
                        break
                if not has_questions:
                    break
                continue
            if node.tag in ('h3', 'h4', 'h5', 'h6'):
                flush()
                question = node.text()
                continue
            if node.tag in ('ul', 'ol'):
                question_list = False
                for li in node.children:
                    if not isinstance(li, Node) or li.tag != 'li':
                        continue
                    strong = next((c for c in li.children if isinstance(c, Node)
                                   and c.tag in ('strong', 'b')), None)
                    if strong and '?' in strong.text():
                        question_list = True
                        flush()
                        add(strong.text(), li.text()[len(strong.text()):])
                if not question_list and question:
                    answers.append(node.text())
                continue
            if node.tag == 'p':
                first = next((c for c in node.children
                              if isinstance(c, Node) or c.strip()), None)
                if isinstance(first, Node) and first.tag in ('strong', 'b') and '?' in first.text():
                    flush()
                    question = first.text()
                    rest = node.text()[len(first.text()):]
                    if clean(rest):
                        answers.append(rest)
                elif question:
                    answers.append(node.text())
        flush()
    return result
