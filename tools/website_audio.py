"""Stage verified release recordings as static MP3s, without putting audio in Git."""
import hashlib
import re
from urllib.request import Request, urlopen

MAX_AUDIO_BYTES = 32 * 1024 * 1024


def stage_audio(data, output):
    """Return external-to-local URLs and rewrite the build's edition data."""
    replacements = {}
    for session in data['sessions']:
        for kind in ('closing', 'originalSong'):
            song = session.get(kind) or {}
            source = song.get('audioUrl')
            if not source:
                continue
            digest = song.get('audioSha256', '')
            if not re.fullmatch(r'[a-f0-9]{64}', digest):
                raise ValueError(f"{session['date']}: add the release MP3's audioSha256 before publishing.")
            local = f'/assets/audio/{digest}.mp3'
            destination = output / local.lstrip('/')
            if not destination.exists():
                request = Request(source, headers={'User-Agent': 'MaloSound-website-build'})
                with urlopen(request, timeout=30) as response:
                    recording = response.read(MAX_AUDIO_BYTES + 1)
                if len(recording) > MAX_AUDIO_BYTES:
                    raise ValueError(f"{session['date']}: recording exceeds the website size limit.")
                if hashlib.sha256(recording).hexdigest() != digest:
                    raise ValueError(f"{session['date']}: recording does not match the approved SHA-256.")
                if not (recording.startswith(b'ID3') or
                        (len(recording) >= 2 and recording[0] == 0xff and recording[1] & 0xe0 == 0xe0)):
                    raise ValueError(f"{session['date']}: recording is not an MP3.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(recording)
            replacements[source] = local
            song['audioUrl'] = local
    return replacements
