#!/usr/bin/env python3
"""Stage the instrument player; retain journal validators for private-source tools."""
from datetime import date
from html.parser import HTMLParser
from html import escape
from pathlib import Path
import json
import hashlib
import shutil
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build'
PUBLIC_FILES = (
    'index.html', 'site.css', '404.html', 'beat-room.html',
    'assets/beat-room/grooves.mjs', 'assets/beat-room/engine.mjs',
    'assets/beat-room/app.mjs', 'assets/beat-room/library.css',
    'assets/beat-room/listening.mjs',
    'assets/beat-room/listening.css',
    'assets/beat-room/moonlight-presto-paul-pitman.mp3',
    'assets/brand/malosound-violet-ice-cover.png',
    'assets/fonts/space-grotesk-latin.ttf',
    'assets/fonts/OFL-SpaceGrotesk.txt',
)
# Under content/ only the instrument documents are public. Everything else there
# (editions, the day archive, minute and hourly history, the ledger, the events
# snapshot, the map) stays in the repository and never reaches the output.
PUBLIC_CONTENT_PREFIX = 'content/instrument/'
PUBLIC_FILES += tuple(sorted(PUBLIC_CONTENT_PREFIX + p.name for p in (ROOT / 'content/instrument').glob('*.json')))
AUDIO_RELEASE = 'https://github.com/marcelozap/malosound/releases/download/instrument-audio-2026-09-13/'
AUDIO_INDEX = json.loads((ROOT / 'config/instrument-audio.json').read_text(encoding='utf-8'))
PUBLIC_FILES += tuple('assets/instrument/' + entry['date'] + '-house.mp3' for entry in AUDIO_INDEX)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def available(path):
    """Validate a private journal's source reference, without publishing it."""
    name = path.split('?')[0].lstrip('/')
    target = (ROOT / name).resolve()
    return target.is_relative_to(ROOT.resolve()) and target.is_file()


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
        if path.is_file():
            name = path.relative_to(output).as_posix()
            require(name in PUBLIC_FILES or name == '.malosound-website-build', f'Unexpected public file: {name}')
            if path.suffix in ('.html', '.css', '.js', '.json', '.svg'):
                text = path.read_text(encoding='utf-8-sig')
                require(not any(token in text for token in ('trades.json', 'trading-journal', 'tradeSections', 'executionSections')),
                        f'Trade record reference in public output: {name}')
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
        if name.startswith('assets/instrument/'):
            continue  # Ignored locally; CI stages hash-verified release assets.
        path = ROOT / name
        require(path.is_file(), f'Missing public file: {name}')
        if path.suffix == '.html':
            page = Page()
            page.feed(path.read_text(encoding='utf-8-sig'))
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


