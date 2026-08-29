#!/usr/bin/env python3
"""Generate the direct-support page that ships inside a release package.

The page leads with the music. The receipt is underneath it, in plain language,
with the one command a stranger runs to check it. Self-contained HTML: no CDN,
no fonts, no tracking, works from a file:// path or any static host.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


AUDIO_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _short(digest: str) -> str:
    return f"{digest[:12]}…{digest[-8:]}" if len(digest) > 24 else digest


def _human_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    total = int(round(float(seconds)))
    return f"{total // 60}:{total % 60:02d}"


def build_page(
    *,
    artist: dict[str, Any],
    title: str,
    audio_name: str,
    audio_bytes: int,
    audio_sha256: str,
    analysis: dict[str, Any],
    analysis_name: str,
    receipt: dict[str, Any],
    manifest_name: str,
    cover_name: str | None = None,
    support_note: str | None = None,
) -> str:
    suffix = Path(audio_name).suffix.lower()
    mime = AUDIO_MIME.get(suffix, "audio/mpeg")
    duration = _duration(analysis.get("duration_s"))
    links = {label: url for label, url in (artist.get("links") or {}).items() if url}

    link_html = ""
    if links:
        items = "".join(
            f'<a class="link" href="{_e(url)}" rel="noopener noreferrer" target="_blank">{_e(label)}</a>'
            for label, url in sorted(links.items())
        )
        link_html = f'<div class="links">{items}</div>'

    cover_html = ""
    if cover_name:
        cover_html = f'<img class="cover" src="{_e(cover_name)}" alt="{_e(title)} cover art">'

    meta_bits = [bit for bit in (duration, _human_bytes(audio_bytes), suffix.lstrip(".").upper()) if bit]

    facts = [
        ("Track", title),
        ("Artist", artist.get("name", "")),
        ("Audio file", audio_name),
        ("Audio SHA-256", audio_sha256),
        ("Analysis", analysis_name),
        ("Receipt hash", receipt.get("record_hash", "")),
        ("Links to receipt", receipt.get("previous_record_hash", "")),
        ("Signed", receipt.get("timestamp", "")),
        ("Signing key", artist.get("public_key", "")),
        ("Key fingerprint", artist.get("key_fingerprint", "")),
    ]
    fact_rows = "".join(
        f'<tr><th>{_e(label)}</th><td class="mono">{_e(value)}</td></tr>'
        for label, value in facts
        if value
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} — {_e(artist.get('name', ''))}</title>
<style>
  :root {{
    --bg: #fbfaf8; --panel: #ffffff; --ink: #17150f; --muted: #6b6459;
    --line: #e6e1d8; --accent: #8a5a2b; --ok: #2f6b4f;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #12100d; --panel: #1a1713; --ink: #f2ece2; --muted: #a49b8c;
      --line: #2c2721; --accent: #d9a05b; --ok: #79c9a0;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.6 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 46rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }}
  header {{ margin-bottom: 2.5rem; }}
  .eyebrow {{ color: var(--muted); font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; }}
  h1 {{ font-size: clamp(2rem, 6vw, 3rem); line-height: 1.1; margin: .4rem 0 .3rem; letter-spacing: -.02em; }}
  h2 {{ font-size: 1.1rem; margin: 2.5rem 0 .75rem; letter-spacing: -.01em; }}
  .by {{ color: var(--muted); margin: 0; }}
  .cover {{ width: 100%; border-radius: 14px; border: 1px solid var(--line); margin: 1.5rem 0; display: block; }}
  audio {{ width: 100%; margin: 1.25rem 0 .5rem; }}
  .meta {{ color: var(--muted); font-size: .85rem; }}
  .actions {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.5rem 0; }}
  .btn {{
    display: inline-block; padding: .7rem 1.1rem; border-radius: 10px; text-decoration: none;
    background: var(--accent); color: #fff; font-weight: 600; border: 1px solid transparent;
  }}
  .btn.secondary {{ background: transparent; color: var(--ink); border-color: var(--line); }}
  .links {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-top: .5rem; }}
  .link {{ color: var(--accent); }}
  .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1.25rem 1.35rem; }}
  p {{ margin: 0 0 1rem; }}
  ul {{ margin: 0 0 1rem; padding-left: 1.2rem; }}
  li {{ margin-bottom: .4rem; }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .8rem; word-break: break-all; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: .5rem .25rem; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ width: 11rem; font-weight: 600; color: var(--muted); font-size: .85rem; }}
  tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
  pre {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: .9rem 1rem; overflow-x: auto; font-size: .85rem; margin: 0 0 1rem;
  }}
  .seal {{ color: var(--ok); font-weight: 600; }}
  footer {{ margin-top: 3.5rem; padding-top: 1.5rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="eyebrow">{_e(artist.get('name', ''))}</div>
  <h1>{_e(title)}</h1>
  <p class="by">Listen free. Download it if you want to keep it. Verify it if you want to.</p>
  {link_html}
</header>

{cover_html}
<audio controls preload="none" src="audio/{_e(audio_name)}" type="{_e(mime)}">
  Your browser cannot play this file. Download it below.
</audio>
<p class="meta">{_e(' · '.join(meta_bits))}</p>

<div class="actions">
  <a class="btn" href="audio/{_e(audio_name)}" download>Download the track</a>
  <a class="btn secondary" href="{_e(manifest_name)}">Release manifest</a>
  <a class="btn secondary" href="ledger/receipt_excerpt.jsonl">Signed receipt</a>
</div>

<h2>What the receipt is</h2>
<p>
  Every file here was hashed and signed with a private key only {_e(artist.get('name', 'the artist'))}
  holds. The signature covers the audio, the analysis of that audio, the artist's own name,
  and the hash of the previous receipt in their ledger. Change one byte of the track and
  every one of those checks fails.
</p>
<p>
  That means you do not have to take anyone's word for it — not the artist's, not a
  platform's, not mine. The proof travels with the file.
</p>

<h2>Check it yourself</h2>
<p>Nothing to install. Python 3 and this folder:</p>
<pre><code>python verify.py . --fingerprint {_e(artist.get('key_fingerprint', ''))}</code></pre>
<p>
  A pass means the audio in this folder is byte-for-byte the audio that was signed,
  and it was signed by the key published under the fingerprint
  <span class="mono seal">{_e(artist.get('key_fingerprint', ''))}</span>.
</p>

<h2>The receipt</h2>
<div class="panel">
  <table>{fact_rows}</table>
</div>

<h2>Why this helps artists</h2>
<ul>
  <li><strong>You can release without permission.</strong> No distributor approval, no
      playlist gatekeeping, no waiting on a platform to accept the upload.</li>
  <li><strong>The proof is yours, not a company's.</strong> The key is on the artist's
      machine. Nobody can revoke it, deprecate it, or change the terms on it later.</li>
  <li><strong>Support goes direct.</strong> A download bought from the artist is money that
      did not pass through a payout formula on the way.</li>
  <li><strong>Authorship is checkable.</strong> Ownership disputes, sample clearance, AI
      accusations — a dated signature over the exact bytes is a much better answer than
      an upload timestamp on someone else's server.</li>
  <li><strong>Resale terms travel with the file.</strong> The manifest carries an
      ERC-2981-compatible royalty split, so if this ever moves on-chain the split is
      already written down.</li>
</ul>
<p>
  {_e(support_note) if support_note else
   'Free to listen. If you want to support the work directly, download it and share it.'}
</p>

<footer>
  <p>
    <strong>The honest boundary.</strong> This is a local cryptographic proof package.
    No smart contract is deployed, no token is minted, no wallet is connected, and no
    third party has attested to anything. What is proven is exactly this: these bytes,
    this analysis, this artist's key, this point in their ledger.
  </p>
  <p>Built with maloSound. Rights holder: {_e(artist.get('rights_holder', ''))}.</p>
</footer>

</div>
</body>
</html>
"""


def write_page(path: Path, **kwargs: Any) -> str:
    page = build_page(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return page


def self_test() -> int:
    page = build_page(
        artist={
            "name": "Fixture Artist",
            "rights_holder": "Fixture Holder",
            "public_key": "aa" * 32,
            "key_fingerprint": "MS1-AAAA-BBBB-CCCC-DDDD",
            "links": {"instagram": "https://example.invalid/x", "empty": ""},
        },
        title="Fixture Track",
        audio_name="fixture.mp3",
        audio_bytes=1234567,
        audio_sha256="bb" * 32,
        analysis={"duration_s": 185.5},
        analysis_name="fixture.audioanalysis.v1.json",
        receipt={"record_hash": "cc" * 32, "previous_record_hash": "GENESIS", "timestamp": "1970-01-01T00:00:00+00:00"},
        manifest_name="manifest/fixture.release_manifest_v1.json",
    )
    assert "<!doctype html>" in page
    assert "MS1-AAAA-BBBB-CCCC-DDDD" in page
    assert "3:06" in page
    assert "https://example.invalid/x" in page
    assert "empty" not in page.split("<header>")[1].split("</header>")[0]
    assert "http://" not in page.replace("https://example.invalid/x", "")
    print("release page self-test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
