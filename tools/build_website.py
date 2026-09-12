#!/usr/bin/env python3
"""Validate the journal and stage only public website files for static hosting."""
from datetime import date
from html.parser import HTMLParser
from html import escape
from pathlib import Path
import json
import shutil
from urllib.parse import unquote, urlsplit
from journal_pages import refresh
from website_audio import stage_audio

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build'
PUBLIC_FILES = (
    # The visual identity published in a11c902 stays in the build alongside the journal.
    'site.css', '404.html', 'assets/brand/orbit-violet-ice.png', 'assets/brand/malosound-violet-ice-cover.png',
    'index.html', 'journal.css', 'journal.js', 'session-playhead.js',
    'market-map.html', 'market-map.js',
    'writings/one-song-one-session.html', 'assets/brand/market-into-music.png',
    'assets/brand/malosound-square.png',
    'assets/brand/market-melody-v5.png',
    'gateway/sample-01.audioanalysis.v1.json', 'gateway/sample-02.audioanalysis.v1.json',
)
# Under content/ only the instrument documents are public. Everything else there
# (editions, the day archive, minute and hourly history, the ledger, the events
# snapshot, the map) stays in the repository and never reaches the output.
PUBLIC_CONTENT_PREFIX = 'content/instrument/'
PUBLIC_FILES += tuple(sorted(PUBLIC_CONTENT_PREFIX + p.name for p in (ROOT / 'content/instrument').glob('*.json')))
PUBLIC_FILES += tuple(p for p in json.loads((ROOT / 'content/market-assets.json').read_text()) if not p.startswith('content/'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def available(path):
    """A journal reference is satisfied by a public file, or by a repository file under content/.

    content/ is not public apart from the instrument documents, so the journal's
    own data files are checked for existence in the checkout, not for
    publication. Anything outside content/ must still be in the allowlist.
    """
    name = path.split('?')[0].lstrip('/')
    if name.startswith('content/'):
        return (ROOT / name).is_file()
    return name in PUBLIC_FILES


def check_content_boundary(output):
    """Prove that under content/ only the instrument documents were staged.

    The allowlist is the first line; this is the second, so that a future entry
    in market-assets.json or a stray write cannot put a day file, a history
    file, the ledger or any trade record into the public output.
    """
    staged = sorted(p.relative_to(output).as_posix() for p in (output / 'content').rglob('*') if p.is_file())
    expected = sorted(n for n in PUBLIC_FILES if n.startswith('content/'))
    require(staged == expected, f'content/ boundary violated: {sorted(set(staged) ^ set(expected))}')
    require(all(n.startswith(PUBLIC_CONTENT_PREFIX) for n in staged), 'Only content/instrument/*.json may be public.')
    for path in output.rglob('*'):
        require('trades' not in path.name and 'trading-journal' not in path.name, f'Trade record in public output: {path}')
    return staged


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
        if session.get('lineChart'):
            for field in ('url', 'dataUrl'):
                require(available(session['lineChart'][field]), f'{day}: missing line asset')
            require(session['lineChart'].get('alt') and session['lineChart'].get('caption'), f'{day}: line needs context')
            if session['lineChart'].get('playheadUrl'):
                require(available(session['lineChart']['playheadUrl']), f'{day}: missing timeline')
        for kind in ('preOpen', 'morning', 'closing', 'originalSong'):
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
                    require(available(entry[field]), f'{day}: missing published {field}')
            if entry.get('chart'):
                for field in ('url','dataUrl'):
                    require(available(entry['chart'][field]), f'{day}: chart asset missing')
                require(entry['chart'].get('alt') and entry['chart'].get('caption'), f'{day}: chart description required')
            if entry.get('song'):
                require(urlsplit(entry['song']['url']).scheme == 'https', f'{day}: HTTPS listening link required')
                require(all(entry['song'].get(k) for k in ('title','artist','reason')), f'{day}: song metadata required')
            if kind in ('closing', 'originalSong') and entry.get('audioUrl'):
                require(duration is not None, 'Choose songDurationSeconds before publishing a song.')
                require(type(entry.get('durationSeconds')) is int and entry['durationSeconds'] == duration,
                        f'{day}: every song must have the series duration of {duration} seconds.')
                require(isinstance(entry.get('audioUrl'), str), f'{day}: add an external audioUrl.')
                audio = urlsplit(entry['audioUrl'])
                require(audio.scheme == 'https' and audio.hostname and not audio.username and not audio.password,
                        f'{day}: use a public HTTPS audio URL without embedded credentials.')

            if kind in ('closing', 'originalSong'):
                require(session.get('lineChart') or entry.get('audioUrl') or entry.get('song') or entry.get('marketClosed') is True or entry.get('songPending') is True,
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


def check_day_audio(output, replacements):
    """Each built day file's audioUrl, with whether it resolves to a staged local file."""
    staged = set(replacements.values())
    for path in sorted((output / 'content/days').glob('*.json')):
        session = json.loads(path.read_text(encoding='utf-8'))
        for kind in ('closing', 'originalSong'):
            url = (session.get(kind) or {}).get('audioUrl')
            if url:
                yield path.name, url in staged


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
    events = json.loads((ROOT / 'content/scheduled-events.json').read_text(encoding='utf-8'))
    require(events.get('schemaVersion') == 1 and isinstance(events.get('events'), list), 'Invalid scheduled-events document')
    event_ids = set()
    for event in events['events']:
        require(event.get('id') and event['id'] not in event_ids, 'Event IDs must be unique')
        event_ids.add(event['id'])
        require(date.fromisoformat(event['date']).isoformat() == event['date'], 'Invalid event date')
        require(event.get('kind') == 'scheduled', 'Events cannot contain forecasts or results')
        require(event.get('status') in ('confirmed', 'tentative') and event.get('official') is True, 'Primary-source event status required')
        require(event.get('category') in ('fed', 'economic', 'earnings', 'treasury', 'exchange'), 'Unknown event category')
        require(event.get('name') and event.get('sourceOrg') and event.get('retrievedAt'), 'Event provenance required')
        date.fromisoformat(event['retrievedAt'][:10])
        source = urlsplit(event.get('sourceUrl', ''))
        require(source.scheme == 'https' and source.hostname and not source.username and not source.password, 'Safe HTTPS event source required')
        require(type(event.get('timeKnown')) is bool and event.get('timezone') == 'America/New_York', 'Explicit ET time precision required')
        if event['timeKnown']:
            hour, minute = event['time'].split(':')
            require(0 <= int(hour) <= 23 and 0 <= int(minute) <= 59 and f'{int(hour):02}:{int(minute):02}' == event['time'], 'Invalid event time')
        else:
            require('time' not in event, 'Unknown time must be omitted')
    # Regenerate the drawings and the archive first, then read what it wrote.
    # This used to run at import time, which made importing the builder edit
    # the checkout; a test that only wants check_day_audio should not do that.
    refresh()
    data = json.loads((ROOT / 'content/editions.json').read_text())
    validate_journal(data)
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
    replacements = stage_audio(data, OUTPUT)
    # Nothing under content/ is written into the output beyond the copied
    # instrument documents: no editions.json, no day archive, no ledger. The
    # journal is still regenerated and validated in the checkout above; it is
    # simply not published.
    staged_content = check_content_boundary(OUTPUT)
    for name in PUBLIC_FILES:
        if name.endswith('.html'):
            page = OUTPUT / name
            text = page.read_text(encoding='utf-8')
            for source, local in replacements.items():
                text = text.replace(f'src="{escape(source, quote=True)}"', f'src="{local}"')
            page.write_text(text, encoding='utf-8')
    print(f'Website ready: {len(PUBLIC_FILES)} public files; journal and local links validated; '
          f'content/ limited to {len(staged_content)} instrument documents.')
    print(f'{len(replacements)} verified MP3 recordings staged for same-origin playback.')


if __name__ == '__main__':
    main()