def validate_instrument(name):
    """Only the documented price-derived schema may cross the public boundary."""
    document = json.loads((ROOT / name).read_text(encoding='utf-8'))
    require(isinstance(document, dict), f'{name}: document must be an object')
    allowed = {'schemaVersion', 'date', 'symbol', 'source', 'method', 'parent',
               'flat', 'derivedObservations', 'bounds', 'runs', 'noteEvents'}
    require(set(document) == allowed, f'{name}: unexpected document fields')
    require(document['schemaVersion'] == 2 and document['symbol'] == 'SPY', f'{name}: unsupported instrument')
    day = date.fromisoformat(document['date']).isoformat()
    require(Path(name).stem == day, f'{name}: filename/date mismatch')
    require(type(document['flat']) is bool, f'{name}: invalid flat flag')
    source = document['source']
    require(set(source) == {'path', 'sha256', 'observations', 'firstMinute', 'lastMinute', 'missingMinutes'},
            f'{name}: unexpected source fields')
    require(isinstance(source['path'], str) and source['path'].startswith(("/assets/charts/", "/content/history/")) and '..' not in source['path'],
            f'{name}: unsafe source reference')
    require(isinstance(source['sha256'], str) and len(source['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in source['sha256']), f'{name}: invalid source hash')
    require(source['firstMinute'] == 0 and source['lastMinute'] == 389,
            f'{name}: player currently supports complete 390-minute windows only')
    method = document['method']
    require(method['landmarks'] == [0, .236, .382, .5, .618, .786, .886, 1] and
            method['semitones'] == [0, 2, 3, 5, 7, 8, 10, 12], f'{name}: mapping changed')
    require(method['smoothing']['window'] == 11 and method['smoothing']['degree'] == 3 and
            method['smoothing']['spacingMinutes'] == 1 and method['smoothing']['edgeLossEachSide'] == 5,
            f'{name}: smoothing changed')
    require(method['anchors']['frozen'] is True and method['anchors']['sessionOpenIsAnchor'] is False,
            f'{name}: anchors changed')
    require(method['colour']['lightness'] == .8 and method['colour']['chroma'] == .16,
            f'{name}: color mapping changed')
    point_fields = {'minute', 'close', 'smoothed', 'velocity', 'acceleration', 'position',
                    'landmark', 'note', 'semitone', 'hue'}
    run_fields = {'startMinute', 'endMinute', 'observations', 'derivedFrom', 'derivedTo', 'points'}
    for runs, parent in ((document['runs'], False), (document['parent']['runs'], True)):
        require(isinstance(runs, list), f'{name}: runs must be a list')
        for run in runs:
            require(set(run) == run_fields | ({'date'} if parent else set()), f'{name}: unexpected run fields')
            require(all(set(point) == point_fields for point in run['points']), f'{name}: unexpected observation fields')
    event_fields = {'startMinute', 'endMinute', 'minutes', 'landmark', 'note', 'semitone', 'hue'}
    for events in (document['noteEvents'], document['parent']['sessionDay']['noteEvents']):
        require(isinstance(events, list) and all(set(event) == event_fields for event in events),
                f'{name}: unexpected event fields')
    require(sum(len(run['points']) for run in document['runs']) == document['derivedObservations'],
            f'{name}: inconsistent observation count')


def validate_audio_index(instrument_files):
    require(isinstance(AUDIO_INDEX, list), 'Audio index must be a list')
    days = [entry['date'] for entry in AUDIO_INDEX]
    require(len(days) == len(set(days)), 'Duplicate audio dates')
    require(set(days) == {Path(name).stem for name in instrument_files}, 'Audio/document date mismatch')
    for entry in AUDIO_INDEX:
        day = date.fromisoformat(entry['date']).isoformat()
        require(set(entry) == {'date', 'url', 'sha256', 'bytes', 'documentSha256'}, 'Unexpected audio metadata')
        require(entry['url'] == AUDIO_RELEASE + day + '-house.mp3', 'Unexpected audio origin')
        for field in ('sha256', 'documentSha256'):
            require(isinstance(entry[field], str) and len(entry[field]) == 64 and
                    all(c in '0123456789abcdef' for c in entry[field]), 'Invalid audio provenance hash')
        require(type(entry['bytes']) is int and 0 < entry['bytes'] <= 10000000, 'Invalid audio size')
        document = ROOT / PUBLIC_CONTENT_PREFIX / (day + '.json')
        require(hashlib.sha256(document.read_bytes()).hexdigest() == entry['documentSha256'],
                f'{day}: House was rendered from a different instrument document')


def stage_house(entry):
    relative = 'assets/instrument/' + entry['date'] + '-house.mp3'
    local = ROOT / relative
    if local.is_file():
        data = local.read_bytes()
    else:
        with urlopen(entry['url'], timeout=60) as response:
            data = response.read(entry['bytes'] + 1)
    require(len(data) == entry['bytes'], f'{relative}: audio size mismatch')
    require(hashlib.sha256(data).hexdigest() == entry['sha256'], f'{relative}: audio hash mismatch')
    target = OUTPUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def main():
    instrument_files = [name for name in PUBLIC_FILES if name.startswith(PUBLIC_CONTENT_PREFIX)]
    require(instrument_files, 'No instrument documents available; preserve the last verified release.')
    for name in instrument_files:
        validate_instrument(name)
    validate_audio_index(instrument_files)
    validate_links()
    marker = OUTPUT / '.malosound-website-build'
    if OUTPUT.exists():
        require(OUTPUT.resolve() == ROOT.resolve() / 'build', 'Refuse deletion outside the intended build directory.')
        require(marker.exists() or not any(OUTPUT.iterdir()),
                'build/ contains other work; preserve it before choosing a website output directory.')
        shutil.rmtree(OUTPUT)
    for name in PUBLIC_FILES:
        if name.startswith('assets/instrument/'):
            continue
        destination = OUTPUT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    marker.touch()
    for entry in AUDIO_INDEX:
        stage_house(entry)
    # No journal regeneration, raw history, private recordings or trade overlays.
    staged_content = check_content_boundary(OUTPUT)
    print(f'Instrument ready: {len(PUBLIC_FILES)} public files; local links validated; '
          f'{len(staged_content)} instrument documents; {len(AUDIO_INDEX)} verified House files; no trading records.')


if __name__ == '__main__':
    main()
