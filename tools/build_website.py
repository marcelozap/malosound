#!/usr/bin/env python3
"""Validate and stage the exact public MaloSound project page. No data intake."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build'
PUBLIC_FILES = (
    'index.html', 'site.css', '404.html',
    'assets/brand/orbit-violet-ice.png',
    'assets/brand/malosound-violet-ice-cover.png',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.h1s = 0
        self.title = False
        self.description = False
        self.viewport = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            require(attrs['id'] not in self.ids, f'Duplicate id: {attrs["id"]}')
            self.ids.add(attrs['id'])
        self.h1s += tag == 'h1'
        self.title |= tag == 'title'
        self.description |= tag == 'meta' and attrs.get('name') == 'description'
        self.viewport |= tag == 'meta' and attrs.get('name') == 'viewport'
        require(tag not in ('script', 'iframe', 'form', 'input'), f'Unexpected active element: {tag}')
        if tag == 'img':
            require('alt' in attrs, 'Images need alt text.')
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.links.append(attrs.get('content', ''))


def validate():
    paths = {(ROOT / name).resolve() for name in PUBLIC_FILES}
    pages = {}
    for name in PUBLIC_FILES:
        path = ROOT / name
        require(path.is_file() and not path.is_symlink(), f'Missing or linked public file: {name}')
        if path.suffix == '.html':
            page = Page()
            page.feed(path.read_text(encoding='utf-8'))
            require(page.h1s == 1 and page.title and page.description and page.viewport,
                    f'{name}: requires one heading, title, description and viewport.')
            pages[path.resolve()] = page
    for path, page in pages.items():
        for raw in page.links:
            url = urlsplit(raw)
            if url.netloc and url.hostname not in ('malosound.ai', 'www.malosound.ai'):
                require(url.scheme == 'https', f'External links must use HTTPS: {raw}')
                continue
            require(not url.scheme or url.scheme == 'https', f'Unsupported URL: {raw}')
            base = ROOT if url.path.startswith('/') else path.parent
            target = (base / unquote(url.path).lstrip('/')).resolve() if url.path else path
            if target.is_dir():
                target /= 'index.html'
            require(target in paths, f'Link omitted from public build: {raw}')
            if url.fragment and target in pages:
                require(unquote(url.fragment) in pages[target].ids, f'Missing anchor: {raw}')


def main():
    validate()
    require(not OUTPUT.is_symlink(), 'Refusing to replace a linked build directory.')
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for name in PUBLIC_FILES:
        target = OUTPUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    actual = {str(p.relative_to(OUTPUT)) for p in OUTPUT.rglob('*') if p.is_file()}
    require(actual == set(PUBLIC_FILES), 'Public output differs from the allowlist.')
    print(f'Validated and staged {len(actual)} public files in {OUTPUT}')


if __name__ == '__main__':
    main()
