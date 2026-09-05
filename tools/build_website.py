#!/usr/bin/env python3
"""Validate the journal and stage only public website files for static hosting."""
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import json
import shutil
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build'
PUBLIC_FILES = (
    'index.html', 'journal.css', 'journal.js', 'content/editions.json',
    'market-map.html', 'market-map.js', 'content/market-map.json', 'content/market-assets.json',
    'writings/one-song-one-session.html', 'assets/brand/market-into-music.png',
    'assets/brand/malosound-square.png',
    'studio.html', 'latin-house-lab.html', 'latin-house-lab.css', 'latin-house-lab.js',
    'gateway/sample-01.audioanalysis.v1.json', 'gateway/sample-02.audioanalysis.v1.json',
)
PUBLIC_FILES += tuple(json.loads((ROOT / 'content/market-assets.json').read_text()))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_journal(data):
    require(isinstance(data, dict), 'The journal must be a JSON object.')
    sessions = data.get('sessions')
    duration = data.get('songDurationSeconds')
    require(isinstance(sessions, list), 'sessions must be a list.')
    require(duration is None or (type(duration) is int and duration > 0),
            'songDurationSeconds must be null or a positive integer.')
    dates = set()
    for session in sessions:
        require(isinstance(session, dict), 'Each session must be an object.')
        day = session.get('date', '')
        parsed = date.fromisoformat(day)
        require(parsed.isoformat() == day, 'Use YYYY-MM-DD session dates.')
        # Recaps can be dated on weekends and exchange holidays.
        require(day not in dates, f'{day}: duplicate session date.')
        dates.add(day)
        require(session.get('morning') or session.get('closing'), f'{day}: add at least one edition.')
        for kind in ('morning', 'closing'):
            entry = session.get(kind)
            if entry is None:
                continue
            require(isinstance(entry, dict), f'{day}: {kind} must be an object.')
            for key in ('title', 'summary'):
                require(isinstance(entry.get(key), str) and entry[key].strip(),
                        f'{day}: {kind}.{key} needs text.')
            paragraphs = entry.get('paragraphs', [])
            require(isinstance(paragraphs, list) and all(isinstance(p, str) and p.strip() for p in paragraphs),
                    f'{day}: {kind}.paragraphs must contain nonempty strings.')
            for field in ('reportUrl', 'mapUrl'):
                if entry.get(field):
                    require(entry[field].startswith('/') and '..' not in entry[field], f'{day}: safe local {field} required')
                    require(entry[field].split('?')[0].lstrip('/') in PUBLIC_FILES, f'{day}: missing published {field}')
            if entry.get('chart'):
                for field in ('url','dataUrl'):
                    require(entry['chart'][field].lstrip('/') in PUBLIC_FILES, f'{day}: chart asset missing')
                require(entry['chart'].get('alt') and entry['chart'].get('caption'), f'{day}: chart description required')
            if entry.get('song'):
                require(urlsplit(entry['song']['url']).scheme == 'https', f'{day}: HTTPS listening link required')
                require(all(entry['song'].get(k) for k in ('title','artist','reason')), f'{day}: song metadata required')
            if kind == 'closing' and entry.get('audioUrl'):
                require(duration is not None, 'Choose songDurationSeconds before publishing a song.')
                require(type(entry.get('durationSeconds')) is int and entry['durationSeconds'] == duration,
                        f'{day}: every song must have the series duration of {duration} seconds.')
                require(isinstance(entry.get('audioUrl'), str), f'{day}: add an external audioUrl.')
                audio = urlsplit(entry['audioUrl'])
                require(audio.scheme == 'https' and audio.hostname and not audio.username and not audio.password,
                        f'{day}: use a public HTTPS audio URL without embedded credentials.')

            if kind == 'closing':
                require(entry.get('audioUrl') or entry.get('song') or entry.get('marketClosed') is True or entry.get('songPending') is True,
                        f'{day}: recording, reference song, marketClosed, or explicit songPending required')


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
            require(attrs['id'] not in self.ids, f'Duplicate HTML id: {attrs["id"]}')
            self.ids.add(attrs['id'])
        self.h1s += tag == 'h1'
        self.title |= tag == 'title'
        self.description |= tag == 'meta' and attrs.get('name') == 'description'
        self.viewport |= tag == 'meta' and attrs.get('name') == 'viewport'
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == 'img':
            require('alt' in attrs, 'Images need alt text.')


def validate_links():
    pages = {}
    for name in PUBLIC_FILES:
        path = ROOT / name
        require(path.is_file(), f'Missing public file: {name}')
        if path.suffix == '.html':
            page = Page()
            page.feed(path.read_text())
            require(page.h1s == 1 and page.title and page.description and page.viewport,
                    f'{name}: requires one h1, a title, description, and viewport.')
            pages[path.resolve()] = page
    public_paths = {(ROOT / p).resolve() for p in PUBLIC_FILES}
    for path, page in pages.items():
        for raw in page.links:
            url = urlsplit(raw)
            if url.scheme or url.netloc:
                continue
            target = ((ROOT if url.path.startswith('/') else path.parent) / unquote(url.path).lstrip('/')).resolve() if url.path else path
            if target.is_dir():
                target /= 'index.html'
            require(target in public_paths, f'{path.name}: link omitted from public build: {raw}')
            if url.fragment and target in pages:
                require(unquote(url.fragment) in pages[target].ids, f'{path.name}: missing anchor: {raw}')


def main():
    validate_journal(json.loads((ROOT / 'content/editions.json').read_text()))
    validate_links()
    marker = OUTPUT / '.malosound-website-build'
    if OUTPUT.exists():
        require(OUTPUT.resolve() == ROOT.resolve() / 'build', 'Refuse deletion outside the intended build directory.')
        require(marker.exists() or not any(OUTPUT.iterdir()),
                'build/ contains other work; preserve it before choosing a website output directory.')
        shutil.rmtree(OUTPUT)
    for name in PUBLIC_FILES:
        destination = OUTPUT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    marker.touch()
    print(f'Website ready: {len(PUBLIC_FILES)} public files; journal and local links validated.')


if __name__ == '__main__':
    main()
